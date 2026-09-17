"""Adapt confirmed mode sets to the existing single-mode provider interface."""

from pydantic import ValidationError

from app.schemas.common import DataWarning, Source
from app.services.http_state import StateError


def _matches_source(item, source):
    return (
        item.provider == source.provider
        and item.basis_at == source.basis_at
        and item.retrieved_at == source.retrieved_at
        and item.service_date == source.service_date
    )


def _with_verified_sources(option, evidence):
    """출처를 보존하고 검증되지 않은 실시간 근거는 계산에서 제외한다."""
    raw_sources = option.get("sources", [])
    raw_warnings = option.get("warnings", [])
    if not isinstance(raw_sources, list) or not isinstance(raw_warnings, list):
        raise StateError("UPSTREAM_RESPONSE_INVALID", 502)
    try:
        sources = [Source.model_validate(source) for source in raw_sources]
        warnings = [DataWarning.model_validate(warning) for warning in raw_warnings]
    except ValidationError:
        raise StateError("UPSTREAM_RESPONSE_INVALID", 502) from None

    for source in sources:
        if source.basis == "realtime":
            # basis_at만 있어도 사용 규칙·정규화 검증이 끝난 것은 아니다.
            verified = any(
                item.realtime_usable and _matches_source(item, source)
                for item in evidence
            )
            if not verified:
                return None
        elif source.basis == "schedule" and source.basis_at is None:
            warning = DataWarning(
                code="SOURCE_BASIS_UNKNOWN",
                message=(
                    "시간표 기준시각은 확인되지 않았습니다. "
                    f"자료의 적용 운행일은 {source.service_date.isoformat()}입니다."
                ),
            )
            if warning not in warnings:
                warnings.append(warning)

        if source.basis == "schedule":
            for item in evidence:
                if item.basis not in ("static", "schedule") or not _matches_source(
                    item, source
                ):
                    continue
                fields = (
                    ("기준일", item.reference_date),
                    ("개정", item.revision),
                    ("적용 시작일", item.valid_from),
                    ("적용 종료일", item.valid_until),
                )
                details = "; ".join(
                    f"{label}: {value}" for label, value in fields if value is not None
                )
                if details:
                    warning = DataWarning(
                        code="SOURCE_REFERENCE",
                        message=(
                            f"출처 {item.provider}/{item.service}/{item.operation}: "
                            f"{details}"
                        ),
                    )
                    if warning not in warnings:
                        warnings.append(warning)

    return dict(
        option,
        sources=[source.model_dump(mode="json") for source in sources],
        warnings=[warning.model_dump(mode="json") for warning in warnings],
    )


async def search_options(
    provider, request, *, departure_at=None, arrival_deadline=None
):
    modes = request.transport_modes or [request.transport_mode]
    options = []
    for mode in modes:
        result = await provider.search_options(
            origin_place_id=request.origin_place_id,
            destination_place_id=request.destination_place_id,
            departure_at=departure_at,
            arrival_deadline=arrival_deadline,
            transport_mode=mode,
            max_options=request.max_options or 3,
        )
        if not result.ok:
            raise StateError("ROUTING_PROVIDER_UNAVAILABLE", 503)
        if result.data is not None and not isinstance(result.data, list):
            raise StateError("UPSTREAM_RESPONSE_INVALID", 502)
        for option in result.data or []:
            if not isinstance(option, dict):
                raise StateError("UPSTREAM_RESPONSE_INVALID", 502)
            option = _with_verified_sources(option, result.evidence)
            if option is None:
                continue
            if option not in options:
                options.append(option)
    return options
