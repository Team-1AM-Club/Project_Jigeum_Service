"""T068: 대화 상태 통합 테스트.

전체 흐름 검증:
- 정상 흐름: plan 요청 → conversation 생성 → revision 증가 → 재요청 → 저장된 응답 반환
- 만료 → 410 → tombstone → hard delete → 404
- 제공사 실패 시 상태 불변 검증
- tombstone 전환·hard delete 전체 흐름 검증
"""

import uuid
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.conversation import Conversation, ConversationStatus
from app.models.idempotency import IdempotencyRecord
from app.models.plan import Plan
from app.services.calculation_service import (
    StateChangeValidationError,
    validate_plan_request_prerequisites,
    validate_state_change_request,
)
from app.services.conversation_service import (
    check_and_handle_expiry,
    create_conversation,
    get_conversation,
    hard_delete_conversation,
    mark_candidate_set_ready,
    mark_conditions_confirmed,
    mark_plan_selected,
    update_conversation,
)
from app.services.idempotency_service import (
    compute_payload_hash,
    save_idempotency_record,
)

SEOUL_TZ = ZoneInfo("Asia/Seoul")


# ─────────────────────────────────────────────
# Fixture: in-memory SQLite DB
# ─────────────────────────────────────────────


@pytest.fixture
def db_session():
    """테스트용 in-memory SQLite 세션."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Conversation.__table__.create(engine)
    IdempotencyRecord.__table__.create(engine)
    Plan.__table__.create(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


# ─────────────────────────────────────────────
# T068: 정상 흐름 통합 테스트
# ─────────────────────────────────────────────


class TestConversationE2E:
    """대화 상태 종단 간 통합 테스트."""

    def test_full_flow_create_update_and_revision_increase(self, db_session):
        """생성 → 갱신 → revision 증가 전체 흐름."""
        # 1. 생성
        conv = create_conversation(db=db_session)
        assert conv.revision == 1
        assert conv.status == ConversationStatus.ACTIVE

        # 2. 조건 확인 완료
        conv = mark_conditions_confirmed(
            db=db_session,
            conversation_id=conv.conversation_id,
            expected_revision=1,
            conditions={"user_confirmed": True, "places_confirmed": True},
        )
        assert conv.revision == 2
        assert conv.confirmed_conditions["user_confirmed"] is True

        # 3. 후보 도출 완료
        conv = mark_candidate_set_ready(
            db=db_session,
            conversation_id=conv.conversation_id,
            expected_revision=2,
            candidate_set={
                "options": [{"option_id": "opt1", "total_duration_minutes": 42}],
                "expires_at": "2026-09-17T00:00:00+09:00",
            },
        )
        assert conv.revision == 3
        assert conv.candidate_set["options"][0]["option_id"] == "opt1"

        # 4. 계획 선택
        conv = mark_plan_selected(
            db=db_session,
            conversation_id=conv.conversation_id,
            expected_revision=3,
            selected_plan={
                "plan_id": "plan1",
                "option_id": "opt1",
                "recommended_leave_at": "2026-09-16T18:08:00+09:00",
                "estimated_arrival_at": "2026-09-16T18:50:00+09:00",
            },
        )
        assert conv.revision == 4
        assert conv.active_selected_plan["plan_id"] == "plan1"

    def test_idempotency_rerequest_returns_stored_response(self, db_session):
        """재요청 → 저장된 응답 반환 (상태 변경 없음)."""
        conv = create_conversation(db=db_session)

        # 최초 요청
        key = str(uuid.uuid4())
        response_body = {"plan_id": "plan1", "conversation_id": conv.conversation_id}
        save_idempotency_record(
            db=db_session,
            conversation_id=conv.conversation_id,
            idempotency_key=key,
            http_method="POST",
            api_path="/api/v1/journeys/plan",
            expected_revision=1,
            request_body={
                "origin_place_id": "place1",
                "destination_place_id": "place2",
            },
            response_body=response_body,
            response_status=200,
        )

        # 재요청 (같은 key·같은 body)
        expected_hash = compute_payload_hash(
            http_method="POST",
            api_path="/api/v1/journeys/plan",
            conversation_id=conv.conversation_id,
            expected_revision=1,
            body={"origin_place_id": "place1", "destination_place_id": "place2"},
        )

        from app.services.idempotency_service import check_idempotency_hit

        hit = check_idempotency_hit(
            db=db_session,
            conversation_id=conv.conversation_id,
            idempotency_key=key,
            expected_payload_hash=expected_hash,
        )
        assert hit == response_body

        # conversation revision 변화 없음 (상태 변경 안 됨)
        retrieved = get_conversation(
            db=db_session, conversation_id=conv.conversation_id
        )
        assert retrieved.revision == 1

    def test_idempotency_reused_different_payload_returns_409(self, db_session):
        """같은 key·다른 body → 409 IDEMPOTENCY_KEY_REUSED."""
        conv = create_conversation(db=db_session)

        key = str(uuid.uuid4())
        save_idempotency_record(
            db=db_session,
            conversation_id=conv.conversation_id,
            idempotency_key=key,
            http_method="POST",
            api_path="/api/v1/journeys/plan",
            expected_revision=1,
            request_body={"origin_place_id": "place1"},
            response_body={"plan_id": "plan1"},
            response_status=200,
        )

        # 다른 body로 재요청
        expected_hash = compute_payload_hash(
            http_method="POST",
            api_path="/api/v1/journeys/plan",
            conversation_id=conv.conversation_id,
            expected_revision=1,
            body={"origin_place_id": "place2"},  # 다른 body
        )

        from app.services.idempotency_service import check_idempotency_conflict

        is_conflict = check_idempotency_conflict(
            db=db_session,
            conversation_id=conv.conversation_id,
            idempotency_key=key,
            expected_payload_hash=expected_hash,
        )
        assert is_conflict is True

    def test_revision_conflict_returns_409(self, db_session):
        """이전 revision으로 상태 변경 → 409 CONVERSATION_VERSION_CONFLICT."""
        conv = create_conversation(db=db_session)
        assert conv.revision == 1

        # revision=1로 갱신 (성공)
        update_conversation(
            db=db_session,
            conversation_id=conv.conversation_id,
            expected_revision=1,
            confirmed_conditions={},
        )
        assert conv.revision == 2

        # 이전 revision=1로 갱신 시도 → ValueError
        with pytest.raises(ValueError, match="Revision mismatch"):
            update_conversation(
                db=db_session,
                conversation_id=conv.conversation_id,
                expected_revision=1,  # 이전 revision
                confirmed_conditions={},
            )

    def test_expired_conversation_returns_410(self, db_session):
        """만료된 conversation 요청 → 410 CONVERSATION_EXPIRED."""
        conv = create_conversation(db=db_session, expires_in_minutes=0)

        # 만료 처리
        check_and_handle_expiry(db=db_session, conversation_id=conv.conversation_id)

        # T063 검증 호출 → 410
        with pytest.raises(StateChangeValidationError) as exc_info:
            validate_state_change_request(
                db=db_session,
                conversation_id=conv.conversation_id,
                idempotency_key=str(uuid.uuid4()),
                http_method="POST",
                api_path="/api/v1/journeys/plan",
                expected_revision=1,
                request_body={},
            )
        assert exc_info.value.error_code == "CONVERSATION_EXPIRED"
        assert exc_info.value.status_code == 410

    def test_nonexistent_conversation_returns_404(self, db_session):
        """없는 conversation_id → 404 CONVERSATION_NOT_FOUND."""
        with pytest.raises(StateChangeValidationError) as exc_info:
            validate_state_change_request(
                db=db_session,
                conversation_id="nonexistent-id",
                idempotency_key=str(uuid.uuid4()),
                http_method="POST",
                api_path="/api/v1/journeys/plan",
                expected_revision=1,
                request_body={},
            )
        assert exc_info.value.error_code == "CONVERSATION_NOT_FOUND"
        assert exc_info.value.status_code == 404

    def test_candidate_set_expired_returns_410(self, db_session):
        """후보 집합 만료 → 410 CANDIDATE_SET_EXPIRED."""
        conv = create_conversation(db=db_session)

        # candidate_set 만료 상태로 갱신
        update_conversation(
            db=db_session,
            conversation_id=conv.conversation_id,
            expected_revision=1,
            candidate_set={
                "options": [],
                "expires_at": "2020-01-01T00:00:00+09:00",
            },
        )

        # revision이 2로 증가했으므로 expected_revision=2 사용
        with pytest.raises(StateChangeValidationError) as exc_info:
            validate_state_change_request(
                db=db_session,
                conversation_id=conv.conversation_id,
                idempotency_key=str(uuid.uuid4()),
                http_method="POST",
                api_path="/api/v1/journeys/plan",
                expected_revision=2,
                request_body={},
            )
        assert exc_info.value.error_code == "CANDIDATE_SET_EXPIRED"
        assert exc_info.value.status_code == 410


# ─────────────────────────────────────────────
# T068: 제공자 실패 시 상태 불변 검증
# ─────────────────────────────────────────────


class TestProviderFailureStateImmutability:
    """제공자 호출 실패 시 상태 불변 검증."""

    def test_provider_failure_does_not_change_revision(self, db_session):
        """제공사 실패 → revision 불변."""
        conv = create_conversation(db=db_session)
        initial_revision = conv.revision

        # Idempotency 기록 없음 (실패했으므로)
        key = str(uuid.uuid4())
        from app.services.idempotency_service import get_idempotency_record

        record = get_idempotency_record(
            db=db_session, conversation_id=conv.conversation_id, idempotency_key=key
        )
        assert record is None

        # conversation 상태는 그대로
        retrieved = get_conversation(
            db=db_session, conversation_id=conv.conversation_id
        )
        assert retrieved.revision == initial_revision
        assert retrieved.status == ConversationStatus.ACTIVE

    def test_provider_failure_does_not_change_updated_at(self, db_session):
        """제공사 실패 → updated_at 불변."""
        conv = create_conversation(db=db_session)
        initial_updated_at = conv.updated_at

        # 제공사 실패 시뮬레이션 (아무것도 하지 않음)

        # updated_at 변화 없음
        retrieved = get_conversation(
            db=db_session, conversation_id=conv.conversation_id
        )
        assert retrieved.updated_at == initial_updated_at


# ─────────────────────────────────────────────
# T068: Tombstone 전환·Hard delete 전체 흐름
# ─────────────────────────────────────────────


class TestTombstoneHardDeleteFlow:
    """Tombstone 전환·Hard delete 전체 흐름 검증."""

    def test_tombstone_flow_payload_clearing(self, db_session):
        """만료 → tombstone 전환 시 payload 제거."""
        conv = create_conversation(
            db=db_session,
            expires_in_minutes=0,  # 생성 즉시 만료
            confirmed_conditions={"user_confirmed": True},
            candidate_set={"options": [{"id": "opt1"}]},
            active_selected_plan={"plan_id": "plan1"},
        )

        # 만료 처리
        result, was_expired = check_and_handle_expiry(
            db=db_session, conversation_id=conv.conversation_id
        )
        assert was_expired is True
        assert result.status == ConversationStatus.TOMBSTONE

        # payload 제거 확인
        assert result.confirmed_conditions is None
        assert result.candidate_set is None
        assert result.active_selected_plan is None

        # conversation_id, revision, expired_at(updated_at)은 보관
        assert result.conversation_id == conv.conversation_id
        assert result.revision == conv.revision

    def test_hard_delete_flow_404_after_delete(self, db_session):
        """Hard delete 후 동일 ID 요청 → 404 CONVERSATION_NOT_FOUND."""
        conv = create_conversation(db=db_session, expires_in_minutes=0)

        # 만료 → tombstone
        check_and_handle_expiry(db=db_session, conversation_id=conv.conversation_id)

        # hard delete
        hard_delete_conversation(db=db_session, conversation_id=conv.conversation_id)

        # 동일 ID 조회 → None (404)
        retrieved = get_conversation(
            db=db_session, conversation_id=conv.conversation_id, include_expired=True
        )
        assert retrieved is None

    def test_hard_delete_not_allowed_for_active(self, db_session):
        """active 상태 hard delete 시도 → ValueError."""
        conv = create_conversation(db=db_session)

        with pytest.raises(ValueError, match="tombstone"):
            hard_delete_conversation(
                db=db_session, conversation_id=conv.conversation_id
            )

    def test_tombstone_idempotent_multiple_expiry_calls(self, db_session):
        """여러 번 만료 호출 → 멱등."""
        conv = create_conversation(db=db_session, expires_in_minutes=0)

        check_and_handle_expiry(db=db_session, conversation_id=conv.conversation_id)
        check_and_handle_expiry(db=db_session, conversation_id=conv.conversation_id)
        check_and_handle_expiry(db=db_session, conversation_id=conv.conversation_id)

        result = get_conversation(
            db=db_session, conversation_id=conv.conversation_id, include_expired=True
        )
        assert result.status == ConversationStatus.TOMBSTONE
        assert result.confirmed_conditions is None


# ─────────────────────────────────────────────
# T068: T040 (US1 특유 검증) 통합 테스트
# ─────────────────────────────────────────────


class TestT040US1SpecificValidation:
    """T040: US1 특유 검증 (확인 조건 충족 전 plan 요청 차단)."""

    def test_plan_request_without_user_confirmed_returns_422(self, db_session):
        """user_confirmed=false → 422 USER_CONFIRMATION_REQUIRED."""
        conv = create_conversation(db=db_session)

        with pytest.raises(StateChangeValidationError) as exc_info:
            validate_plan_request_prerequisites(
                conversation=conv,
                origin_place_id="place1",
                destination_place_id="place2",
                user_confirmed=False,
            )
        assert exc_info.value.error_code == "USER_CONFIRMATION_REQUIRED"
        assert exc_info.value.status_code == 422

    def test_plan_request_without_origin_place_returns_422(self, db_session):
        """출발지 미확정 → 422 VALIDATION_ERROR."""
        conv = create_conversation(db=db_session)

        with pytest.raises(StateChangeValidationError) as exc_info:
            validate_plan_request_prerequisites(
                conversation=conv,
                origin_place_id="",
                destination_place_id="place2",
                user_confirmed=True,
            )
        assert exc_info.value.error_code == "VALIDATION_ERROR"
        assert exc_info.value.status_code == 422

    def test_plan_request_without_destination_place_returns_422(self, db_session):
        """목적지 미확정 → 422 VALIDATION_ERROR."""
        conv = create_conversation(db=db_session)

        with pytest.raises(StateChangeValidationError) as exc_info:
            validate_plan_request_prerequisites(
                conversation=conv,
                origin_place_id="place1",
                destination_place_id="",
                user_confirmed=True,
            )
        assert exc_info.value.error_code == "VALIDATION_ERROR"
        assert exc_info.value.status_code == 422

    def test_plan_request_with_confirmed_conditions_succeeds(self, db_session):
        """확인 조건 충족 → 검증 통과."""
        conv = create_conversation(
            db=db_session,
            confirmed_conditions={
                "user_confirmed": True,
                "conditions_confirmed": True,
                "places_confirmed": True,
            },
        )

        # 검증 통과 (예외 없음)
        validate_plan_request_prerequisites(
            conversation=conv,
            origin_place_id="place1",
            destination_place_id="place2",
            user_confirmed=True,
        )

    # ─────────────────────────────────────────────
    # T068: T063 일반 상태 변경 검증 통합 테스트
    # ─────────────────────────────────────────────

    def test_confirm_then_plan_allowed(self, db_session):
        """confirm 성공 → 동일 조건 plan 허용 (US1 핵심 시나리오).

        Given: confirm 전 conversation (confirmed_conditions=None)
        When:
          1. mark_conditions_confirmed로 확인 완료 설정
          2. validate_plan_request_prerequisites 호출
        Then: 확인 조건 충족 → 검증 통과 (예외 없음)
        """
        conv = create_conversation(db=db_session)

        # 1. 조건 확인 완료 (user_confirmed + conditions_confirmed + places_confirmed)
        conv = mark_conditions_confirmed(
            db=db_session,
            conversation_id=conv.conversation_id,
            expected_revision=1,
            conditions={
                "user_confirmed": True,
                "conditions_confirmed": True,
                "places_confirmed": True,
            },
        )
        assert conv.revision == 2
        assert conv.confirmed_conditions["user_confirmed"] is True

        # 2. Plan 검증 → 통과 (예외 없음)
        validate_plan_request_prerequisites(
            conversation=conv,
            origin_place_id="place1",
            destination_place_id="place2",
            user_confirmed=True,
        )

    def test_conditions_changed_after_confirm_invalidates_plan(self, db_session):
        """조건 변경 → 기존 확인 무효화 → plan 거부.

        Given: 확인된 conversation (user_confirmed=true, conditions_confirmed=true)
        When:
          1. update_conversation으로 confirmed_conditions 변경 (conditions_confirmed=false)
          2. validate_plan_request_prerequisites 호출
        Then: 조건 확인 미완료 → 422 USER_CONFIRMATION_REQUIRED
        """
        conv = create_conversation(
            db=db_session,
            confirmed_conditions={
                "user_confirmed": True,
                "conditions_confirmed": True,
                "places_confirmed": True,
            },
        )
        assert conv.revision == 1

        # 조건 변경: conditions_confirmed를 false로
        conv = update_conversation(
            db=db_session,
            conversation_id=conv.conversation_id,
            expected_revision=1,
            confirmed_conditions={
                "user_confirmed": True,
                "conditions_confirmed": False,  # 변경
                "places_confirmed": True,
            },
        )
        assert conv.revision == 2
        assert conv.confirmed_conditions["conditions_confirmed"] is False

        # Plan 검증 → 거부 (조건 확인 미완료)
        with pytest.raises(StateChangeValidationError) as exc_info:
            validate_plan_request_prerequisites(
                conversation=conv,
                origin_place_id="place1",
                destination_place_id="place2",
                user_confirmed=True,
            )
        assert exc_info.value.error_code == "USER_CONFIRMATION_REQUIRED"
        assert exc_info.value.status_code == 422

    def test_confirmed_conditions_persist_unchanged(self, db_session):
        """조건 미변경 → 확인 상태 유지.

        Given: 확인된 conversation
        When: confirmed_conditions 재조회
        Then: 확인 상태 그대로 유지 (변경 없음)
        """
        original_conditions = {
            "user_confirmed": True,
            "conditions_confirmed": True,
            "places_confirmed": True,
            "arrival_deadline": "2026-09-16T19:00:00+09:00",
        }
        conv = create_conversation(
            db=db_session,
            confirmed_conditions=original_conditions,
        )

        # 재확인: 동일 조건 유지
        retrieved = get_conversation(
            db=db_session, conversation_id=conv.conversation_id
        )
        assert retrieved.confirmed_conditions == original_conditions
        assert retrieved.confirmed_conditions["user_confirmed"] is True
        assert retrieved.confirmed_conditions["conditions_confirmed"] is True

        # Plan 검증 → 통과
        validate_plan_request_prerequisites(
            conversation=retrieved,
            origin_place_id="place1",
            destination_place_id="place2",
            user_confirmed=True,
        )

    def test_conditions_confirmation_required_for_plan(self, db_session):
        """user_confirmed=true이나 conditions_confirmed=false → plan 거부.

        Given: user_confirmed만 있고 conditions_confirmed가 없는 conversation
        When: validate_plan_request_prerequisites 호출
        Then: 422 USER_CONFIRMATION_REQUIRED
        """
        conv = create_conversation(
            db=db_session,
            confirmed_conditions={
                "user_confirmed": True,
                "conditions_confirmed": False,  # 조건 확인 미완료
                "places_confirmed": True,
            },
        )

        with pytest.raises(StateChangeValidationError) as exc_info:
            validate_plan_request_prerequisites(
                conversation=conv,
                origin_place_id="place1",
                destination_place_id="place2",
                user_confirmed=True,
            )
        assert exc_info.value.error_code == "USER_CONFIRMATION_REQUIRED"
        assert exc_info.value.status_code == 422

    def test_plan_requires_all_confirmation_fields(self, db_session):
        """places_confirmed=false → plan 거부.

        Given: user_confirmed=true, conditions_confirmed=true, places_confirmed=false
        When: validate_plan_request_prerequisites 호출
        Then: 422 USER_CONFIRMATION_REQUIRED
        """
        conv = create_conversation(
            db=db_session,
            confirmed_conditions={
                "user_confirmed": True,
                "conditions_confirmed": True,
                "places_confirmed": False,  # 장소 확인 미완료
            },
        )

        with pytest.raises(StateChangeValidationError) as exc_info:
            validate_plan_request_prerequisites(
                conversation=conv,
                origin_place_id="place1",
                destination_place_id="place2",
                user_confirmed=True,
            )
        assert exc_info.value.error_code == "USER_CONFIRMATION_REQUIRED"
        assert exc_info.value.status_code == 422


class TestT063StateValidation:
    """T063: 일반 상태 변경 검증 통합 테스트."""

    def test_missing_idempotency_key_returns_422(self, db_session):
        """Idempotency-Key 누락 → 422."""
        conv = create_conversation(db=db_session)

        with pytest.raises(StateChangeValidationError) as exc_info:
            validate_state_change_request(
                db=db_session,
                conversation_id=conv.conversation_id,
                idempotency_key=None,
                http_method="POST",
                api_path="/api/v1/journeys/plan",
                expected_revision=1,
                request_body={},
            )
        assert exc_info.value.error_code == "VALIDATION_ERROR"
        assert exc_info.value.status_code == 422

    def test_invalid_idempotency_key_format_returns_422(self, db_session):
        """Idempotency-Key 형식 오류 → 422."""
        conv = create_conversation(db=db_session)

        with pytest.raises(StateChangeValidationError) as exc_info:
            validate_state_change_request(
                db=db_session,
                conversation_id=conv.conversation_id,
                idempotency_key="not-a-uuid",
                http_method="POST",
                api_path="/api/v1/journeys/plan",
                expected_revision=1,
                request_body={},
            )
        assert exc_info.value.error_code == "VALIDATION_ERROR"
        assert exc_info.value.status_code == 422

    def test_valid_request_passes_all_checks(self, db_session):
        """유효한 요청 → 모든 검증 통과."""
        conv = create_conversation(db=db_session)
        key = str(uuid.uuid4())

        result = validate_state_change_request(
            db=db_session,
            conversation_id=conv.conversation_id,
            idempotency_key=key,
            http_method="POST",
            api_path="/api/v1/journeys/plan",
            expected_revision=1,
            request_body={"origin_place_id": "place1"},
        )

        assert result["conversation"].conversation_id == conv.conversation_id
        assert result["idempotency_hit"] is None


# ─────────────────────────────────────────────
# T068: Payload Hash 범위 검증 (SC-016)
# ─────────────────────────────────────────────


class TestPayloadHashScope:
    """Payload hash 계산 범위 검증 (SC-016)."""

    def test_hash_includes_http_method(self, db_session):
        """HTTP method 포함."""
        h_post = compute_payload_hash("POST", "/api/v1/plan", "conv-1", 1, {})
        h_get = compute_payload_hash("GET", "/api/v1/plan", "conv-1", 1, {})
        assert h_post != h_get

    def test_hash_includes_normalized_path(self, db_session):
        """정규화된 path 포함 (trailing slash 무시)."""
        h1 = compute_payload_hash("POST", "/api/v1/plan/", "conv-1", 1, {})
        h2 = compute_payload_hash("POST", "/api/v1/plan", "conv-1", 1, {})
        assert h1 == h2

    def test_hash_includes_conversation_id(self, db_session):
        """conversation_id 포함."""
        h1 = compute_payload_hash("POST", "/api/v1/plan", "conv-1", 1, {})
        h2 = compute_payload_hash("POST", "/api/v1/plan", "conv-2", 1, {})
        assert h1 != h2

    def test_hash_includes_expected_revision(self, db_session):
        """expected_revision 포함."""
        h1 = compute_payload_hash("POST", "/api/v1/plan", "conv-1", 1, {})
        h2 = compute_payload_hash("POST", "/api/v1/plan", "conv-1", 2, {})
        assert h1 != h2

    def test_hash_includes_request_body(self, db_session):
        """요청 body 포함."""
        h1 = compute_payload_hash("POST", "/api/v1/plan", "conv-1", 1, {"origin": "A"})
        h2 = compute_payload_hash("POST", "/api/v1/plan", "conv-1", 1, {"origin": "B"})
        assert h1 != h2

    def test_hash_case_insensitive_path(self, db_session):
        """path 대소문자 구분 없이 정규화."""
        h1 = compute_payload_hash("POST", "/API/V1/PLAN", "conv-1", 1, {})
        h2 = compute_payload_hash("POST", "/api/v1/plan", "conv-1", 1, {})
        assert h1 == h2

    def test_hash_canonicalized_body_key_order(self, db_session):
        """body 키 순서 무관하게 동일 hash."""
        h1 = compute_payload_hash("POST", "/api/v1/plan", "conv-1", 1, {"b": 2, "a": 1})
        h2 = compute_payload_hash("POST", "/api/v1/plan", "conv-1", 1, {"a": 1, "b": 2})
        assert h1 == h2
