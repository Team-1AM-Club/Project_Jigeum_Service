"""Mobility (이동/해석) 스키마.

T034: TripDraft 구조를 포함한 interpret 요청/응답 스키마.
- 자연어 입력 → TripDraft 변환 (해석 서비스)
- 확인 질문 포함 응답
"""

from datetime import datetime

from pydantic import BaseModel, Field


class PlaceInfo(BaseModel):
    """장소 정보 (간략)."""

    place_id: str
    name: str | None = None
    address: str | None = None
    place_type: str | None = None
    confidence: float = Field(1.0, ge=0.0, le=1.0)


class TripDraft(BaseModel):
    """자연어 해석 결과 - 이동 조건 초안.

    자연어 입력으로부터 해석된 이동 조건을 담는다.
    모든 필드는 해석 결과에 따라 채워지며, 미확정 항목은 null일 수 있다.
    """

    origin_place_id: str | None = Field(
        None, description="출발지 장소 ID (미확정 시 null)"
    )
    origin_place_name: str | None = Field(None, description="출발지 이름")
    destination_place_id: str | None = Field(None, description="목적지 장소 ID")
    destination_place_name: str | None = Field(None, description="목적지 이름")
    departure_at: datetime | None = Field(None, description="출발 예정 시각")
    arrival_deadline: datetime | None = Field(None, description="도착 마감 시한")
    arrival_preference_minutes: int = Field(
        10, ge=0, le=60, description="도착 여유 시간 (분)"
    )
    transport_mode: str | None = Field(
        None, pattern="^(subway|bus|walking|taxi|bicycle)$", description="이동수단"
    )
    natural_language: str = Field(..., description="사용자 원본 자연어 입력")

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "natural_language": "오늘 오후 7시까지 테스트 B역 2번 출구에 도착해야 해. 집에서 출발할 거야.",
                    "arrival_deadline": "2026-09-16T19:00:00+09:00",
                    "arrival_preference_minutes": 10,
                    "transport_mode": None,
                    "origin_place_id": None,
                    "destination_place_id": None,
                }
            ]
        }


class ConfirmationQuestion(BaseModel):
    """확인 질문 (해석 결과)."""

    question_type: str = Field(
        ..., description="질문 유형: place_confirmation | condition_confirmation"
    )
    place_id: str | None = Field(None, description="관련 장소 ID")
    place_name: str | None = Field(None, description="관련 장소 이름")
    question: str = Field(..., description="확인 질문 내용")
    alternatives: list[dict] = Field(
        default_factory=list, description="대안 목록 (장소 선택 시)"
    )


class InterpretRequest(BaseModel):
    """해석 요청 스키마."""

    natural_language: str = Field(
        ..., min_length=1, max_length=2000, description="사용자 자연어 입력"
    )
    conversation_id: str | None = Field(None, description="대화 ID (선택)")

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "natural_language": "오늘 오후 7시까지 강남역에 도착해야 해.",
                    "conversation_id": "conv_example123",
                }
            ]
        }


class InterpretResponse(BaseModel):
    """해석 응답 스키마.

    공통 응답 봉투: {status, data, error, meta} 구조를 따름.
    """

    trip_draft: TripDraft
    confirmation_questions: list[ConfirmationQuestion] = Field(default_factory=list)
    requires_confirmation: bool = Field(True, description="확인 필요 여부")
    next_action: str = Field("confirm", description="다음 액션: confirm | plan | retry")

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "trip_draft": {
                        "natural_language": "오늘 오후 7시까지 강남역에 도착해야 해.",
                        "arrival_deadline": "2026-09-16T19:00:00+09:00",
                        "arrival_preference_minutes": 10,
                        "origin_place_id": None,
                        "destination_place_id": "place_gangnam_station",
                        "destination_place_name": "강남역",
                    },
                    "confirmation_questions": [
                        {
                            "question_type": "place_confirmation",
                            "place_id": "place_gangnam_station",
                            "place_name": "강남역",
                            "question": "목적지를 '강남역'으로 확인하셨나요?",
                            "alternatives": [],
                        }
                    ],
                    "requires_confirmation": True,
                    "next_action": "confirm",
                }
            ]
        }


# 기존 MobilityRequest/Response도 유지 (T034 이전 스키마 호환)
class MobilityOption(BaseModel):
    option_id: str
    leg_index: int = 0
    departure_at: datetime | None = None
    arrival_at: datetime | None = None
    total_duration_minutes: int | None = None
    legs: list[dict] = []
    price: int | None = None
    distance_meters: int | None = None
    mode: str = "unknown"


class MobilityRequest(BaseModel):
    origin_place_id: str
    destination_place_id: str
    departure_at: datetime | None = None
    arrival_deadline: datetime | None = None
    transport_mode: str | None = Field(
        None, pattern="^(subway|bus|walking|taxi|bicycle)$"
    )
    max_options: int = Field(5, ge=1, le=10)


class MobilityResponse(BaseModel):
    options: list[MobilityOption] = []
    origin: dict | None = None
    destination: dict | None = None
