from typing import Any

from pydantic import BaseModel, Field


class Meta(BaseModel):
    request_id: str | None = None
    server_time: str | None = None
    api_version: str | None = None
    is_demo: bool = True
    # T066: 대화 상태 정보 (US4)
    conversation_id: str | None = Field(None, description="대화 ID (US4)")
    revision: int | None = Field(None, description="대화 revision (US4)")
    expires_at: str | None = Field(None, description="대화 만료 시각 ISO 8601 (US4)")


class Envelope(BaseModel):
    status: str = "ok"
    data: Any | None = None
    error: dict | None = None
    meta: Meta | None = None


def envelope_ok(
    data: Any = None, meta: Meta | None = None, request_id: str | None = None
) -> Envelope:
    meta_obj = meta or Meta()
    return Envelope(
        status="ok",
        data=data,
        meta=meta_obj,
    )


def envelope_err(
    error_code: str,
    message: str,
    status_code: int,
    details: Any | None = None,
    request_id: str | None = None,
) -> Envelope:
    return Envelope(
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
