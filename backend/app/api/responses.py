from fastapi.responses import JSONResponse
from app.schemas.common import Envelope, Meta
from typing import Any, Optional


def success_response(data: Any = None, meta: Optional[Meta] = None) -> Envelope:
    """성공 응답 봉투 생성."""
    if meta is None:
        meta = Meta()
    return Envelope(status="ok", data=data, meta=meta)


def error_response(
    error_code: str,
    message: str,
    status_code: int,
    details: Optional[Any] = None,
) -> JSONResponse:
    """오류 응답 봉투 생성 (JSONResponse로 proper HTTP status code 반환)."""
    envelope = Envelope(
        status="error",
        data=None,
        error={
            "code": error_code,
            "message": message,
            "status_code": status_code,
            "details": details,
        },
        meta=Meta(),
    )
    return JSONResponse(
        status_code=status_code,
        content=envelope.model_dump(exclude_none=True, mode="json"),
    )
