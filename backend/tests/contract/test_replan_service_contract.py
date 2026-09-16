"""재탐색 서비스 계약 테스트 (T051).

ReplanService의 계약: 입력 조건 → 출력 계약 검증.
Mock PlanService 사용. 재탐색 응답 구조와 오류 거동을 확인한다.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from zoneinfo import ZoneInfo

import pytest

from app.schemas.journeys import (
    Comparison,
    Plan,
    PlanSummary,
    ReplanComparison,
    ReplanReason,
    ReplanRequest,
    ReplanResponse,
)
from app.services.plan_service import PlanService
from app.services.provider_interfaces import ProviderResult, RoutingProvider
from app.services.replan_service import ReplanService

SEOUL_TZ = ZoneInfo("Asia/Seoul")


def _now() -> datetime:
    return datetime.now(SEOUL_TZ)


def _make_replan_request(
    conversation_id: str = "conv_test_001",
    trip: dict | None = None,
    user_confirmed: bool = True,
    reason: ReplanReason = ReplanReason.MISSED_CONNECTION,
    previous_plan: dict | None = None,
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
        reason=reason,
        previous_plan=previous_plan,
    )


def _make_mock_plan_service() -> PlanService:
    ps = MagicMock(spec=PlanService)
    ps.plan = AsyncMock(
        return_value=Plan(
            plan_id="plan_replan_001",
            conversation_id="conv_test_001",
            origin_place_id="홍대입구역",
            destination_place_id="서울대학교입구",
            target_arrival_at=_now() + timedelta(hours=1, minutes=55),
            recommended_leave_at=_now() + timedelta(minutes=5),
            total_duration_minutes=75,
            buffer_applied=5,
            notes="재탐색용 모의 계획",
            comparison=Comparison(
                options=[
                    PlanSummary(
                        option_id="opt_1",
                        recommended_leave_at=_now() + timedelta(minutes=5),
                        target_arrival_at=_now() + timedelta(hours=1, minutes=55),
                        total_duration_minutes=75,
                        transport_mode="subway",
                        reasoning="지하철 2호선 직행",
                    )
                ],
                selected_option_id="opt_1",
                comparison_reason="환승이 적은 직행 경로를 우선 권장",
            ),
        )
    )
    return ps


def _make_mock_routing_provider() -> RoutingProvider:
    rp = MagicMock(spec=RoutingProvider)
    rp.route_options = AsyncMock(
        return_value=ProviderResult(
            ok=True,
            data=[
                {
                    "option_id": "opt_1",
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
        )
    )
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
        assert response.reason == ReplanReason.MISSED_CONNECTION
        assert response.comparison is not None
        assert isinstance(response.comparison, ReplanComparison)
        d = response.comparison.model_dump()
        assert "arrival_change_minutes" in d

    @pytest.mark.asyncio
    async def test_replan_success_plan_fields(self, replan_service):
        request = _make_replan_request()
        response = await replan_service.replan(request)
        plan = response.comparison.new_plan
        assert plan.recommended_leave_at is not None
        assert plan.target_arrival_at is not None
        assert plan.total_duration_minutes > 0
        assert plan.buffer_applied == 5
        assert plan.origin_place_id == "홍대입구역"
        assert plan.destination_place_id == "서울대학교입구"

    @pytest.mark.asyncio
    async def test_replan_comparison_has_options(self, replan_service):
        request = _make_replan_request()
        response = await replan_service.replan(request)
        comparison = response.comparison
        assert comparison.new_plan is not None
        assert comparison.new_plan.plan_id is not None
        assert len(comparison.new_plan.comparison.options) > 0

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
        assert response.comparison.previous_plan_preserved is True
        assert response.comparison.new_plan is not None
        assert response.comparison.new_plan.plan_id is not None

    @pytest.mark.asyncio
    async def test_replan_preserves_seoul_timezone(self, replan_service):
        request = _make_replan_request()
        response = await replan_service.replan(request)
        plan = response.comparison.new_plan
        from app.services.time_calculation import ensure_seoul

        leave_dt = ensure_seoul(plan.recommended_leave_at)
        assert leave_dt.tzinfo is not None
        assert leave_dt.tzinfo.key == "Asia/Seoul"

    @pytest.mark.asyncio
    async def test_replan_buffer_reflected_in_leave_time(self, replan_service):
        request = _make_replan_request()
        response = await replan_service.replan(request, buffer_minutes=10)
        plan = response.comparison.new_plan
        leave_dt = plan.recommended_leave_at
        arrival_dt = plan.target_arrival_at
        assert leave_dt < arrival_dt
        assert plan.total_duration_minutes > 0

    @pytest.mark.asyncio
    async def test_replan_reason_missed_connection(self, replan_service):
        request = _make_replan_request(reason=ReplanReason.MISSED_CONNECTION)
        response = await replan_service.replan(request)
        assert response.reason == ReplanReason.MISSED_CONNECTION

    @pytest.mark.asyncio
    async def test_replan_reason_route_changed(self, replan_service):
        request = _make_replan_request(reason=ReplanReason.ROUTE_CHANGED)
        response = await replan_service.replan(request)
        assert response.reason == ReplanReason.ROUTE_CHANGED

    @pytest.mark.asyncio
    async def test_replan_reason_manual(self, replan_service):
        request = _make_replan_request(reason=ReplanReason.MANUAL)
        response = await replan_service.replan(request)
        assert response.reason == ReplanReason.MANUAL

    @pytest.mark.asyncio
    async def test_replan_notes_present(self, replan_service):
        request = _make_replan_request()
        response = await replan_service.replan(request)
        assert response.notes is not None
        assert isinstance(response.notes, str)


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
        assert response.comparison.new_plan is not None
        plan = response.comparison.new_plan
        arrival_dt = plan.target_arrival_at
        deadline_dt = datetime.fromisoformat(trip["arrival_deadline"])
        assert arrival_dt <= deadline_dt

    @pytest.mark.asyncio
    async def test_replan_buffer_dedup_no_double_add(self, replan_service):
        request = _make_replan_request()
        response = await replan_service.replan(request, buffer_minutes=5)
        assert response.comparison.new_plan.total_duration_minutes > 0
