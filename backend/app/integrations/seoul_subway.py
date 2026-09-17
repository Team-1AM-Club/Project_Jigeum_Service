"""서울 지하철 공식 역 코드표의 검증된 row만 정규화한다."""

from collections.abc import Mapping

from app.domain.transit import Evidence, ProviderIdentifier, TransitPlace

_STATION_SERVICE = "subway-stations"
_STATION_OPERATION = "SearchSTNBySubwayLineInfo"
_REQUIRED_STATION_FIELDS = ("STATION_CD", "FR_CODE", "STATION_NM", "LINE_NUM")


def _required_string(row: Mapping[str, object], field: str) -> str:
    value = row.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"역 코드표의 필수 문자열이 올바르지 않습니다: {field}")
    return value


def normalize_station_row(
    row: Mapping[str, object], *, place_id: str, evidence: Evidence
) -> TransitPlace:
    """OA-15442 역 코드표 row를 좌표 없는 내부 역 모델로 변환한다."""
    if evidence.service != _STATION_SERVICE:
        raise ValueError("역 코드표와 다른 서비스 근거는 사용할 수 없습니다.")
    if evidence.operation != _STATION_OPERATION:
        raise ValueError("역 코드표와 다른 작업 근거는 사용할 수 없습니다.")

    station_cd, fr_code, station_name, line_num = (
        _required_string(row, field) for field in _REQUIRED_STATION_FIELDS
    )
    return TransitPlace(
        place_id=place_id,
        mode="subway",
        name=station_name,
        line=line_num,
        provider_ids=[
            ProviderIdentifier(namespace="STATION_CD", value=station_cd),
            ProviderIdentifier(namespace="FR_CODE", value=fr_code),
        ],
        coordinate=None,
        evidence=evidence,
    )
