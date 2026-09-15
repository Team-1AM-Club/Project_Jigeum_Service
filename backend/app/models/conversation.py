"""Conversation SQLAlchemy 모델.

T057: 대화 상태 관리 모델 - conversation_id (PK), revision, expires_at,
confirmed_conditions, candidate_set, active_selected_plan, updated_at, created_at.
"""
from sqlalchemy import Column, Integer, String, DateTime, JSON, Enum as SQLEnum
from sqlalchemy.orm import declarative_base
from datetime import datetime, timezone
import enum

Base = declarative_base()


class ConversationStatus(str, enum.Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    TOMBSTONE = "tombstone"


class Conversation(Base):
    """대화 상태 관리 모델.

    Attributes:
        conversation_id: PK, UUID 문자열 (36자)
        revision: 낙관적 동시성 제어용 버전 번호
        created_at: 생성 시각
        expires_at: 만료 시각 (ISO 8601)
        confirmed_conditions: 사용자 확인 조건 (JSON)
        candidate_set: 후보 계획 집합 (JSON)
        active_selected_plan: 활성 선택 계획 (JSON)
        updated_at: 마지막 갱신 시각
        status: active/expired/tombstone
    """
    __tablename__ = "conversations"

    conversation_id = Column(String(36), primary_key=True, nullable=False)
    revision = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    confirmed_conditions = Column(JSON, nullable=True)
    candidate_set = Column(JSON, nullable=True)
    active_selected_plan = Column(JSON, nullable=True)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))
    status = Column(SQLEnum(ConversationStatus), nullable=False, default=ConversationStatus.ACTIVE)

    def to_dict(self) -> dict:
        return {
            "conversation_id": self.conversation_id,
            "revision": self.revision,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "confirmed_conditions": self.confirmed_conditions,
            "candidate_set": self.candidate_set,
            "active_selected_plan": self.active_selected_plan,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "status": self.status.value if self.status else None,
        }
