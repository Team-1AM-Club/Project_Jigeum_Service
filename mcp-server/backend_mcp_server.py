"""Stateful backend contract exposed over MCP; no fixture fallback."""
from __future__ import annotations

import os
from typing import Any
from urllib.parse import quote
from uuid import uuid4

import httpx
from mcp.server.mcpserver import MCPServer

server = MCPServer(name='jigeum', version='0.2.0', description=(
    '이동 조건 해석 후 사용자에게 조건을 보여주고 명시적으로 동의받아 confirm_trip을 호출한다. '
    'meta.conversation_id와 최신 meta.revision을 다음 호출에 전달한다. '
    'HTTP 연결도 현재 백엔드는 mock 데이터다. 후보 선택과 재탐색 적용은 사용자 결정이다.'
))


def _error(code: str, message: str, retryable: bool = False) -> dict[str, Any]:
    # Import lazily: demo module owns envelope formatting, not HTTP routing.
    from jigeum_mcp_server import _error_envelope
    return _error_envelope(code, message, retryable=retryable, details=[])


def _request(method: str, path: str, *, body=None, params=None) -> dict[str, Any]:
    base = os.environ.get('JIGEUM_API_BASE_URL', '').rstrip('/')
    if not base:
        return _error('INTERNAL_ERROR', 'JIGEUM_API_BASE_URL(/api/v1 포함)을 설정하세요.')
    try:
        timeout = float(os.environ.get('JIGEUM_API_TIMEOUT', '15'))
        if not 0 < timeout <= 120:
            raise ValueError
    except ValueError:
        return _error('INVALID_ARGUMENT', 'JIGEUM_API_TIMEOUT은 0 초과 120 이하 숫자여야 합니다.')
    headers = {'Accept': 'application/json'}
    if method == 'POST':
        headers['Idempotency-Key'] = str(uuid4())
    # Reuse the identical body and key if the first response is lost.
    for attempt in range(2):
        try:
            response = httpx.request(method, base + path, json=body, params=params,
                                     headers=headers, timeout=timeout)
        except (httpx.TransportError, httpx.TimeoutException):
            if attempt == 0:
                continue
            return _error('ROUTING_PROVIDER_UNAVAILABLE', '백엔드 응답을 확인하지 못했습니다.', True)
        except (httpx.HTTPError, ValueError):
            return _error('UPSTREAM_RESPONSE_INVALID', '백엔드 주소 또는 HTTP 응답이 올바르지 않습니다.')
        try:
            envelope = response.json()
        except ValueError:
            envelope = None
        if (not isinstance(envelope, dict)
                or not {'status', 'data', 'error', 'meta'} <= envelope.keys()
                or not isinstance(envelope['meta'], dict)
                or envelope['status'] not in ('ok', 'needs_confirmation', 'unavailable', 'error')
                or (response.is_error and envelope['status'] != 'error')):
            return _error('UPSTREAM_RESPONSE_INVALID', '백엔드 응답이 envelope 계약과 다릅니다.')
        # Preserve domain errors, unavailable, demo flags and state metadata exactly.
        return envelope
    raise AssertionError('unreachable')


@server.tool(description='백엔드 지원 범위와 데이터 상태를 조회한다. is_demo 표시를 사용자에게 전달한다.')
def get_capabilities() -> dict[str, Any]:
    return _request('GET', '/capabilities')


@server.tool(description='장소 후보를 검색한다. 사용자가 선택한 실제 place_id를 조건에 사용한다.')
def search_places(query: str, limit: int = 5) -> dict[str, Any]:
    return _request('GET', '/places', params={'query': query, 'limit': limit})


@server.tool(description=(
    '자연어를 해석한다. context에는 flat 조건(kind, origin_place_id, destination_place_id, '
    'arrival_deadline, arrival_preference_minutes, service_date, transport_modes)을 전달한다. '
    '기존 대화 수정에는 conversation_id와 expected_revision이 모두 필요하다. '
    '반환 조건을 사용자에게 보여주고 동의받기 전 confirm이나 계산을 하지 않는다.'
))
def interpret_trip(text: str, context: dict[str, Any] | None = None,
                   conversation_id: str | None = None,
                   expected_revision: int | None = None) -> dict[str, Any]:
    body = {'natural_language': text, 'context': context or {}}
    if conversation_id is not None:
        body['conversation_id'] = conversation_id
    if expected_revision is not None:
        body['expected_revision'] = expected_revision
    return _request('POST', '/mobility/interpret', body=body)


@server.tool(description=(
    '해석된 출발지·도착지·시간·교통수단 전체를 사용자에게 보여주고 명시적으로 동의받은 뒤 호출한다. '
    'confirmed_data는 해석된 flat 조건이며 변경하려면 먼저 interpret_trip을 다시 호출한다. '
    '사용자 동의 없이 user_confirmed=true를 만들지 않는다.'
))
def confirm_trip(conversation_id: str, expected_revision: int,
                 confirmed_data: dict[str, Any], user_confirmed: bool = False) -> dict[str, Any]:
    if user_confirmed is not True:
        return _error('USER_CONFIRMATION_REQUIRED', '조건 전체에 대한 사용자 확인이 필요합니다.')
    return _request('POST', f'/conversations/{quote(conversation_id, safe="")}/confirm',
                    body={'expected_revision': expected_revision, 'confirmed_data': confirmed_data})


@server.tool(description=(
    'confirm_trip 성공 후 최신 revision과 확정된 flat trip 조건으로 경로 후보를 계산한다. '
    'kind=last_journey이면 막차 API를 호출한다. 반환 후보는 사용자 선택 전 자동 적용하지 않는다.'
))
def plan_journey(trip: dict[str, Any], conversation_id: str,
                 expected_revision: int, max_options: int = 3) -> dict[str, Any]:
    path = '/journeys/plan/last_journey' if trip.get('kind') == 'last_journey' else '/journeys/plan'
    return _request('POST', path, body={**trip, 'conversation_id': conversation_id,
                    'expected_revision': expected_revision, 'max_options': max_options})


@server.tool(description=(
    '사용자가 재탐색을 요청했을 때 대안을 계산한다. 변경된 출발 조건은 먼저 interpret/confirm한다. '
    'previous_plan에는 사용자가 선택한 plan_id, selected_option_id, recommended_leave_at, '
    'estimated_arrival_at을 전달한다. 결과는 사용자가 선택할 때까지 기존 계획에 적용하지 않는다.'
))
def replan_journey(trip: dict[str, Any], conversation_id: str, expected_revision: int,
                   previous_plan: dict[str, Any], current_origin_place_id: str,
                   reason: str, user_confirmed: bool = False,
                   max_options: int = 3) -> dict[str, Any]:
    if user_confirmed is not True:
        return _error('USER_CONFIRMATION_REQUIRED', '재탐색에 대한 사용자 확인이 필요합니다.')
    return _request('POST', '/journeys/replan', body={
        'trip': trip, 'conversation_id': conversation_id, 'expected_revision': expected_revision,
        'previous_plan': previous_plan, 'current_origin_place_id': current_origin_place_id,
        'reason': reason, 'user_confirmed': True, 'max_options': max_options})


async def main() -> None:
    await server.run_stdio_async()


if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
