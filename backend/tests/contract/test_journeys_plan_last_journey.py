"""T043: POST /api/v1/journeys/plan/last_journey 막차 계획 계약 테스트.

계약 테스트: API 명세 대비 막차 요청/응답 스키마 검증.
- LAST_JOURNEY_UNSUPPORTED 검증
- NO_FEASIBLE_JOURNEY 검증 (Mock 환경)
- 정상 막차 계획 검증 (Mock 환경에서 지원 가능하다고 가정 시)
"""

import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import uuid

from app.schemas.errors import ErrorCode
from app.schemas.journeys import TripRequest, Plan
from app.schemas.common import Envelope

SEOUL_TZ = ZoneInfo("Asia/Seoul")


class TestLastJourneyContract:
    """POST /api/v1/journeys/plan/last_journey 계약 테스트."""

    def test_last_journey_success_response_schema(self, client):
        """막차 계획 성공 응답 스키마 검증.

        Given: Mock 환경이 막차 운행을 지원 (현재 Mock은 지원함)
        When: POST /api/v1/journeys/plan/last_journey 호출
        Then: 200 OK, Plan 구조 응답, is_last_journey=True, 운행일/도착일 구분
        """
        request_body = {
            "conversation_id": "test_conv_last_001",
            "origin_place_id": "place_seoul_station",
            "destination_place_id": "place_gangnam_station",
            "arrival_deadline": "2026-09-17T00:30:00+09:00",
            "arrival_preference_minutes": 10,
            "max_options": 3,
        }

        response = client.post(
            "/api/v1/journeys/plan/last_journey",
            json=request_body,
            headers={"Idempotency-Key": str(uuid.uuid4())},
        )

        # 상태 코드 검증: Mock은 지원하므로 200 반환
        assert response.status_code == 200, f"예상 200, 실제 {response.status_code}: {response.text}"

        body = response.json()
        assert body.get("status") == "ok", f"status=ok 기대, 실제={body.get('status')}"
        assert "data" in body, "data 필드 누락"
        assert body.get("error") is None, "error 필드에 값이 있음"

        data = body["data"]
        
        # Plan 구조 검증
        assert "plan_id" in data, "plan_id 누락"
        assert "is_last_journey" in data, "is_last_journey 필드 누락"
        assert data["is_last_journey"] is True, f"is_last_journey=True 기대, 실제={data.get('is_last_journey')}"
        
        # 막차 관련 필드 검증
        assert "operating_date" in data, "operating_date 필드 누락"
        assert "arrival_date" in data, "arrival_date 필드 누락"
        assert "last_journey_supported" in data, "last_journey_supported 필드 누락"
        assert data["last_journey_supported"] is True

    def test_last_journey_request_schema_validation(self, client):
        """막차 계획 요청 스키마 검증.

        Given: 유효한 TripRequest (막차 계획용)
        When: POST /api/v1/journeys/plan/last_journey 호출
        Then: 요청 스키마 검증 통과 (Pydantic), 출발지 빈 값이면 422
        """
        # 유효한 요청
        valid_request = {
            "conversation_id": "test_conv_last_002",
            "origin_place_id": "place_seoul_station",
            "destination_place_id": "place_gangnam_station",
            "arrival_deadline": "2026-09-17T00:30:00+09:00",
            "arrival_preference_minutes": 10,
        }

        response = client.post(
            "/api/v1/journeys/plan/last_journey",
            json=valid_request,
            headers={"Idempotency-Key": str(uuid.uuid4())},
        )

        # Mock은 막차 지원하므로 200 성공 응답
        assert response.status_code == 200, f"예상 200, 실제 {response.status_code}"

        # 출발지 빈 값 → 422 VALIDATION_ERROR
        invalid_request = {
            "conversation_id": "test_conv_last_003",
            "origin_place_id": "",  # 빈 값
            "destination_place_id": "place_gangnam_station",
        }

        response = client.post(
            "/api/v1/journeys/plan/last_journey",
            json=invalid_request,
            headers={"Idempotency-Key": str(uuid.uuid4())},
        )

        assert response.status_code == 422
        body = response.json()
        
        # envelope 오류 형식 (API_SPEC.md §4 공통 응답)
        assert body["status"] == "error"
        assert body["error"]["code"] == "VALIDATION_ERROR"
        # details에서 field 정보 확인
        details = body["error"].get("details", [])
        assert any("origin_place_id" in d.get("field", "") for d in details), \
            f"details에 origin_place_id 관련 오류 포함 기대: {details}"

    def test_last_journey_response_common_envelope(self, client):
        """막차 계획 응답 envelope 구조 검증.

        Mock 환경 성공 응답 envelope 구조 검증.
        """
        request_body = {
            "conversation_id": "test_conv_last_004",
            "origin_place_id": "place_seoul_station",
            "destination_place_id": "place_gangnam_station",
            "arrival_deadline": "2026-09-17T00:30:00+09:00",
        }

        response = client.post(
            "/api/v1/journeys/plan/last_journey",
            json=request_body,
            headers={"Idempotency-Key": str(uuid.uuid4())},
        )

        # 성공 응답 envelope 구조 검증
        assert response.status_code == 200
        body = response.json()

        # 공통 envelope 필드
        assert "status" in body
        assert "data" in body
        assert "meta" in body
        assert body["status"] == "ok"
        assert body.get("error") is None

        # meta 필드 구조
        meta = body["meta"]
        assert meta.get("api_version") == "v1"
        assert meta.get("is_demo") is True

    def test_last_journey_missing_origin_returns_422(self, client):
        """출발지 미확정 → 422 VALIDATION_ERROR.

        Given: origin_place_id가 빈 값인 막차 계획 요청
        When: POST /api/v1/journeys/plan/last_journey 호출
        Then: 422 VALIDATION_ERROR
        """
        request_body = {
            "conversation_id": "test_conv_last_005",
            "origin_place_id": "",  # 빈 값 → 출발지 미확정
            "destination_place_id": "place_gangnam_station",
            "arrival_deadline": "2026-09-17T00:30:00+09:00",
        }

        response = client.post(
            "/api/v1/journeys/plan/last_journey",
            json=request_body,
            headers={"Idempotency-Key": str(uuid.uuid4())},
        )

        assert response.status_code == 422
        body = response.json()
        
        # envelope 오류 형식 (API_SPEC.md §4 공통 응답)
        assert body["status"] == "error"
        assert body["error"]["code"] == "VALIDATION_ERROR"
        # details에서 field 정보 확인
        details = body["error"].get("details", [])
        assert any("origin_place_id" in d.get("field", "") for d in details), \
            f"details에 origin_place_id 관련 오류 포함 기대: {details}" 

    def test_last_journey_idempotency_key_required(self, client):
        """Idempotency-Key 누락 → 422.

        Given: Idempotency-Key 헤더 없는 막차 계획 요청
        When: POST /api/v1/journeys/plan/last_journey 호출
        Then: 422 VALIDATION_ERROR (FastAPI 기본 검증 또는 envelope 오류)
        """
        request_body = {
            "conversation_id": "test_conv_last_006",
            "origin_place_id": "place_seoul_station",
            "destination_place_id": "place_gangnam_station",
        }

        response = client.post(
            "/api/v1/journeys/plan/last_journey",
            json=request_body,
            # Idempotency-Key 헤더 없음
        )

        # Idempotency-Key 없으면 422 (FastAPI Header 검증 또는 엔드포인트 내부 검증)
        assert response.status_code == 422, f"예상 422, 실제 {response.status_code}: {response.text}"
        body = response.json()
        
        # 응답 형식 검증: envelope 또는 FastAPI 기본값 모두 허용
        if body.get("status") == "error":
            assert "Idempotency-Key" in body["error"]["message"]
        elif "detail" in body:
            # FastAPI 기본 검증 오류 형식 - detail은 문자열 또는 문자열 리스트
            detail = body["detail"]
            if isinstance(detail, str):
                assert "Idempotency-Key" in detail, f"detail에 Idempotency-Key 포함 기대: {detail}"
            elif isinstance(detail, list):
                assert any("Idempotency-Key" in str(d) for d in detail),                     f"detail에 Idempotency-Key 관련 오류 포함 기대: {detail}"
