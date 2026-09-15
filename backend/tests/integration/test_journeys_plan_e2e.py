"""T032: interpret → confirm → plan 종단 간 통합 테스트 (Mock 제공자 사용).

종단 간 흐름:
1. POST /api/v1/mobility/interpret → 자연어 해석 → TripDraft + 확인 질문
2. (가상의 confirm 단계 - 사용자 확인 가정)
3. POST /api/v1/journeys/plan → Plan 응답

Mock 제공자 사용: 실제 AI/라우팅 제공자 없이 고정 응답으로 흐름 검증.
"""

import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import uuid
import json

from app.schemas.mobility import InterpretRequest, InterpretResponse, TripDraft
from app.schemas.journeys import TripRequest, Plan
from app.schemas.errors import ErrorCode
from app.schemas.common import Envelope

SEOUL_TZ = ZoneInfo("Asia/Seoul")


class TestJourneysPlanE2E:
    """해석 → 확인 → 계획 종단 간 통합 테스트."""

    def test_e2e_interpret_then_plan_flow(self, client):
        """종단 간 흐름: interpret → (confirm 가정) → plan.

        Given: 자연어 입력 "오늘 오후 7시까지 강남역에 도착해야 해."
        When: 
          1. POST /api/v1/mobility/interpret 호출
          2. (가상 confirm - 확인 질문 수용 가정)
          3. POST /api/v1/journeys/plan 호출
        Then: 
          - interpret 응답에 TripDraft 포함, 확인 질문 존재
          - plan 응답에 Plan 구조 포함, 권장 출발시각 계산됨
        """
        # Step 1: Interpret 요청
        interpret_request = {
            "natural_language": "오늘 오후 7시까지 강남역에 도착해야 해. 집에서 출발할 거야.",
            "conversation_id": "e2e_conv_001",
        }

        interpret_response = client.post(
            "/api/v1/mobility/interpret",
            json=interpret_request,
            headers={"Idempotency-Key": str(uuid.uuid4())},
        )

        assert interpret_response.status_code == 200,             f"interpret 실패: {interpret_response.status_code} {interpret_response.text}"

        interpret_body = interpret_response.json()
        assert interpret_body["status"] == "ok"
        assert "data" in interpret_body

        interpret_data = interpret_body["data"]

        # TripDraft 검증
        assert "trip_draft" in interpret_data
        trip_draft = interpret_data["trip_draft"]
        assert isinstance(trip_draft, dict)
        assert "natural_language" in trip_draft
        assert trip_draft["natural_language"] == interpret_request["natural_language"]
        assert "arrival_deadline" in trip_draft
        assert "arrival_preference_minutes" in trip_draft

        # 도착 마감 시간 검증: 오후 7시 (19:00) 오늘
        arrival_deadline = datetime.fromisoformat(trip_draft["arrival_deadline"])
        assert arrival_deadline.hour == 19, f"도착 마감 19시 기대, 실제 {arrival_deadline.hour}시"
        assert arrival_deadline.minute == 0, f"도착 마감 0분 기대, 실제 {arrival_deadline.minute}분"

        # 확인 질문 검증
        assert "confirmation_questions" in interpret_data
        questions = interpret_data["confirmation_questions"]
        assert isinstance(questions, list)
        assert len(questions) >= 2, f"확인 질문 2개 이상 기대, 실제 {len(questions)}개"
        assert any(q.get("question_type") == "place_confirmation" for q in questions),             "place_confirmation 질문 필요"

        # Step 2: (가상 confirm) - 해석 결과에서 place 정보 추출
        confirm_data = {
            "origin_place_id": trip_draft.get("origin_place_id") or "place_seoul_station",
            "destination_place_id": trip_draft.get("destination_place_id") or "place_gangnam_station",
            "arrival_deadline": trip_draft["arrival_deadline"],
            "arrival_preference_minutes": trip_draft.get("arrival_preference_minutes", 10),
        }

        # Step 3: Plan 요청
        plan_request = {
            "conversation_id": "e2e_conv_001",
            "origin_place_id": confirm_data["origin_place_id"],
            "destination_place_id": confirm_data["destination_place_id"],
            "arrival_deadline": confirm_data["arrival_deadline"],
            "arrival_preference_minutes": confirm_data["arrival_preference_minutes"],
            "transport_mode": trip_draft.get("transport_mode"),
            "max_options": 3,
        }

        plan_response = client.post(
            "/api/v1/journeys/plan",
            json=plan_request,
            headers={"Idempotency-Key": str(uuid.uuid4())},
        )

        assert plan_response.status_code == 200,             f"plan 실패: {plan_response.status_code} {plan_response.text}"

        plan_body = plan_response.json()
        assert plan_body["status"] == "ok"
        assert "data" in plan_body

        plan_data = plan_body["data"]

        # Plan 구조 검증
        assert "plan_id" in plan_data
        assert "target_arrival_at" in plan_data
        assert "recommended_leave_at" in plan_data
        assert "total_duration_minutes" in plan_data
        assert "comparison" in plan_data

        # target_arrival_at = arrival_deadline - arrival_preference_minutes
        target_arrival = datetime.fromisoformat(plan_data["target_arrival_at"])
        preferred_deadline = datetime.fromisoformat(confirm_data["arrival_deadline"])
        expected_target = preferred_deadline - timedelta(
            minutes=confirm_data["arrival_preference_minutes"]
        )
        assert target_arrival == expected_target,             f"target_arrival_at 불일치: 기대={expected_target}, 실제={target_arrival}"

        # recommended_leave_at = target - total_duration - buffer
        # Mock: total=42, buffer=5 → target - 47
        expected_leave = expected_target - timedelta(minutes=42 + 5)
        recommended = datetime.fromisoformat(plan_data["recommended_leave_at"])
        assert recommended == expected_leave,             f"recommended_leave_at 불일치: 기대={expected_leave}, 실제={recommended}"

        # recommended_leave_at < target_arrival_at
        assert recommended < target_arrival, "권장 출발시각이 목표 도착보다 이후"

        # 비교 옵션 1개 이상
        comparison = plan_data["comparison"]
        assert len(comparison["options"]) >= 1

    def test_e2e_interpret_with_place_confirmation(self, client):
        """해석 응답에 장소 확인 질문이 포함되는지 검증.

        Given: "서울역에서 강남역으로 지하철 타고 오후 6시까지 가야 해"
        When: POST /api/v1/mobility/interpret
        Then: 출발지/목적지 확인 질문 포함, 이동수단(subway) 해석
        """
        interpret_request = {
            "natural_language": "서울역에서 강남역으로 지하철 타고 오후 6시까지 가야 해",
            "conversation_id": "e2e_conv_002",
        }

        response = client.post(
            "/api/v1/mobility/interpret",
            json=interpret_request,
            headers={"Idempotency-Key": str(uuid.uuid4())},
        )

        assert response.status_code == 200
        data = response.json()["data"]

        trip_draft = data["trip_draft"]

        # 출발지: 서울역
        assert trip_draft["origin_place_id"] == "place_seoul_station",             f"출발지 서울역 기대, 실제={trip_draft.get('origin_place_id')}"
        # 목적지: 강남역
        assert trip_draft["destination_place_id"] == "place_gangnam_station",             f"목적지 강남역 기대, 실제={trip_draft.get('destination_place_id')}"

        # 교통수단: subway
        assert trip_draft["transport_mode"] == "subway",             f"transport_mode=subway 기대, 실제={trip_draft.get('transport_mode')}"

        # 도착 마감: 오후 6시 (18:00)
        deadline = datetime.fromisoformat(trip_draft["arrival_deadline"])
        assert deadline.hour == 18, f"18시 기대, 실제 {deadline.hour}시"

        # 확인 질문: 출발지/목적지 모두 확정되어도 확인 질문 존재
        questions = data["confirmation_questions"]
        assert any(q.get("place_id") == "place_seoul_station" for q in questions),             "서울역 확인 질문 필요"
        assert any(q.get("place_id") == "place_gangnam_station" for q in questions),             "강남역 확인 질문 필요"

    def test_e2e_interpret_missing_places_requires_confirmation(self, client):
        """장소 미확정 시 requires_confirmation=true & 확인 질문.

        Given: "어디론가 가야 해" (장소 정보 없음)
        When: POST /api/v1/mobility/interpret
        Then: requires_confirmation=true, place_confirmation 질문 존재
        """
        interpret_request = {
            "natural_language": "어디론가 가야 해. 일단 늦어",
            "conversation_id": "e2e_conv_003",
        }

        response = client.post(
            "/api/v1/mobility/interpret",
            json=interpret_request,
            headers={"Idempotency-Key": str(uuid.uuid4())},
        )

        assert response.status_code == 200
        data = response.json()["data"]

        # requires_confirmation = true
        assert data["requires_confirmation"] is True,             f"requires_confirmation=true 기대, 실제={data['requires_confirmation']}"

        # next_action = confirm
        assert data["next_action"] == "confirm",             f"next_action=confirm 기대, 실제={data['next_action']}"

        # 확인 질문에 place_confirmation 포함
        questions = data["confirmation_questions"]
        assert any(q.get("question_type") == "place_confirmation" for q in questions),             "place_confirmation 질문 필요 (장소 미확정)"

        # TripDraft의 place_id는 null
        trip_draft = data["trip_draft"]
        assert trip_draft.get("origin_place_id") is None or                trip_draft.get("destination_place_id") is None,                "미확정 장소는 null"

    def test_e2e_interpret_then_plan_with_time_calculation(self, client):
        """종단 간 시간 계산 검증.

        Given: 오후 7시 도착 마감, 도착 여유 15분
        When: interpret → plan
        Then: target_arrival_at = 19:00 - 15분 = 18:45
              recommended_leave_at = 18:45 - total - buffer
        """
        interpret_request = {
            "natural_language": "오늘 오후 7시까지 꼭 도착해야 해. 15분 여유 있게 가고 싶어.",
            "conversation_id": "e2e_conv_004",
        }

        # Interpret
        interpret_resp = client.post(
            "/api/v1/mobility/interpret",
            json=interpret_request,
            headers={"Idempotency-Key": str(uuid.uuid4())},
        )
        assert interpret_resp.status_code == 200

        interpret_data = interpret_resp.json()["data"]
        deadline_iso = interpret_data["trip_draft"]["arrival_deadline"]
        preference = interpret_data["trip_draft"]["arrival_preference_minutes"]
        dest_id = interpret_data["trip_draft"]["destination_place_id"] or "place_gangnam_station"

        # Plan (출발지는 Mock으로 채움)
        plan_request = {
            "conversation_id": "e2e_conv_004",
            "origin_place_id": "place_seoul_station",
            "destination_place_id": dest_id,
            "arrival_deadline": deadline_iso,
            "arrival_preference_minutes": preference,
            "max_options": 1,
        }

        plan_resp = client.post(
            "/api/v1/journeys/plan",
            json=plan_request,
            headers={"Idempotency-Key": str(uuid.uuid4())},
        )

        assert plan_resp.status_code == 200
        plan_data = plan_resp.json()["data"]

        deadline = datetime.fromisoformat(deadline_iso)
        target = datetime.fromisoformat(plan_data["target_arrival_at"])

        # target = deadline - preference (buffer 별도)
        expected_target = deadline - timedelta(minutes=preference)
        assert target == expected_target,             f"target 계산 불일치: 기대={expected_target}, 실제={target}"

        # leave = target - total(42) - buffer(5)
        expected_leave = expected_target - timedelta(minutes=42 + 5)
        leave = datetime.fromisoformat(plan_data["recommended_leave_at"])
        assert leave == expected_leave,             f"leave 계산 불일치: 기대={expected_leave}, 실제={leave}"

    def test_e2e_plan_requires_origin_confirmation_before_plan(self, client):
        """출발지 미확정 상태에서 plan 요청 → 422.

        Given: interpret로 목적지 후보만 있는 상태
        When: 출발지 없이 plan 요청
        Then: 422 VALIDATION_ERROR
        """
        # 출발지 없는 plan 요청
        plan_request = {
            "conversation_id": "e2e_conv_005",
            "origin_place_id": "",  # 빈 값
            "destination_place_id": "place_gangnam_station",
            "arrival_deadline": "2026-09-16T19:00:00+09:00",
        }

        response = client.post(
            "/api/v1/journeys/plan",
            json=plan_request,
            headers={"Idempotency-Key": str(uuid.uuid4())},
        )

        assert response.status_code == 422,             f"출발지 미확정 422 기대, 실제 {response.status_code}"

        body = response.json()
        assert body["status"] == "error"
        assert body["error"]["code"] == ErrorCode.VALIDATION_ERROR.value
        assert "출발지" in body["error"]["message"]
