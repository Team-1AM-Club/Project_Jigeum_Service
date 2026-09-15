"""Idempotency 서비스 - Idempotency-Key 처리 로직.

T061: Idempotency-Key 처리 완성
- conversation_id + idempotency_key UNIQUE 제약
- payload hash 계산 (HTTP method, 정규화된 path, conversation_id, expected revision,
  canonicalized body → SHA-256)
- 저장·조회
- 같은 key·동일 payload → 최초 응답 반환
- 같은 key·다른 payload → 409 IDEMPOTENCY_KEY_REUSED
- 누락·형식 오류 → 422 VALIDATION_ERROR
"""
import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, UniqueConstraint
from sqlalchemy.orm import Session

from app.models.idempotency import IdempotencyRecord
from app.models.conversation import Conversation

# UUID v4 패턴: xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx (y = 8,9,A,B)
UUID_V4_PATTERN = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$',
    re.IGNORECASE
)


# ─────────────────────────────────────────────
# Payload Hash 계산 (SHA-256)
# ─────────────────────────────────────────────

def compute_payload_hash(
    http_method: str,
    api_path: str,
    conversation_id: str,
    expected_revision: Optional[int],
    body: Optional[dict],
) -> str:
    """HTTP method + 정규화된 path + conversation_id + expected revision +
    canonicalized body → SHA-256.

    canonicalized body: JSON 키를 정렬하여 직렬화.
    """
    # 정규화된 path: trailing slash 제거, 소문자화
    normalized_path = api_path.rstrip("/").lower()

    canonical = {
        "method": http_method.upper(),
        "path": normalized_path,
        "conversation_id": conversation_id,
        "expected_revision": expected_revision,
        "body": _canonicalize_body(body),
    }

    raw = json.dumps(canonical, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _canonicalize_body(body: Optional[dict]) -> Optional[dict]:
    """body를 정렬 키 JSON으로 canonicalize."""
    if body is None:
        return None
    return json.loads(json.dumps(body, sort_keys=True, ensure_ascii=False))


# ─────────────────────────────────────────────
# Idempotency-Key 검증
# ─────────────────────────────────────────────

def validate_idempotency_key_format(idempotency_key: Optional[str]) -> str:
    """Idempotency-Key 형식 검증 (UUID v4, 36자).

    Args:
        idempotency_key: 헤더 값 또는 None

    Returns:
        검증된 key 문자열

    Raises:
        ValueError: 누락 또는 형식 오류
    """
    if not idempotency_key:
        raise ValueError("Idempotency-Key 헤더가 필수입니다.")

    key = idempotency_key.strip()

    if len(key) != 36:
        raise ValueError("Idempotency-Key는 UUID v4 표준 36자여야 합니다.")

    if not UUID_V4_PATTERN.match(key):
        raise ValueError("Idempotency-Key는 유효한 UUID v4여야 합니다.")

    return key


# ─────────────────────────────────────────────
# Idempotency 기록 저장
# ─────────────────────────────────────────────

def save_idempotency_record(
    db: Session,
    conversation_id: str,
    idempotency_key: str,
    http_method: str,
    api_path: str,
    expected_revision: int,
    request_body: Optional[dict],
    response_body: dict,
    response_status: int,
) -> IdempotencyRecord:
    """IdempotencyRecord 생성·저장.

    conversation_id + idempotency_key UNIQUE 위반 시 예외 발생.

    Args:
        db: DB 세션
        conversation_id: 대화 ID
        idempotency_key: UUID v4 키
        http_method: HTTP 메서드
        api_path: API 경로
        expected_revision: 기대 revision
        request_body: 요청 본문 (hash 계산용)
        response_body: 응답 본문
        response_status: 응답 상태 코드

    Returns:
        생성된 IdempotencyRecord
    """
    payload_hash = compute_payload_hash(
        http_method=http_method,
        api_path=api_path,
        conversation_id=conversation_id,
        expected_revision=expected_revision,
        body=request_body,
    )

    record = IdempotencyRecord(
        conversation_id=conversation_id,
        idempotency_key=idempotency_key,
        method=http_method.upper(),
        path=api_path.rstrip("/").lower(),
        payload_hash=payload_hash,
        expected_revision=expected_revision,
        response_data=json.dumps(response_body, ensure_ascii=False) if response_body else None,
        created_at=datetime.now(timezone.utc),
    )

    db.add(record)
    db.flush()
    db.refresh(record)
    return record


# ─────────────────────────────────────────────
# Idempotency 기록 조회
# ─────────────────────────────────────────────

def get_idempotency_record(
    db: Session,
    conversation_id: str,
    idempotency_key: str,
) -> Optional[IdempotencyRecord]:
    """conversation_id + idempotency_key로 record 조회.

    Args:
        db: DB 세션
        conversation_id: 대화 ID
        idempotency_key: UUID v4 키

    Returns:
        IdempotencyRecord 또는 None
    """
    stmt = select(IdempotencyRecord).where(
        IdempotencyRecord.conversation_id == conversation_id,
        IdempotencyRecord.idempotency_key == idempotency_key,
    )
    result = db.execute(stmt)
    return result.scalar_one_or_none()


# ─────────────────────────────────────────────
# Idempotency 충돌 확인
# ─────────────────────────────────────────────

def check_idempotency_conflict(
    db: Session,
    conversation_id: str,
    idempotency_key: str,
    expected_payload_hash: str,
) -> bool:
    """동일 키에 다른 payload hash 존재 → 409 IDEMPOTENCY_KEY_REUSED.

    Args:
        db: DB 세션
        conversation_id: 대화 ID
        idempotency_key: UUID v4 키
        expected_payload_hash: 현재 요청의 예상 hash

    Returns:
        True: 충돌 발생 (다른 payload), False: 일치 또는 없음
    """
    record = get_idempotency_record(db, conversation_id, idempotency_key)
    if record is None:
        return False

    return record.payload_hash != expected_payload_hash


def check_idempotency_hit(
    db: Session,
    conversation_id: str,
    idempotency_key: str,
    expected_payload_hash: str,
) -> Optional[dict]:
    """같은 key·같은 payload 재요청 → 저장된 응답 반환.

    Args:
        db: DB 세션
        conversation_id: 대화 ID
        idempotency_key: UUID v4 키
        expected_payload_hash: 현재 요청의 예상 hash

    Returns:
        저장된 response_body (dict) 또는 None (miss)
    """
    record = get_idempotency_record(db, conversation_id, idempotency_key)
    if record is None:
        return None

    if record.payload_hash != expected_payload_hash:
        return None  # 다른 payload → caller가 409 처리해야 함

    if record.response_data:
        return json.loads(record.response_data)
    return None
