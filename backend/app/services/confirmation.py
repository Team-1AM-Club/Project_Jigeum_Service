"""Canonical calculation conditions; draft completeness is not consent."""

from datetime import date, datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Conditions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["appointment", "last_journey"] = "appointment"
    origin_place_id: str = Field(min_length=1)
    destination_place_id: str = Field(min_length=1)
    arrival_deadline: datetime | None = None
    arrival_preference_minutes: int | None = Field(None, ge=0, le=120, strict=True)
    service_date: date | None = None
    transport_modes: list[Literal["subway", "bus"]] | None = None

    @model_validator(mode="after")
    def validate_kind(self):
        if not self.origin_place_id.strip() or not self.destination_place_id.strip():
            raise ValueError("Places must be resolved")
        if self.kind == "appointment":
            if (
                self.arrival_deadline is None
                or self.arrival_deadline.utcoffset() is None
            ):
                raise ValueError(
                    "Appointment requires an offset-aware arrival_deadline"
                )
            if self.service_date is not None:
                raise ValueError("Appointment service_date must be null")
            if self.arrival_preference_minutes is None:
                self.arrival_preference_minutes = 0
        else:
            if self.service_date is None or self.arrival_deadline is not None:
                raise ValueError(
                    "Last journey requires service_date and null arrival_deadline"
                )
            if self.arrival_preference_minutes not in (None, 0):
                raise ValueError("Last journey arrival_preference_minutes must be zero")
            self.arrival_preference_minutes = 0
        self.transport_modes = sorted(
            set(
                self.transport_modes
                if self.transport_modes is not None
                else ["subway", "bus"]
            )
        )
        if not self.transport_modes:
            raise ValueError("transport_modes cannot be empty")
        if self.arrival_deadline:
            self.arrival_deadline = self.arrival_deadline.astimezone(timezone.utc)
        return self


FIELDS = set(Conditions.model_fields)


def canonical(data):
    values = {k: v for k, v in data.items() if k in FIELDS}
    legacy_mode = data.get("transport_mode")
    if legacy_mode:
        mode = {"walking": "walk"}.get(legacy_mode, legacy_mode)
        if values.get("transport_modes") is None:
            values["transport_modes"] = [mode]
        elif set(values["transport_modes"]) != {mode}:
            raise ValueError("transport_mode conflicts with transport_modes")
    return Conditions.model_validate(values).model_dump(mode="json")


def complete_draft(data):
    try:
        return canonical(data)
    except ValueError:
        return None


class ConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1, strict=True)
    confirmed_data: Conditions


class PreviousSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plan_id: str = Field(min_length=1)
    selected_option_id: str = Field(min_length=1)
    recommended_leave_at: datetime
    estimated_arrival_at: datetime

    @model_validator(mode="after")
    def aware_times(self):
        if (
            self.recommended_leave_at.utcoffset() is None
            or self.estimated_arrival_at.utcoffset() is None
        ):
            raise ValueError("Previous selection timestamps require timezone offsets")
        return self
