from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional, Any


# ─────────────────────────────────────────────
# 오류 코드 열거 (Enum)
# ─────────────────────────────────────────────
class ErrorCode(str, Enum):
    # 4xx 클라이언트 오류
    VALIDATION_ERROR = "VALIDATION_ERROR"                    # 422
    USER_CONFIRMATION_REQUIRED = "USER_CONFIRMATION_REQUIRED" # 422
    PLACE_NOT_RESOLVABLE = "PLACE_NOT_RESOLVABLE"            # 422
    CONVERSATION_NOT_FOUND = "CONVERSATION_NOT_FOUND"        # 404
    CONVERSATION_VERSION_CONFLICT = "CONVERSATION_VERSION_CONFLICT"  # 409
    IDEMPOTENCY_KEY_REUSED = "IDEMPOTENCY_KEY_REUSED"        # 409
    CONVERSATION_EXPIRED = "CONVERSATION_EXPIRED"            # 410
    CANDIDATE_SET_EXPIRED = "CANDIDATE_SET_EXPIRED"          # 410
    RATE_LIMITED = "RATE_LIMITED"                            # 429

    # 5xx 서버 오류
    INTERNAL_ERROR = "INTERNAL_ERROR"                        # 500
    UPSTREAM_RESPONSE_INVALID = "UPSTREAM_RESPONSE_INVALID"  # 502
    ROUTING_PROVIDER_UNAVAILABLE = "ROUTING_PROVIDER_UNAVAILABLE"  # 503
    PLACE_PROVIDER_UNAVAILABLE = "PLACE_PROVIDER_UNAVAILABLE"      # 503
    AI_UNAVAILABLE = "AI_UNAVAILABLE"                        # 503
    UPSTREAM_TIMEOUT = "UPSTREAM_TIMEOUT"                    # 504


# ─────────────────────────────────────────────
# 오류 정보 (코드별 메시지 템플릿, 상태 코드)
# ─────────────────────────────────────────────
class ErrorDetail(BaseModel):
    code: ErrorCode
    message_template: str
    status_code: int = Field(..., ge=400, le=599)
    description: str = ""


ERROR_CATALOG: dict[ErrorCode, ErrorDetail] = {
    ErrorCode.VALIDATION_ERROR: ErrorDetail(
        code=ErrorCode.VALIDATION_ERROR,
        message_template="입력 값이 유효하지 않습니다: {reason}",
        status_code=422,
        description="요청 파라미터 검증 실패",
    ),
    ErrorCode.USER_CONFIRMATION_REQUIRED: ErrorDetail(
        code=ErrorCode.USER_CONFIRMATION_REQUIRED,
        message_template="조건 확인 후 다시 시도해주세요: {reason}",
        status_code=422,
        description="사용자 확인이 필요한 상태",
    ),
    ErrorCode.PLACE_NOT_RESOLVABLE: ErrorDetail(
        code=ErrorCode.PLACE_NOT_RESOLVABLE,
        message_template="장소를 식별할 수 없습니다: {query}",
        status_code=422,
        description="장소 검색 결과가 없음",
    ),
    ErrorCode.CONVERSATION_NOT_FOUND: ErrorDetail(
        code=ErrorCode.CONVERSATION_NOT_FOUND,
        message_template="대화를 찾을 수 없습니다: {conversation_id}",
        status_code=404,
        description="존재하지 않는 conversation_id",
    ),
    ErrorCode.CONVERSATION_VERSION_CONFLICT: ErrorDetail(
        code=ErrorCode.CONVERSATION_VERSION_CONFLICT,
        message_template="대화 버전이 충돌했습니다: 기대={expected}, 실제={actual}",
        status_code=409,
        description="동시 수정 충돌 (optimistic locking)",
    ),
    ErrorCode.IDEMPOTENCY_KEY_REUSED: ErrorDetail(
        code=ErrorCode.IDEMPOTENCY_KEY_REUSED,
        message_template="이미 사용된 Idempotency-Key입니다: {idempotency_key}",
        status_code=409,
        description="동일 키에 다른 페이로드",
    ),
    ErrorCode.CONVERSATION_EXPIRED: ErrorDetail(
        code=ErrorCode.CONVERSATION_EXPIRED,
        message_template="대화 기한이 만료되었습니다: {conversation_id}",
        status_code=410,
        description="expires_at 초과",
    ),
    ErrorCode.CANDIDATE_SET_EXPIRED: ErrorDetail(
        code=ErrorCode.CANDIDATE_SET_EXPIRED,
        message_template="후보군 집합이 만료되었습니다",
        status_code=410,
        description="후보군 만료",
    ),
    ErrorCode.RATE_LIMITED: ErrorDetail(
        code=ErrorCode.RATE_LIMITED,
        message_template="요청 빈도가 너무 높습니다. {retry_after}초 후 재시도하세요.",
        status_code=429,
        description="레이트 리밋 초과",
    ),
    ErrorCode.INTERNAL_ERROR: ErrorDetail(
        code=ErrorCode.INTERNAL_ERROR,
        message_template="서버 내부 오류가 발생했습니다: {detail}",
        status_code=500,
        description="예기치 않은 서버 오류",
    ),
    ErrorCode.UPSTREAM_RESPONSE_INVALID: ErrorDetail(
        code=ErrorCode.UPSTREAM_RESPONSE_INVALID,
        message_template="외부 제공자 응답이 유효하지 않습니다: {provider}",
        status_code=502,
        description="외부 API 응답 형식 오류",
    ),
    ErrorCode.ROUTING_PROVIDER_UNAVAILABLE: ErrorDetail(
        code=ErrorCode.ROUTING_PROVIDER_UNAVAILABLE,
        message_template="경로 제공자를 사용할 수 없습니다",
        status_code=503,
        description="RoutingProvider 다운",
    ),
    ErrorCode.PLACE_PROVIDER_UNAVAILABLE: ErrorDetail(
        code=ErrorCode.PLACE_PROVIDER_UNAVAILABLE,
        message_template="장소 제공자를 사용할 수 없습니다",
        status_code=503,
        description="PlaceProvider 다운",
    ),
    ErrorCode.AI_UNAVAILABLE: ErrorDetail(
        code=ErrorCode.AI_UNAVAILABLE,
        message_template="AI 제공자를 사용할 수 없습니다",
        status_code=503,
        description="ModelProvider 다운",
    ),
    ErrorCode.UPSTREAM_TIMEOUT: ErrorDetail(
        code=ErrorCode.UPSTREAM_TIMEOUT,
        message_template="외부 제공자 응답이 시간 초과되었습니다: {provider}",
        status_code=504,
        description="외부 API 타임아웃",
    ),
}


# ─────────────────────────────────────────────
# 오류 응답 스키마 (Pydantic)
# ─────────────────────────────────────────────
class ErrorResponse(BaseModel):
    """개별 오류 객체 (envelope.error 필드)."""
    code: ErrorCode
    message: str
    status_code: int = Field(..., ge=400, le=599)
    details: Optional[Any] = None

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "code": "VALIDATION_ERROR",
                    "message": "입력 값이 유효하지 않습니다: departure_at이(가) 미래여야 합니다",
                    "status_code": 422,
                    "details": {"field": "departure_at", "issue": "과거 시간"},
                },
                {
                    "code": "CONVERSATION_NOT_FOUND",
                    "message": "대화를 찾을 수 없습니다: conv_abc123",
                    "status_code": 404,
                },
                {
                    "code": "INTERNAL_ERROR",
                    "message": "서버 내부 오류가 발생했습니다: 연결 실패",
                    "status_code": 500,
                },
                {
                    "code": "RATE_LIMITED",
                    "message": "요청 빈도가 너무 높습니다. 30초 후 재시도하세요.",
                    "status_code": 429,
                    "details": {"retry_after": 30},
                },
            ]
        }


class ErrorEnvelope(BaseModel):
    """오류 전용 봉투 (일관성 유지용）。"""
    status: str = "error"
    data: None = None
    error: ErrorResponse
    meta: dict = Field(default_factory=dict)
