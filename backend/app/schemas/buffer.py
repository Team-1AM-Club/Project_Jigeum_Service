"""Buffer (계획) 스키마.

target_arrival_at, recommended_leave_at, total_duration_minutes, legs, buffer 필드 포함.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class Leg(BaseModel):
    """경로 다리(leg) 스키마."""

    mode: str
    departure_at: datetime | None = None
    arrival_at: datetime | None = None
    origin_place_id: str | None = None
    destination_place_id: str | None = None
    route_id: str | None = None
    leg_index: int = 0
    duration_minutes: int | None = None
    distance_meters: int | None = None


class BufferPlan(BaseModel):
    """완충 계획(Buffer Plan) 스키마.

    target_arrival_at: 목표 도착 시각 (사용자가 지정한 arrival_deadline + buffer 고려)
    recommended_leave_at: 권장 출발 시각
    total_duration_minutes: 총 소요 시간 (분)
    legs: 경로 상세 다리 목록
    buffer: 적용된 완충 시간 (분)
    """

    plan_id: str | None = None
    conversation_id: str | None = None
    selected_option_id: str | None = None
    origin_place_id: str
    destination_place_id: str
    target_arrival_at: datetime | None = Field(
        None, description="목표 도착 시각 (arrival_deadline 기준)"
    )
    recommended_leave_at: datetime | None = Field(
        None, description="권장 출발 시각 (total_duration + buffer 반영)"
    )
    total_duration_minutes: int | None = Field(
        None, ge=0, description="총 소요 시간 (분)"
    )
    legs: list[Leg] = Field(default_factory=list, description="경로 다리 목록")
    buffer: int = Field(5, ge=0, le=30, description="완충 시간 (분)")
    transport_mode: str | None = Field(
        None, pattern="^(subway|bus|walking|taxi|bicycle)$"
    )
    confidence: float = Field(1.0, ge=0.0, le=1.0)
    notes: str | None = None

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
