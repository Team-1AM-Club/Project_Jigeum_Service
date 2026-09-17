"""제공처 원문을 추정으로 보완하지 않는 교통 조회·계산 근거 모델."""

from datetime import date, datetime
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictStr,
    field_validator,
    model_validator,
)

SEOUL = ZoneInfo("Asia/Seoul")


class TransitModel(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)


def seoul_time(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("시각에는 시간대가 필요합니다.")
    return value.astimezone(SEOUL)


class Evidence(TransitModel):
    provider: StrictStr = Field(min_length=1)
    service: StrictStr = Field(min_length=1)
    operation: StrictStr = Field(min_length=1)
    basis: Literal["static", "schedule", "realtime", "demo"]
    basis_at: datetime | None = None
    retrieved_at: datetime
    reference_date: date | None = None
    revision: StrictStr | None = None
    valid_from: date | None = None
    valid_until: date | None = None
    service_date: date | None = None
    day_type: StrictStr | None = None
    usage_rules_verified: bool = False
    verification_state: Literal[
        "documented",
        "configured",
        "real_call_verified",
        "normalized",
        "planning_verified",
    ] = "documented"

    _aware = field_validator("basis_at", "retrieved_at")(seoul_time)

    @model_validator(mode="after")
    def check_validity(self):
        if self.valid_from and self.valid_until and self.valid_from > self.valid_until:
            raise ValueError("적용 기간이 역전됐습니다.")
        return self

    @property
    def realtime_usable(self) -> bool:
        return (
            self.basis == "realtime"
            and self.basis_at is not None
            and self.basis_at <= self.retrieved_at
            and self.usage_rules_verified
            and self.verification_state in ("normalized", "planning_verified")
        )


class ProviderIdentifier(TransitModel):
    namespace: StrictStr = Field(min_length=1)
    value: StrictStr = Field(min_length=1)


class Coordinate(TransitModel):
    system: Literal["WGS84", "GRS80"]
    x: float = Field(allow_inf_nan=False)
    y: float = Field(allow_inf_nan=False)

    @model_validator(mode="after")
    def check_wgs84_range(self):
        if self.system == "WGS84" and not (
            -180 <= self.x <= 180 and -90 <= self.y <= 90
        ):
            raise ValueError("WGS84 좌표 범위를 벗어났습니다.")
        return self

    def wgs84(self) -> tuple[float, float]:
        if self.system != "WGS84":
            raise ValueError("공개 좌표는 검증된 WGS84만 사용할 수 있습니다.")
        return self.y, self.x


class TransitPlace(TransitModel):
    place_id: StrictStr = Field(min_length=1)
    mode: Literal["subway", "bus"]
    name: StrictStr = Field(min_length=1)
    line: StrictStr | None = None
    provider_ids: list[ProviderIdentifier] = Field(min_length=1)
    coordinate: Coordinate | None = None
    evidence: Evidence


class StopOccurrence(TransitModel):
    place_id: StrictStr = Field(min_length=1)
    sequence: int = Field(ge=1, strict=True)
    section_id: ProviderIdentifier | None = None
    direction: StrictStr | None = None


class RoutePattern(TransitModel):
    route_id: ProviderIdentifier
    mode: Literal["subway", "bus"]
    direction: StrictStr = Field(min_length=1)
    name: StrictStr | None = None
    headsign: StrictStr | None = None
    occurrences: list[StopOccurrence] = Field(min_length=1)
    evidence: Evidence

    @model_validator(mode="after")
    def check_sequences(self):
        sequences = [stop.sequence for stop in self.occurrences]
        if sequences != sorted(set(sequences)):
            raise ValueError("정류소 occurrence 순서는 중복 없이 증가해야 합니다.")
        return self


class ScheduledCall(TransitModel):
    occurrence: StopOccurrence
    service_id: ProviderIdentifier
    direction: StrictStr = Field(min_length=1)
    headsign: StrictStr = Field(min_length=1)
    service_date: date
    arrival_at: datetime | None = None
    departure_at: datetime
    raw_arrival_time: StrictStr | None = None
    raw_departure_time: StrictStr | None = None
    evidence: Evidence

    _aware = field_validator("arrival_at", "departure_at")(seoul_time)

    @model_validator(mode="after")
    def check_times(self):
        if self.arrival_at and self.arrival_at > self.departure_at:
            raise ValueError("정차 도착·출발 시각이 역전됐습니다.")
        return self


class TransitObservation(TransitModel):
    kind: Literal["position", "arrival_prediction", "status"]
    occurrence: StopOccurrence
    service_id: ProviderIdentifier | None = None
    raw_eta: StrictStr | None = None
    eta_unit: Literal["seconds", "minutes"] | None = None
    predicted_arrival_at: datetime | None = None
    evidence: Evidence

    _aware = field_validator("predicted_arrival_at")(seoul_time)

    @model_validator(mode="after")
    def check_prediction_type(self):
        if self.kind != "arrival_prediction" and self.predicted_arrival_at is not None:
            raise ValueError("위치·상태 관측에서 도착예측을 생성할 수 없습니다.")
        return self

    @property
    def usable_for_current_operation(self) -> bool:
        return (
            self.kind == "arrival_prediction"
            and self.evidence.realtime_usable
            and self.predicted_arrival_at is not None
            and self.predicted_arrival_at >= self.evidence.retrieved_at
        )


class TransferLink(TransitModel):
    origin_place_id: StrictStr = Field(min_length=1)
    destination_place_id: StrictStr = Field(min_length=1)
    connection_id: StrictStr = Field(min_length=1)
    minimum_minutes: float = Field(ge=0, allow_inf_nan=False)
    evidence: Evidence


class JourneyLeg(TransitModel):
    leg_id: StrictStr = Field(min_length=1)
    mode: Literal["subway", "bus", "walk", "wait"]
    origin_place_id: StrictStr = Field(min_length=1)
    destination_place_id: StrictStr = Field(min_length=1)
    departure_at: datetime
    arrival_at: datetime
    wait_reason: Literal["scheduled_wait", "safety_buffer"] | None = None
    evidence: Evidence

    _aware = field_validator("departure_at", "arrival_at")(seoul_time)

    @model_validator(mode="after")
    def check_times(self):
        if self.arrival_at < self.departure_at:
            raise ValueError("구간 시각이 역전됐습니다.")
        if (self.mode == "wait") != (self.wait_reason is not None):
            raise ValueError("대기 구간에는 대기 이유가 필요합니다.")
        if self.mode == "wait" and self.origin_place_id != self.destination_place_id:
            raise ValueError("대기 중에는 장소를 변경할 수 없습니다.")
        return self

    @property
    def duration_minutes(self) -> float:
        return (self.arrival_at - self.departure_at).total_seconds() / 60


class JourneyCandidate(TransitModel):
    option_id: StrictStr = Field(min_length=1)
    legs: list[JourneyLeg] = Field(min_length=2)

    @model_validator(mode="after")
    def check_connections_and_buffer(self):
        if len({leg.leg_id for leg in self.legs}) != len(self.legs):
            raise ValueError("구간 ID는 후보 안에서 고유해야 합니다.")
        for previous, current in zip(self.legs, self.legs[1:], strict=False):
            if (
                previous.arrival_at != current.departure_at
                or previous.destination_place_id != current.origin_place_id
            ):
                raise ValueError("구간의 시각과 장소가 연속해야 합니다.")
        margins = [leg for leg in self.legs if leg.wait_reason == "safety_buffer"]
        if len(margins) != 1 or margins[0].duration_minutes != 5:
            raise ValueError("첫 승차 전 5분 여유를 한 번 배정해야 합니다.")
        first_ride = next(
            (i for i, leg in enumerate(self.legs) if leg.mode in ("subway", "bus")),
            None,
        )
        if first_ride is None or self.legs.index(margins[0]) >= first_ride:
            raise ValueError("승차 전 여유는 첫 승차보다 앞에 있어야 합니다.")
        return self

    @property
    def recommended_leave_at(self) -> datetime:
        return self.legs[0].departure_at

    @property
    def estimated_arrival_at(self) -> datetime:
        return self.legs[-1].arrival_at

    @property
    def total_duration_minutes(self) -> float:
        return sum(leg.duration_minutes for leg in self.legs)

    @property
    def is_demo(self) -> bool:
        return any(leg.evidence.basis == "demo" for leg in self.legs)


class CoverageEvidence(TransitModel):
    service: StrictStr = Field(min_length=1)
    operation: StrictStr = Field(min_length=1)
    state: Literal[
        "documented",
        "configured",
        "real_call_verified",
        "normalized",
        "planning_verified",
    ]
    scope: list[StrictStr] = Field(default_factory=list)
    limitations: list[StrictStr] = Field(default_factory=list)
    evidence: Evidence | None = None

    @model_validator(mode="after")
    def check_planning_evidence(self):
        if self.state == "planning_verified" and (
            not self.scope or self.evidence is None or self.evidence.basis == "demo"
        ):
            raise ValueError("실제 계획 지원에는 검증한 범위와 실제 근거가 필요합니다.")
        return self
