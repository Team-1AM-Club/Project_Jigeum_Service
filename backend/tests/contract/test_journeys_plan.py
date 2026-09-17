"""T031: POST /api/v1/journeys/plan 계약 테스트.

계약 테스트: API 명세 대비 요청/응답 스키마 검증.
- 정상 요청 → Plan 응답 검증
- 출발지 미확정 → 422 VALIDATION_ERROR 검증
"""

import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from http_setup import confirmed_request

from app.schemas.errors import ErrorCode

SEOUL_TZ = ZoneInfo("Asia/Seoul")


class TestJourneysPlanContract:
    """POST /api/v1/journeys/plan 계약 테스트."""

    def test_plan_success_response_schema(self, client):
        """정상 요청 → Plan 응답 스키마 검증.

        Given: 유효한 TripRequest
        When: POST /api/v1/journeys/plan 호출
        Then: 200 OK, Plan 구조 응답, common envelope 형식
        """
        # 유효한 요청 생성
        request_body = {
            "conversation_id": "test_conv_001",
            "origin_place_id": "place_seoul_station",
            "destination_place_id": "place_gangnam_station",
            "arrival_deadline": "2026-09-16T19:00:00+09:00",
            "arrival_preference_minutes": 10,
            "transport_mode": "subway",
            "max_options": 3,
        }

        response = client.post(
            "/api/v1/journeys/plan",
            json=confirmed_request(client, request_body),
            headers={"Idempotency-Key": str(uuid.uuid4())},
        )

        # 상태 코드 검증
        assert response.status_code == 200, (
            f"예상 200, 실제 {response.status_code}: {response.text}"
        )

        # Envelope 구조 검증
        body = response.json()
        assert body.get("status") == "ok", f"status=ok 기대, 실제={body.get('status')}"
        assert "data" in body, "data 필드 누락"
        assert "meta" in body, "meta 필드 누락"
        assert body.get("error") is None, "error 필드에 값이 있음"

        # data가 Plan 구조인지 검증
        data = body["data"]
        assert "plan_id" in data, "plan_id 누락"
        assert "conversation_id" in data, "conversation_id 누락"
        assert data["conversation_id"] == request_body["conversation_id"]
        assert "origin_place_id" in data, "origin_place_id 누락"
        assert data["origin_place_id"] == "place_seoul_station"
        assert "destination_place_id" in data, "destination_place_id 누락"
        assert data["destination_place_id"] == "place_gangnam_station"
        assert "target_arrival_at" in data, "target_arrival_at 누락"
        assert "recommended_leave_at" in data, "recommended_leave_at 누락"
        assert "total_duration_minutes" in data, "total_duration_minutes 누락"
        assert "comparison" in data, "comparison 누락"
        assert "buffer_applied" in data, "buffer_applied 누락"

        # target_arrival_at 검증: arrival_deadline - arrival_preference_minutes
        arrival_deadline = datetime.fromisoformat("2026-09-16T19:00:00+09:00")
        expected_target = arrival_deadline - timedelta(minutes=10)  # preference=10
        actual_target = datetime.fromisoformat(data["target_arrival_at"])
        assert actual_target == expected_target, (
            f"target_arrival_at 불일치: 기대={expected_target}, 실제={actual_target}"
        )

        # recommended_leave_at = target - total_duration - buffer
        # Mock: total_duration=42, buffer=5 → 18:50 - 42 - 5 = 18:03
        expected_leave = expected_target - timedelta(minutes=42 + 5)
        actual_leave = datetime.fromisoformat(data["recommended_leave_at"])
        assert actual_leave == expected_leave, (
            f"recommended_leave_at 불일치: 기대={expected_leave}, 실제={actual_leave}"
        )

        # recommended_leave_at < target_arrival_at
        assert actual_leave < actual_target, (
            "recommended_leave_at이 target_arrival_at보다 이후"
        )

        # comparison 구조 검증
        comparison = data["comparison"]
        assert "options" in comparison, "comparison.options 누락"
        assert isinstance(comparison["options"], list), (
            "comparison.options가 리스트 아님"
        )
        assert len(comparison["options"]) >= 1, "후보 경로가 1개 이상 필요"

        for opt in comparison["options"]:
            assert "option_id" in opt, "option option_id 누락"
            assert "recommended_leave_at" in opt, "option recommended_leave_at 누락"
            assert "target_arrival_at" in opt, "option target_arrival_at 누락"
            assert "total_duration_minutes" in opt, "option total_duration_minutes 누락"
            assert "reasoning" in opt, "option reasoning 누락"

        # meta 검증
        meta = body["meta"]
        assert meta.get("api_version") == "v1", (
            f"api_version=v1 기대, 실제={meta.get('api_version')}"
        )
        assert meta.get("is_demo") is True, "is_demo=True 기대"

    def test_plan_missing_origin_returns_422(self, client):
        """출발지 미확정(origin_place_id 빈 값) → 422 VALIDATION_ERROR.

        Given: origin_place_id가 빈 값인 TripRequest
        When: POST /api/v1/journeys/plan 호출
        Then: 422 VALIDATION_ERROR (Pydantic이 차단, 우리 envelope 또는 FastAPI 기본 응답)
        """
        request_body = {
            "conversation_id": "test_conv_001",
            "origin_place_id": "",  # 빈 값 → 출발지 미확정 (Pydantic에서 차단)
            "destination_place_id": "place_gangnam_station",
            "arrival_deadline": "2026-09-16T19:00:00+09:00",
            "arrival_preference_minutes": 10,
        }

        response = client.post(
            "/api/v1/journeys/plan",
            json=request_body,
            headers={"Idempotency-Key": str(uuid.uuid4())},
        )

        # 422 응답 검증
        assert response.status_code == 422, (
            f"예상 422, 실제 {response.status_code}: {response.text}"
        )

        body = response.json()

        # Envelope 형식일 수도 있고, FastAPI 기본 형식일 수도 있음
        if body.get("status") == "error":
            # 우리 envelope 형식
            assert "error" in body, "error 필드 누락"
            error = body["error"]
            assert error.get("code") == ErrorCode.VALIDATION_ERROR.value, (
                f"오류 코드 VALIDATION_ERROR 기대, 실제={error.get('code')}"
            )
        elif "detail" in body:
            # FastAPI 기본 ValidationError 형식
            detail = body["detail"]
            assert isinstance(detail, list), "detail이 리스트여야 함"
            assert any("origin_place_id" in str(d.get("loc", [])) for d in detail), (
                "origin_place_id 검증 오류 필요"
            )
        else:
            pytest.fail(f"예상치 못한 422 응답 형식: {body}")

    def test_plan_missing_idempotency_key_returns_422(self, client):
        """Idempotency-Key 누락 → 422.

        Given: Idempotency-Key 헤더 없는 요청
        When: POST /api/v1/journeys/plan 호출
        Then: 422 (FastAPI 예외 핸들러로 처리)
        """
        request_body = {
            "conversation_id": "test_conv_001",
            "origin_place_id": "place_seoul_station",
            "destination_place_id": "place_gangnam_station",
        }

        response = client.post(
            "/api/v1/journeys/plan",
            json=confirmed_request(client, request_body),
            # Idempotency-Key 헤더 없음
        )

        # 422 응답 (FastAPI 헤더 검증)
        assert response.status_code == 422, f"예상 422, 실제 {response.status_code}"

    def test_plan_response_envelope_structure(self, client):
        """공통 응답 봉투 구조 검증: {status, data, error, meta}.

        Given: 정상 Plan 요청
        When: POST /api/v1/journeys/plan 호출
        Then: Envelope 구조 준수
        """
        request_body = {
            "conversation_id": "test_conv_002",
            "origin_place_id": "place_seoul_station",
            "destination_place_id": "place_gangnam_station",
            "arrival_deadline": "2026-09-16T18:00:00+09:00",
            "arrival_preference_minutes": 5,
        }

        response = client.post(
            "/api/v1/journeys/plan",
            json=confirmed_request(client, request_body),
            headers={"Idempotency-Key": str(uuid.uuid4())},
        )

        assert response.status_code == 200
        body = response.json()

        # Envelope 필수 필드 검증
        required_fields = ["status", "data", "error", "meta"]
        for field in required_fields:
            assert field in body, f"Envelope 필드 '{field}' 누락"

        # status 값 검증
        assert body["status"] in ("ok", "error"), (
            f"유효하지 않은 status: {body['status']}"
        )

        # 성공 응답일 때 data ≠ null, error = null
        if body["status"] == "ok":
            assert body["data"] is not None, "data가 null"
            assert body["error"] is None, "error가 null이 아님"
        elif body["status"] == "error":
            assert body["data"] is None, "error 응답일 때 data가 null이 아님"
            assert body["error"] is not None, "error 응답일 때 error가 null"
            assert "code" in body["error"], "error.code 누락"
            assert "message" in body["error"], "error.message 누락"
            assert "status_code" in body["error"], "error.status_code 누락"

    def test_plan_with_arrival_preference_calculation(self, client):
        """도착 여유 시간 반영 검증: target_arrival_at = arrival_deadline - arrival_preference_minutes.

        Given: arrival_deadline = 19:00, arrival_preference_minutes = 10
        When: POST /api/v1/journeys/plan 호출
        Then: target_arrival_at = 18:50 (buffer 별도)
        """
        arrival_deadline = datetime(2026, 9, 16, 19, 0, 0, tzinfo=SEOUL_TZ)
        request_body = {
            "conversation_id": "test_conv_pref_001",
            "origin_place_id": "place_seoul_station",
            "destination_place_id": "place_gangnam_station",
            "arrival_deadline": arrival_deadline.isoformat(),
            "arrival_preference_minutes": 10,
            "max_options": 1,
        }

        response = client.post(
            "/api/v1/journeys/plan",
            json=confirmed_request(client, request_body),
            headers={"Idempotency-Key": str(uuid.uuid4())},
        )

        assert response.status_code == 200
        data = response.json()["data"]

        # target_arrival_at = arrival_deadline - arrival_preference_minutes
        # buffer는 recommended_leave_at 계산 시에만 적용 (target에는 미적용)
        actual_target = datetime.fromisoformat(data["target_arrival_at"])
        expected_target = arrival_deadline - timedelta(minutes=10)
        assert actual_target == expected_target, (
            f"target_arrival_at 불일치: 기대={expected_target}, 실제={actual_target}"
        )

        # recommended_leave_at = target - total_duration - buffer
        # Mock: total=42, buffer=5 → 18:50 - 47 = 18:03
        actual_leave = datetime.fromisoformat(data["recommended_leave_at"])
        expected_leave = expected_target - timedelta(minutes=42 + 5)
        assert actual_leave == expected_leave, (
            f"recommended_leave_at 불일치: 기대={expected_leave}, 실제={actual_leave}"
        )
