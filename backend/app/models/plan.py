"""Plan SQLAlchemy 모델.

Conversation 모델과 1:N 관계. Plan은 특정 대화의 선택된 이동 계획을 저장한다.
"""
from sqlalchemy import Column, Integer, String, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime, timezone

# conversation.py의 Base를 공유
from app.models.conversation import Base


class Plan(Base):
    """계획(Plan) 모델.

    Attributes:
        plan_id: PK
        conversation_id: FK → conversations.conversation_id
        selected_option_id: 선택된 옵션 ID
        recommended_leave_at: 권장 출발 시각
        estimated_arrival_at: 예상 도착 시각
        total_duration_minutes: 총 소요 시간 (분)
        legs: 경로 상세 (JSON 배열)
        origin_place_id: 출발지 장소 ID
        destination_place_id: 도착지 장소 ID
        created_at: 생성 시각
    """
    __tablename__ = "plans"

    plan_id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(String(36), ForeignKey("conversations.conversation_id"), nullable=False, index=True)
    selected_option_id = Column(String(255), nullable=False)
    recommended_leave_at = Column(DateTime(timezone=True), nullable=True)
    estimated_arrival_at = Column(DateTime(timezone=True), nullable=True)
    total_duration_minutes = Column(Integer, nullable=True)
    legs = Column(JSON, nullable=True)  # JSON 배열, 경로 상세
    origin_place_id = Column(String(255), nullable=False)
    destination_place_id = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Conversation과의 관계 (선택적)
    conversation = relationship("Conversation", back_populates="plans")


# Conversation 모델에 plans 관계 추가 (양방향)
from app.models.conversation import Conversation
Conversation.plans = relationship("Plan", back_populates="conversation", cascade="all, delete-orphan")
