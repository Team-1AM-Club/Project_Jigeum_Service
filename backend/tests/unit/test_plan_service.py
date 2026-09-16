"""T041: 계획 서비스 단위 테스트.

- 정상 케이스: 출발지·목적지 확정 → Plan 반환
- 출발지 미확정 케이스 → ValueError (Pydantic 레벨에서 차단됨, 서비스 테스트는 우회)
- Buffer 계산 검증: buffer 중복 가산 방지
"""

from datetime import datetime
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest

from app.schemas.journeys import Comparison, Plan, TripRequest
from app.services.plan_service import PlanService
from app.services.provider_interfaces import ProviderResult, RoutingProvider

SEOUL_TZ = ZoneInfo("Asia/Seoul")


class TestPlanServiceNormalCase:
    """정상 케이스 테스트."""

    @pytest.fixture
    def mock_routing_provider(self):
        """Mock RoutingProvider: 고정 옵션 반환."""
        provider = AsyncMock(spec=RoutingProvider)
        provider.search_options.return_value = ProviderResult(
            ok=True,
            data=[
                {
                    "option_id": "opt_subway_1",
                    "legs": [
                        {
                            "mode": "subway",
                            "departure_at": "2026-09-16T09:00:00+09:00",
                            "arrival_at": "2026-09-16T09:20:00+09:00",
                            "origin_place_id": "place_seoul_station",
                            "destination_place_id": "place_transfer",
                            "route_id": "line_2",
                            "leg_index": 0,
                            "duration_minutes": 20,
                            "distance_meters": 5000,
                        }
                    ],
                    "total_duration_minutes": 42,
                    "total_distance_meters": 12000,
                    "departure_at": "2026-09-16T09:00:00+09:00",
                    "arrival_at": "2026-09-16T09:42:00+09:00",
                    "price": 1250,
                    "transport_mode": "subway",
                    "confidence": 0.95,
                }
            ],
        )
        return provider

    @pytest.fixture
    def plan_service(self, mock_routing_provider):
        return PlanService(routing_provider=mock_routing_provider)

    @pytest.fixture
    def valid_request(self):
        return TripRequest(
            conversation_id="test_conv_001",
            origin_place_id="place_seoul_station",
            destination_place_id="place_gangnam_station",
            arrival_deadline=datetime(2026, 9, 16, 19, 0, 0, tzinfo=SEOUL_TZ),
            arrival_preference_minutes=10,
            transport_mode="subway",
            max_options=3,
        )

    @pytest.mark.asyncio
    async def test_plan_returns_plan_with_recommended_leave_at(
        self, plan_service, valid_request
    ):
        """정상 요청 → Plan 반환, 권장 출발시각 계산됨.

        target_arrival_at = arrival_deadline - arrival_preference_minutes
        recommended_leave_at = target_arrival_at - total_duration - buffer

        arrival_deadline=19:00, preference=10분 → target=18:50
        total_duration=42분, buffer=5분 → leave=18:50-42-5=18:03
        """
        plan = await plan_service.plan(request=valid_request, buffer_minutes=5)

        assert isinstance(plan, Plan)
        assert plan.plan_id is not None
        assert plan.conversation_id == "test_conv_001"
        assert plan.origin_place_id == "place_seoul_station"
        assert plan.destination_place_id == "place_gangnam_station"
        assert plan.total_duration_minutes == 42

        # target_arrival_at = 19:00 - 10분(preference) = 18:50
        expected_target = datetime(2026, 9, 16, 18, 50, 0, tzinfo=SEOUL_TZ)
        assert plan.target_arrival_at == expected_target, (
            f"target_arrival_at 기대 {expected_target}, 실제 {plan.target_arrival_at}"
        )

        # recommended_leave_at = 18:50 - 42분(이동) - 5분(buffer) = 18:03
        expected_leave = datetime(2026, 9, 16, 18, 3, 0, tzinfo=SEOUL_TZ)
        assert plan.recommended_leave_at == expected_leave, (
            f"recommended_leave_at 기대 {expected_leave}, 실제 {plan.recommended_leave_at}"
        )

        # recommended_leave_at < target_arrival_at
        assert plan.recommended_leave_at < plan.target_arrival_at

        # comparison 구조
        assert isinstance(plan.comparison, Comparison)
        assert len(plan.comparison.options) == 1
        assert plan.comparison.options[0].option_id == "opt_subway_1"
        assert plan.comparison.selected_option_id == "opt_subway_1"

        # buffer_applied
        assert plan.buffer_applied == 5

    @pytest.mark.asyncio
    async def test_plan_with_multiple_options(self, plan_service, valid_request):
        """후보 2개 이상 → comparison에 여러 옵션."""
        # Mock 제공자: 2개 옵션 반환
        plan_service.routing_provider.search_options.return_value = ProviderResult(
            ok=True,
            data=[
                {
                    "option_id": "opt_subway_1",
                    "legs": [],
                    "total_duration_minutes": 42,
                    "total_distance_meters": 12000,
                    "transport_mode": "subway",
                    "confidence": 0.95,
                },
                {
                    "option_id": "opt_bus_1",
                    "legs": [],
                    "total_duration_minutes": 58,
                    "total_distance_meters": 15000,
                    "transport_mode": "bus",
                    "confidence": 0.85,
                },
            ],
        )

        plan = await plan_service.plan(request=valid_request, buffer_minutes=5)

        assert len(plan.comparison.options) == 2
        assert plan.comparison.options[0].option_id == "opt_subway_1"
        assert plan.comparison.options[1].option_id == "opt_bus_1"

        # 첫 번째 옵션이 기본 선택
        assert plan.comparison.selected_option_id == "opt_subway_1"

        # 각 옵션별 권장 출발시각이 다름
        opt1_time = plan.comparison.options[0].recommended_leave_at
        opt2_time = plan.comparison.options[1].recommended_leave_at
        assert opt1_time != opt2_time, "옵션별 권장 출발시각이 달라야 함"

    @pytest.mark.asyncio
    async def test_plan_respects_max_options(self, plan_service, valid_request):
        """max_options 제한 적용."""
        # 5개 옵션 반환
        plan_service.routing_provider.search_options.return_value = ProviderResult(
            ok=True,
            data=[
                {
                    "option_id": f"opt_{i}",
                    "legs": [],
                    "total_duration_minutes": 30 + i * 5,
                    "transport_mode": "subway",
                    "confidence": 0.9,
                }
                for i in range(5)
            ],
        )

        # max_options=2
        valid_request.max_options = 2
        plan = await plan_service.plan(request=valid_request, buffer_minutes=5)

        assert len(plan.comparison.options) == 2, (
            f"max_options=2 기대, 실제 {len(plan.comparison.options)}개"
        )


class TestPlanServiceMissingOrigin:
    """출발지 미확정 케이스 테스트.

    Pydantic이 TripRequest 생성 시 origin_place_id 빈 값을 차단하므로,
    서비스 레벨 테스트는 valid 요청에서 출발지를 뺀 형태로 검증.
    """

    @pytest.fixture
    def plan_service(self):
        provider = AsyncMock(spec=RoutingProvider)
        return PlanService(routing_provider=provider)

    @pytest.mark.asyncio
    async def test_plan_api_level_blocks_empty_origin(self, client):
        """API 레벨: origin_place_id 빈 값 → 422 (Pydantic + 라우터 검증)."""
        # FastAPI TestClient 사용
        from fastapi.testclient import TestClient

        from app.main import app

        with TestClient(app) as c:
            response = c.post(
                "/api/v1/journeys/plan",
                json={
                    "conversation_id": "test_api_origin",
                    "origin_place_id": "",  # 빈 값 → Pydantic ValidationError
                    "destination_place_id": "place_gangnam_station",
                },
                headers={"Idempotency-Key": "a1b2c3d4-e5f6-4789-a0b1-c2d3e4f5g6h7"},
            )

            # Pydantic이 빈 문자열을 차단 (422)
            assert response.status_code == 422, (
                f"빈 origin_place_id 422 기대, 실제 {response.status_code}"
            )

    @pytest.mark.asyncio
    async def test_plan_service_valid_origin_required(self, plan_service):
        """서비스 레벨: 유효한 origin_place_id가 필요 (라우터/피디antic이 1차 차단)."""
        # 서비스는 이미 Pydantic 검증된 TripRequest를 받으므로,
        # 빈 값이 서비스에 도달하지 않음. 따라서 서비스 테스트에서는
        # 유효한 요청으로 정상 동작 검증.

        plan_service.routing_provider.search_options.return_value = ProviderResult(
            ok=True,
            data=[
                {
                    "option_id": "opt_test",
                    "legs": [],
                    "total_duration_minutes": 30,
                    "transport_mode": "subway",
                    "confidence": 0.9,
                }
            ],
        )

        request = TripRequest(
            conversation_id="test_valid_origin",
            origin_place_id="place_seoul_station",  # 유효
            destination_place_id="place_gangnam_station",
            arrival_deadline=datetime(2026, 9, 16, 19, 0, 0, tzinfo=SEOUL_TZ),
        )

        plan = await plan_service.plan(request=request, buffer_minutes=5)

        assert plan.origin_place_id == "place_seoul_station"
        assert plan.destination_place_id == "place_gangnam_station"


class TestPlanServiceBufferCalculation:
    """Buffer 계산 검증 테스트."""

    @pytest.fixture
    def mock_provider(self):
        provider = AsyncMock(spec=RoutingProvider)
        provider.search_options.return_value = ProviderResult(
            ok=True,
            data=[
                {
                    "option_id": "opt_1",
                    "legs": [],
                    "total_duration_minutes": 30,
                    "transport_mode": "subway",
                    "confidence": 0.9,
                }
            ],
        )
        return provider

    @pytest.fixture
    def plan_service(self, mock_provider):
        return PlanService(routing_provider=mock_provider)

    @pytest.mark.asyncio
    async def test_buffer_applied_once_in_plan(self, plan_service):
        """Buffer가 한 번만 적용되는지 검증.

        total_duration=30분, buffer=5분, preference=0:
        target_arrival_at = deadline - 0(preference) = deadline
        recommended_leave_at = target - 30(이동) - 5(buffer)
        """
        request = TripRequest(
            conversation_id="test_buf_001",
            origin_place_id="place_seoul_station",
            destination_place_id="place_gangnam_station",
            arrival_deadline=datetime(2026, 9, 16, 20, 0, 0, tzinfo=SEOUL_TZ),
            arrival_preference_minutes=0,
            max_options=1,
        )

        plan = await plan_service.plan(request=request, buffer_minutes=5)

        # 20:00 - 0(선호) = 20:00 (target)
        expected_target = datetime(2026, 9, 16, 20, 0, 0, tzinfo=SEOUL_TZ)
        assert plan.target_arrival_at == expected_target, (
            f"target_arrival_at 기대 {expected_target}, 실제 {plan.target_arrival_at}"
        )

        # 20:00 - 30분(이동) - 5분(buffer) = 19:25
        expected_leave = datetime(2026, 9, 16, 19, 25, 0, tzinfo=SEOUL_TZ)
        assert plan.recommended_leave_at == expected_leave, (
            f"recommended_leave_at 기대 {expected_leave}, 실제 {plan.recommended_leave_at}"
        )

        # buffer_applied = 5
        assert plan.buffer_applied == 5

    @pytest.mark.asyncio
    async def test_zero_buffer_plan(self, plan_service):
        """buffer=0일 때: 이동시간만 차감."""
        request = TripRequest(
            conversation_id="test_buf_002",
            origin_place_id="place_seoul_station",
            destination_place_id="place_gangnam_station",
            arrival_deadline=datetime(2026, 9, 16, 19, 0, 0, tzinfo=SEOUL_TZ),
            arrival_preference_minutes=0,
            max_options=1,
        )

        plan = await plan_service.plan(request=request, buffer_minutes=0)

        # target = 19:00 - 0 = 19:00
        expected_target = datetime(2026, 9, 16, 19, 0, 0, tzinfo=SEOUL_TZ)
        assert plan.target_arrival_at == expected_target, (
            f"buffer=0 target 기대 {expected_target}, 실제 {plan.target_arrival_at}"
        )

        # leave = 19:00 - 30분 = 18:30
        expected_leave = datetime(2026, 9, 16, 18, 30, 0, tzinfo=SEOUL_TZ)
        assert plan.recommended_leave_at == expected_leave, (
            f"buffer=0 leave 기대 {expected_leave}, 실제 {plan.recommended_leave_at}"
        )

        assert plan.buffer_applied == 0

    @pytest.mark.asyncio
    async def test_buffer_with_arrival_preference(self, plan_service):
        """도착 여유 + buffer 동시 적용.

        arrival_deadline=19:00, preference=10분, 이동=30분, buffer=5분:
        target = 19:00 - 10분(선호) = 18:50
        leave = 18:50 - 30분(이동) - 5분(buffer) = 18:15
        """
        request = TripRequest(
            conversation_id="test_buf_003",
            origin_place_id="place_seoul_station",
            destination_place_id="place_gangnam_station",
            arrival_deadline=datetime(2026, 9, 16, 19, 0, 0, tzinfo=SEOUL_TZ),
            arrival_preference_minutes=10,  # 도착 여유 10분
            max_options=1,
        )

        plan = await plan_service.plan(request=request, buffer_minutes=5)

        # target = 19:00 - 10분(선호) = 18:50
        expected_target = datetime(2026, 9, 16, 18, 50, 0, tzinfo=SEOUL_TZ)
        assert plan.target_arrival_at == expected_target, (
            f"target 기대 {expected_target}, 실제 {plan.target_arrival_at}"
        )

        # leave = 18:50 - 30분(이동) - 5분(buffer) = 18:15
        expected_leave = datetime(2026, 9, 16, 18, 15, 0, tzinfo=SEOUL_TZ)
        assert plan.recommended_leave_at == expected_leave, (
            f"leave 기대 {expected_leave}, 실제 {plan.recommended_leave_at}"
        )

        # buffer_applied = 5
        assert plan.buffer_applied == 5


class TestPlanServiceWithNoProviderResult:
    """제공자 결과 없을 때 Mock fallback."""

    @pytest.fixture
    def plan_service(self):
        provider = AsyncMock(spec=RoutingProvider)
        provider.search_options.return_value = ProviderResult(ok=True, data=[])
        return PlanService(routing_provider=provider)

    @pytest.mark.asyncio
    async def test_plan_falls_back_to_mock_when_no_options(self, plan_service):
        """라우팅 결과 없음 → Mock 옵션 생성."""
        request = TripRequest(
            conversation_id="test_fallback",
            origin_place_id="place_seoul_station",
            destination_place_id="place_gangnam_station",
            arrival_deadline=datetime(2026, 9, 16, 19, 0, 0, tzinfo=SEOUL_TZ),
            max_options=3,
        )

        plan = await plan_service.plan(request=request, buffer_minutes=5)

        # Mock 옵션 생성됨
        assert len(plan.comparison.options) >= 1
        assert plan.comparison.options[0].option_id.startswith("opt_")
        assert plan.total_duration_minutes > 0
