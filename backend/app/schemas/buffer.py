"""Buffer (계획) 스키마.

target_arrival_at, recommended_leave_at, total_duration_minutes, legs, buffer 필드 포함.
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class Leg(BaseModel):
    """경로 다리(leg) 스키마."""
    mode: str
    departure_at: Optional[datetime] = None
    arrival_at: Optional[datetime] = None
    origin_place_id: Optional[str] = None
    destination_place_id: Optional[str] = None
    route_id: Optional[str] = None
    leg_index: int = 0
    duration_minutes: Optional[int] = None
    distance_meters: Optional[int] = None


class BufferPlan(BaseModel):
    """완충 계획(Buffer Plan) 스키마.

    target_arrival_at: 목표 도착 시각 (사용자가 지정한 arrival_deadline + buffer 고려)
    recommended_leave_at: 권장 출발 시각
    total_duration_minutes: 총 소요 시간 (분)
    legs: 경로 상세 다리 목록
    buffer: 적용된 완충 시간 (분)
    """
    plan_id: Optional[str] = None
    conversation_id: Optional[str] = None
    selected_option_id: Optional[str] = None
    origin_place_id: str
    destination_place_id: str
    target_arrival_at: Optional[datetime] = Field(None, description="목표 도착 시각 (arrival_deadline 기준)")
    recommended_leave_at: Optional[datetime] = Field(None, description="권장 출발 시각 (total_duration + buffer 반영)")
    total_duration_minutes: Optional[int] = Field(None, ge=0, description="총 소요 시간 (분)")
    legs: List[Leg] = Field(default_factory=list, description="경로 다리 목록")
    buffer: int = Field(5, ge=0, le=30, description="완충 시간 (분)")
    transport_mode: Optional[str] = Field(None, pattern="^(subway|bus|walking|taxi|bicycle)$")
    confidence: float = Field(1.0, ge=0.0, le=1.0)
    notes: Optional[str] = None

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "plan_id": "plan_abc123",
                    "conversation_id": "conv_xyz789",
                    "selected_option_id": "opt_subway_1",
                    "origin_place_id": "place_seoul_station",
                    "destination_place_id": "place_gangnam_station",
                    "target_arrival_at": "2026-09-16T10:00:00+09:00",
                    "recommended_leave_at": "2026-09-16T09:15:00+09:00",
                    "total_duration_minutes": 42,
                    "legs": [
                        {
                            "mode": "subway",
                            "departure_at": "2026-09-16T09:15:00+09:00",
                            "arrival_at": "2026-09-16T09:35:00+09:00",
                            "origin_place_id": "place_seoul_station",
                            "destination_place_id": "place_transfer",
                            "route_id": "line_2",
                            "leg_index": 0,
                            "duration_minutes": 20,
                            "distance_meters": 5000,
                        }
                    ],
                    "buffer": 5,
                    "transport_mode": "subway",
                    "confidence": 0.95,
                    "notes": "혼잡도 보통",
                }
            ]
        }


class BufferPolicy(BaseModel):
    """완충 정책 스키마."""
    default_buffer_minutes: int = Field(5, ge=0, le=30)
    max_buffer_minutes: int = Field(30, ge=0, le=60)
    apply_buffer: bool = True
    buffer_on_transfer: bool = True
    buffer_for_running_risk: bool = True
