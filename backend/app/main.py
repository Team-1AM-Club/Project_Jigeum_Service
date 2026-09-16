from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.api.capabilities import router as capabilities_router
from app.api.health import router as health_router
from app.api.journeys import router as journeys_router
from app.api.mobility import router as mobility_router
from app.api.places import router as places_router
from app.config import get_settings

settings = get_settings()
from fastapi.responses import JSONResponse

from app.lifecycle import lifespan
from app.services.http_state import StateError, envelope

SEOUL_TZ = ZoneInfo("Asia/Seoul")

app = FastAPI(
    lifespan=lifespan,
    title="Jigeum API",
    version=settings.api_version,
    docs_url="/docs",
    openapi_url="/openapi.json",
)


# CORS
@app.exception_handler(StateError)
async def state_error_handler(request: Request, exc: StateError):
    return JSONResponse(
        status_code=exc.status,
        content=envelope(status="error", code=exc.code, message=exc.message),
    )


# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────
# Idempotency-Key 헤더 파싱 의존성 (T021)
# ─────────────────────────────────────────────
async def get_idempotency_key(
    idempotency_key: str | None = Header(default=None, include_in_schema=False),
) -> str:
    """Idempotency-Key 헤더 파싱. UUID v4 36자 검증."""
    if not idempotency_key:
        raise HTTPException(
            status_code=422, detail="Idempotency-Key 헤더가 필수입니다."
        )
    try:
        uid = UUID(idempotency_key)
        if uid.version != 4:
            raise ValueError("UUID 버전 4만 허용")
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=422,
            detail="Idempotency-Key는 유효한 UUID v4 (36자)여야 합니다.",
        )
    return idempotency_key


# ─────────────────────────────────────────────
# 응답 헤더에 Idempotency-Key 반환 미들웨어 (T021a, SC-013)
# ─────────────────────────────────────────────
@app.middleware("http")
async def idempotency_response_header(request: Request, call_next):
    """상태 변경 성공 시 응답 헤더에 Idempotency-Key 반환 (SC-013)."""
    response = await call_next(request)
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        key = request.headers.get("Idempotency-Key")
        if key:
            response.headers["Idempotency-Key"] = key
    return response


# ─────────────────────────────────────────────
# 라우터 등록
# ─────────────────────────────────────────────
app.include_router(health_router, prefix="/api/v1")
app.include_router(capabilities_router, prefix="/api/v1")
app.include_router(places_router, prefix="/api/v1")
app.include_router(mobility_router, prefix="/api/v1")
app.include_router(journeys_router, prefix="/api/v1")


# ─────────────────────────────────────────────
# RequestValidationError 핸들러 (Pydantic 검증 오류 → envelope)
# ─────────────────────────────────────────────
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    from fastapi.responses import JSONResponse

    details = []
    for error in exc.errors():
        loc = ".".join(str(l) for l in error.get("loc", []))
        msg = error.get("msg", "검증 오류")
        details.append({"field": loc or "body", "message": msg})
    return JSONResponse(
        status_code=422,
        content={
            "status": "error",
            "data": None,
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "요청 검증에 실패했습니다.",
                "status_code": 422,
                "details": details,
            },
            "meta": envelope()["meta"],
        },
    )


# ─────────────────────────────────────────────
# HTTPException 핸들러 (dependency-injected Idempotency-Key 검증 등)
# ─────────────────────────────────────────────
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    from fastapi.responses import JSONResponse

    status_code = exc.status_code
    detail = exc.detail
    if isinstance(detail, list):
        details = [
            {
                "field": d.get("loc", ["body"])[0] if isinstance(d, dict) else "body",
                "message": d.get("msg", str(d)) if isinstance(d, dict) else str(d),
            }
            for d in detail
        ]
        message = "요청 검증에 실패했습니다."
    elif isinstance(detail, dict):
        details = detail.get("details", [])
        message = detail.get("message", "요청 처리 중 오류가 발생했습니다.")
    else:
        details = []
        message = str(detail)

    return JSONResponse(
        status_code=status_code,
        content={
            "status": "error",
            "data": None,
            "error": {
                "code": "VALIDATION_ERROR" if status_code == 422 else "UNKNOWN_ERROR",
                "message": message,
                "retryable": False,
                "details": details,
                "status_code": status_code,
            },
            "meta": envelope()["meta"],
        },
    )


# ─────────────────────────────────────────────
# 전역 예외 핸들러
# ─────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    from fastapi.responses import JSONResponse

    status_code = getattr(exc, "status_code", 500)
    detail = "서버 내부 오류가 발생했습니다."
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "error",
            "data": None,
            "error": {
                "code": "INTERNAL_ERROR" if status_code >= 500 else "UNKNOWN_ERROR",
                "message": detail,
                "status_code": status_code,
            },
            "meta": envelope()["meta"],
        },
    )
