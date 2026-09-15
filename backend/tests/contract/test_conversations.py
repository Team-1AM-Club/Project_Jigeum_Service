"""T067: 대화 상태 계약 테스트.

대화 상태 생명주기 검증:
- 생성 → 갱신 → 만료 → tombstone → hard delete
- Idempotency-Key 동일/다른 요청 처리
- revision 충돌 처리
"""
import pytest
import uuid
import json
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.conversation import Conversation, ConversationStatus
from app.models.idempotency import IdempotencyRecord
from app.services.conversation_service import (
    create_conversation,
    get_conversation,
    update_conversation,
    expire_conversation,
    hard_delete_conversation,
    check_and_handle_expiry,
    candidate_set_expired,
    hard_delete_if_eligible,
    mark_conditions_confirmed,
    mark_candidate_set_ready,
    mark_plan_selected,
)
from app.services.idempotency_service import (
    compute_payload_hash,
    save_idempotency_record,
    get_idempotency_record,
    check_idempotency_conflict,
    check_idempotency_hit,
    validate_idempotency_key_format,
)
from app.schemas.errors import ErrorCode

SEOUL_TZ = ZoneInfo("Asia/Seoul")


# ─────────────────────────────────────────────
# Fixture: in-memory SQLite DB
# ─────────────────────────────────────────────

@pytest.fixture
def db_session():
    """테스트용 in-memory SQLite 세션."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    # UNIQUE 제약 등 SQLite에서 지원 안 하는 기능은 제외
    Conversation.__table__.create(engine)
    IdempotencyRecord.__table__.create(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


# ─────────────────────────────────────────────
# T067: 대화 생성 테스트
# ─────────────────────────────────────────────

class TestConversationCreation:
    """대화 생성 계약 테스트."""

    def test_create_conversation_generates_uuid(self, db_session):
        """conversation_id 자동 생성 (UUID v4)."""
        conv = create_conversation(db=db_session)
        assert conv.conversation_id
        assert len(conv.conversation_id) == 36
        # UUID v4 패턴 검증
        import re
        uuid_v4_pattern = re.compile(
            r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$',
            re.IGNORECASE
        )
        assert uuid_v4_pattern.match(conv.conversation_id)

    def test_create_conversation_default_revision_is_1(self, db_session):
        """기본 revision = 1."""
        conv = create_conversation(db=db_session)
        assert conv.revision == 1

    def test_create_conversation_status_is_active(self, db_session):
        """기본 상태 = active."""
        conv = create_conversation(db=db_session)
        assert conv.status == ConversationStatus.ACTIVE

    def test_create_conversation_expires_at_set(self, db_session):
        """expires_at = 생성 시각 + 24시간 (기본)."""
        conv = create_conversation(db=db_session)
        assert conv.expires_at is not None
        now = datetime.now(timezone.utc)
        expected = now + timedelta(days=1)
        # 1분 오차 허용
        assert abs((conv.expires_at - expected).total_seconds()) < 60

    def test_create_conversation_with_custom_id(self, db_session):
        """직접 conversation_id 지정 가능."""
        custom_id = str(uuid.uuid4())
        conv = create_conversation(db=db_session, conversation_id=custom_id)
        assert conv.conversation_id == custom_id

    def test_create_conversation_with_confirmed_conditions(self, db_session):
        """confirmed_conditions 초기값 설정 가능."""
        conv = create_conversation(
            db=db_session,
            confirmed_conditions={"places_confirmed": True, "conditions_confirmed": True},
        )
        assert conv.confirmed_conditions["places_confirmed"] is True


# ─────────────────────────────────────────────
# T067: 대화 갱신 (revision 증가) 테스트
# ─────────────────────────────────────────────

class TestConversationUpdate:
    """대화 갱신 (revision 증가) 계약 테스트."""

    def test_update_conversation_increments_revision(self, db_session):
        """갱신 시 revision +1."""
        conv = create_conversation(db=db_session)
        assert conv.revision == 1

        updated = update_conversation(
            db=db_session,
            conversation_id=conv.conversation_id,
            expected_revision=1,
            confirmed_conditions={"user_confirmed": True},
        )
        assert updated.revision == 2

    def test_update_conversation_revision_conflict(self, db_session):
        """이전 revision으로 갱신 시도 → ValueError."""
        conv = create_conversation(db=db_session)
        assert conv.revision == 1

        with pytest.raises(ValueError, match="Revision mismatch"):
            update_conversation(
                db=db_session,
                conversation_id=conv.conversation_id,
                expected_revision=0,  # 이전 revision
                confirmed_conditions={},
            )

    def test_update_conversation_not_found(self, db_session):
        """없는 conversation_id → ValueError."""
        with pytest.raises(ValueError, match="Conversation not found"):
            update_conversation(
                db=db_session,
                conversation_id="nonexistent",
                expected_revision=1,
                confirmed_conditions={},
            )

    def test_update_conversation_tombstone_forbidden(self, db_session):
        """tombstone 상태 갱신 시도 → ValueError."""
        conv = create_conversation(db=db_session)
        expire_conversation(db=db_session, conversation_id=conv.conversation_id)

        with pytest.raises(ValueError, match="tombstone"):
            update_conversation(
                db=db_session,
                conversation_id=conv.conversation_id,
                expected_revision=1,
                confirmed_conditions={},
            )

    def test_update_conversation_updates_fields(self, db_session):
        """필드가 정상 갱신됨."""
        conv = create_conversation(db=db_session)
        updated = update_conversation(
            db=db_session,
            conversation_id=conv.conversation_id,
            expected_revision=1,
            confirmed_conditions={"user_confirmed": True},
            candidate_set={"options": []},
        )
        assert updated.confirmed_conditions["user_confirmed"] is True
        assert updated.candidate_set["options"] == []


# ─────────────────────────────────────────────
# T067: 상태 전이 테스트
# ─────────────────────────────────────────────

class TestConversationStateTransitions:
    """대화 상태 전이 계약 테스트."""

    def test_mark_conditions_confirmed(self, db_session):
        """조건 확인 완료 상태로 전이."""
        conv = create_conversation(db=db_session)
        updated = mark_conditions_confirmed(
            db=db_session,
            conversation_id=conv.conversation_id,
            expected_revision=1,
            conditions={"user_confirmed": True, "places_confirmed": True},
        )
        assert updated.confirmed_conditions["user_confirmed"] is True
        assert updated.revision == 2

    def test_mark_candidate_set_ready(self, db_session):
        """후보 도출 완료 상태로 전이."""
        conv = create_conversation(db=db_session)
        updated = mark_candidate_set_ready(
            db=db_session,
            conversation_id=conv.conversation_id,
            expected_revision=1,
            candidate_set={"options": [{"id": "opt1"}], "expires_at": "2026-09-17T00:00:00+09:00"},
        )
        assert updated.candidate_set["options"][0]["id"] == "opt1"
        assert updated.revision == 2

    def test_mark_plan_selected(self, db_session):
        """계획 선택 완료 상태로 전이."""
        conv = create_conversation(db=db_session)
        updated = mark_plan_selected(
            db=db_session,
            conversation_id=conv.conversation_id,
            expected_revision=1,
            selected_plan={"plan_id": "plan1", "option_id": "opt1"},
        )
        assert updated.active_selected_plan["plan_id"] == "plan1"
        assert updated.revision == 2


# ─────────────────────────────────────────────
# T067: 만료·tombstone·hard delete 테스트
# ─────────────────────────────────────────────

class TestConversationExpiry:
    """만료·tombstone·hard delete 계약 테스트."""

    def test_expire_conversation_basic(self, db_session):
        """만료 → tombstone 전환."""
        conv = create_conversation(db=db_session)
        expired = expire_conversation(db=db_session, conversation_id=conv.conversation_id)
        assert expired.status == ConversationStatus.TOMBSTONE

    def test_expire_conversation_idempotent(self, db_session):
        """이미 tombstone → 멱등 처리."""
        conv = create_conversation(db=db_session)
        expire_conversation(db=db_session, conversation_id=conv.conversation_id)
        expired2 = expire_conversation(db=db_session, conversation_id=conv.conversation_id)
        assert expired2.status == ConversationStatus.TOMBSTONE

    def test_check_and_handle_expiry_active(self, db_session):
        """active conversation → was_expired=False."""
        conv = create_conversation(db=db_session)
        result, was_expired = check_and_handle_expiry(db=db_session, conversation_id=conv.conversation_id)
        assert was_expired is False
        assert result.status == ConversationStatus.ACTIVE

    def test_check_and_handle_expiry_expired(self, db_session):
        """expires_at <= now → tombstone 전환."""
        conv = create_conversation(db=db_session, expires_in_minutes=0)  # 즉시 만료
        result, was_expired = check_and_handle_expiry(db=db_session, conversation_id=conv.conversation_id)
        assert was_expired is True
        assert result.status == ConversationStatus.TOMBSTONE
        # payload 제거 확인
        assert result.confirmed_conditions is None
        assert result.candidate_set is None
        assert result.active_selected_plan is None

    def test_check_and_handle_expiry_tombstone_idempotent(self, db_session):
        """이미 tombstone → 멱등."""
        conv = create_conversation(db=db_session, expires_in_minutes=0)
        check_and_handle_expiry(db=db_session, conversation_id=conv.conversation_id)
        result, was_expired = check_and_handle_expiry(db=db_session, conversation_id=conv.conversation_id)
        assert was_expired is True
        assert result.status == ConversationStatus.TOMBSTONE

    def test_hard_delete_requires_tombstone(self, db_session):
        """active 상태에서 hard delete 시도 → ValueError."""
        conv = create_conversation(db=db_session)
        with pytest.raises(ValueError, match="tombstone"):
            hard_delete_conversation(db=db_session, conversation_id=conv.conversation_id)

    def test_hard_delete_tombstone(self, db_session):
        """tombstone → hard delete 가능."""
        conv = create_conversation(db=db_session, expires_in_minutes=0)
        check_and_handle_expiry(db=db_session, conversation_id=conv.conversation_id)
        result = hard_delete_conversation(db=db_session, conversation_id=conv.conversation_id)
        assert result is True

        # 삭제 후 조회 → None
        retrieved = get_conversation(db=db_session, conversation_id=conv.conversation_id, include_expired=True)
        assert retrieved is None

    def test_hard_delete_not_found(self, db_session):
        """없는 ID → False."""
        result = hard_delete_conversation(db=db_session, conversation_id="nonexistent")
        assert result is False

    def test_hard_delete_if_eligible_active(self, db_session):
        """active → hard_delete_if_eligible → False."""
        conv = create_conversation(db=db_session)
        result = hard_delete_if_eligible(db=db_session, conversation_id=conv.conversation_id)
        assert result is False

    def test_hard_delete_if_eligible_tombstone_not_elapsed(self, db_session):
        """tombstone but 24h not elapsed → False."""
        conv = create_conversation(db=db_session, expires_in_minutes=0)
        check_and_handle_expiry(db=db_session, conversation_id=conv.conversation_id)
        # tombstone 전환 후 updated_at이 지금이므로 24시간 미경과
        result = hard_delete_if_eligible(db=db_session, conversation_id=conv.conversation_id)
        assert result is False


# ─────────────────────────────────────────────
# T067: Idempotency-Key 계약 테스트
# ─────────────────────────────────────────────

class TestIdempotencyKey:
    """Idempotency-Key 계약 테스트."""

    def test_compute_payload_hash_deterministic(self, db_session):
        """같은 입력 → 같은 hash."""
        h1 = compute_payload_hash(
            http_method="POST",
            api_path="/api/v1/journeys/plan",
            conversation_id="conv-123",
            expected_revision=1,
            body={"origin_place_id": "place1"},
        )
        h2 = compute_payload_hash(
            http_method="POST",
            api_path="/api/v1/journeys/plan",
            conversation_id="conv-123",
            expected_revision=1,
            body={"origin_place_id": "place1"},
        )
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex

    def test_compute_payload_hash_different_body(self, db_session):
        """다른 body → 다른 hash."""
        h1 = compute_payload_hash(
            http_method="POST",
            api_path="/api/v1/journeys/plan",
            conversation_id="conv-123",
            expected_revision=1,
            body={"origin_place_id": "place1"},
        )
        h2 = compute_payload_hash(
            http_method="POST",
            api_path="/api/v1/journeys/plan",
            conversation_id="conv-123",
            expected_revision=1,
            body={"origin_place_id": "place2"},
        )
        assert h1 != h2

    def test_validate_idempotency_key_format_valid(self, db_session):
        """유효한 UUID v4 → 통과."""
        key = str(uuid.uuid4())
        result = validate_idempotency_key_format(key)
        assert result == key

    def test_validate_idempotency_key_format_missing(self, db_session):
        """None → ValueError."""
        with pytest.raises(ValueError, match="필수"):
            validate_idempotency_key_format(None)

    def test_validate_idempotency_key_format_empty(self, db_session):
        """빈 문자열 → ValueError."""
        with pytest.raises(ValueError, match="필수"):
            validate_idempotency_key_format("")

    def test_validate_idempotency_key_format_not_uuid_v4(self, db_session):
        """UUID v4 아님 → ValueError."""
        with pytest.raises(ValueError):
            validate_idempotency_key_format("not-a-uuid")

    def test_validate_idempotency_key_format_uuid_v1(self, db_session):
        """UUID v1 → ValueError."""
        import uuid as uuid_mod
        key = str(uuid_mod.uuid1())
        with pytest.raises(ValueError):
            validate_idempotency_key_format(key)

    def test_save_and_get_idempotency_record(self, db_session):
        """저장·조회."""
        conv = create_conversation(db=db_session)
        record = save_idempotency_record(
            db=db_session,
            conversation_id=conv.conversation_id,
            idempotency_key=str(uuid.uuid4()),
            http_method="POST",
            api_path="/api/v1/journeys/plan",
            expected_revision=1,
            request_body={"origin_place_id": "place1"},
            response_body={"plan_id": "plan1"},
            response_status=200,
        )
        assert record.id is not None
        assert record.payload_hash
        assert len(record.payload_hash) == 64

        retrieved = get_idempotency_record(db=db_session, conv.conversation_id, record.idempotency_key)
        assert retrieved
        assert retrieved.payload_hash == record.payload_hash

    def test_idempotency_key_reused_different_payload(self, db_session):
        """같은 key·다른 payload → conflict."""
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

        # 같은 key·다른 body → hash 다름 → conflict
        assert check_idempotency_conflict(
            db=db_session,
            conversation_id=conv.conversation_id,
            idempotency_key=key,
            expected_payload_hash=compute_payload_hash(
                http_method="POST",
                api_path="/api/v1/journeys/plan",
                conversation_id=conv.conversation_id,
                expected_revision=1,
                body={"origin_place_id": "place2"},  # 다른 body
            ),
        )

    def test_idempotency_hit_same_payload(self, db_session):
        """같은 key·같은 payload → 저장된 응답 반환."""
        conv = create_conversation(db=db_session)
        key = str(uuid.uuid4())
        response_body = {"plan_id": "plan1", "conversation_id": conv.conversation_id}
        save_idempotency_record(
            db=db_session,
            conversation_id=conv.conversation_id,
            idempotency_key=key,
            http_method="POST",
            api_path="/api/v1/journeys/plan",
            expected_revision=1,
            request_body={"origin_place_id": "place1"},
            response_body=response_body,
            response_status=200,
        )

        hit = check_idempotency_hit(
            db=db_session,
            conversation_id=conv.conversation_id,
            idempotency_key=key,
            expected_payload_hash=compute_payload_hash(
                http_method="POST",
                api_path="/api/v1/journeys/plan",
                conversation_id=conv.conversation_id,
                expected_revision=1,
                body={"origin_place_id": "place1"},  # 같은 body
            ),
        )
        assert hit == response_body

    def test_idempotency_hit_no_record(self, db_session):
        """기록 없음 → None."""
        conv = create_conversation(db=db_session)
        hit = check_idempotency_hit(
            db=db_session,
            conversation_id=conv.conversation_id,
            idempotency_key=str(uuid.uuid4()),
            expected_payload_hash="abc",
        )
        assert hit is None

    def test_unique_constraint_conversation_id_key(self, db_session):
        """conversation_id + idempotency_key 중복 → IntegrityError."""
        conv = create_conversation(db=db_session)
        from sqlalchemy.exc import IntegrityError
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

        with pytest.raises(IntegrityError):
            save_idempotency_record(
                db=db_session,
                conversation_id=conv.conversation_id,
                idempotency_key=key,  # 같은 key
                http_method="POST",
                api_path="/api/v1/journeys/plan",
                expected_revision=1,
                request_body={"origin_place_id": "place2"},
                response_body={"plan_id": "plan2"},
                response_status=200,
            )


# ─────────────────────────────────────────────
# T067: Candidate set 만료 테스트
# ─────────────────────────────────────────────

class TestCandidateSetExpiry:
    """후보 집합 만료 계약 테스트."""

    def test_candidate_set_expired_true(self, db_session):
        """candidate_set expires_at 지남 → True."""
        conv = create_conversation(db=db_session)
        update_conversation(
            db=db_session,
            conversation_id=conv.conversation_id,
            expected_revision=1,
            candidate_set={
                "options": [],
                "expires_at": "2020-01-01T00:00:00+09:00",  # 과거
            },
        )
        assert candidate_set_expired(db=db_session, conv.conversation_id) is True

    def test_candidate_set_expired_false(self, db_session):
        """candidate_set expires_at 미래 → False."""
        conv = create_conversation(db=db_session)
        update_conversation(
            db=db_session,
            conversation_id=conv.conversation_id,
            expected_revision=1,
            candidate_set={
                "options": [],
                "expires_at": "2099-01-01T00:00:00+09:00",  # 미래
            },
        )
        assert candidate_set_expired(db=db_session, conv.conversation_id) is False

    def test_candidate_set_expired_no_candidate_set(self, db_session):
        """candidate_set 없음 → False."""
        conv = create_conversation(db=db_session)
        assert candidate_set_expired(db=db_session, conv.conversation_id) is False
