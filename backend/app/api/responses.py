from typing import Any

from fastapi.responses import JSONResponse

from app.schemas.common import Envelope, Meta


def success_response(data: Any = None, meta: Meta | None = None) -> Envelope:
    """성공 응답 봉투 생성."""
    if meta is None:
        meta = Meta()
    return Envelope(status="ok", data=data, meta=meta)


def error_response(
    error_code: str,
    message: str,
    status_code: int,
    details: Any | None = None,
) -> JSONResponse:
    """오류 응답 봉투 생성 (JSONResponse로 proper HTTP status code 반환)."""
    # details가 None이면 빈 리스트로 기본값 설정 (API_SPEC.md에서 details는 배열)
    details_list = details if details is not None else []
    envelope = Envelope(
        status="error",
        data=None,
        error={
            "code": error_code,
            "message": message,
            "status_code": status_code,
            "details": details_list,
        },
        meta=Meta(),
    )
    return JSONResponse(
        status_code=status_code,
        content=envelope.model_dump(exclude_none=True, mode="json"),
    )
