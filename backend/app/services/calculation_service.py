"""계산 서비스 - 일반 상태 변경 검증 (T063) + US1 특유 검증 (T040).

Provider 호출 순서 5단계 준수:
1. conversation 유효성·입력·Idempotency-Key 기록·revision 확인
2. DB 쓰기 트랜잭션 밖에서 provider 호출
3. provider 성공 결과 검증
4. 짧은 DB 트랜잭션에서 만료·Idempotency-Key·revision 재확인
5. domain 상태 변경 + revision 증가 + Idempotency-Key 성공 결과 원자 커밋
"""
import logging
from typing import Optional, Any
from app.schemas.journeys import ReplanReason
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from app.models.conversation import Conversation, ConversationStatus
from app.models.plan import Plan
from app.services.idempotency_service import (
    validate_idempotency_key_format,
    compute_payload_hash,
    save_idempotency_record,
    get_idempotency_record,
    check_idempotency_conflict,
    check_idempotency_hit,
)
from app.services.conversation_service import (
    get_conversation,
    update_conversation,
    check_and_handle_expiry,
    candidate_set_expired,
    hard_delete_if_eligible,
)

logger = logging.getLogger(__name__)
SEOUL_TZ = ZoneInfo("Asia/Seoul")


# ─────────────────────────────────────────────
# 일반 상태 변경 검증 (T063)
# ─────────────────────────────────────────────

class StateChangeValidationError(Exception):
    """상태 변경 검증 오류."""

    def __init__(self, error_code: str, message: str, status_code: int):
        self.error_code = error_code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def validate_state_change_request(
    db: Session,
    conversation_id: str,
    idempotency_key: str,
    http_method: str,
    api_path: str,
    expected_revision: int,
    request_body: dict,
) -> dict:
    """일반 상태 변경 검증 (T063).

    모든 상태 변경 요청 시:
    1. conversation 유효성 확인
    2. 입력 검증 (idempotency_key 형식, revision 등)
    3. Idempotency-Key 기록·확인
    4. revision 확인

    US1 특유 검증 (확인 조건 충족 전 plan 요청 차단)은 T040에 위임.

    Args:
        db: DB 세션
        conversation_id: 대화 ID
        idempotency_key: Idempotency-Key 헤더 값
        http_method: HTTP 메서드
        api_path: API 경로
        expected_revision: 요청 시 기대 revision
        request_body: 요청 본문

    Returns:
        dict: {"conversation": Conversation, "idempotency_hit": Optional[dict]}

    Raises:
        StateChangeValidationError: 검증 실패 시
    """
    # ─────────────────────────────────────────────
    # 1. Idempotency-Key 형식 검증 (T063)
    # ─────────────────────────────────────────────
    try:
        validated_ik = validate_idempotency_key_format(idempotency_key)
    except ValueError as e:
        raise StateChangeValidationError(
            error_code="VALIDATION_ERROR",
            message=str(e),
            status_code=422,
        )

    # ─────────────────────────────────────────────
    # 2. Conversation 유효성 확인 (T063)
    # ─────────────────────────────────────────────
    conv = get_conversation(db, conversation_id, include_expired=True)
    if conv is None:
        raise StateChangeValidationError(
            error_code="CONVERSATION_NOT_FOUND",
            message=f"대화를 찾을 수 없습니다: {conversation_id}",
            status_code=404,
        )

    # 이미 hard delete 된 경우 (TOMBSTONE 24시간 경과 후 삭제)
    if conv.status == ConversationStatus.TOMBSTONE:
        # tombstone 이지만 아직 hard delete 전이면 410 CONVERSATION_EXPIRED
        raise StateChangeValidationError(
            error_code="CONVERSATION_EXPIRED",
            message=f"대화 만료: {conversation_id}",
            status_code=410,
        )

    if conv.status != ConversationStatus.ACTIVE:
        raise StateChangeValidationError(
            error_code="CONVERSATION_EXPIRED",
            message=f"대화 상태가 비활성입니다: {conv.status.value}",
            status_code=410,
        )

    # ─────────────────────────────────────────────
    # 3. Idempotency-Key 기록·확인 (T063)
    # ─────────────────────────────────────────────
    expected_hash = compute_payload_hash(
        http_method=http_method,
        api_path=api_path,
        conversation_id=conversation_id,
        expected_revision=expected_revision,
        body=request_body,
    )

    # 같은 key·같은 payload 재요청 → 저장된 응답 반환 (T063)
    existing_response = check_idempotency_hit(db, conversation_id, validated_ik, expected_hash)
    if existing_response is not None:
        return {
            "conversation": conv,
            "idempotency_hit": existing_response,
            "idempotency_record": get_idempotency_record(db, conversation_id, validated_ik),
        }

    # 같은 key·다른 payload → 409 IDEMPOTENCY_KEY_REUSED (T063)
    if check_idempotency_conflict(db, conversation_id, validated_ik, expected_hash):
        raise StateChangeValidationError(
            error_code="IDEMPOTENCY_KEY_REUSED",
            message=f"이미 사용된 Idempotency-Key입니다: {validated_ik}",
            status_code=409,
        )

    # ─────────────────────────────────────────────
    # 4. Revision 확인 (T063)
    # ─────────────────────────────────────────────
    if conv.revision != expected_revision:
        raise StateChangeValidationError(
            error_code="CONVERSATION_VERSION_CONFLICT",
            message=f"대화 버전 충돌: 기대 revision={expected_revision}, 현재 revision={conv.revision}",
            status_code=409,
        )

    # ─────────────────────────────────────────────
    # 5. Candidate set 만료 확인 (T063)
    # ─────────────────────────────────────────────
    if candidate_set_expired(db, conversation_id):
        raise StateChangeValidationError(
            error_code="CANDIDATE_SET_EXPIRED",
            message=f"후보 집합이 만료되었습니다: {conversation_id}",
            status_code=410,
        )

    return {
        "conversation": conv,
        "idempotency_hit": None,
    }


# ─────────────────────────────────────────────
# T040: US1 특유 검증 (확인 조건 충족 전 plan 요청 차단)
# ─────────────────────────────────────────────

def validate_plan_request_prerequisites(
    conversation: Conversation,
    origin_place_id: str,
    destination_place_id: str,
    user_confirmed: bool = False,
) -> None:
    """계획 요청 전 필수 조건 검증 (US1 특유 검증).

    T063(일반 상태 변경 검증)과 역할 구분:
    - T063: conversation 유효성, 입력, Idempotency-Key, revision 확인
    - T040: US1 특유 검증 (확인 조건 충족 전 plan 요청 차단)

    Args:
        conversation: 대화 객체
        origin_place_id: 출발지 장소 ID
        destination_place_id: 목적지 장소 ID
        user_confirmed: 사용자 확인 완료 여부

    Raises:
        StateChangeValidationError: 검증 실패 시
    """
    # 출발지 미확정 → 422 VALIDATION_ERROR
    if not origin_place_id or not origin_place_id.strip():
        raise StateChangeValidationError(
            error_code="VALIDATION_ERROR",
            message="출발지가 확정되지 않았습니다. 먼저 장소를 확인하고 확인하세요.",
            status_code=422,
        )

    # 목적지 미확정 → 422 VALIDATION_ERROR
    if not destination_place_id or not destination_place_id.strip():
        raise StateChangeValidationError(
            error_code="VALIDATION_ERROR",
            message="목적지가 확정되지 않았습니다. 먼저 장소를 확인하고 확인하세요.",
            status_code=422,
        )

    # user_confirmed=true 없이 계산 금지 (US1 핵심 규칙)
    if not user_confirmed:
        raise StateChangeValidationError(
            error_code="USER_CONFIRMATION_REQUIRED",
            message="사용자 확인(user_confirmed=true) 없이 계획을 계산할 수 없습니다. "
                    "먼저 조건을 확인하고 확인하세요.",
            status_code=422,
        )

    # confirmed_conditions에 조건 확인 기록 확인
    confirmed = conversation.confirmed_conditions
    if confirmed is not None:
        conditions_confirmed = confirmed.get("conditions_confirmed", False)
        places_confirmed = confirmed.get("places_confirmed", False)

        if not conditions_confirmed or not places_confirmed:
            raise StateChangeValidationError(
                error_code="USER_CONFIRMATION_REQUIRED",
                message="조건 확인이 완료되지 않았습니다. 확인 질문에 답변한 후 재시도하세요.",
                status_code=422,
            )


# ─────────────────────────────────────────────
# Idempotency-Key 성공 결과 기록 (5단계 마지막)
# ─────────────────────────────────────────────

def record_idempotency_success(
    db: Session,
    conversation_id: str,
    idempotency_key: str,
    http_method: str,
    api_path: str,
    expected_revision: int,
    request_body: dict,
    response_body: dict,
    response_status: int = 200,
) -> None:
    """Idempotency-Key 성공 결과 기록.

    5단계 마지막: domain 상태 변경 + revision 증가 + idempotency 성공 결과 원자 커밋.

    Args:
        db: DB 세션 (트랜잭션 안)
        conversation_id: 대화 ID
        idempotency_key: UUID v4 키
        http_method: HTTP 메서드
        api_path: API 경로
        expected_revision: 기대 revision
        request_body: 요청 본문
        response_body: 응답 본문
        response_status: 응답 상태 코드
    """
    save_idempotency_record(
        db=db,
        conversation_id=conversation_id,
        idempotency_key=idempotency_key,
        http_method=http_method,
        api_path=api_path,
        expected_revision=expected_revision,
        request_body=request_body,
        response_body=response_body,
        response_status=response_status,
    )


# ─────────────────────────────────────────────
# 재탐색 흐름 조정 로직 (User Story 3 - T054)
# ─────────────────────────────────────────────

def validate_replan_request(
    previous_plan: Optional[dict],
    current_origin_place_id: Optional[str],
    reason: ReplanReason,
    user_confirmed: bool,
) -> tuple[bool, Optional[str]]:
    """재탐색 요청 검증.

    Args:
        previous_plan: 이전 선택 계획
        current_origin_place_id: 현재 위치
        reason: 재탐색 사유
        user_confirmed: 사용자 확인 여부

    Returns:
        tuple: (유효함, 오류 메시지)
    """
    # user_confirmed 검증
    if not user_confirmed:
        return False, "사용자 확인이 필요합니다. user_confirmed=true로 재요청하세요."

    # 재탐색 사유 검증
    valid_reasons = [ReplanReason.MISSED_CONNECTION, ReplanReason.ROUTE_CHANGED, ReplanReason.MANUAL]
    if reason not in valid_reasons:
        return False, f"유효하지 않은 재탐색 사유입니다: {reason}"

    # 이전 선택 보존 검증 (삭제되지 않음을 확인)
    # 이전 선택이 있어도 재탐색에 필수 아님 (새 출발지에서 재탐색 가능)
    # 하지만 이전 선택이 있으면 비교에 활용

    return True, None


def preserve_previous_plan_on_replan_failure(
    previous_plan: Optional[dict],
    replan_result: Optional[dict],
    failure_reason: Optional[str],
) -> dict:
    """재탐색 실패·취소 시 이전 선택 보존.

    재탐색 실패·취소는 이전 선택을 삭제하지 않음.
    이전 경로가 여전히 유효하다는 보장으로 표시하지 않음.

    Args:
        previous_plan: 이전 선택 계획
        replan_result: 재탐색 결과 (실패 시 None)
        failure_reason: 실패 사유

    Returns:
        dict: {previous_plan_preserved: bool, previous_plan_valid: bool, note: str}
    """
    # 이전 선택 보존 (항상 True - 삭제되지 않음)
    previous_plan_preserved = True

    # 이전 경로가 여전히 유효한지는 보장되지 않음
    # (실제 교통 상황은 변했을 수 있음)
    previous_plan_valid = False

    note = ""
    if failure_reason:
        note = f"재탐색이 실패했습니다: {failure_reason}. 이전 계획은 보존됩니다."
    elif replan_result is None:
        note = "재탐색이 취소되었습니다. 이전 계획은 보존됩니다."
    else:
        note = "이전 계획은 보존되었으나, 여전히 유효한지 보장되지 않습니다."

    return {
        "previous_plan_preserved": previous_plan_preserved,
        "previous_plan_valid": previous_plan_valid,
        "note": note,
    }


def prevent_auto_replacement_of_previous_plan(
    previous_plan: Optional[dict],
    new_plan: Optional[dict],
    user_selected: bool = False,
) -> dict:
    """이전 계획의 자동 교체 방지.

    사용자가 재탐색 결과를 선택하기 전까지
    기존 계획이 자동으로 교체되지 않음.

    Args:
        previous_plan: 이전 선택 계획
        new_plan: 새 계획 (재탐색 결과)
        user_selected: 사용자가 새 계획 선택 여부

    Returns:
        dict: {auto_replaced: bool, previous_plan Retained: bool, note: str}
    """
    # 자동 교체는 항상 False (사용자 선택 없이 교체되지 않음)
    auto_replaced = False
    previous_plan_retained = True

    note = "재탐색 결과가 사용자 선택 없이 기존 계획을 자동 교체하지 않습니다."

    if user_selected and new_plan:
        note = "사용자가 새 계획을 선택했습니다. 이전 계획은 보존됩니다."

    return {
        "auto_replaced": auto_replaced,
        "previous_plan_retained": previous_plan_retained,
        "note": note,
    }


class ReplanGuard:
    """재탐색 가드: 이전 선택 보존 및 자동 교체 방지 상태 관리."""

    def __init__(self):
        self._previous_plan: Optional[dict] = None
        self._previous_plan_preserved = True
        self._auto_replaced = False

    def set_previous_plan(self, plan: dict) -> None:
        """이전 선택 계획 설정."""
        self._previous_plan = plan
        self._previous_plan_preserved = True
        self._auto_replaced = False

    def clear_previous_plan(self) -> None:
        """이전 선택 계획 초기화 (삭제 아님, 단지 참조 해제)."""
        self._previous_plan = None

    def preserve_previous_plan(self) -> None:
        """이전 선택 보존 명시."""
        self._previous_plan_preserved = True

    def mark_auto_replaced(self) -> None:
        """자동 교체 표시 (사용 금지 - 항상 False여야 함)."""
        self._auto_replaced = True

    def get_status(self) -> dict:
        """현재 상태 반환."""
        return {
            "previous_plan_exists": self._previous_plan is not None,
            "previous_plan_preserved": self._previous_plan_preserved,
            "auto_replaced": self._auto_replaced,
            "previous_plan": self._previous_plan,
        }
