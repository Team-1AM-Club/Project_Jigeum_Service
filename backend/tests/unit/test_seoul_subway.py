"""OA-15442 역 코드표 row의 최소 정규화 경계를 검증한다."""

from datetime import datetime, timedelta, timezone

import pytest

from app.domain.transit import Evidence
from app.integrations.seoul_subway import normalize_station_row


def moment() -> datetime:
    return datetime(2026, 9, 16, 18, 0, tzinfo=timezone(timedelta(hours=9)))


def station_evidence(**changes) -> Evidence:
    values = {
        "provider": "seoul-open-api",
        "service": "subway-stations",
        "operation": "SearchSTNBySubwayLineInfo",
        "basis": "static",
        "retrieved_at": moment(),
        "verification_state": "real_call_verified",
    }
    values.update(changes)
    return Evidence(**values)


def station_row(**changes) -> dict[str, object]:
    values: dict[str, object] = {
        "STATION_CD": "0015",
        "FR_CODE": "0150",
        "STATION_NM": "합성역",
        "LINE_NUM": "01호선",
    }
    values.update(changes)
    return values


def test_normalizes_confirmed_station_row_without_synthesizing_coordinate_or_dates():
    evidence = station_evidence()

    place = normalize_station_row(
        station_row(), place_id="opaque-station-place", evidence=evidence
    )

    assert place.place_id == "opaque-station-place"
    assert place.mode == "subway"
    assert place.name == "합성역"
    assert place.line == "01호선"
    assert [(item.namespace, item.value) for item in place.provider_ids] == [
        ("STATION_CD", "0015"),
        ("FR_CODE", "0150"),
    ]
    assert place.coordinate is None
    assert place.evidence == evidence
    assert place.evidence.basis_at is None
    assert place.evidence.service_date is None


@pytest.mark.parametrize("field", ["STATION_CD", "FR_CODE", "STATION_NM", "LINE_NUM"])
def test_rejects_missing_required_station_row_fields(field):
    row = station_row()
    row.pop(field)

    with pytest.raises(ValueError):
        normalize_station_row(
            row, place_id="opaque-station-place", evidence=station_evidence()
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("STATION_CD", 15),
        ("FR_CODE", None),
        ("STATION_NM", "   "),
        ("LINE_NUM", ""),
    ],
)
def test_rejects_malformed_required_station_row_fields(field, value):
    with pytest.raises(ValueError):
        normalize_station_row(
            station_row(**{field: value}),
            place_id="opaque-station-place",
            evidence=station_evidence(),
        )


@pytest.mark.parametrize(
    "evidence",
    [
        station_evidence(service="subway-arrivals"),
        station_evidence(operation="realtimeStationArrival"),
    ],
)
def test_rejects_station_rows_with_evidence_from_another_service_or_operation(evidence):
    with pytest.raises(ValueError):
        normalize_station_row(
            station_row(), place_id="opaque-station-place", evidence=evidence
        )


def test_rejects_timetable_or_path_shaped_rows():
    with pytest.raises(ValueError):
        normalize_station_row(
            {
                "TRAIN_NO": "101",
                "ARRIVETIME": "235900",
                "LEFTTIME": "240100",
                "tmnlStnCd": "0150",
            },
            place_id="opaque-station-place",
            evidence=station_evidence(),
        )
