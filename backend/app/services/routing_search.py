"""Adapt confirmed mode sets to the existing single-mode provider interface."""

from app.services.http_state import StateError


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
            if option not in options:
                options.append(option)
    return options
