"""대화 상태 관리 서비스.

Conversation 모델 기반 CRUD + 만료(tombstone 전환) + hard delete.
"""
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.conversation import Conversation, ConversationStatus
from app.models.plan import Plan
from app.schemas.errors import ErrorCode

SEOUL_TZ = ZoneInfo("Asia/Seoul")


def _ensure_aware_utc(dt):
    """DB 조회 시 timezone 정보가 소실된 datetime을 UTC aware로 복원.

    SQLite는 timezone 정보를 저장하지 않아 naive datetime으로 조회된다.
    비교·연산 전 UTC로 보정한다.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


# ─────────────────────────────────────────────
# 대화 생성
# ─────────────────────────────────────────────
def create_conversation(
    db: Session,
    conversation_id: Optional[str] = None,
    expires_in_minutes: int = 1440,  # 기본 24시간
    confirmed_conditions: Optional[dict] = None,
    candidate_set: Optional[dict] = None,
    active_selected_plan: Optional[dict] = None,
) -> Conversation:
    """새 대화 생성.

    Args:
        db: DB 세션
        conversation_id: 직접 지정 UUID (미지정 시 자동 생성)
        expires_in_minutes: 생성 시점부터 만료까지 분
        confirmed_conditions: 초기 확인 조건 (옵션)
        candidate_set: 초기 후보 집합 (옵션)
        active_selected_plan: 초기 선택 계획 (옵션)

    Returns:
        생성된 Conversation 객체
    """
    if conversation_id is None:
        conversation_id = str(uuid.uuid4())

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=expires_in_minutes)

    conv = Conversation(
        conversation_id=conversation_id,
        revision=1,
        expires_at=expires_at,
        confirmed_conditions=confirmed_conditions,
        candidate_set=candidate_set,
        active_selected_plan=active_selected_plan,
        status=ConversationStatus.ACTIVE,
        updated_at=now,
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


# ─────────────────────────────────────────────
# 대화 조회
# ─────────────────────────────────────────────
def get_conversation(
    db: Session,
    conversation_id: str,
    include_expired: bool = False,
) -> Optional[Conversation]:
    """conversation_id로 대화 조회.

    Args:
        db: DB 세션
        conversation_id: UUID 문자열
        include_expired: expired/tombstone 상태도 반환할지

    Returns:
        Conversation 또는 None
    """
    stmt = select(Conversation).where(Conversation.conversation_id == conversation_id)
    result = db.execute(stmt)
    conv = result.scalar_one_or_none()

    if conv is None:
        return None

    # 기본: active만 반환, expired/tombstone은 제외
    if not include_expired and conv.status in (ConversationStatus.EXPIRED, ConversationStatus.TOMBSTONE):
        return None

    return conv


# ─────────────────────────────────────────────
# 대화 갱신 (revision 증가)
# ─────────────────────────────────────────────
def update_conversation(
    db: Session,
    conversation_id: str,
    expected_revision: int,
    **updates,
) -> Conversation:
    """대화 갱신 (optimistic locking: revision 확인).

    Args:
        db: DB 세션
        conversation_id: UUID 문자열
        expected_revision: 기대 revision (불일치 시 409)
        **updates: 갱신할 필드 (confirmed_conditions, candidate_set 등)

    Returns:
        갱신된 Conversation

    Raises:
        ValueError: 대화 없음 또는 revision 불일치
    """
    conv = get_conversation(db, conversation_id, include_expired=True)
    if conv is None:
        raise ValueError(f"Conversation not found: {conversation_id}")

    if conv.status == ConversationStatus.TOMBSTONE:
        raise ValueError(f"Conversation is tombstone: {conversation_id}")

    if conv.revision != expected_revision:
        raise ValueError(
            f"Revision mismatch: expected={expected_revision}, actual={conv.revision}"
        )

    # 필드 갱신
    for key, value in updates.items():
        if hasattr(conv, key):
            setattr(conv, key, value)

    conv.revision += 1
    conv.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(conv)
    return conv


# ─────────────────────────────────────────────
# 대화 만료 → tombstone 전환 (soft delete)
# ─────────────────────────────────────────────
def expire_conversation(
    db: Session,
    conversation_id: str,
) -> Conversation:
    """대화 만료 (tombstone 전환).

    active → tombstone 으로 변경. 데이터 보존.
    """
    conv = get_conversation(db, conversation_id, include_expired=True)
    if conv is None:
        raise ValueError(f"Conversation not found: {conversation_id}")

    if conv.status == ConversationStatus.TOMBSTONE:
        return conv  # 이미 tombstone

    conv.status = ConversationStatus.TOMBSTONE
    conv.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(conv)
    return conv


# ─────────────────────────────────────────────
# 대화 hard delete
# ─────────────────────────────────────────────
def hard_delete_conversation(
    db: Session,
    conversation_id: str,
) -> bool:
    """대화 완전 삭제 (Tombstone인 경우만 허용, 안전장치).

    Plan도 함께 삭제 (CASCADE). 보안상 active/ expired는 삭제 불가.
    """
    conv = get_conversation(db, conversation_id, include_expired=True)
    if conv is None:
        return False

    if conv.status != ConversationStatus.TOMBSTONE:
        raise ValueError(f"Hard delete는 tombstone 상태에서만 허용됨: status={conv.status.value}")

    db.delete(conv)
    db.commit()
    return True



# ─────────────────────────────────────────────
# 상태 전이 헬퍼
# ─────────────────────────────────────────────

def mark_conditions_confirmed(
    db: Session,
    conversation_id: str,
    expected_revision: int,
    conditions: dict,
) -> Conversation:
    """조건 확인 완료 상태로 전이.

    Args:
        db: DB 세션
        conversation_id: UUID 문자열
        expected_revision: 기대 revision
        conditions: 확인된 조건 dict (예: {"user_confirmed": True, "places_confirmed": True, ...})

    Returns:
        갱신된 Conversation

    Raises:
        ValueError: 대화 없음, revision 불일치, 이미 만료
    """
    conv = update_conversation(
        db=db,
        conversation_id=conversation_id,
        expected_revision=expected_revision,
        confirmed_conditions=conditions,
    )
    return conv


def mark_candidate_set_ready(
    db: Session,
    conversation_id: str,
    expected_revision: int,
    candidate_set: dict,
) -> Conversation:
    """후보 도출 완료 상태로 전이.

    Args:
        db: DB 세션
        conversation_id: UUID 문자열
        expected_revision: 기대 revision
        candidate_set: 후보 계획 집합 (예: {"options": [...], "expires_at": "...", ...})

    Returns:
        갱신된 Conversation
    """
    conv = update_conversation(
        db=db,
        conversation_id=conversation_id,
        expected_revision=expected_revision,
        candidate_set=candidate_set,
    )
    return conv


def mark_plan_selected(
    db: Session,
    conversation_id: str,
    expected_revision: int,
    selected_plan: dict,
) -> Conversation:
    """계획 선택 완료 상태로 전이.

    Args:
        db: DB 세션
        conversation_id: UUID 문자열
        expected_revision: 기대 revision
        selected_plan: 선택된 계획 dict

    Returns:
        갱신된 Conversation
    """
    conv = update_conversation(
        db=db,
        conversation_id=conversation_id,
        expected_revision=expected_revision,
        active_selected_plan=selected_plan,
    )
    return conv


def check_and_handle_expiry(
    db: Session,
    conversation_id: str,
) -> tuple[Optional[Conversation], bool]:
    """만료 확인 + tombstone 전환 (멱등).

    expires_at <= now 이면:
    1. confirmed_conditions, candidate_set, active_selected_plan payload 제거
    2. status → tombstone
    3. conversation_id, 마지막 revision, expired_at 보관

    Args:
        db: DB 세션
        conversation_id: UUID 문자열

    Returns:
        (conversation, was_expired) 튜플
        - was_expired=True: 만료 처리됨 (또는 이미 tombstone)
        - was_expired=False: 아직 active 상태
    """
    conv = get_conversation(db, conversation_id, include_expired=True)
    if conv is None:
        return None, False  # conversation 없음 → 404로 처리해야 함

    now = datetime.now(timezone.utc)

    if conv.status == ConversationStatus.TOMBSTONE:
        # 이미 tombstone → 멱등 반환
        return conv, True

    expires_at = _ensure_aware_utc(conv.expires_at)
    if expires_at is not None and expires_at <= now:
        # 만료 → tombstone 전환
        # payload 제거 (보안상 완전히 삭제)
        conv.confirmed_conditions = None
        conv.candidate_set = None
        conv.active_selected_plan = None
        conv.status = ConversationStatus.TOMBSTONE
        conv.updated_at = now
        db.commit()
        db.refresh(conv)
        return conv, True

    # 아직 active
    return conv, False


def candidate_set_expired(
    db: Session,
    conversation_id: str,
) -> bool:
    """후보 집합만 만료되었는지 확인.

    conversation은 active지만 candidate_set의 expires_at이 지난 경우.

    Args:
        db: DB 세션
        conversation_id: UUID 문자열

    Returns:
        True: candidate_set 만료, False: 아님 또는 candidate_set 없음
    """
    conv = get_conversation(db, conversation_id)
    if conv is None:
        return False

    if conv.candidate_set is None:
        return False

    # candidate_set 내 expires_at 확인 (ISO 8601 문자열일 수 있음)
    cs_expires = conv.candidate_set.get("expires_at")
    if cs_expires is None:
        return False

    # 문자열 → datetime 파싱
    from datetime import datetime
    if isinstance(cs_expires, str):
        cs_expires_dt = datetime.fromisoformat(cs_expires.replace("Z", "+00:00"))
        if cs_expires_dt.tzinfo is None:
            from zoneinfo import ZoneInfo
            cs_expires_dt = cs_expires_dt.replace(tzinfo=ZoneInfo("Asia/Seoul"))
    else:
        cs_expires_dt = cs_expires

    now = datetime.now(timezone.utc)
    cs_expires_dt = _ensure_aware_utc(cs_expires_dt)
    return cs_expires_dt <= now


def hard_delete_if_eligible(
    db: Session,
    conversation_id: str,
    tombstone_age_hours: int = 24,
) -> bool:
    """tombstone 24시간 경과 시 hard delete.

    Args:
        db: DB 세션
        conversation_id: UUID 문자열
        tombstone_age_hours: tombstone 유지 시간 (기본 24시간)

    Returns:
        True: 삭제됨, False: 아직 삭제 불가 (24시간 미경과 또는 tombstone 아님)
    """
    conv = get_conversation(db, conversation_id, include_expired=True)
    if conv is None:
        return False

    if conv.status != ConversationStatus.TOMBSTONE:
        return False

    # tombstone 전환된 시각 확인 (updated_at 기준)
    tombstone_since = conv.updated_at
    if tombstone_since is None:
        return False

    tombstone_since = _ensure_aware_utc(tombstone_since)
    eligible = datetime.now(timezone.utc) - tombstone_since >= __import__("datetime").timedelta(hours=tombstone_age_hours)
    if not eligible:
        return False

    # 하드 삭제
    db.delete(conv)
    db.commit()
    return True
