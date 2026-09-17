from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.transit import seoul_time


class Source(BaseModel):
    """제공처 기준시각과 조회시각을 분리하는 전환 호환 출처."""

    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    provider: str = Field(min_length=1)
    basis: Literal["schedule", "realtime", "demo"]
    basis_at: datetime | None = None
    retrieved_at: datetime
    service_date: date

    @field_validator("basis_at", "retrieved_at", mode="before")
    @classmethod
    def reject_date_only(cls, value):
        if isinstance(value, date) and not isinstance(value, datetime):
            raise ValueError("날짜만으로 기준시각을 만들 수 없습니다.")
        if isinstance(value, str) and "T" not in value:
            raise ValueError("시각과 시간대를 포함한 ISO 8601이 필요합니다.")
        if value is not None and not isinstance(value, (str, datetime)):
            raise ValueError("검증 가능한 datetime이 필요합니다.")
        return value

    _aware = field_validator("basis_at", "retrieved_at")(seoul_time)


class DataWarning(BaseModel):
    """후보별 자료 한계를 전달하는 공개 경고."""

    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    code: str = Field(min_length=1)
    message: str = Field(min_length=1)


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
