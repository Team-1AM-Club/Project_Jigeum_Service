"""Mock 제공자 구현.

실제 데이터 의존 없이 고정/hardcoded 응답을 반환한다.
Phase 1 MVP에서 제공자 의존성을 분리하기 위한 테스트 더블.
"""
from typing import Any, List, Optional
from app.schemas.places import PlaceResult
from app.services.provider_interfaces import (
    RoutingProvider,
    TransitProvider,
    PlaceProvider,
    ModelProvider,
    ProviderResult,
)

# ─────────────────────────────────────────────
# MockPlaceProvider
# ─────────────────────────────────────────────
class MockPlaceProvider(PlaceProvider):
    """고정 장소 데이터를 반환하는 Mock PlaceProvider."""

    # Seoul 랜드마크 고정 데이터
    _MOCK_PLACES: List[dict] = [
        {
            "place_id": "place_seoul_station",
            "name": "서울역",
            "address": "서울특별시 용산구 한강대로 405",
            "latitude": 37.5546,
            "longitude": 126.9708,
            "place_type": "train_station",
            "confidence": 0.98,
        },
        {
            "place_id": "place_gangnam_station",
            "name": "강남역",
            "address": "서울특별시 강남구 강남대로 396",
            "latitude": 37.4971,
            "longitude": 127.0276,
            "place_type": "subway_station",
            "confidence": 0.97,
        },
        {
            "place_id": "place_jongro3ga_station",
            "name": "종로3가역",
            "address": "서울특별시 종로구 종로 129",
            "latitude": 37.5710,
            "longitude": 126.9920,
            "place_type": "subway_station",
            "confidence": 0.95,
        },
        {
            "place_id": "place_bongeunsa",
            "name": "봉은사",
            "address": "서울특별시 강남구 봉은사로 531",
            "latitude": 37.5172,
            "longitude": 127.0591,
            "place_type": "landmark",
            "confidence": 0.92,
        },
        {
            "place_id": "place_lake_palace",
            "name": "석촌호수",
            "address": "서울특별시 송파구 잠실동",
            "latitude": 37.5087,
            "longitude": 127.1044,
            "place_type": "park",
            "confidence": 0.90,
        },
    ]

    async def search_places(
        self,
        query: str,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        radius_meters: Optional[int] = None,
        limit: int = 5,
        offset: int = 0,
    ) -> ProviderResult:
        """검색어 포함 고정 장소 반환 (대소문자 구분 없는 부분 일치)."""
        q = query.lower()
        results: List[PlaceResult] = []
        for p in self._MOCK_PLACES:
            if q in p["name"].lower() or q in p["address"].lower():
                if len(results) >= limit:
                    break
                results.append(PlaceResult(**p))
        return ProviderResult(
            ok=True,
            data=results,
        )

    async def health(self) -> bool:
        return True


# ─────────────────────────────────────────────
# MockRoutingProvider
# ─────────────────────────────────────────────
class MockRoutingProvider(RoutingProvider):
    """고정 이동 옵션을 반환하는 Mock RoutingProvider."""

    async def search_options(
        self,
        origin_place_id: str,
        destination_place_id: str,
        departure_at: Optional[str] = None,
        arrival_deadline: Optional[str] = None,
        transport_mode: Optional[str] = None,
        max_options: int = 5,
    ) -> ProviderResult:
        """고정 이동 옵션 2~3개 반환 (subway + walking + bus)."""

        options: List[dict] = [
            {
                "option_id": f"opt_{origin_place_id}_{destination_place_id}_subway_1",
                "leg_index": 0,
                "departure_at": departure_at or "2026-09-16T09:00:00+09:00",
                "arrival_at": "2026-09-16T09:42:00+09:00",
                "total_duration_minutes": 42,
                "legs": [
                    {
                        "mode": "subway",
                        "departure_at": "2026-09-16T09:00:00+09:00",
                        "arrival_at": "2026-09-16T09:20:00+09:00",
                        "origin_place_id": origin_place_id,
                        "destination_place_id": "place_transfer",
                        "route_id": "line_2",
                        "leg_index": 0,
                        "duration_minutes": 20,
                    },
                    {
                        "mode": "subway",
                        "departure_at": "2026-09-16T09:22:00+09:00",
                        "arrival_at": "2026-09-16T09:42:00+09:00",
                        "origin_place_id": "place_transfer",
                        "destination_place_id": destination_place_id,
                        "route_id": "line_2",
                        "leg_index": 1,
                        "duration_minutes": 20,
                    },
                ],
                "price": 1250,
                "distance_meters": 12000,
                "mode": "subway",
            },
            {
                "option_id": f"opt_{origin_place_id}_{destination_place_id}_walking_1",
                "leg_index": 0,
                "departure_at": departure_at or "2026-09-16T09:00:00+09:00",
                "arrival_at": "2026-09-16T10:30:00+09:00",
                "total_duration_minutes": 90,
                "legs": [
                    {
                        "mode": "walking",
                        "departure_at": "2026-09-16T09:00:00+09:00",
                        "arrival_at": "2026-09-16T10:30:00+09:00",
                        "origin_place_id": origin_place_id,
                        "destination_place_id": destination_place_id,
                        "leg_index": 0,
                        "duration_minutes": 90,
                    }
                ],
                "price": 0,
                "distance_meters": 3500,
                "mode": "walking",
            },
        ]

        # transport_mode 필터 적용
        if transport_mode:
            options = [o for o in options if o.get("mode") == transport_mode]

        # max_options 제한
        options = options[:max(max_options, 1)]

        return ProviderResult(ok=True, data=options)

    async def health(self) -> bool:
        return True


# ─────────────────────────────────────────────
# MockTransitProvider
# ─────────────────────────────────────────────
class MockTransitProvider(TransitProvider):
    """고정 대중교통 상세 정보를 반환하는 Mock TransitProvider."""

    async def get_transit_details(
        self,
        option_id: str,
        departure_at: Optional[str] = None,
    ) -> ProviderResult:
        """옵션 ID 기반 고정 상세 반환."""
        details = {
            "option_id": option_id,
            "departure_at": departure_at or "2026-09-16T09:00:00+09:00",
            "arrival_at": "2026-09-16T09:42:00+09:00",
            "transfers": 1,
            "total_duration_minutes": 42,
            "instructions": [
                "서울역에서 2호선 탑승",
                "환승역에서 2호선 환승",
                "강남역에서 하차 후 도보 3분",
            ],
            "crowding_level": "보통",
        }
        return ProviderResult(ok=True, data=details)

    async def health(self) -> bool:
        return True


# ─────────────────────────────────────────────
# MockModelProvider
# ─────────────────────────────────────────────
class MockModelProvider(ModelProvider):
    """고정 해석을 반환하는 Mock ModelProvider.

    자연어 해석 결과를 하드코딩하여 반환한다.
    실제 AI 연동 전까지 해석 파이프라인을 Mock으로 대체한다.
    """

    async def interpret(
        self,
        user_text: str,
        context: Optional[dict] = None,
    ) -> ProviderResult:
        """간단한 키워드 기반 Mock 해석."""
        text_lower = user_text.lower()

        result: dict = {
            "intent": "unknown",
            "origin_place_id": None,
            "destination_place_id": None,
            "departure_time": None,
            "arrival_deadline": None,
            "transport_mode": None,
            "needs_confirmation": False,
            "raw_text": user_text,
            "interpretation_note": "Mock 제공자 응답 (실제 AI 연동 전)",
        }

        # 간단한 키워드 매핑 (Mock)
        if "서울역" in user_text:
            result["origin_place_id"] = "place_seoul_station"
        if "강남" in user_text:
            result["destination_place_id"] = "place_gangnam_station"
        if "종로" in user_text:
            result["destination_place_id"] = "place_jongro3ga_station"

        if "출발" in user_text or "depart" in text_lower:
            result["departure_time"] = "2026-09-16T09:00:00+09:00"
        if "도착" in user_text or "도착" in text_lower:
            result["arrival_deadline"] = "2026-09-16T10:00:00+09:00"
        # "오후 X시" 패턴 인식 (MockModelProvider 개선)
        import re
        time_match = re.search(r'오후\s*(\d{1,2})\s*시', user_text)
        if time_match:
            hour = int(time_match.group(1))
            if hour < 12:
                hour += 12
            from datetime import datetime, timedelta, timezone
            from zoneinfo import ZoneInfo
            seoul = ZoneInfo("Asia/Seoul")
            now = datetime.now(seoul)
            deadline = now.replace(hour=hour, minute=0, second=0, microsecond=0)
            if deadline < now:
                deadline += timedelta(days=1)
            result["arrival_deadline"] = deadline.isoformat()

        if "지하철" in user_text or "subway" in text_lower:
            result["transport_mode"] = "subway"

        if result["origin_place_id"] or result["destination_place_id"]:
            result["intent"] = "plan_trip"
            if not result["origin_place_id"] or not result["destination_place_id"]:
                result["needs_confirmation"] = True

        return ProviderResult(ok=True, data=result)

    async def health(self) -> bool:
        return True
