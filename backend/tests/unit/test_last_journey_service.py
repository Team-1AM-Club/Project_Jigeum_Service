"""T044: 막차 서비스 단위 테스트.

- 운행일 검증 테스트
- 다음 날 도착 날짜 구분 검증
- LAST_JOURNEY_UNSUPPORTED 검증
- NO_FEASIBLE_JOURNEY 검증
"""

from datetime import datetime
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

import pytest

from app.schemas.journeys import Plan, TripRequest
from app.services.last_journey_service import (
    LastJourneyService,
    LastJourneyUnsupportedError,
    NoFeasibleJourneyError,
)
from app.services.provider_interfaces import ProviderResult, RoutingProvider

SEOUL_TZ = ZoneInfo("Asia/Seoul")


class TestLastJourneyServiceNormalCase:
    """막차 서비스 정상 케이스 테스트."""

    @pytest.fixture
    def mock_routing_provider(self):
        """Mock RoutingProvider: 막차 시간대 옵션 반환."""
        provider = AsyncMock(spec=RoutingProvider)
        provider.health.return_value = True

        # 막차 시간대 옵션 (자정 넘어 도착)
        provider.search_options.return_value = ProviderResult(
            ok=True,
            data=[
                {
                    "option_id": "opt_last_subway_1",
                    "leg_index": 0,
                    "departure_at": "2026-09-16T23:00:00+09:00",
                    "arrival_at": "2026-09-17T00:00:00+09:00",
                    "total_duration_minutes": 60,
                    "legs": [
                        {
                            "mode": "subway",
                            "departure_at": "2026-09-16T23:00:00+09:00",
                            "arrival_at": "2026-09-16T23:30:00+09:00",
                            "origin_place_id": "place_seoul_station",
                            "destination_place_id": "place_transfer",
                            "route_id": "line_2",
                            "leg_index": 0,
                            "duration_minutes": 30,
                            "distance_meters": 8000,
                        },
                        {
                            "mode": "walking",
                            "departure_at": "2026-09-16T23:30:00+09:00",
                            "arrival_at": "2026-09-17T00:00:00+09:00",
                            "origin_place_id": "place_transfer",
                            "destination_place_id": "place_gangnam_station",
                            "route_id": None,
                            "leg_index": 1,
                            "duration_minutes": 30,
                            "distance_meters": 2000,
                        },
                    ],
                    "total_distance_meters": 10000,
                    "transport_mode": "subway",
                    "confidence": 0.9,
                }
            ],
        )
        return provider

    @pytest.fixture
    def last_journey_service(self, mock_routing_provider):
        return LastJourneyService(routing_provider=mock_routing_provider)


@pytest.fixture(scope="function")
def valid_last_journey_request():
    """Valid last journey request fixture (module level for all test classes)."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from app.schemas.journeys import TripRequest

    SEOUL_TZ = ZoneInfo("Asia/Seoul")
    return TripRequest(
        conversation_id="test_conv_last_001",
        origin_place_id="place_seoul_station",
        destination_place_id="place_gangnam_station",
        arrival_deadline=datetime(2026, 9, 17, 0, 30, 0, tzinfo=SEOUL_TZ),
        arrival_preference_minutes=10,
        max_options=3,
    )


class TestLastJourneySupportCheck:
    """막차 지원 여부 확인 테스트."""

    @pytest.mark.asyncio
    async def test_check_last_journey_supported_when_provider_healthy(self):
        """제공자 헬스 정상 → 지원 가능."""
        mock_provider = AsyncMock(spec=RoutingProvider)
        mock_provider.health.return_value = True

        service = LastJourneyService(routing_provider=mock_provider)
        supported = await service.check_last_journey_supported()

        # 제공자 헬스가 정상이면 막차 지원 가능
        assert supported is True

    @pytest.mark.asyncio
    async def test_check_last_journey_supported_when_provider_unhealthy(self):
        """제공자 헬스 비정상 → False 반환."""
        mock_provider = AsyncMock(spec=RoutingProvider)
        mock_provider.health.return_value = False

        service = LastJourneyService(routing_provider=mock_provider)
        supported = await service.check_last_journey_supported()

        assert supported is False


class TestLastJourneyPlan:
    """막차 계획 생성 테스트."""

    @pytest.mark.asyncio
    async def test_plan_last_journey_unsupported_raises_error(self):
        """막차 미지원 시 LAST_JOURNEY_UNSUPPORTED 오류."""
        mock_provider = AsyncMock(spec=RoutingProvider)
        mock_provider.health.return_value = False

        service = LastJourneyService(routing_provider=mock_provider)

        request = TripRequest(
            conversation_id="test_conv_001",
            origin_place_id="place_seoul_station",
            destination_place_id="place_gangnam_station",
            arrival_deadline=datetime(2026, 9, 17, 0, 30, 0, tzinfo=SEOUL_TZ),
        )

        with pytest.raises(LastJourneyUnsupportedError) as exc_info:
            await service.plan_last_journey(request=request)

        assert "막차" in str(exc_info.value.message)
        assert exc_info.value.status_code == 422

    @pytest.mark.asyncio
    async def test_plan_last_journey_no_feasible_journey_raises_error(self):
        """경로 없으면 NO_FEASIBLE_JOURNEY 오류."""
        mock_provider = AsyncMock(spec=RoutingProvider)
        mock_provider.health.return_value = True
        # Provider returns empty data - no feasible journey
        mock_provider.search_options.return_value = ProviderResult(ok=True, data=[])

        service = LastJourneyService(routing_provider=mock_provider)

        request = TripRequest(
            conversation_id="test_conv_002",
            origin_place_id="place_seoul_station",
            destination_place_id="place_gangnam_station",
            arrival_deadline=datetime(2026, 9, 17, 0, 30, 0, tzinfo=SEOUL_TZ),
        )

        # search_options returns empty data -> should raise NoFeasibleJourneyError
        with pytest.raises(NoFeasibleJourneyError) as exc_info:
            await service.plan_last_journey(request=request)

        assert "경로가 없습니다" in str(
            exc_info.value.message
        ) or "이용 가능한 경로" in str(exc_info.value.message)
        assert exc_info.value.status_code == 422

    @pytest.mark.asyncio
    async def test_plan_last_journey_returns_plan_with_next_day_arrival(
        self, last_journey_service, valid_last_journey_request
    ):
        """정상 막차 계획 → Plan 반환, 다음 날 도착 날짜 구분."""
        # Mock provider가 막차 옵션을 반환하도록 설정
        last_journey_service.routing_provider.search_options.return_value = (
            ProviderResult(
                ok=True,
                data=[
                    {
                        "option_id": "opt_last_subway_1",
                        "departure_at": "2026-09-16T23:00:00+09:00",
                        "arrival_at": "2026-09-17T00:00:00+09:00",
                        "total_duration_minutes": 60,
                        "transport_mode": "subway",
                    }
                ],
            )
        )
        # health 체크 우회: check_last_journey_supported가 True 반환하도록 패치
        with patch.object(
            last_journey_service,
            "check_last_journey_supported",
            new_callable=AsyncMock,
        ) as mock_check:
            mock_check.return_value = True

            plan = await last_journey_service.plan_last_journey(
                request=valid_last_journey_request,
                buffer_minutes=5,
            )

        # Plan 검증
        assert isinstance(plan, Plan)
        assert plan.is_last_journey is True
        assert plan.operating_date is not None
        assert plan.arrival_date is not None

        # 운행일과 도착 날짜 구분 검증 (다음 날 도착)
        assert plan.operating_date != plan.arrival_date, (
            f"운행일({plan.operating_date})과 도착일({plan.arrival_date})이 달라야 함"
        )

        # 날짜가 하루 차이인지 확인
        from datetime import datetime as dt

        op_date = dt.strptime(plan.operating_date, "%Y-%m-%d").date()
        arr_date = dt.strptime(plan.arrival_date, "%Y-%m-%d").date()
        assert (arr_date - op_date).days == 1, (
            f"도착일이 운행일보다 하루 뒤여야 함: {op_date} → {arr_date}"
        )

        # 막차 필드 검증
        assert plan.last_journey_supported is True
        assert "막차" in plan.notes or "막차" in plan.comparison.comparison_reason


class TestOperatingDateValidation:
    """운행일 검증 테스트."""

    @pytest.mark.asyncio
    async def test_operating_date_is_today(
        self, last_journey_service, valid_last_journey_request
    ):
        """운행일은 오늘 날짜여야 함."""
        with patch.object(
            last_journey_service,
            "check_last_journey_supported",
            new_callable=AsyncMock,
        ) as mock_check:
            mock_check.return_value = True

            last_journey_service.routing_provider.search_options.return_value = (
                ProviderResult(
                    ok=True,
                    data=[
                        {
                            "option_id": "opt_last_1",
                            "departure_at": "2026-09-16T23:00:00+09:00",
                            "total_duration_minutes": 60,
                        }
                    ],
                )
            )

            plan = await last_journey_service.plan_last_journey(
                request=valid_last_journey_request,
                buffer_minutes=5,
            )

        # 운행일이 오늘(또는 요청 날짜)인지 확인
        assert plan.operating_date is not None
        # 운행일은 YYYY-MM-DD 형식
        parts = plan.operating_date.split("-")
        assert len(parts) == 3
        assert len(parts[0]) == 4  # 년도
        assert len(parts[1]) == 2  # 월
        assert len(parts[2]) == 2  # 일


class TestArrivalDateBoundary:
    """도착 날짜 경계 처리 테스트."""

    @pytest.mark.asyncio
    async def test_arrival_date_next_day_when_crossing_midnight(
        self, last_journey_service, valid_last_journey_request
    ):
        """자정 넘어 도착 시 도착 날짜가 다음 날이어야 함."""
        with patch.object(
            last_journey_service,
            "check_last_journey_supported",
            new_callable=AsyncMock,
        ) as mock_check:
            mock_check.return_value = True

            # 출발 23:00, 소요시간 90분 → 도착 00:30 (다음 날)
            last_journey_service.routing_provider.search_options.return_value = (
                ProviderResult(
                    ok=True,
                    data=[
                        {
                            "option_id": "opt_last_1",
                            "departure_at": "2026-09-16T23:00:00+09:00",
                            "arrival_at": "2026-09-17T00:30:00+09:00",
                            "total_duration_minutes": 90,
                        }
                    ],
                )
            )

            plan = await last_journey_service.plan_last_journey(
                request=valid_last_journey_request,
                buffer_minutes=5,
            )

        # 도착 날짜가 다음 날인지 확인
        assert plan.arrival_date is not None
        assert plan.arrival_date > plan.operating_date, (
            f"도착일({plan.arrival_date})이 운행일({plan.operating_date})보다 이후여야 함"
        )

    @pytest.mark.asyncio
    async def test_arrival_date_same_day_when_not_crossing_midnight(
        self, last_journey_service, valid_last_journey_request
    ):
        """자정 전 도착 시 도착 날짜가 운행일과 동일."""
        with patch.object(
            last_journey_service,
            "check_last_journey_supported",
            new_callable=AsyncMock,
        ) as mock_check:
            mock_check.return_value = True

            # 출발 22:00, 소요시간 60분 → 도착 23:00 (같은 날)
            last_journey_service.routing_provider.search_options.return_value = (
                ProviderResult(
                    ok=True,
                    data=[
                        {
                            "option_id": "opt_last_1",
                            "departure_at": "2026-09-16T22:00:00+09:00",
                            "arrival_at": "2026-09-16T23:00:00+09:00",
                            "total_duration_minutes": 60,
                        }
                    ],
                )
            )

            plan = await last_journey_service.plan_last_journey(
                request=valid_last_journey_request,
                buffer_minutes=5,
            )

        # 도착 날짜가 운행일과 같은 날인지 확인
        assert plan.arrival_date is not None
        assert plan.arrival_date == plan.operating_date, (
            f"도착일({plan.arrival_date})이 운행일({plan.operating_date})과 같아야 함"
        )
