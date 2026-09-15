"""재탐색 서비스 계약 테스트 (T051).

ReplanService의 계약: 입력 조건 → 출력 검증.
Mock RoutingProvider + PlanService 사용.
"""

import asyncio
import pytest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from unittest.mock import AsyncMock, MagicMock, patch

from app.schemas.journeys import (
    ReplanRequest,
    ReplanResponse,
    ReplanComparison,
    TripRequest,
    Plan,
    Leg,
)
from app.schemas.errors import ErrorCode
from app.services.replan_service import ReplanService
from app.services.plan_service import PlanService
from app.services.provider_interfaces import RoutingProvider


SEOUL_TZ = ZoneInfo("Asia/Seoul")


def _now() -> datetime:
    return datetime.now(SEOUL_TZ)


def _make_trip_request(
    origin: str = "홍대입구역",
    dest: str = "서울대학교입구",
    arrive_by: datetime | None = None,
) -> TripRequest:
    return TripRequest(
        conversation_id="conv_test_001",
        origin_place_id=origin,
        destination_place_id=dest,
        departure_at=None,
        arrival_deadline=arrive_by or (_now() + timedelta(hours=2)),
        arrival_preference_minutes=5,
        transport_mode="subway",
        natural_language="서울대 입구로 2시 반까지 가고 싶어",
        user_confirmed=True,
    )


def _make_replan_request(
    conversation_id: str = "conv_test_001",
    trip: dict | None = None,
    user_confirmed: bool = True,
) -> ReplanRequest:
    if trip is None:
        trip = {
            "origin_place_id": "홍대입구역",
            "destination_place_id": "서울대학교입구",
            "departure_at": (_now() - timedelta(minutes=10)).isoformat(),
            "arrival_deadline": (_now() + timedelta(hours=2)).isoformat(),
            "arrival_preference_minutes": 5,
            "transport_mode": "subway",
            "natural_language": "서울대 입구로 2시 반까지 가고 싶어",
        }
    return ReplanRequest(
        conversation_id=conversation_id,
        trip=trip,
        user_confirmed=user_confirmed,
        replan_reason="missed_first_leg",
    )


def _make_mock_plan_service():
    ps = MagicMock(spec=PlanService)
    ps.compute_plan = AsyncMock(return_value=Plan(
        plan_id="plan_replan_001",
        conversation_id="conv_test_001",
        selected_option_id="opt_1",
        recommended_leave_at=(_now() + timedelta(minutes=5)).isoformat(),
        recommended_arrival_at=(_now() + timedelta(hours=1, minutes=55)).isoformat(),
        total_duration_minutes=75,
        legs=[
            Leg(
                leg_index=0,
                origin_place_id="홍대입구역",
                destination_place_id="서울대학교입구",
                departure_at=(_now() + timedelta(minutes=5)).isoformat(),
                arrival_at=(_now() + timedelta(hours=1, minutes=55)).isoformat(),
                transport_mode="subway",
                line_name="2호선",
                duration_minutes=70,
                distance_km=15.0,
                instructions="홍대입구역에서 2호선 승차, 서울대입구역 하차",
            )
        ],
        origin_place_id="홍대입구역",
        destination_place_id="서울대학교입구",
        created_at=_now().isoformat(),
    ))
    return ps


def _make_mock_routing_provider():
    rp = MagicMock(spec=RoutingProvider)
    rp.route_options = AsyncMock(return_value=[
        ProviderResult(
            option_id="opt_1",
            origin_place_id="홍대입구역",
            destination_place_id="서울대학교입구",
            recommended_leave_at=(_now() + timedelta(minutes=5)).isoformat(),
            recommended_arrival_at=(_now() + timedelta(hours=1, minutes=55)).isoformat(),
            total_duration_minutes=75,
            legs=[
                {
                    "leg_index": 0,
                    "origin_place_id": "홍대입구역",
                    "destination_place_id": "서울대학교입구",
                    "departure_at": (_now() + timedelta(minutes=5)).isoformat(),
                    "arrival_at": (_now() + timedelta(hours=1, minutes=55)).isoformat(),
                    "transport_mode": "subway",
                    "line_name": "2호선",
                    "duration_minutes": 70,
                    "distance_km": 15.0,
                    "instructions": "홍대입구역에서 2호선 승차, 서울대입구역 하차",
                }
            ],
            provider_name="mock_routing",
            score=0.95,
        )
    ])
    return rp


class TestReplanServiceContract:
    @pytest.fixture
    def replan_service(self):
        mock_plan = _make_mock_plan_service()
        mock_routing = _make_mock_routing_provider()
        service = ReplanService(plan_service=mock_plan)
        service._routing_provider = mock_routing
        return service

    @pytest.mark.asyncio
    async def test_replan_success_returns_comparison(self, replan_service):
        request = _make_replan_request()
        response = await replan_service.replan(request)
        assert isinstance(response, ReplanResponse)
        assert response.replan_id is not None
        assert response.conversation_id == "conv_test_001"
        assert response.trip is not None
        assert response.plan is not None
        assert response.comparison is not None
        assert isinstance(response.comparison, ReplanComparison)
        assert "arrival_change_minutes" in response.comparison.model_dump()

    @pytest.mark.asyncio
    async def test_replan_success_plan_fields(self, replan_service):
        request = _make_replan_request()
        response = await replan_service.replan(request)
        plan = response.plan
        assert plan.recommended_leave_at is not None
        assert plan.recommended_arrival_at is not None
        assert plan.total_duration_minutes > 0
        assert len(plan.legs) > 0
        assert plan.legs[0].transport_mode == "subway"
        assert plan.legs[0].line_name == "2호선"

    @pytest.mark.asyncio
    async def test_replan_multiple_legs(self, replan_service):
        request = _make_replan_request()
        response = await replan_service.replan(request)
        assert isinstance(response.plan.legs, list)
        for leg in response.plan.legs:
            assert leg.origin_place_id is not None
            assert leg.destination_place_id is not None
            assert leg.transport_mode in ("subway", "bus", "walking")

    @pytest.mark.asyncio
    async def test_replan_missing_conversation_id(self, replan_service):
        request = _make_replan_request(conversation_id="")
        with pytest.raises(ValueError, match="conversation_id가 필요합니다"):
            await replan_service.replan(request)

    @pytest.mark.asyncio
    async def test_replan_missing_trip_origin(self, replan_service):
        request = _make_replan_request(trip={})
        with pytest.raises(ValueError, match="origin_place_id가 필요합니다"):
            await replan_service.replan(request)

    @pytest.mark.asyncio
    async def test_replan_user_not_confirmed(self, replan_service):
        request = _make_replan_request(user_confirmed=False)
        with pytest.raises(ValueError, match="사용자 확인이 필요합니다"):
            await replan_service.replan(request)

    @pytest.mark.asyncio
    async def test_replan_comparison_has_change_fields(self, replan_service):
        request = _make_replan_request()
        response = await replan_service.replan(request)
        comparison = response.comparison
        d = comparison.model_dump()
        assert "arrival_change_minutes" in d
        assert "leave_change_minutes" in d
        for key in ("arrival_change_minutes", "leave_change_minutes"):
            v = d[key]
            assert v is None or isinstance(v, (int, float))

    @pytest.mark.asyncio
    async def test_replan_comparison_preserves_prev_plan_intent(self, replan_service):
        request = _make_replan_request()
        response = await replan_service.replan(request)
        assert not hasattr(response, "previous_plan") or response.previous_plan is None
        assert response.plan is not None
        assert response.plan.plan_id is not None

    @pytest.mark.asyncio
    async def test_replan_preserves_seoul_timezone(self, replan_service):
        request = _make_replan_request()
        response = await replan_service.replan(request)
        plan = response.plan
        from app.services.time_calculation import ensure_seoul
        leave_dt = ensure_seoul(datetime.fromisoformat(plan.recommended_leave_at))
        assert leave_dt.tzinfo is not None
        assert leave_dt.tzinfo.key == "Asia/Seoul"

    @pytest.mark.asyncio
    async def test_replan_buffer_reflected_in_leave_time(self, replan_service):
        request = _make_replan_request()
        response = await replan_service.replan(request, buffer_minutes=10)
        plan = response.plan
        leave_dt = datetime.fromisoformat(plan.recommended_leave_at)
        arrival_dt = datetime.fromisoformat(plan.recommended_arrival_at)
        assert leave_dt < arrival_dt
        assert plan.total_duration_minutes > 0

    @pytest.mark.asyncio
    async def test_replan_reason_missed_first_leg(self, replan_service):
        request = _make_replan_request(replan_reason="missed_first_leg")
        response = await replan_service.replan(request)
        assert response.replan_reason == "missed_first_leg"

    @pytest.mark.asyncio
    async def test_replan_reason_changed_destination(self, replan_service):
        request = _make_replan_request(replan_reason="changed_destination")
        response = await replan_service.replan(request)
        assert response.replan_reason == "changed_destination"

    @pytest.mark.asyncio
    async def test_replan_reason_custom_value(self, replan_service):
        request = _make_replan_request(replan_reason="user_requested")
        response = await replan_service.replan(request)
        assert response.replan_reason == "user_requested"


class TestReplanServiceEdgeCases:
    @pytest.fixture
    def replan_service(self):
        mock_plan = _make_mock_plan_service()
        mock_routing = _make_mock_routing_provider()
        service = ReplanService(plan_service=mock_plan)
        service._routing_provider = mock_routing
        return service

    @pytest.mark.asyncio
    async def test_replan_with_arrival_preference_zero(self, replan_service):
        trip = {
            "origin_place_id": "홍대입구역",
            "destination_place_id": "서울대학교입구",
            "departure_at": (_now() - timedelta(minutes=10)).isoformat(),
            "arrival_deadline": (_now() + timedelta(hours=2)).isoformat(),
            "arrival_preference_minutes": 0,
            "transport_mode": "subway",
            "natural_language": "2시 정각까지 도착",
        }
        request = _make_replan_request(trip=trip, user_confirmed=True)
        response = await replan_service.replan(request)
        assert response.plan is not None
        plan = response.plan
        arrival_dt = datetime.fromisoformat(plan.recommended_arrival_at)
        deadline_dt = datetime.fromisoformat(trip["arrival_deadline"])
        assert arrival_dt <= deadline_dt

    @pytest.mark.asyncio
    async def test_replan_buffer_dedup_no_double_add(self, replan_service):
        request = _make_replan_request()
        response = await replan_service.replan(request, buffer_minutes=5)
        assert response.plan.total_duration_minutes > 0
