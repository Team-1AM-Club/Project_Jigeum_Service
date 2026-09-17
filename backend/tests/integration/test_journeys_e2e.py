"""T042: interpret→plan 종단 간 통합 테스트 보완.

실제 Mock 흐름 검증:
- MockModelProvider → 자연어 해석 → TripDraft
- MockRoutingProvider → 경로 옵션 → Plan
- 종단 간 흐름에서 실제 Mock 제공자 응답 기반 검증
"""

import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from freezegun import freeze_time
from http_setup import confirmed_request, interpreted_request

from app.services.provider_interfaces import RoutingProvider

SEOUL_TZ = ZoneInfo("Asia/Seoul")


class TestJourneysE2EWithActualMock:
    """실제 Mock 제공자 기반 종단 간 통합 테스트."""

    def test_mock_flow_interpret_natural_language_to_tripdraft(self, client):
        """MockModelProvider 실제 흐름: 자연어 → TripDraft.

        MockModelProvider의 interpret()가 실제 호출되어
        키워드 기반 고정 응답을 반환하는지 검증.
        """
        # MockModelProvider가 인식하는 키워드 포함
        natural_lang = "서울역에서 강남역까지 지하철로 오후 7시까지 가야 해"

        response = client.post(
            "/api/v1/mobility/interpret",
            json=interpreted_request(
                client,
                {
                    "natural_language": natural_lang,
                    "conversation_id": "mock_e2e_001",
                },
            ),
            headers={"Idempotency-Key": str(uuid.uuid4())},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "needs_confirmation"

        data = body["data"]
        trip_draft = data["trip_draft"]

        # MockModelProvider의 키워드 매핑 검증
        # "서울역" → origin_place_id = place_seoul_station
        assert trip_draft["origin_place_id"] == "place_seoul_station", (
            f"Mock: 서울역→place_seoul_station 기대, 실제={trip_draft['origin_place_id']}"
        )
        # "강남" → destination_place_id = place_gangnam_station
        assert trip_draft["destination_place_id"] == "place_gangnam_station", (
            f"Mock: 강남→place_gangnam_station 기대, 실제={trip_draft['destination_place_id']}"
        )
        # "지하철" → transport_mode = subway
        assert trip_draft["transport_mode"] == "subway", (
            f"Mock: 지하철→subway 기대, 실제={trip_draft['transport_mode']}"
        )
        # "오후 7시" → arrival_deadline = 오늘 19:00
        deadline = datetime.fromisoformat(trip_draft["arrival_deadline"])
        assert deadline.hour == 19, f"Mock: 19시 기대, 실제 {deadline.hour}시"
        assert deadline.minute == 0

    def test_mock_flow_plan_uses_mock_routing_provider(self, client):
        """MockRoutingProvider 실제 흐름: plan 호출 → Mock 옵션.

        MockRoutingProvider.search_options()가 실제 호출되어
        고정 옵션 2개(subway, walking)를 반환하는지 검증.
        """
        response = client.post(
            "/api/v1/journeys/plan",
            json=confirmed_request(
                client,
                {
                    "conversation_id": "mock_e2e_002",
                    "origin_place_id": "place_seoul_station",
                    "destination_place_id": "place_gangnam_station",
                    "arrival_deadline": "2026-09-16T19:00:00+09:00",
                    "arrival_preference_minutes": 10,
                    "transport_mode": "subway",
                    "max_options": 2,
                },
            ),
            headers={"Idempotency-Key": str(uuid.uuid4())},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"

        plan_data = body["data"]

        # MockRoutingProvider는 transport_mode 필터 적용
        # subway 요청 → subway 옵션만
        comparison = plan_data["comparison"]
        options = comparison["options"]

        # transport_mode 필터: subway만 반환됨 (walking 제외)
        for opt in options:
            assert opt.get("transport_mode") == "subway", (
                f"transport_mode=subway 필터 위반: {opt.get('transport_mode')}"
            )

        # selected_option_id 확인
        assert comparison["selected_option_id"] == options[0]["option_id"]

        # Mock 옵션 데이터 검증 (고정값)
        # MockRoutingProvider: subway 42분, walking 90분 (subway 필터로 walking 제외)
        assert plan_data["total_duration_minutes"] == 42, (
            f"Mock subway: 42분 기대, 실제={plan_data['total_duration_minutes']}"
        )

    def test_mock_flow_plan_with_walking_mode(self, client):
        """교통수단은 bus/subway만 허용하며 도보는 연결 구간이다."""
        response = client.post(
            "/api/v1/journeys/plan",
            json=confirmed_request(
                client,
                {
                    "conversation_id": "mock_e2e_003",
                    "origin_place_id": "place_seoul_station",
                    "destination_place_id": "place_gangnam_station",
                    "arrival_deadline": "2026-09-16T19:00:00+09:00",
                    "arrival_preference_minutes": 0,
                    "transport_mode": "walking",
                    "max_options": 1,
                },
            ),
            headers={"Idempotency-Key": str(uuid.uuid4())},
        )

        assert response.status_code == 422
        assert response.json()["data"] is None

    def test_mock_flow_plan_time_calculation_with_actual_mock(self, client):
        """실제 Mock 데이터로 시간 계산 검증.

        MockRoutingProvider: subway 42분 고정.
        arrival_deadline = 19:00, arrival_preference = 10분.
        target_arrival_at = 19:00 - 10분(preference) = 18:50
        recommended_leave_at = 18:50 - 42분(이동) - 5분(buffer) = 18:03
        """
        response = client.post(
            "/api/v1/journeys/plan",
            json=confirmed_request(
                client,
                {
                    "conversation_id": "mock_e2e_004",
                    "origin_place_id": "place_seoul_station",
                    "destination_place_id": "place_gangnam_station",
                    "arrival_deadline": "2026-09-16T19:00:00+09:00",
                    "arrival_preference_minutes": 10,
                    "transport_mode": "subway",
                    "max_options": 1,
                },
            ),
            headers={"Idempotency-Key": str(uuid.uuid4())},
        )

        assert response.status_code == 200
        plan_data = response.json()["data"]

        # target_arrival_at = 19:00 - 10분(선호) = 18:50
        target = datetime.fromisoformat(plan_data["target_arrival_at"])
        expected_target = datetime(2026, 9, 16, 18, 50, 0, tzinfo=SEOUL_TZ)
        assert target == expected_target, (
            f"Mock target 계산: 기대 {expected_target}, 실제 {target}"
        )

        # recommended_leave_at = 18:50 - 42분(이동) - 5분(buffer) = 18:03
        leave = datetime.fromisoformat(plan_data["recommended_leave_at"])
        expected_leave = datetime(2026, 9, 16, 18, 3, 0, tzinfo=SEOUL_TZ)
        assert leave == expected_leave, (
            f"Mock leave 계산: 기대 {expected_leave}, 실제 {leave}"
        )

        # 총 소요시간 = Mock 고정값 42분
        assert plan_data["total_duration_minutes"] == 42
        assert plan_data["buffer_applied"] == 5

    @freeze_time("2026-09-16 10:00:00+09:00")
    def test_mock_flow_interpret_then_plan_full_chain(self, client):
        """전체 Mock 체인: interpret → plan (확인 가정).

        1. 자연어 해석 (MockModelProvider)
        2. TripDraft에서 장소 추출
        3. Plan 요청 (MockRoutingProvider)
        4. Plan 응답 검증
        """
        # Step 1: Interpret
        natural_lang = "서울역에서 강남역으로 지하철 타고 오후 7시까지 가야 해"
        interpret_resp = client.post(
            "/api/v1/mobility/interpret",
            json=interpreted_request(
                client,
                {
                    "natural_language": natural_lang,
                    "conversation_id": "mock_chain_001",
                    "context": {"arrival_preference_minutes": 10},
                },
            ),
            headers={"Idempotency-Key": str(uuid.uuid4())},
        )
        assert interpret_resp.status_code == 200

        interpret_data = interpret_resp.json()["data"]
        trip_draft = interpret_data["trip_draft"]

        # MockModelProvider: 출발지/목적지/교통수단 해석됨
        assert trip_draft["origin_place_id"] == "place_seoul_station"
        assert trip_draft["destination_place_id"] == "place_gangnam_station"
        assert trip_draft["transport_mode"] == "subway"

        # Step 2: Plan (출발지는 이미 확정, 목적지도 확정)
        plan_resp = client.post(
            "/api/v1/journeys/plan",
            json=confirmed_request(
                client,
                {
                    "conversation_id": "mock_chain_001",
                    "origin_place_id": trip_draft["origin_place_id"],
                    "destination_place_id": trip_draft["destination_place_id"],
                    "arrival_deadline": trip_draft["arrival_deadline"],
                    "arrival_preference_minutes": trip_draft.get(
                        "arrival_preference_minutes", 10
                    ),
                    "transport_mode": trip_draft["transport_mode"],
                    "max_options": 2,
                },
            ),
            headers={"Idempotency-Key": str(uuid.uuid4())},
        )
        assert plan_resp.status_code == 200

        plan_data = plan_resp.json()["data"]

        # 전체 체인 검증
        assert plan_data["origin_place_id"] == "place_seoul_station"
        assert plan_data["destination_place_id"] == "place_gangnam_station"
        assert plan_data["transport_mode"] == "subway"
        assert plan_data["total_duration_minutes"] == 42  # Mock subway
        assert plan_data["buffer_applied"] == 5

        # 시간 계산: target = 19:00 - 10분(선호) = 18:50
        target = datetime.fromisoformat(plan_data["target_arrival_at"])
        assert target == datetime(2026, 9, 16, 18, 50, 0, tzinfo=SEOUL_TZ)

        # leave = 18:50 - 42분(이동) - 5분(buffer) = 18:03
        leave = datetime.fromisoformat(plan_data["recommended_leave_at"])
        assert leave == datetime(2026, 9, 16, 18, 3, 0, tzinfo=SEOUL_TZ)

    def test_mock_flow_interpret_empty_dialogue(self, client):
        """빈/무의미한 자연어 → 확인 질문 중심 응답.

        MockModelProvider가 인식하지 못하는 텍스트 → 기본 해석.
        """
        response = client.post(
            "/api/v1/mobility/interpret",
            json=interpreted_request(
                client,
                {
                    "natural_language": "그냥 어디 좀 가야 하는데",
                    "conversation_id": "mock_e2e_005",
                },
            ),
            headers={"Idempotency-Key": str(uuid.uuid4())},
        )

        assert response.status_code == 200
        data = response.json()["data"]

        # MockModelProvider가 places 못 찾으면 needs_confirmation
        trip_draft = data["trip_draft"]

        # MockModelProvider: Seoul/Gangnam 키워드 없음 → place_id null
        assert trip_draft.get("origin_place_id") is None
        assert trip_draft.get("destination_place_id") is None

        # requires_confirmation = true
        assert data["requires_confirmation"] is True

        # 확인 질문 존재
        assert len(data["confirmation_questions"]) >= 2

    def test_mock_flow_plan_with_no_options_is_unavailable(self, client):
        """라우팅 결과 없을 때 Mock fallback 옵션 생성 검증.

        MockRoutingProvider가 빈 배열 반환 → PlanService._generate_mock_options() 호출.
        """
        from unittest.mock import AsyncMock

        # 직접 테스트: 빈 provider 결과 → Mock 옵션 생성
        from app.services.plan_service import PlanService
        from app.services.provider_interfaces import ProviderResult

        provider = AsyncMock(spec=RoutingProvider)
        provider.search_options.return_value = ProviderResult(ok=True, data=[])

        service = PlanService(routing_provider=provider)

        request = type(
            "TripRequest",
            (),
            {
                "conversation_id": "fallback_test",
                "origin_place_id": "place_seoul_station",
                "destination_place_id": "place_gangnam_station",
                "arrival_deadline": datetime(2026, 9, 16, 19, 0, 0, tzinfo=SEOUL_TZ),
                "arrival_preference_minutes": 10,
                "transport_mode": "subway",
                "transport_modes": ["subway"],
                "max_options": 3,
            },
        )()

        import asyncio

        from app.services.last_journey_service import NoFeasibleJourneyError

        with pytest.raises(NoFeasibleJourneyError):
            asyncio.run(service.plan(request=request, buffer_minutes=5))
