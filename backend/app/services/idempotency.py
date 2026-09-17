"""Idempotency Record 모델 및 서비스.

- conversation_id + idempotency_key UNIQUE 제약
- payload hash 계산 (SHA-256): HTTP method + 정규화된 path + conversation_id + expected revision + canonicalized body
- 저장·조회 기능 제공
"""

import hashlib
import json
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from pydantic import BaseModel

SEOUL_TZ = ZoneInfo("Asia/Seoul")


# ─────────────────────────────────────────────
# Pydantic 스키마 (API 표현용)
# ─────────────────────────────────────────────
class IdempotencyRecordResponse(BaseModel):
    id: int
    conversation_id: str
    idempotency_key: str
    payload_hash: str
    http_method: str
    api_path: str
    expected_revision: int | None = None
    response_body: dict | None = None
    response_status: int | None = None
    created_at: datetime


# ─────────────────────────────────────────────
# SQLAlchemy 모델 (T022 부분, 별도 모델 파일로도 정의 가능)
# 여기서는 서비스 로직에 필요한 최소 모델 포함
# ─────────────────────────────────────────────
from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class IdempotencyRecord(Base):
    """IdempotencyRecord SQLAlchemy 모델."""

    __tablename__ = "idempotency_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(String(255), nullable=False, index=True)
    idempotency_key = Column(String(36), nullable=False)
    payload_hash = Column(String(64), nullable=False)
    http_method = Column(String(10), nullable=False)
    api_path = Column(String(255), nullable=False)
    expected_revision = Column(Integer, nullable=True)
    response_body = Column(Text, nullable=True)  # JSON 직렬화 문자열
    response_status = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


# conversation_id + idempotency_key UNIQUE 제약은
# DB 마이그레이션 또는 테이블 생성 시 추가해야 함.
# 여기서는 주석으로만 표시하고, 실제 UNIQUE 제약은
# migrations 또는 Base.metadata.create_all 전에 수동으로 지정.


# ─────────────────────────────────────────────
# Payload Hash 계산 (SHA-256)
# ─────────────────────────────────────────────
def compute_payload_hash(
    http_method: str,
    api_path: str,
    conversation_id: str,
    expected_revision: int | None,
    body: dict | None,
) -> str:
    """HTTP method + 정규화된 path + conversation_id + expected revision + canonicalized body → SHA-256.

    canonicalized body: JSON 키를 정렬하여 직렬화.
    """
    canonical = {
        "method": http_method.upper(),
        "path": api_path.rstrip("/"),
        "conversation_id": conversation_id,
        "expected_revision": expected_revision,
        "body": _canonicalize_body(body),
    }
    raw = json.dumps(canonical, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _canonicalize_body(body: dict | None) -> dict | None:
    """body를 정렬 키 JSON으로 canonicalize."""
    if body is None:
        return None
    return json.loads(json.dumps(body, sort_keys=True, ensure_ascii=False))


# ─────────────────────────────────────────────
# Idempotency 서비스 함수
# ─────────────────────────────────────────────
async def save_idempotency_record(
    db_session,
    conversation_id: str,
    idempotency_key: str,
    http_method: str,
    api_path: str,
    expected_revision: int | None,
    body: dict | None,
    response_body: dict | None,
    response_status: int,
) -> IdempotencyRecord:
    """IdempotencyRecord 생성·저장.

    conversation_id + idempotency_key UNIQUE 위반 시 예외 발생.
    """
    payload_hash = compute_payload_hash(
        http_method=http_method,
        api_path=api_path,
        conversation_id=conversation_id,
        expected_revision=expected_revision,
        body=body,
    )

    record = IdempotencyRecord(
        conversation_id=conversation_id,
        idempotency_key=idempotency_key,
        payload_hash=payload_hash,
        http_method=http_method,
        api_path=api_path,
        expected_revision=expected_revision,
        response_body=json.dumps(response_body) if response_body else None,
        response_status=response_status,
        created_at=datetime.now(UTC),
    )
    db_session.add(record)
    db_session.flush()
    db_session.refresh(record)
    return record


async def get_idempotency_record(
    db_session,
    conversation_id: str,
    idempotency_key: str,
) -> IdempotencyRecord | None:
    """conversation_id + idempotency_key로 record 조회."""
    return (
        db_session.query(IdempotencyRecord)
        .filter(
            IdempotencyRecord.conversation_id == conversation_id,
            IdempotencyRecord.idempotency_key == idempotency_key,
        )
        .first()
    )


async def check_idempotency_conflict(
    db_session,
    conversation_id: str,
    idempotency_key: str,
    expected_payload_hash: str,
) -> bool:
    """동일 키에 다른 payload hash → 409 IDEMPOTENCY_KEY_REUSED."""
    record = await get_idempotency_record(db_session, conversation_id, idempotency_key)
    if record and record.payload_hash != expected_payload_hash:
        return True  # conflict
    return False
