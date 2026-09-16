"""Mobility API 라우터 - interpret + 대화 상태 연동.

T066: interpret 응답에 conversation_id, revision, expires_at 포함.
"""
import logging
import uuid
from fastapi import APIRouter, HTTPException, Header, Response
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.schemas.mobility import (
    InterpretRequest,
    InterpretResponse,
)
from app.schemas.errors import ErrorCode
from app.schemas.common import Envelope, Meta
from app.services.interpret_service import InterpretService
from app.api.responses import success_response, error_response

logger = logging.getLogger(__name__)
SEOUL_TZ = ZoneInfo("Asia/Seoul")

router = APIRouter()

# Mock 모델 제공자 (실제 구현 시 LLM 기반 제공자로 교체)
from app.services.mock.mock_providers import MockModelProvider
mock_model_provider = MockModelProvider()
interpret_service = InterpretService(model_provider=mock_model_provider)


def validate_idempotency_key(key: str | None) -> str:
    """Idempotency-Key 헤더 검증 (UUID v4, 36자).
    검증 실패 시 ValueError를 raise → 호출부에서 error_response로 처리.
    """
    if not key:
        raise ValueError("Idempotency-Key 헤더가 필수입니다.")
    try:
        uid = uuid.UUID(key)
        if uid.version != 4:
            raise ValueError("UUID 버전 4만 허용")
    except (ValueError, AttributeError):
        raise ValueError("Idempotency-Key는 유효한 UUID v4 (36자)여야 합니다.")
    return key


@router.post("/mobility/interpret", response_model=Envelope, status_code=200)
async def mobility_interpret(
    request_body: InterpretRequest,
    idempotency_key: str | None = Header(default=None, include_in_schema=False),
    response: Response = None,
) -> Envelope:
    """자연어 입력 → TripDraft + 확인 질문 해석 (T066 완성).

    - 자연어 입력을 받아 TripDraft로 변환
    - 확인이 필요한 항목(장소 등)에 대한 확인 질문 반환
    - 응답 meta에 conversation_id, revision, expires_at 포함 (T066)
    - 응답 헤더에 Idempotency-Key 반환 (SC-013)
    - Envelope에 Idempotency-Key 중복 포함 금지 (SC-014)
    """
    # Idempotency-Key 검증
    ikey = validate_idempotency_key(idempotency_key)

    # 입력 검증
    if not request_body.natural_language or not request_body.natural_language.strip():
        return error_response(
            error_code=ErrorCode.VALIDATION_ERROR,
            message="자연어 입력이 필요합니다.",
            status_code=422,
        )

    conversation_id = request_body.conversation_id or ""

    try:
        response_data = await interpret_service.interpret(request_body)

        # 응답을 dict로 직렬화
        response_dict = {
            "trip_draft": response_data.trip_draft.model_dump(mode="json"),
            "confirmation_questions": [
                q.model_dump(exclude_none=True) for q in response_data.confirmation_questions
            ],
            "requires_confirmation": response_data.requires_confirmation,
            "next_action": response_data.next_action,
        }

        # ─────────────────────────────────────────────
        # T066: meta에 conversation_id, revision, expires_at 포함
        # ─────────────────────────────────────────────
        meta = Meta(
            server_time=datetime.now(SEOUL_TZ).isoformat(),
            api_version="v1",
            is_demo=True,
            conversation_id=conversation_id,
            revision=1,  # interpret 단계에서는 revision=1 (새 대화 생성 시)
            expires_at=(datetime.now(SEOUL_TZ) + __import__("datetime").timedelta(days=1)).isoformat(),
        )

        # 응답 헤더에 Idempotency-Key 반환 (SC-013)
        if response:
            response.headers["Idempotency-Key"] = ikey

        # Envelope에 Idempotency-Key 중복 포함 금지 (SC-014)
        return success_response(data=response_dict, meta=meta)

    except ValueError as e:
        logger.warning(f"해석 요청 검증 실패: {e}")
        return error_response(
            error_code=ErrorCode.VALIDATION_ERROR,
            message=str(e),
            status_code=422,
        )
    except Exception as e:
        logger.error(f"해석 중 오류: {e}", exc_info=True)
        return error_response(
            error_code=ErrorCode.AI_UNAVAILABLE,
            message="자연어 해석 중 오류가 발생했습니다.",
            status_code=503,
        )
