"""교통 ID·좌표·근거·시간 연결을 합성 자료로 검증한다."""

from datetime import date, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.domain.transit import (
    Coordinate,
    Evidence,
    JourneyCandidate,
    JourneyLeg,
    ProviderIdentifier,
    RoutePattern,
    ScheduledCall,
    StopOccurrence,
    TransferLink,
    TransitObservation,
    TransitPlace,
)
from app.services.provider_interfaces import ProviderResult


def moment(minutes=0):
    return datetime(
        2026, 9, 16, 18, 0, tzinfo=timezone(timedelta(hours=9))
    ) + timedelta(minutes=minutes)


def evidence(**changes):
    return Evidence(
        provider="synthetic",
        service="fixture",
        operation="fixture",
        basis="demo",
        retrieved_at=moment(),
        **changes,
    )


def leg(**changes):
    values = {
        "leg_id": "ride",
        "mode": "subway",
        "origin_place_id": "a",
        "destination_place_id": "b",
        "departure_at": moment(10),
        "arrival_at": moment(50),
        "evidence": evidence(),
    }
    values.update(changes)
    return JourneyLeg(**values)


def test_provider_ids_preserve_namespace_and_leading_zero():
    station = ProviderIdentifier(namespace="STATION_CD", value="0012")
    external = ProviderIdentifier(namespace="FR_CODE", value="0012")
    assert station.value == "0012"
    assert station != external
    with pytest.raises(ValidationError):
        ProviderIdentifier(namespace="STATION_CD", value=12)


@pytest.mark.parametrize("state", ["documented", "configured", "real_call_verified"])
def test_unvalidated_realtime_state_is_never_usable(state):
    source = Evidence(
        provider="synthetic",
        service="fixture",
        operation="fixture",
        basis="realtime",
        basis_at=moment(),
        retrieved_at=moment(),
        usage_rules_verified=True,
        verification_state=state,
    )
    assert source.realtime_usable is False


def test_missing_coordinate_is_unknown_and_never_zero_filled():
    place = TransitPlace(
        place_id="a",
        mode="subway",
        name="합성역",
        provider_ids=[ProviderIdentifier(namespace="STATION_CD", value="0012")],
        evidence=evidence(),
    )
    assert place.coordinate is None
    with pytest.raises(ValidationError):
        Coordinate(system="WGS84", x=127)


def test_coordinate_requires_verified_system_for_public_point():
    assert Coordinate(system="WGS84", x=127, y=37.5).wgs84() == (37.5, 127)
    with pytest.raises(ValueError):
        Coordinate(system="GRS80", x=127, y=37.5).wgs84()
    with pytest.raises(ValidationError):
        Coordinate(system="WGS84", x=127, y=100)


def test_circular_route_preserves_each_stop_occurrence():
    stops = [
        StopOccurrence(place_id="a", sequence=1),
        StopOccurrence(place_id="b", sequence=2),
        StopOccurrence(place_id="a", sequence=3),
    ]
    route = RoutePattern(
        route_id=ProviderIdentifier(namespace="busRouteId", value="001"),
        mode="bus",
        direction="합성방향",
        occurrences=stops,
        evidence=evidence(),
    )
    assert len(route.occurrences) == 3
    with pytest.raises(ValidationError):
        route.model_copy().model_validate(
            {**route.model_dump(), "occurrences": [stops[0], stops[0]]}
        )


@pytest.mark.parametrize("field", ["basis_at", "retrieved_at"])
def test_evidence_rejects_naive_timestamps(field):
    values = {
        "provider": "synthetic",
        "service": "fixture",
        "operation": "fixture",
        "basis": "realtime",
        "retrieved_at": moment(),
    }
    values[field] = moment().replace(tzinfo=None)
    with pytest.raises(ValidationError):
        Evidence(**values)


def test_static_reference_date_never_becomes_basis_timestamp():
    source = Evidence(
        provider="synthetic",
        service="fixture",
        operation="fixture",
        basis="schedule",
        reference_date=date(2026, 9, 1),
        retrieved_at=moment(),
    )
    assert source.basis_at is None
    assert source.reference_date == date(2026, 9, 1)


def test_realtime_without_basis_or_rules_is_not_usable():
    values = {
        "provider": "synthetic",
        "service": "fixture",
        "operation": "fixture",
        "basis": "realtime",
        "retrieved_at": moment(),
    }
    assert Evidence(**values).realtime_usable is False
    assert Evidence(**values, basis_at=moment()).realtime_usable is False
    assert (
        Evidence(
            **values,
            basis_at=moment(),
            usage_rules_verified=True,
            verification_state="normalized",
        ).realtime_usable
        is True
    )
    assert (
        Evidence(
            **values, basis_at=moment(1), usage_rules_verified=True
        ).realtime_usable
        is False
    )


def test_observation_keeps_eta_units_and_position_cannot_invent_prediction():
    observation = TransitObservation(
        kind="arrival_prediction",
        occurrence=StopOccurrence(place_id="a", sequence=1),
        raw_eta="120",
        eta_unit="seconds",
        predicted_arrival_at=moment(2),
        evidence=evidence(),
    )
    assert observation.raw_eta == "120"
    assert observation.eta_unit == "seconds"
    with pytest.raises(ValidationError):
        TransitObservation(
            kind="position",
            occurrence=observation.occurrence,
            predicted_arrival_at=moment(2),
            evidence=evidence(),
        )


def test_past_prediction_is_not_clamped_to_now():
    source = Evidence(
        provider="synthetic",
        service="fixture",
        operation="fixture",
        basis="realtime",
        retrieved_at=moment(),
        basis_at=moment(),
        usage_rules_verified=True,
    )
    observation = TransitObservation(
        kind="arrival_prediction",
        occurrence=StopOccurrence(place_id="a", sequence=1),
        predicted_arrival_at=moment(-1),
        evidence=source,
    )
    assert observation.usable_for_current_operation is False
    assert observation.predicted_arrival_at == moment(-1)


def test_scheduled_call_keeps_service_date_and_actual_next_day():
    call = ScheduledCall(
        occurrence=StopOccurrence(place_id="a", sequence=1),
        service_id=ProviderIdentifier(namespace="train", value="0001"),
        direction="합성방향",
        headsign="합성종착역",
        service_date=date(2026, 9, 16),
        departure_at=datetime(2026, 9, 17, 0, 5, tzinfo=moment().tzinfo),
        raw_departure_time="24:05:00",
        evidence=evidence(),
    )
    assert call.service_date == date(2026, 9, 16)
    assert call.departure_at.date() == date(2026, 9, 17)
    assert call.raw_departure_time == "24:05:00"


def test_transfer_link_requires_actual_route_and_minutes():
    with pytest.raises(ValidationError):
        TransferLink(origin_place_id="a", destination_place_id="b", evidence=evidence())
    link = TransferLink(
        origin_place_id="a",
        destination_place_id="b",
        connection_id="synthetic-walk",
        minimum_minutes=3,
        evidence=evidence(),
    )
    assert link.minimum_minutes == 3


def test_candidate_buffer_once_and_total_matches_time_and_legs():
    buffer_leg = leg(
        leg_id="buffer",
        mode="wait",
        destination_place_id="a",
        departure_at=moment(5),
        arrival_at=moment(10),
        wait_reason="safety_buffer",
    )
    candidate = JourneyCandidate(option_id="synthetic", legs=[buffer_leg, leg()])
    assert candidate.total_duration_minutes == 45
    assert candidate.recommended_leave_at == moment(5)
    assert candidate.estimated_arrival_at == moment(50)
    assert candidate.is_demo is True
    with pytest.raises(ValidationError):
        JourneyCandidate(
            option_id="synthetic", legs=[buffer_leg, leg(departure_at=moment(11))]
        )
    with pytest.raises(ValidationError):
        JourneyCandidate(
            option_id="synthetic", legs=[buffer_leg, leg(origin_place_id="elsewhere")]
        )


def test_missing_or_duplicated_buffer_cannot_be_a_valid_candidate():
    with pytest.raises(ValidationError):
        JourneyCandidate(option_id="synthetic", legs=[leg()])
    buffer_leg = leg(
        leg_id="buffer",
        mode="wait",
        destination_place_id="a",
        departure_at=moment(),
        arrival_at=moment(5),
        wait_reason="safety_buffer",
    )
    second = leg(
        leg_id="buffer2",
        mode="wait",
        destination_place_id="a",
        departure_at=moment(5),
        arrival_at=moment(10),
        wait_reason="safety_buffer",
    )
    with pytest.raises(ValidationError):
        JourneyCandidate(option_id="synthetic", legs=[buffer_leg, second, leg()])


def test_normal_empty_provider_result_is_distinct_from_failure():
    assert ProviderResult(ok=True, data=[]).ok is True
    assert ProviderResult(ok=False, error_code="PROVIDER_UNAVAILABLE").ok is False
