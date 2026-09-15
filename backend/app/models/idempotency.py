"""IdempotencyRecord SQLAlchemy 모델.

T058: IdempotencyRecord 모델 생성
- id (PK), conversation_id (FK), idempotency_key, method, path, payload_hash,
  expected_revision, created_at, response_data
- conversation_id + idempotency_key UNIQUE 제약 포함
"""
from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.orm import declarative_base
from datetime import datetime, timezone


Base = declarative_base()


class IdempotencyRecord(Base):
    """Idempotency-Key 기록 모델.

    Attributes:
        id: PK, 자동 증가
        conversation_id: FK 참조 Conversation.conversation_id
        idempotency_key: UUID v4 문자열 (36자)
        method: HTTP 메서드 (GET/POST/PUT/DELETE 등)
        path: 정규화된 API 경로
        payload_hash: SHA-256 해시 (64자 hex)
        expected_revision: 요청 시 기대 revision
        response_data: 응답 본문 JSON 직렬화 문자열
        created_at: 기록 생성 시각
    """
    __tablename__ = "idempotency_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(String(36), nullable=False, index=True)
    idempotency_key = Column(String(36), nullable=False)
    method = Column(String(10), nullable=False)
    path = Column(String(255), nullable=False)
    payload_hash = Column(String(64), nullable=False)
    expected_revision = Column(Integer, nullable=True)
    response_data = Column(Text, nullable=True)  # JSON 직렬화 문자열
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        nullable=False)

    # conversation_id + idempotency_key UNIQUE 제약
    __table_args__ = (
        # SQLite에서는 UniqueConstraint로 선언
        __import__("sqlalchemy").UniqueConstraint(
            "conversation_id", "idempotency_key",
            name="uq_conversation_id_idempotency_key"
        ),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "idempotency_key": self.idempotency_key,
            "method": self.method,
            "path": self.path,
            "payload_hash": self.payload_hash,
            "expected_revision": self.expected_revision,
            "response_data": self.response_data,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
