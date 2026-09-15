"""Journeys (경로 계획) 스키마.

T035: TripRequest, Plan, PlanSummary, Comparison 구조를 포함한
plan 요청/응답 스키마.
"""

from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class Place(BaseModel):
    """장소 정보."""
    place_id: str
    name: Optional[str] = None
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    place_type: Optional[str] = None


class RouteLeg(BaseModel):
    """경로 다리(leg)."""
    mode: str
    departure_at: Optional[datetime] = None
    arrival_at: Optional[datetime] = None
    origin_place_id: Optional[str] = None
    destination_place_id: Optional[str] = None
    route_id: Optional[str] = None
    leg_index: int = 0
    duration_minutes: Optional[int] = None
    distance_meters: Optional[int] = None


class RouteOption(BaseModel):
    """경로 옵션 (후보 경로 1개)."""
    option_id: str
    legs: List[RouteLeg] = Field(default_factory=list)
    total_duration_minutes: Optional[int] = Field(None, ge=0)
    total_distance_meters: Optional[int] = Field(None, ge=0)
    departure_at: Optional[datetime] = None
    arrival_at: Optional[datetime] = None
    price: Optional[int] = None
    transport_mode: Optional[str] = Field(None, pattern="^(subway|bus|walking|taxi|bicycle)$")
    confidence: float = Field(1.0, ge=0.0, le=1.0)


class TripRequest(BaseModel):
    """경로 계획 요청.

    출발지·목적지가 확정된 상태에서 경로 계획을 요청한다.
    출발지가 미확정(origin_place_id가 빈 값)이면 422 VALIDATION_ERROR 처리.
    """
    conversation_id: str = Field(..., description="대화 ID")
    origin_place_id: str = Field(..., min_length=1, description="출발지 장소 ID (빈 값이면 422)")
    destination_place_id: str = Field(..., min_length=1, description="목적지 장소 ID")
    arrival_deadline: Optional[datetime] = Field(None, description="도착 마감 시한")
    arrival_preference_minutes: int = Field(10, ge=0, le=60, description="도착 여유 시간 (분)")
    transport_mode: Optional[str] = Field(None, pattern="^(subway|bus|walking|taxi|bicycle)$", description="이동수단 필터")
    max_options: int = Field(3, ge=1, le=5, description="최대 후보 경로 수")

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "conversation_id": "conv_xyz789",
                    "origin_place_id": "place_seoul_station",
                    "destination_place_id": "place_gangnam_station",
                    "arrival_deadline": "2026-09-16T19:00:00+09:00",
                    "arrival_preference_minutes": 10,
                    "transport_mode": "subway",
                    "max_options": 3,
                }
            ]
        }


class PlanSummary(BaseModel):
    """계획 요약 (후보 경로별 권장 출발시각)."""
    option_id: str
    recommended_leave_at: datetime
    target_arrival_at: datetime
    total_duration_minutes: int
    transport_mode: Optional[str] = None
    reasoning: str = Field(..., description="권장 출발시각 근거 설명")


class Comparison(BaseModel):
    """경로 비교 정보."""
    options: List[PlanSummary] = Field(default_factory=list)
    selected_option_id: Optional[str] = Field(None, description="선택된 옵션 ID (사용자 선택 전엔 null)")
    comparison_reason: str = Field("", description="비교 근거 요약")


class Plan(BaseModel):
    """경로 계획 응답.

    공통 응답 봉투: {status, data, error, meta} 구조를 따름.
    """
    plan_id: str
    conversation_id: str
    origin_place_id: str
    destination_place_id: str
    arrival_deadline: Optional[datetime] = None
    target_arrival_at: datetime = Field(..., description="목표 도착 시각 (arrival_deadline - arrival_preference_minutes)")
    recommended_leave_at: datetime = Field(..., description="권장 출발 시각")
    total_duration_minutes: int
    transport_mode: Optional[str] = None
    comparison: Comparison = Field(default_factory=Comparison)
    buffer_applied: int = Field(5, ge=0, le=30, description="적용된 완충 시간 (분)")
    notes: Optional[str] = None
    # 막차 관련 필드 (User Story 2)
    is_last_journey: bool = Field(False, description="막차 계획 여부")
    operating_date: Optional[str] = Field(None, description="운행일 (막차 운행일, YYYY-MM-DD)")
    arrival_date: Optional[str] = Field(None, description="도착 날짜 (자정 넘어 도착 시 다음 날, YYYY-MM-DD)")
    last_journey_supported: bool = Field(False, description="막차 지원 여부 (데이터 제공자가 막차 운행 정보를 제공하는지)")

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "plan_id": "plan_abc123",
                    "conversation_id": "conv_xyz789",
                    "origin_place_id": "place_seoul_station",
                    "destination_place_id": "place_gangnam_station",
                    "arrival_deadline": "2026-09-16T19:00:00+09:00",
                    "target_arrival_at": "2026-09-16T18:50:00+09:00",
                    "recommended_leave_at": "2026-09-16T18:08:00+09:00",
                    "total_duration_minutes": 42,
                    "transport_mode": "subway",
                    "comparison": {
                        "options": [
                            {
                                "option_id": "opt_subway_1",
                                "recommended_leave_at": "2026-09-16T18:08:00+09:00",
                                "target_arrival_at": "2026-09-16T18:50:00+09:00",
                                "total_duration_minutes": 42,
                                "transport_mode": "subway",
                                "reasoning": "지하철 2호선 직행, 환승 없음. 권장 출발시각: 18:08 (buffer 5분 포함)"
                            }
                        ],
                        "selected_option_id": "opt_subway_1",
                        "comparison_reason": "환승이 적은 직행 경로를 우선 권장"
                    },
                    "buffer_applied": 5,
                    "notes": "혼잡 시간대이므로 여유 있게 출발하세요.",
                    "is_last_journey": False,
                    "operating_date": None,
                    "arrival_date": None,
                    "last_journey_supported": True
                }
            ]
        }


# ─────────────────────────────────────────────
# 재탐색 (Replan) 관련 스키마 (User Story 3)
# ─────────────────────────────────────────────

class ReplanReason(str, Enum):
    """재탐색 사유 열거형."""
    MISSED_CONNECTION = "missed_connection"
    ROUTE_CHANGED = "route_changed"
    MANUAL = "manual"


class ReplanRequest(BaseModel):
    """재탐색 요청 스키마.
    
    사용자가 기존 계획을 재탐색할 때 사용.
    이전 선택(previous_plan)은 삭제되지 않으며, 자동 교체되지 않음.
    """
    conversation_id: str = Field(..., description="대화 ID")
    trip: dict = Field(..., description="재탐색할 Trip 정보 (origin/destination 등)")
    previous_plan: Optional[dict] = Field(None, description="이전 선택 계획 (도착 변화 비교용)")
    current_origin_place_id: Optional[str] = Field(None, description="현재 위치 (변경된 출발지)")
    reason: ReplanReason = Field(..., description="재탐색 사유")
    user_confirmed: bool = Field(True, description="사용자 확인 여부")
    max_options: int = Field(3, ge=1, le=5, description="최대 후보 경로 수")

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "conversation_id": "conv_xyz789",
                    "trip": {
                        "origin_place_id": "place_seoul_station",
                        "destination_place_id": "place_gangnam_station"
                    },
                    "previous_plan": {
                        "plan_id": "plan_abc123",
                        "target_arrival_at": "2026-09-16T18:50:00+09:00",
                        "recommended_leave_at": "2026-09-16T18:08:00+09:00",
                        "total_duration_minutes": 42
                    },
                    "current_origin_place_id": "place_seoul_station",
                    "reason": "missed_connection",
                    "user_confirmed": True,
                    "max_options": 3
                }
            ]
        }


class ReplanComparison(BaseModel):
    """재탐색 비교 정보."""
    new_plan: Plan = Field(..., description="새로 계산된 계획")
    arrival_change_minutes: Optional[int] = Field(None, description="도착 시각 변화 (분, 양수=더 늦게, 음수=더 일찍)")
    leave_change_minutes: Optional[int] = Field(None, description="출발 시각 변화 (분, 양수=더 늦게, 음수=더 일찍)")
    previous_plan_preserved: bool = Field(True, description="이전 선택이 삭제되지 않고 보존됨")
    previous_plan_valid: bool = Field(False, description="이전 경로가 여전히 유효한지 (보장되지 않음)")


class ReplanResponse(BaseModel):
    """재탐색 응답 스키마."""
    replan_id: str
    conversation_id: str
    reason: ReplanReason
    comparison: ReplanComparison
    notes: Optional[str] = None

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "replan_id": "replan_xyz456",
                    "conversation_id": "conv_xyz789",
                    "reason": "missed_connection",
                    "comparison": {
                        "new_plan": {
                            "plan_id": "plan_new789",
                            "target_arrival_at": "2026-09-16T19:10:00+09:00",
                            "recommended_leave_at": "2026-09-16T18:28:00+09:00",
                            "total_duration_minutes": 42
                        },
                        "arrival_change_minutes": 20,
                        "leave_change_minutes": 20,
                        "previous_plan_preserved": True,
                        "previous_plan_valid": False
                    },
                    "notes": "이전 계획 대비 20분 늦게 도착합니다."
                }
            ]
        }
