from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field


class Meta(BaseModel):
    request_id: Optional[str] = None
    server_time: Optional[str] = None
    api_version: Optional[str] = None
    is_demo: bool = True
    # T066: 대화 상태 정보 (US4)
    conversation_id: Optional[str] = Field(None, description="대화 ID (US4)")
    revision: Optional[int] = Field(None, description="대화 revision (US4)")
    expires_at: Optional[str] = Field(None, description="대화 만료 시각 ISO 8601 (US4)")


class Envelope(BaseModel):
    status: str = "ok"
    data: Optional[Any] = None
    error: Optional[dict] = None
    meta: Optional[Meta] = None


def envelope_ok(data: Any = None, meta: Optional[Meta] = None, request_id: Optional[str] = None) -> Envelope:
    meta_obj = meta or Meta()
    return Envelope(
        status="ok",
        data=data,
        meta=meta_obj,
    )


def envelope_err(error_code: str, message: str, status_code: int, details: Optional[Any] = None,
                 request_id: Optional[str] = None) -> Envelope:
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
