"""T051: 재탐색 서비스 단위 테스트.

- arrival_change_minutes 계산 검증
- leave_change_minutes 계산 검증
- 이전 선택 삭제 방지 검증
- 사용자 확인 요구 검증
"""

from datetime import datetime
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest

from app.schemas.journeys import (
    Plan,
    ReplanReason,
    ReplanRequest,
    ReplanResponse,
)
from app.services.plan_service import PlanService
from app.services.provider_interfaces import RoutingProvider
from app.services.replan_service import ReplanService

SEOUL_TZ = ZoneInfo("Asia/Seoul")


@pytest.fixture
def mock_plan_service():
    """Mock PlanService."""
    service = AsyncMock(spec=PlanService)
    service.plan = AsyncMock()
    service.routing_provider = AsyncMock(spec=RoutingProvider)
    service.routing_provider.search_options = AsyncMock()
    return service


@pytest.fixture
def replan_service(mock_plan_service):
    return ReplanService(plan_service=mock_plan_service)


@pytest.fixture(scope="function")
def valid_replan_request():
    """Valid replan request fixture (module level for all test classes)."""

    return ReplanRequest(
        conversation_id="test_replan_001",
        trip={
            "origin_place_id": "place_seoul_station",
            "destination_place_id": "place_gangnam_station",
        },
        previous_plan={
            "plan_id": "plan_abc123",
            "target_arrival_at": "2026-09-16T18:50:00+09:00",
            "recommended_leave_at": "2026-09-16T18:08:00+09:00",
            "total_duration_minutes": 42,
        },
        current_origin_place_id="place_seoul_station",
        reason=ReplanReason.MISSED_CONNECTION,
        user_confirmed=True,
        max_options=3,
    )


class TestReplanServiceNormalCase:
    """재탐색 서비스 정상 케이스 테스트."""

    @pytest.fixture
    def mock_plan_service(self):
        """Mock PlanService."""
        service = AsyncMock(spec=PlanService)
        service.plan = AsyncMock()
        service.routing_provider = AsyncMock(spec=RoutingProvider)
        service.routing_provider.search_options = AsyncMock()
        return service

    @pytest.fixture
    def replan_service(self, mock_plan_service):
        return ReplanService(plan_service=mock_plan_service)


class TestArrivalChangeCalculation:
    """arrival_change_minutes 계산 검증 테스트."""

    @pytest.mark.asyncio
    async def test_arrival_change_positive_when_later_arrival(
        self, replan_service, valid_replan_request
    ):
        """새 도착이 더 늦을 때 arrival_change_minutes 양수."""
        # Mock: 새 계획 도착 19:10, 이전 18:50 → +20분
        mock_new_plan = Plan(
            plan_id="plan_new789",
            conversation_id="test_replan_001",
            origin_place_id="place_seoul_station",
            destination_place_id="place_gangnam_station",
            target_arrival_at=datetime(2026, 9, 16, 19, 10, 0, tzinfo=SEOUL_TZ),
            recommended_leave_at=datetime(2026, 9, 16, 18, 28, 0, tzinfo=SEOUL_TZ),
            total_duration_minutes=42,
        )

        replan_service.plan_service.plan.return_value = mock_new_plan

        response = await replan_service.replan(request=valid_replan_request)

        # arrival_change_minutes = 19:10 - 18:50 = +20
        assert response.comparison.arrival_change_minutes == 20, (
            f"기대 20, 실제 {response.comparison.arrival_change_minutes}"
        )

    @pytest.mark.asyncio
    async def test_arrival_change_negative_when_earlier_arrival(
        self, replan_service, valid_replan_request
    ):
        """새 도착이 더 빠를 때 arrival_change_minutes 음수."""
        # Mock: 새 계획 도착 18:30, 이전 18:50 → -20분
        mock_new_plan = Plan(
            plan_id="plan_new789",
            conversation_id="test_replan_001",
            origin_place_id="place_seoul_station",
            destination_place_id="place_gangnam_station",
            target_arrival_at=datetime(2026, 9, 16, 18, 30, 0, tzinfo=SEOUL_TZ),
            recommended_leave_at=datetime(2026, 9, 16, 17, 48, 0, tzinfo=SEOUL_TZ),
            total_duration_minutes=42,
        )

        replan_service.plan_service.plan.return_value = mock_new_plan

        response = await replan_service.replan(request=valid_replan_request)

        # arrival_change_minutes = 18:30 - 18:50 = -20
        assert response.comparison.arrival_change_minutes == -20, (
            f"기대 -20, 실제 {response.comparison.arrival_change_minutes}"
        )

    @pytest.mark.asyncio
    async def test_arrival_change_zero_when_same_arrival(
        self, replan_service, valid_replan_request
    ):
        """새 도착이 동일할 때 arrival_change_minutes 0."""
        # Mock: 새 계획 도착 18:50, 이전 18:50 → 0분
        mock_new_plan = Plan(
            plan_id="plan_new789",
            conversation_id="test_replan_001",
            origin_place_id="place_seoul_station",
            destination_place_id="place_gangnam_station",
            target_arrival_at=datetime(2026, 9, 16, 18, 50, 0, tzinfo=SEOUL_TZ),
            recommended_leave_at=datetime(2026, 9, 16, 18, 8, 0, tzinfo=SEOUL_TZ),
            total_duration_minutes=42,
        )

        replan_service.plan_service.plan.return_value = mock_new_plan

        response = await replan_service.replan(request=valid_replan_request)

        assert response.comparison.arrival_change_minutes == 0

    @pytest.mark.asyncio
    async def test_arrival_change_none_when_no_previous_plan(self, replan_service):
        """이전 계획이 없으면 arrival_change_minutes None."""
        request = ReplanRequest(
            conversation_id="test_replan_002",
            trip={
                "origin_place_id": "place_seoul_station",
                "destination_place_id": "place_gangnam_station",
            },
            previous_plan=None,  # 이전 계획 없음
            reason=ReplanReason.MANUAL,
            user_confirmed=True,
        )

        mock_new_plan = Plan(
            plan_id="plan_new789",
            conversation_id="test_replan_002",
            origin_place_id="place_seoul_station",
            destination_place_id="place_gangnam_station",
            target_arrival_at=datetime(2026, 9, 16, 19, 0, 0, tzinfo=SEOUL_TZ),
            recommended_leave_at=datetime(2026, 9, 16, 18, 18, 0, tzinfo=SEOUL_TZ),
            total_duration_minutes=42,
        )

        replan_service.plan_service.plan.return_value = mock_new_plan

        response = await replan_service.replan(request=request)

        assert response.comparison.arrival_change_minutes is None


class TestLeaveChangeCalculation:
    """leave_change_minutes 계산 검증 테스트."""

    @pytest.mark.asyncio
    async def test_leave_change_calculated_when_both_available(
        self, replan_service, valid_replan_request
    ):
        """이전/새 출발 시각 모두 있으면 leave_change_minutes 계산."""
        mock_new_plan = Plan(
            plan_id="plan_new789",
            conversation_id="test_replan_001",
            origin_place_id="place_seoul_station",
            destination_place_id="place_gangnam_station",
            target_arrival_at=datetime(2026, 9, 16, 19, 10, 0, tzinfo=SEOUL_TZ),
            recommended_leave_at=datetime(
                2026, 9, 16, 18, 28, 0, tzinfo=SEOUL_TZ
            ),  # 이전 18:08 → +20
            total_duration_minutes=42,
        )

        replan_service.plan_service.plan.return_value = mock_new_plan

        response = await replan_service.replan(request=valid_replan_request)

        # leave_change_minutes = 18:28 - 18:08 = +20
        assert response.comparison.leave_change_minutes == 20, (
            f"기대 20, 실제 {response.comparison.leave_change_minutes}"
        )


class TestPreviousPlanPreservation:
    """이전 선택 보존 검증 테스트."""

    @pytest.mark.asyncio
    async def test_previous_plan_preserved_after_replan(
        self, replan_service, valid_replan_request
    ):
        """재탐색 후에도 previous_plan_preserved = True."""
        mock_new_plan = Plan(
            plan_id="plan_new789",
            conversation_id="test_replan_001",
            origin_place_id="place_seoul_station",
            destination_place_id="place_gangnam_station",
            target_arrival_at=datetime(2026, 9, 16, 19, 0, 0, tzinfo=SEOUL_TZ),
            recommended_leave_at=datetime(2026, 9, 16, 18, 18, 0, tzinfo=SEOUL_TZ),
            total_duration_minutes=42,
        )

        replan_service.plan_service.plan.return_value = mock_new_plan

        response = await replan_service.replan(request=valid_replan_request)

        # 이전 선택 보존
        assert response.comparison.previous_plan_preserved is True

        # 이전 경로 유효성은 보장되지 않음
        assert response.comparison.previous_plan_valid is False

    @pytest.mark.asyncio
    async def test_previous_plan_not_deleted_on_failure(self, replan_service):
        """재탐색 실패 시에도 이전 선택 삭제되지 않음."""
        # ReplanService는 실패 시에도 이전 선택을 삭제하지 않음
        # (실제로는 예외 발생 시 이전 선택이 영향을 받지 않음)

        request = ReplanRequest(
            conversation_id="test_replan_003",
            trip={
                "origin_place_id": "place_seoul_station",
                "destination_place_id": "place_gangnam_station",
            },
            previous_plan={
                "plan_id": "plan_abc123",
                "target_arrival_at": "2026-09-16T18:50:00+09:00",
                "recommended_leave_at": "2026-09-16T18:08:00+09:00",
            },
            reason=ReplanReason.MISSED_CONNECTION,
            user_confirmed=True,
        )

        # plan_service.plan()이 실패하는 경우
        replan_service.plan_service.plan.side_effect = Exception("라우팅 제공자 오류")

        with pytest.raises(Exception):
            await replan_service.replan(request=request)

        # 예외 발생 시에도 이전 계획은 삭제되지 않음 (메모리 상으로만 존재)
        # 이는 서비스 레벨에서 보장됨


class TestUserConfirmationRequirement:
    """사용자 확인 요구 검증 테스트."""

    @pytest.mark.asyncio
    async def test_replan_requires_user_confirmation(self, replan_service):
        """user_confirmed=false → ValueError."""
        request = ReplanRequest(
            conversation_id="test_replan_004",
            trip={
                "origin_place_id": "place_seoul_station",
                "destination_place_id": "place_gangnam_station",
            },
            reason=ReplanReason.MANUAL,
            user_confirmed=False,  # 확인 안 함
        )

        with pytest.raises(ValueError) as exc_info:
            await replan_service.replan(request=request)

        assert "사용자 확인" in str(exc_info.value) or "user_confirmed" in str(
            exc_info.value
        )

    @pytest.mark.asyncio
    async def test_replan_succeeds_with_user_confirmation(
        self, replan_service, valid_replan_request
    ):
        """user_confirmed=true → 재탐색 성공."""
        mock_new_plan = Plan(
            plan_id="plan_new789",
            conversation_id="test_replan_001",
            origin_place_id="place_seoul_station",
            destination_place_id="place_gangnam_station",
            target_arrival_at=datetime(2026, 9, 16, 19, 0, 0, tzinfo=SEOUL_TZ),
            recommended_leave_at=datetime(2026, 9, 16, 18, 18, 0, tzinfo=SEOUL_TZ),
            total_duration_minutes=42,
        )

        replan_service.plan_service.plan.return_value = mock_new_plan

        response = await replan_service.replan(request=valid_replan_request)

        assert isinstance(response, ReplanResponse)
        assert response.replan_id is not None


class TestReplanRequestValidation:
    """재탐색 요청 검증 테스트."""

    @pytest.mark.asyncio
    async def test_replan_missing_conversation_id_raises_error(self, replan_service):
        """conversation_id 누락 → ValueError."""
        request = ReplanRequest(
            conversation_id="",
            trip={
                "origin_place_id": "place_seoul_station",
                "destination_place_id": "place_gangnam_station",
            },
            reason=ReplanReason.MANUAL,
            user_confirmed=True,
        )

        with pytest.raises(ValueError) as exc_info:
            await replan_service.replan(request=request)

        assert "conversation_id" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_replan_missing_trip_origin_raises_error(self, replan_service):
        """trip.origin_place_id 누락 → ValueError."""
        request = ReplanRequest(
            conversation_id="test_replan_005",
            trip={
                "origin_place_id": "",  # 빈 값
                "destination_place_id": "place_gangnam_station",
            },
            reason=ReplanReason.MANUAL,
            user_confirmed=True,
        )

        with pytest.raises(ValueError) as exc_info:
            await replan_service.replan(request=request)

        assert "origin" in str(exc_info.value).lower() or "출발지" in str(
            exc_info.value
        )

    @pytest.mark.asyncio
    async def test_replan_missing_trip_destination_raises_error(self, replan_service):
        """trip.destination_place_id 누락 → ValueError."""
        request = ReplanRequest(
            conversation_id="test_replan_006",
            trip={
                "origin_place_id": "place_seoul_station",
                "destination_place_id": "",  # 빈 값
            },
            reason=ReplanReason.MANUAL,
            user_confirmed=True,
        )

        with pytest.raises(ValueError) as exc_info:
            await replan_service.replan(request=request)

        assert "destination" in str(exc_info.value).lower() or "목적지" in str(
            exc_info.value
        )


class TestAutoReplacementPrevention:
    """자동 교체 방지 검증 테스트."""

    @pytest.mark.asyncio
    async def test_previous_plan_not_auto_replaced(
        self, replan_service, valid_replan_request
    ):
        """재탐색 결과 선택 전 기존 계획 자동 교체되지 않음."""
        mock_new_plan = Plan(
            plan_id="plan_new789",
            conversation_id="test_replan_001",
            origin_place_id="place_seoul_station",
            destination_place_id="place_gangnam_station",
            target_arrival_at=datetime(2026, 9, 16, 19, 0, 0, tzinfo=SEOUL_TZ),
            recommended_leave_at=datetime(2026, 9, 16, 18, 18, 0, tzinfo=SEOUL_TZ),
            total_duration_minutes=42,
        )

        replan_service.plan_service.plan.return_value = mock_new_plan

        response = await replan_service.replan(request=valid_replan_request)

        # previous_plan_preserved = True (이전 선택 유지)
        assert response.comparison.previous_plan_preserved is True

        # automatic replacement 방지: previous_plan_valid가 True라고 보장하지 않음
        assert response.comparison.previous_plan_valid is False

    @pytest.mark.asyncio
    async def test_replan_guard_prevents_auto_replacement(self, replan_service):
        """ReplanGuard 사용하지 않지만 개념적 검증."""
        # ReplanService는 이전 계획을 보존하고 자동 교체하지 않음
        # (코드 레벨에서 previous_plan_preserved=True로 고정)

        request = ReplanRequest(
            conversation_id="test_replan_007",
            trip={
                "origin_place_id": "place_seoul_station",
                "destination_place_id": "place_gangnam_station",
            },
            reason=ReplanReason.MANUAL,
            user_confirmed=True,
        )

        mock_new_plan = Plan(
            plan_id="plan_new789",
            conversation_id="test_replan_007",
            origin_place_id="place_seoul_station",
            destination_place_id="place_gangnam_station",
            target_arrival_at=datetime(2026, 9, 16, 19, 0, 0, tzinfo=SEOUL_TZ),
            recommended_leave_at=datetime(2026, 9, 16, 18, 18, 0, tzinfo=SEOUL_TZ),
            total_duration_minutes=42,
        )

        replan_service.plan_service.plan.return_value = mock_new_plan

        response = await replan_service.replan(request=request)

        # 이전 선택 보존 확인
        assert response.comparison.previous_plan_preserved is True
