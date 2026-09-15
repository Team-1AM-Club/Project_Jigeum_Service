"""지금 MCP 서버 — stdio MCP 서버 (get_capabilities, interpret_trip, search_places 도구)."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

import json
import httpx
from mcp.server.mcpserver import MCPServer


# ---------------------------------------------------------------------------
# 데모 fixture — Docs/api/examples.json 의 capabilities 케이스 응답
# (백엔드 없이 standalone MCP 데모 실행을 위한 내장 응답)
# ---------------------------------------------------------------------------

CAPABILITIES_DEMO_RESPONSE: dict[str, Any] = {
    "status": "ok",
    "data": {
        "timezone": "Asia/Seoul",
        "place_search": {"available": True},
        "interpretation": {"available": True},
        "appointment": {"available": True, "time_basis": "arrival_time_search"},
        "last_journey": {
            "available": True,
            "scope_note": "가상 노선 A만 사용하는 시연 범위",
            "service_date_from": "2026-09-12",
            "service_date_to": "2026-09-13",
        },
        "transport_modes": ["subway", "bus"],
        "max_options": 3,
        "defaults": {
            "arrival_preference_minutes": 0,
            "transport_modes": ["subway", "bus"],
        },
        "buffer_policy": {"version": "demo-v1", "label": "시연용 정책"},
        "limitations": ["가상 시연용 응답입니다. 실제 서버의 지원 범위와 다릅니다."],
    },
    "error": None,
    "meta": {
        "request_id": "fixture-capabilities",
        "server_time": "2026-09-13T18:00:00+09:00",
        "api_version": "v1",
        "is_demo": True,
    },
}


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _request_id() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# search_places 데모 응답 — Docs/api/examples.json 의 places_found 케이스 계약
# (백엔드·실제 장소 제공자 없이 서버에서 자급하는 결정적 시연 응답)
# ---------------------------------------------------------------------------

SEARCH_PLACES_DEMO_RESPONSE: dict[str, Any] = {
    "status": "ok",
    "data": {
        "query": "테스트",
        "places": [
            {
                "place_id": "fixture:place-a",
                "name": "테스트 A역 1번 출구",
                "address": "서울 내 가상 출발 지점",
                "latitude": 37.5,
                "longitude": 126.95,
            },
            {
                "place_id": "fixture:place-b",
                "name": "테스트 B역 2번 출구",
                "address": "서울 내 가상 도착 지점",
                "latitude": 37.51,
                "longitude": 127.02,
            },
        ],
        "source": {
            "provider": "fixture",
            "retrieved_at": "2026-09-13T18:00:00+09:00",
        },
        "has_more": False,
    },
    "error": None,
    "meta": {
        "request_id": "fixture-places_found",
        "server_time": "2026-09-13T18:00:00+09:00",
        "api_version": "v1",
        "is_demo": True,
    },
}


def _validate_search_places_query(raw: Any) -> str:
    """search_places의 query 투입 계약 검증.

    - 필수 문자열
    - 앞뒤 공백 제거 후 1~100자
    """

    if not isinstance(raw, str):
        raise RuntimeError("query는 필수 문자열입니다.")
    query = raw.strip()
    if query == "":
        raise RuntimeError("query는 공백 제거 후 1자 이상이어야 합니다.")
    if len(query) > 100:
        raise RuntimeError("query는 공백 제거 후 100자 이하여야 합니다.")
    return query


def _validate_search_places_limit(raw: Any, default: int = 5) -> int:
    """search_places의 limit 투입 계약 검증.

    - 생략 시 기본 5
    - 정수 1~10
    - 그 외(0, 음수, 11 이상, 정수 아닌 값)는 VALIDATION_ERROR
    """

    if raw is None:
        return default
    # bool은 int의 서브클래스이므로 type()으로 엄격히 체크
    if type(raw) is not int:
        raise RuntimeError("limit는 정수여야 합니다.")
    if raw < 1 or raw > 10:
        raise RuntimeError("limit는 1~10의 정수여야 합니다.")
    return raw


def _search_places_demo(query: str, limit: int) -> dict[str, Any]:
    """examples.json places_found 케이스와 정확히 일치하는 요청에는 해당 fixture
    응답을 반환한다.

    그 외 유효 입력은 빈 결과(places=[])를 반환한다.
    실제 장소 제공자·좌표 새로 만들기를 사용하지 않는다.
    """

    normalized_query = (query or "").strip()
    if normalized_query == "테스트" and limit == 5:
        return SEARCH_PLACES_DEMO_RESPONSE
    return {
        "status": "ok",
        "data": {
            "query": normalized_query,
            "places": [],
            "source": {
                "provider": "fixture",
                "retrieved_at": "2026-09-13T18:00:00+09:00",
            },
            "has_more": False,
        },
        "error": None,
        "meta": {
            "request_id": _request_id(),
            "server_time": _now_iso(),
            "api_version": "v1",
            "is_demo": True,
        },
    }


# ---------------------------------------------------------------------------
# interpret_trip 데모 응답 — Docs/api/examples.json 의 interpret 케이스 2건 계약
# (백엔드·AI·장소 검색 없이 서버에서 자급하는 결정적 시연 응답)
# ---------------------------------------------------------------------------

INTERPRET_NEEDS_CONFIRMATION_REQUEST: dict[str, Any] = {
    "text": "오늘 오후 7시까지 테스트 B역 2번 출구에 도착해야 해. 집에서 출발할 거야.",
    "reference_time": "2026-09-13T18:00:00+09:00",
    "timezone": "Asia/Seoul",
    "context": None,
}

INTERPRET_NEEDS_CONFIRMATION_RESPONSE: dict[str, Any] = {
    "status": "needs_confirmation",
    "data": {
        "draft": {
            "kind": "appointment",
            "origin": {
                "query": "집",
                "place": None,
                "confirmed": False,
            },
            "destination": {
                "query": "테스트 B역 2번 출구",
                "place": None,
                "confirmed": False,
            },
            "arrival_deadline": "2026-09-13T19:00:00+09:00",
            "arrival_preference_minutes": None,
            "service_date": None,
            "transport_modes": None,
            "ambiguities": [],
        },
        "ready_for_plan": False,
        "missing_fields": ["origin.place_id", "destination.place_id"],
        "questions": [
            {
                "field": "origin.place_id",
                "type": "place_search",
                "prompt": "출발 기준으로 사용할 가까운 역·정류장이나 건물 출입구를 선택해 주세요.",
                "options": [],
            },
            {
                "field": "destination.place_id",
                "type": "place_search",
                "prompt": "테스트 B역 2번 출구의 검색 결과를 선택해 주세요.",
                "options": [],
            },
        ],
        "applied_defaults": [],
        "summary": "도착 마감은 오늘 19:00입니다. 출발지와 목적지의 위치 선택이 필요합니다.",
    },
    "error": None,
    "meta": {
        "request_id": "fixture-interpret_needs_confirmation",
        "server_time": "2026-09-13T18:00:00+09:00",
        "api_version": "v1",
        "is_demo": True,
    },
}

INTERPRET_READY_REQUEST: dict[str, Any] = {
    "text": "이동 조건을 정리해줘.",
    "reference_time": "2026-09-13T18:00:00+09:00",
    "timezone": "Asia/Seoul",
    "context": {
        "kind": "appointment",
        "origin": {
            "query": "테스트 A역 1번 출구",
            "place": {
                "place_id": "fixture:place-a",
                "name": "테스트 A역 1번 출구",
                "address": "서울 내 가상 출발 지점",
                "latitude": 37.5,
                "longitude": 126.95,
            },
            "confirmed": True,
        },
        "destination": {
            "query": "테스트 B역 2번 출구",
            "place": {
                "place_id": "fixture:place-b",
                "name": "테스트 B역 2번 출구",
                "address": "서울 내 가상 도착 지점",
                "latitude": 37.51,
                "longitude": 127.02,
            },
            "confirmed": True,
        },
        "arrival_deadline": "2026-09-13T19:00:00+09:00",
        "arrival_preference_minutes": 10,
        "service_date": None,
        "transport_modes": ["subway", "bus"],
        "ambiguities": [],
    },
}

INTERPRET_READY_RESPONSE: dict[str, Any] = {
    "status": "ok",
    "data": {
        "draft": {
            "kind": "appointment",
            "origin": {
                "query": "테스트 A역 1번 출구",
                "place": {
                    "place_id": "fixture:place-a",
                    "name": "테스트 A역 1번 출구",
                    "address": "서울 내 가상 출발 지점",
                    "latitude": 37.5,
                    "longitude": 126.95,
                },
                "confirmed": True,
            },
            "destination": {
                "query": "테스트 B역 2번 출구",
                "place": {
                    "place_id": "fixture:place-b",
                    "name": "테스트 B역 2번 출구",
                    "address": "서울 내 가상 도착 지점",
                    "latitude": 37.51,
                    "longitude": 127.02,
                },
                "confirmed": True,
            },
            "arrival_deadline": "2026-09-13T19:00:00+09:00",
            "arrival_preference_minutes": 10,
            "service_date": None,
            "transport_modes": ["subway", "bus"],
            "ambiguities": [],
        },
        "ready_for_plan": True,
        "missing_fields": [],
        "questions": [],
        "applied_defaults": [],
        "summary": "오늘 19:00까지 테스트 B역 2번 출구 도착, 10분 전 도착 선호",
    },
    "error": None,
    "meta": {
        "request_id": "fixture-interpret_ready",
        "server_time": "2026-09-13T18:00:00+09:00",
        "api_version": "v1",
        "is_demo": True,
    },
}


def _request_matches(a: dict[str, Any], b: dict[str, Any]) -> bool:
    return (
        a.get("text") == b.get("text")
        and a.get("reference_time") == b.get("reference_time")
        and a.get("timezone") == b.get("timezone")
        and _json_stable(a.get("context")) == _json_stable(b.get("context"))
    )


def _json_stable(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True)


def _validate_interpret_text(raw: Any) -> str:
    """interpret_trip의 text 투입 계약 검증.

    - 필수 문자열
    - 1~2000자
    """
    if not isinstance(raw, str) or raw == "":
        raise RuntimeError("text는 필수 문자열입니다.")
    if len(raw) > 2000:
        raise RuntimeError("text는 2000자 이하여야 합니다.")
    return raw.strip()


def _interpret_demo(request: dict[str, Any]) -> dict[str, Any]:
    """examples.json interpret 케이스 2건과 정확히 일치할 때만 해당 응답을 반환.

    그 외 입력은 동일한 setup에서 input validation을 통과한 경우,
    계약된 데모 응답 중 interpret_needs_confirmation 응답을 기본값으로 반환한다.
    실제 AI·장소 검색·대화 상태는 사용하지 않는다.
    """
    if _request_matches(request, INTERPRET_READY_REQUEST):
        return INTERPRET_READY_RESPONSE
    return INTERPRET_NEEDS_CONFIRMATION_RESPONSE


server = MCPServer(
    name="jigeum",
    version="0.1.0",
    description="지금(Jigeum) 이동 판단 MCP 서버 — 사용자 조건 확인·후보 선택 흐름을 위한 도구.",
)


def _capabilities_demo() -> dict[str, Any]:
    return CAPABILITIES_DEMO_RESPONSE


def _capabilities_http(base_url: str, timeout_seconds: int = 15) -> dict[str, Any]:
    """HTTP 모드: Base URL + /capabilities 호출.

    Base URL은 /api/v1을 포함한 전체 접두사(예: https://api.example.com/api/v1)를
    사용한다. API_SPEC.md의 Base URL 정의(주소 + /api/v1)에 맞춘다.
    MCP 서버는 여기에 /capabilities를 붙여 GET /api/v1/capabilities를 호출한다.
    Base URL에 /api/v1이 빠져 있으면 경로가 맞지 않을 수 있다.
    """
    if not base_url:
        raise RuntimeError("JIGEUM_API_BASE_URL이 설정되지 않았습니다.")

    url = base_url.rstrip("/") + "/capabilities"
    timeout = int(os.environ.get("JIGEUM_API_TIMEOUT", str(timeout_seconds)))

    try:
        resp = httpx.get(url, timeout=timeout, headers={"Accept": "application/json"})
    except httpx.ConnectError:
        return _error_envelope(
            "ROUTING_PROVIDER_UNAVAILABLE",
            "백엔드 서버에 연결할 수 없습니다. 잠시 후 다시 시도하거나 데모 모드를 사용하세요.",
            retryable=True,
            details=[{"field": "api_base_url", "reason": "CONNECTION_FAILED"}],
        )
    except httpx.TimeoutException:
        return _error_envelope(
            "UPSTREAM_TIMEOUT",
            "백엔드 응답이 지연되고 있습니다. 잠시 후 다시 시도하세요.",
            retryable=True,
            details=[{"field": "api_base_url", "reason": "TIMEOUT"}],
        )
    except httpx.HTTPError:
        return _error_envelope(
            code="UPSTREAM_RESPONSE_INVALID",
            message="백엔드 연결 중 오류가 발생했습니다.",
            retryable=True,
            details=[{"field": "api_base_url", "reason": "HTTP_ERROR"}],
        )

    if resp.status_code != 200:
        # 백엔드가 오류 envelope를 함께 반환했을 수 있으므로 body를 먼저 확인한다.
        try:
            body = resp.json()
        except Exception:
            body = None
        if isinstance(body, dict) and body.get("status") == "error" and isinstance(body.get("error"), dict):
            return body
        return _error_envelope(
            code="UPSTREAM_RESPONSE_INVALID",
            message=f"백엔드가 예상치 못한 상태 코드 {resp.status_code}를 반환했습니다.",
            retryable=False,
            details=[{"field": "status_code", "reason": str(resp.status_code)}],
        )

    try:
        body = resp.json()
    except Exception:
        return _error_envelope(
            code="UPSTREAM_RESPONSE_INVALID",
            message="백엔드가 유효한 JSON을 반환하지 않았습니다.",
            retryable=False,
            details=[{"field": "content_type", "reason": "INVALID_JSON"}],
        )

    if not isinstance(body, dict):
        return _error_envelope(
            code="UPSTREAM_RESPONSE_INVALID",
            message="백엔드 응답 형식이 계약(JSON 객체)과 다릅니다.",
            retryable=False,
            details=[{"field": "response", "reason": "NOT_OBJECT"}],
        )

    return body


def _error_envelope(
    code: str,
    message: str,
    *,
    retryable: bool,
    details: list[dict[str, str]],
) -> dict[str, Any]:
    return {
        "status": "error",
        "data": None,
        "error": {
            "code": code,
            "message": message,
            "retryable": retryable,
            "details": details,
        },
        "meta": {
            "request_id": _request_id(),
            "server_time": _now_iso(),
            "api_version": "v1",
            "is_demo": False,
        },
    }


@server.tool(description="지원 교통수단·지역·운행일·기본값·데이터 상태를 확인한다.")
def get_capabilities(mode: Literal["demo", "http"] = "demo") -> dict[str, Any]:
    """지원 교통수단·지역·운행일·기본값·데이터 상태를 확인한다.

    Args:
        mode: "demo" (내장 시연 응답) 또는 "http" (백엔드 /api/v1/capabilities 호출).

    Returns:
        API_SPEC 공통 응답 envelope: {status, data, error, meta}.
        - demo: meta.is_demo=true, 고정 시연 데이터.
        - http 성공: 백엔드 응답을 그대로 전달.
        - http 실패: 데모 응답으로 자동 대체하지 않고 error envelope를 반환.
    """
    if mode == "demo":
        return _capabilities_demo()
    if mode == "http":
        base_url = os.environ.get("JIGEUM_API_BASE_URL", "")
        try:
            return _capabilities_http(base_url)
        except RuntimeError as e:
            return _error_envelope(
                code="INTERNAL_ERROR",
                message=str(e),
                retryable=False,
                details=[{"field": "api_base_url", "reason": "NOT_CONFIGURED"}],
            )
    # 도달 불가 — Literal로 제한되므로 정상 흐름에서 발생하지 않음
    return _error_envelope(
        code="INVALID_ARGUMENT",
        message="mode는 'demo' 또는 'http'여야 합니다.",
        retryable=False,
        details=[{"field": "mode", "reason": "OUT_OF_RANGE"}],
    )


@server.tool(
    description="자연어 이동 요청을 구조화하고 부족한 조건을 확인한다. MCP 데모 응답을 위해 examples.json interpret 케이스 2건과 정확히 일치하는 요청에는 해당 fixture 응답을 반환한다."
)
def interpret_trip(
    text: str,
    reference_time: str,
    timezone: str,
    context: dict | None = None,
) -> dict[str, Any]:
    """자연어 이동 요청을 구조화하고 부족한 조건을 확인한다.

    Args:
        text: 사용자 자연어 요청(1~2000자).
        reference_time: 해석 기준 시각.
        timezone: Asia/Seoul.
        context: 이전 TripDraft 또는 null.

    Returns:
        API_SPEC 공통 응답 envelope: {status, data, error, meta}.
        - examples.json interpret 케이스 2건과 일치하는 요청에만 해당 fixture 응답을 반환.
        - 그 외 유효 입력: interpret_needs_confirmation 데모 응답을 반환.
        - text 투입 계약 위반 시: VALIDATION_ERROR envelope 반환.
        실제 AI·장소 검색·대화 상태는 사용하지 않는다.
    """
    try:
        validated = _validate_interpret_text(text)
    except RuntimeError as e:
        return _error_envelope(
            code="VALIDATION_ERROR",
            message=str(e),
            retryable=False,
            details=[{"field": "text", "reason": "OUT_OF_RANGE"}],
        )
    request = {
        "text": validated,
        "reference_time": reference_time,
        "timezone": timezone,
        "context": context,
    }
    return _interpret_demo(request)


@server.tool(
    description=(
        "장소 검색 후보를 반환한다. MCP 데모 응답은 examples.json places_found "
        "케이스에 고정돼 있다.\n\n"
        "Args:\n"
        "    query: 장소 검색어(1~100자, 앞뒤 공백 제거 후).\n"
        "    limit: 반환할 최대 후보 수(1~10 정수, 생략 시 5).\n\n"
        "Returns:\n"
        "    API_SPEC 공통 응답 envelope: {status, data, error, meta}.\n"
        "    - examples.json places_found 케이스와 일치하는 요청에만 해당 fixture 응답을 반환.\n"
        "    - 그 외 유효 입력: 빈 결과(places=[]) 데모 응답을 반환.\n"
        "    - query/limit 투입 계약 위반 시: VALIDATION_ERROR envelope 반환.\n"
        "    실제 장소 제공자·좌표 새로 만들기를 사용하지 않는다."
    )
)
def search_places(query: Any, limit: Any | None = None) -> dict[str, Any]:
    """장소 검색 후보를 반환한다.

    Args:
        query: 장소 검색어(1~100자, 앞뒤 공백 제거 후).
        limit: 반환할 최대 후보 수(1~10 정수, 생략 시 5).

    Returns:
        API_SPEC 공통 응답 envelope: {status, data, error, meta}.
        - examples.json places_found 케이스와 일치하는 요청에만 해당 fixture 응답을 반환.
        - 그 외 유효 입력: 빈 결과(places=[]) 데모 응답을 반환.
        - query/limit 투입 계약 위반 시: VALIDATION_ERROR envelope 반환.
        실제 장소 제공자·좌표 새로 만들기를 사용하지 않는다.
    """
    try:
        validated_query = _validate_search_places_query(query)
    except RuntimeError as e:
        return _error_envelope(
            code="VALIDATION_ERROR",
            message=str(e),
            retryable=False,
            details=[{"field": "query", "reason": "OUT_OF_RANGE"}],
        )
    try:
        validated_limit = _validate_search_places_limit(limit)
    except RuntimeError as e:
        return _error_envelope(
            code="VALIDATION_ERROR",
            message=str(e),
            retryable=False,
            details=[{"field": "limit", "reason": "OUT_OF_RANGE"}],
        )
    return _search_places_demo(validated_query, validated_limit)


async def main() -> None:
    # stdio MCP 서버 실행. stdout에는 MCP 프로토콜(JSON-RPC)만 기록한다.
    await server.run_stdio_async()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
