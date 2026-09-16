"""POST /api/v1/journeys/plan 라우터.

T038: TripRequest 검증 → plan 서비스 호출 → Plan 응답 반환.
출발지 미확정(origin_place_id 빈 값) 시 422 VALIDATION_ERROR 처리.
"""

import logging
from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Header

from app.api.responses import error_response, success_response
from app.schemas.common import Envelope, Meta
from app.schemas.errors import ErrorCode
from app.schemas.journeys import (
    ReplanRequest,
    TripRequest,
)
from app.services.mock.mock_providers import MockRoutingProvider
from app.services.plan_service import PlanService

logger = logging.getLogger(__name__)
SEOUL_TZ = ZoneInfo("Asia/Seoul")

router = APIRouter()

# Mock 라우팅 제공자
mock_routing_provider = MockRoutingProvider()
plan_service = PlanService(routing_provider=mock_routing_provider)


def validate_idempotency_key(key: str | None) -> str:
    """Idempotency-Key 헤더 검증 (UUID v4).
    검증 실패 시 ValueError를 raise → 호출부에서 error_response로 처리.
    """
    if not key:
        raise ValueError("Idempotency-Key 헤더가 필수입니다.")
    try:
        uid = UUID(key)
        if uid.version != 4:
            raise ValueError("UUID 버전 4만 허용")
    except (ValueError, AttributeError):
        raise ValueError("Idempotency-Key는 유효한 UUID v4 (36자)여야 합니다.")
    return key


@router.post("/journeys/plan", response_model=Envelope, status_code=200)
async def journeys_plan(
    request_body: TripRequest,
    idempotency_key: str | None = Header(default=None, include_in_schema=False),
) -> Envelope:
    """경로 계획 요청.

    출발지·목적지가 확정된 상태에서 경로 후보 1~3개와 권장 출발시각·근거를 반환.

    - 출발지 미확정(origin_place_id 빈 값) → 422 VALIDATION_ERROR
    - 공통 응답 봉투: {status, data, error, meta}

    요청 본문 예시:
    {
        "conversation_id": "conv_xyz789",
        "origin_place_id": "place_seoul_station",
        "destination_place_id": "place_gangnam_station",
        "arrival_deadline": "2026-09-16T19:00:00+09:00",
        "arrival_preference_minutes": 10,
        "transport_mode": "subway",
        "max_options": 3
    }

    성공 응답 예시:
    {
        "status": "ok",
        "data": {
            "plan_id": "plan_abc123",
            "conversation_id": "conv_xyz789",
            "origin_place_id": "place_seoul_station",
            "destination_place_id": "place_gangnam_station",
            "target_arrival_at": "2026-09-16T18:50:00+09:00",
            "recommended_leave_at": "2026-09-16T18:08:00+09:00",
            "total_duration_minutes": 42,
            "transport_mode": "subway",
            "comparison": { ... },
            "buffer_applied": 5,
            "notes": "..."
        },
        "meta": { ... }
    }
    """
    # Idempotency-Key 검증 (try 블록 내에서 호출하여 ValueError 캐치)
    # 출발지 확정 검증
    if not request_body.origin_place_id or not request_body.origin_place_id.strip():
        return error_response(
            error_code=ErrorCode.VALIDATION_ERROR,
            message="출발지가 확정되지 않았습니다. origin_place_id가 필요합니다.",
            status_code=422,
        )

    # 대화 ID 필수 확인
    if not request_body.conversation_id:
        return error_response(
            error_code=ErrorCode.VALIDATION_ERROR,
            message="conversation_id가 필요합니다.",
            status_code=422,
        )

    try:
        # Idempotency-Key 검증
        ikey = validate_idempotency_key(idempotency_key)

        # Plan 서비스 호출
        plan_result = await plan_service.plan(
            request=request_body,
            buffer_minutes=5,
        )

        meta = Meta(
            server_time=datetime.now(SEOUL_TZ).isoformat(),
            api_version="v1",
            is_demo=True,
        )

        response_dict = plan_result.model_dump(mode="json")

        return success_response(data=response_dict, meta=meta)

    except ValueError as e:
        logger.warning(f"계획 요청 검증 실패: {e}")
        return error_response(
            error_code=ErrorCode.VALIDATION_ERROR,
            message=str(e),
            status_code=422,
        )
    except Exception as e:
        logger.error(f"계획 중 오류: {e}", exc_info=True)
        return error_response(
            error_code=ErrorCode.INTERNAL_ERROR,
            message="경로 계획 중 오류가 발생했습니다.",
            status_code=500,
        )


# ─────────────────────────────────────────────
# 막차 귀가 계획 (User Story 2 - T048)
# ─────────────────────────────────────────────


@router.post("/journeys/plan/last_journey", response_model=Envelope, status_code=200)
async def journeys_plan_last_journey(
    request_body: TripRequest,
    idempotency_key: str | None = Header(default=None, include_in_schema=False),
) -> Envelope:
    """막차 귀가 경로 계획 요청.

    출발지·목적지가 확정된 상태에서 막차 귀가 후보 경로와 권장 출발시각·근거를 반환.
    운행일·노선 지원 범위를 검증하고 가능한 경우 자정 이후 도착하는 막차 경로를 반환.

    - 막차 지원 데이터 없으면 LAST_JOURNEY_UNSUPPORTED (422)
    - 지원 범위에서 경로 없으면 NO_FEASIBLE_JOURNEY (422)
    - 공통 응답 봉투: {status, data, error, meta}

    요청 본문 예시:
    {
        "conversation_id": "conv_xyz789",
        "origin_place_id": "place_seoul_station",
        "destination_place_id": "place_gangnam_station",
        "arrival_deadline": "2026-09-17T00:30:00+09:00",
        "arrival_preference_minutes": 10,
        "max_options": 3
    }

    성공 응답 예시:
    {
        "status": "ok",
        "data": {
            "plan_id": "plan_last_001",
            "conversation_id": "conv_xyz789",
            "origin_place_id": "place_seoul_station",
            "destination_place_id": "place_gangnam_station",
            "target_arrival_at": "2026-09-17T00:20:00+09:00",
            "recommended_leave_at": "2026-09-16T23:33:00+09:00",
            "total_duration_minutes": 47,
            "is_last_journey": True,
            "operating_date": "2026-09-16",
            "arrival_date": "2026-09-17",
            "last_journey_supported": True,
            "comparison": { ... },
            "buffer_applied": 5,
            "notes": "막차 귀가 경로입니다..."
        },
        "meta": { ... }
    }
    """
    # Idempotency-Key 검증 (try 블록 내에서 호출하여 ValueError 캐치)
    # 출발지 확정 검증
    if not request_body.origin_place_id or not request_body.origin_place_id.strip():
        return error_response(
            error_code=ErrorCode.VALIDATION_ERROR,
            message="출발지가 확정되지 않았습니다. origin_place_id가 필요합니다.",
            status_code=422,
        )

    # 대화 ID 필수 확인
    if not request_body.conversation_id:
        return error_response(
            error_code=ErrorCode.VALIDATION_ERROR,
            message="conversation_id가 필요합니다.",
            status_code=422,
        )

    from app.services.last_journey_service import (
        LastJourneyService,
        LastJourneyUnsupportedError,
        NoFeasibleJourneyError,
    )
    from app.services.mock.mock_providers import MockRoutingProvider

    try:
        # Idempotency-Key 검증
        ikey = validate_idempotency_key(idempotency_key)

        mock_provider = MockRoutingProvider()
        last_journey_service = LastJourneyService(routing_provider=mock_provider)

        plan = await last_journey_service.plan_last_journey(
            request=request_body,
            buffer_minutes=5,
        )

        meta = Meta(
            server_time=datetime.now(SEOUL_TZ).isoformat(),
            api_version="v1",
            is_demo=True,
        )

        response_dict = plan.model_dump(exclude_none=True, mode="json")

        return success_response(data=response_dict, meta=meta)

    except LastJourneyUnsupportedError as e:
        logger.warning(f"막차 미지원: {e.message}")
        return error_response(
            error_code=ErrorCode.VALIDATION_ERROR,
            message=e.message,
            status_code=422,
        )

    except NoFeasibleJourneyError as e:
        logger.warning(f"feasible 경로 없음: {e.message}")
        return error_response(
            error_code=ErrorCode.VALIDATION_ERROR,
            message=e.message,
            status_code=422,
        )

    except ValueError as e:
        logger.warning(f"막차 계획 요청 검증 실패: {e}")
        return error_response(
            error_code=ErrorCode.VALIDATION_ERROR,
            message=str(e),
            status_code=422,
        )

    except Exception as e:
        logger.error(f"막차 계획 중 오류: {e}", exc_info=True)
        return error_response(
            error_code=ErrorCode.INTERNAL_ERROR,
            message="막차 경로 계획 중 오류가 발생했습니다.",
            status_code=500,
        )


@router.post("/journeys/replan", response_model=Envelope, status_code=200)
async def journeys_replan(
    request_body: ReplanRequest,
    idempotency_key: str | None = Header(default=None, include_in_schema=False),
) -> Envelope:
    """재탐색 요청.

    사용자가 기존 계획을 재탐색할 때 사용.
    현재 서버 시각 기준으로 새 경로를 계산하고 이전 선택 대비 시각 변화를 반환.

    - 재탐색 실패·취소 시 이전 선택 삭제되지 않음
    - 재탐색 결과 선택 전 기존 계획 자동 교체되지 않음
    - 공통 응답 봉투: {status, data, error, meta}

    요청 본문 예시:
    {
        "conversation_id": "conv_xyz789",
        "trip": {
            "origin_place_id": "place_seoul_station",
            "destination_place_id": "place_gangnam_station"
        },
        "previous_plan": {
            "plan_id": "plan_abc123",
            "target_arrival_at": "2026-09-16T18:50:00+09:00",
            "recommended_leave_at": "2026-09-16T18:08:00+09:00",
            "total_duration_minutes": 42
        },
        "current_origin_place_id": "place_seoul_station",
        "reason": "missed_connection",
        "user_confirmed": true,
        "max_options": 3
    }

    성공 응답 예시:
    {
        "status": "ok",
        "data": {
            "replan_id": "replan_xyz456",
            "conversation_id": "conv_xyz789",
            "reason": "missed_connection",
            "comparison": {
                "new_plan": { ... },
                "arrival_change_minutes": 20,
                "leave_change_minutes": 20,
                "previous_plan_preserved": true,
                "previous_plan_valid": false
            },
            "notes": "이전 계획 대비 20분 늦게 도착합니다."
        },
        "meta": { ... }
    }
    """
    # Idempotency-Key 검증 (try 블록 내에서 호출하여 ValueError 캐치)
    # 대화 ID 필수 확인
    if not request_body.conversation_id:
        return error_response(
            error_code=ErrorCode.VALIDATION_ERROR,
            message="conversation_id가 필요합니다.",
            status_code=422,
        )

    # 사용자 확인 검증
    if not request_body.user_confirmed:
        return error_response(
            error_code=ErrorCode.USER_CONFIRMATION_REQUIRED,
            message="사용자 확인이 필요합니다. user_confirmed=true로 재요청하세요.",
            status_code=422,
        )

    # trip 정보 검증
    if not request_body.trip or not request_body.trip.get("origin_place_id"):
        return error_response(
            error_code=ErrorCode.VALIDATION_ERROR,
            message="재탐색할 trip 정보(origin_place_id)가 필요합니다.",
            status_code=422,
        )

    if not request_body.trip.get("destination_place_id"):
        return error_response(
            error_code=ErrorCode.VALIDATION_ERROR,
            message="목적지(destination_place_id)가 필요합니다.",
            status_code=422,
        )

    try:
        from app.services.mock.mock_providers import MockRoutingProvider
        from app.services.plan_service import PlanService
        from app.services.replan_service import ReplanService

        # Idempotency-Key 검증
        ikey = validate_idempotency_key(idempotency_key)

        # 서비스 초기화
        mock_provider = MockRoutingProvider()
        plan_service = PlanService(routing_provider=mock_provider)
        replan_service = ReplanService(plan_service=plan_service)

        # 재탐색 실행
        replan_response = await replan_service.replan(
            request=request_body,
            buffer_minutes=5,
        )

        meta = Meta(
            server_time=datetime.now(SEOUL_TZ).isoformat(),
            api_version="v1",
            is_demo=True,
        )

        response_dict = replan_response.model_dump(mode="json")

        return success_response(data=response_dict, meta=meta)

    except ValueError as e:
        logger.warning(f"재탐색 요청 검증 실패: {e}")
        return error_response(
            error_code=ErrorCode.VALIDATION_ERROR,
            message=str(e),
            status_code=422,
        )

    except Exception as e:
        logger.error(f"재탐색 중 오류: {e}", exc_info=True)
        return error_response(
            error_code=ErrorCode.INTERNAL_ERROR,
            message="재탐색 중 오류가 발생했습니다.",
            status_code=500,
        )
