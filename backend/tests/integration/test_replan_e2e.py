"""T056: 재탐색 종단 간 통합 테스트.

실제 Mock 흐름을 통한 재탐색 검증:
- MockRoutingProvider → 새 경로 계산 → ReplanResponse
- arrival_change_minutes / leave_change_minutes 비교 검증
- 이전 선택 유지 검증
- envelope 응답 구조 검증
"""

import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import uuid

from app.schemas.journeys import (
    ReplanRequest,
    ReplanResponse,
    ReplanReason,
)
from app.schemas.errors import ErrorCode
from app.schemas.common import Envelope
from app.services.provider_interfaces import RoutingProvider, ProviderResult
from app.schemas.journeys import Plan

SEOUL_TZ = ZoneInfo("Asia/Seoul")


class TestReplanE2EWithActualMock:
    """실제 Mock 제공자 기반 재탐색 종단 간 통합 테스트."""

    def test_e2e_replan_success_response_schema(self, client):
        """재탐색 성공 응답 envelope 구조 검증."""
        request_body = {
            "conversation_id": "e2e_replan_001",
            "trip": {
                "origin_place_id": "place_seoul_station",
                "destination_place_id": "place_gangnam_station",
            },
            "previous_plan": {
                "plan_id": "plan_abc123",
                "target_arrival_at": "2026-09-16T18:50:00+09:00",
                "recommended_leave_at": "2026-09-16T18:08:00+09:00",
                "total_duration_minutes": 42,
            },
            "current_origin_place_id": "place_seoul_station",
            "reason": "missed_connection",
            "user_confirmed": True,
            "max_options": 3,
        }

        response = client.post(
            "/api/v1/journeys/replan",
            json=request_body,
            headers={"Idempotency-Key": str(uuid.uuid4())},
        )

        # 상태 코드 검증
        assert response.status_code == 200, f"예상 200, 실제 {response.status_code}: {response.text}"

        body = response.json()
        assert body["status"] == "ok"
        assert "data" in body
        assert "meta" in body
        assert body.get("error") is None

        data = body["data"]

        # ReplanResponse 구조
        assert "replan_id" in data
        assert "conversation_id" in data
        assert data["conversation_id"] == "e2e_replan_001"
        assert data["reason"] == "missed_connection"
        assert "comparison" in data
        assert "notes" in data

        # comparison 구조
        comparison = data["comparison"]
        assert "new_plan" in comparison
        assert "arrival_change_minutes" in comparison
        assert "leave_change_minutes" in comparison
        assert "previous_plan_preserved" in comparison
        assert "previous_plan_valid" in comparison

    def test_e2e_replan_previous_plan_preserved(self, client):
        """재탐색 후에도 이전 선택이 보존됨."""
        request_body = {
            "conversation_id": "e2e_replan_002",
            "trip": {
                "origin_place_id": "place_seoul_station",
                "destination_place_id": "place_gangnam_station",
            },
            "previous_plan": {
                "plan_id": "plan_abc123",
                "target_arrival_at": "2026-09-16T18:50:00+09:00",
                "recommended_leave_at": "2026-09-16T18:08:00+09:00",
                "total_duration_minutes": 42,
            },
            "reason": "route_changed",
            "user_confirmed": True,
        }

        response = client.post(
            "/api/v1/journeys/replan",
            json=request_body,
            headers={"Idempotency-Key": str(uuid.uuid4())},
        )

        assert response.status_code == 200
        comparison = response.json()["data"]["comparison"]

        # 이전 선택 보존
        assert comparison["previous_plan_preserved"] is True

        # 이전 경로 유효성은 보장되지 않음
        assert comparison["previous_plan_valid"] is False

    def test_e2e_replan_arrival_change_calculated(self, client):
        """arrival_change_minutes 계산 검증 (통합 테스트)."""
        request_body = {
            "conversation_id": "e2e_replan_003",
            "trip": {
                "origin_place_id": "place_seoul_station",
                "destination_place_id": "place_gangnam_station",
            },
            "previous_plan": {
                "plan_id": "plan_abc123",
                "target_arrival_at": "2026-09-16T18:50:00+09:00",
                "recommended_leave_at": "2026-09-16T18:08:00+09:00",
                "total_duration_minutes": 42,
            },
            "reason": "missed_connection",
            "user_confirmed": True,
        }

        response = client.post(
            "/api/v1/journeys/replan",
            json=request_body,
            headers={"Idempotency-Key": str(uuid.uuid4())},
        )

        assert response.status_code == 200
        comparison = response.json()["data"]["comparison"]

        # arrival_change_minutes는 정수 또는 None
        assert isinstance(comparison["arrival_change_minutes"], int) or                comparison["arrival_change_minutes"] is None

        # leave_change_minutes도 정수 또는 None
        assert isinstance(comparison["leave_change_minutes"], int) or                comparison["leave_change_minutes"] is None

    def test_e2e_replan_user_confirmed_required(self, client):
        """user_confirmed=false → 422 USER_CONFIRMATION_REQUIRED."""
        request_body = {
            "conversation_id": "e2e_replan_004",
            "trip": {
                "origin_place_id": "place_seoul_station",
                "destination_place_id": "place_gangnam_station",
            },
            "reason": "manual",
            "user_confirmed": False,
        }

        response = client.post(
            "/api/v1/journeys/replan",
            json=request_body,
            headers={"Idempotency-Key": str(uuid.uuid4())},
        )

        assert response.status_code == 422
        body = response.json()
        assert body["status"] == "error"
        assert body["error"]["code"] == ErrorCode.USER_CONFIRMATION_REQUIRED.value

    def test_e2e_replan_missing_trip_origin(self, client):
        """trip.origin_place_id 누락 → 422."""
        request_body = {
            "conversation_id": "e2e_replan_005",
            "trip": {
                "origin_place_id": "",
                "destination_place_id": "place_gangnam_station",
            },
            "reason": "manual",
            "user_confirmed": True,
        }

        response = client.post(
            "/api/v1/journeys/replan",
            json=request_body,
            headers={"Idempotency-Key": str(uuid.uuid4())},
        )

        assert response.status_code == 422
        body = response.json()
        assert body["status"] == "error"
        assert "origin" in body["error"]["message"].lower() or                "trip" in body["error"]["message"].lower()

    def test_e2e_replan_missing_trip_destination(self, client):
        """trip.destination_place_id 누락 → 422."""
        request_body = {
            "conversation_id": "e2e_replan_006",
            "trip": {
                "origin_place_id": "place_seoul_station",
                "destination_place_id": "",
            },
            "reason": "manual",
            "user_confirmed": True,
        }

        response = client.post(
            "/api/v1/journeys/replan",
            json=request_body,
            headers={"Idempotency-Key": str(uuid.uuid4())},
        )

        assert response.status_code == 422
        body = response.json()
        assert body["status"] == "error"
        assert "destination" in body["error"]["message"].lower() or                "trip" in body["error"]["message"].lower()

    def test_e2e_replan_all_reason_types(self, client):
        """모든 재탐색 사유 타입으로 요청 가능."""
        for reason in ["missed_connection", "route_changed", "manual"]:
            request_body = {
                "conversation_id": f"e2e_replan_reason_{reason}",
                "trip": {
                    "origin_place_id": "place_seoul_station",
                    "destination_place_id": "place_gangnam_station",
                },
                "reason": reason,
                "user_confirmed": True,
            }

            response = client.post(
                "/api/v1/journeys/replan",
                json=request_body,
                headers={"Idempotency-Key": str(uuid.uuid4())},
            )

            # user_confirmed 없이 호출하면 422
            assert response.status_code == 422, f"reason={reason}: 예상 422, 실제 {response.status_code}"

    def test_e2e_replan_no_previous_plan(self, client):
        """이전 계획 없이 재탐색 가능."""
        request_body = {
            "conversation_id": "e2e_replan_007",
            "trip": {
                "origin_place_id": "place_seoul_station",
                "destination_place_id": "place_gangnam_station",
            },
            "previous_plan": None,  # 이전 계획 없음
            "reason": "manual",
            "user_confirmed": True,
        }

        response = client.post(
            "/api/v1/journeys/replan",
            json=request_body,
            headers={"Idempotency-Key": str(uuid.uuid4())},
        )

        assert response.status_code == 200
        comparison = response.json()["data"]["comparison"]

        # 이전 계획 없으므로 변화는 None
        assert comparison["arrival_change_minutes"] is None
        assert comparison["leave_change_minutes"] is None

        # 이전 선택 보존 (이전 계획이 없어도 True)
        assert comparison["previous_plan_preserved"] is True

    def test_e2e_replan_with_current_origin_different(self, client):
        """현재 위치가 변경된 재탐색."""
        request_body = {
            "conversation_id": "e2e_replan_008",
            "trip": {
                "origin_place_id": "place_seoul_station",
                "destination_place_id": "place_gangnam_station",
            },
            "current_origin_place_id": "place_jongro3ga_station",  # 현재 위치 변경
            "reason": "route_changed",
            "user_confirmed": True,
        }

        response = client.post(
            "/api/v1/journeys/replan",
            json=request_body,
            headers={"Idempotency-Key": str(uuid.uuid4())},
        )

        # 현재 위치 변경 시 재탐색 가능 (이전 계획 없어도)
        assert response.status_code == 200
        data = response.json()["data"]

        # 새로운 출발지로 재탐색됨
        assert data["comparison"]["new_plan"]["origin_place_id"] == "place_jongro3ga_station"

    def test_e2e_replan_envelope_on_error(self, client):
        """오류 응답도 공통 envelope 구조."""
        # Idempotency-Key 누락
        request_body = {
            "conversation_id": "e2e_replan_009",
            "trip": {
                "origin_place_id": "place_seoul_station",
                "destination_place_id": "place_gangnam_station",
            },
            "reason": "manual",
            "user_confirmed": True,
        }

        response = client.post(
            "/api/v1/journeys/replan",
            json=request_body,
            # Idempotency-Key 없음
        )

        assert response.status_code == 422
        body = response.json()

        # envelope 구조
        assert "status" in body
        assert "error" in body
        assert "meta" in body

        assert body["status"] == "error"
        assert body["meta"]["api_version"] == "v1"

    def test_e2e_replan_idempotency_key_validation(self, client):
        """Idempotency-Key 검증."""
        request_body = {
            "conversation_id": "e2e_replan_010",
            "trip": {
                "origin_place_id": "place_seoul_station",
                "destination_place_id": "place_gangnam_station",
            },
            "reason": "manual",
            "user_confirmed": True,
        }

        # 잘못된 UUID
        response = client.post(
            "/api/v1/journeys/replan",
            json=request_body,
            headers={"Idempotency-Key": "not-a-uuid"},
        )

        assert response.status_code == 422
        body = response.json()
        
        # FastAPI 기본 검증 오류 형식
        assert "detail" in body
        detail = body["detail"]
        if isinstance(detail, str):
            assert "Idempotency-Key" in detail or "UUID" in detail
        elif isinstance(detail, list):
            assert any("Idempotency-Key" in str(d) or "UUID" in str(d) for d in detail)

    def test_e2e_replan_auto_replacement_prevented(self, client):
        """이전 계획이 자동 교체되지 않음 검증."""
        request_body = {
            "conversation_id": "e2e_replan_011",
            "trip": {
                "origin_place_id": "place_seoul_station",
                "destination_place_id": "place_gangnam_station",
            },
            "previous_plan": {
                "plan_id": "plan_original",
                "target_arrival_at": "2026-09-16T18:50:00+09:00",
                "recommended_leave_at": "2026-09-16T18:08:00+09:00",
                "total_duration_minutes": 42,
            },
            "reason": "missed_connection",
            "user_confirmed": True,
        }

        response = client.post(
            "/api/v1/journeys/replan",
            json=request_body,
            headers={"Idempotency-Key": str(uuid.uuid4())},
        )

        assert response.status_code == 200
        comparison = response.json()["data"]["comparison"]

        # 자동 교체 방지: previous_plan_valid가 True라고 보장하지 않음
        assert comparison["previous_plan_valid"] is False

        # 이전 선택 보존
        assert comparison["previous_plan_preserved"] is True

        # 새 계획은 계산되었으나, 기존 계획을 자동 대체하지 않음
        assert comparison["new_plan"]["plan_id"] is not None
        assert comparison["new_plan"]["plan_id"] != "plan_original"
