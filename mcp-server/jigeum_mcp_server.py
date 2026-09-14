"""지금 MCP 서버 — stdio MCP 서버 (get_capabilities 도구 1개)."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

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
# MCP 서버
# ---------------------------------------------------------------------------
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
        return _error_envelope("ROUTING_PROVIDER_UNAVAILABLE",
                               "백엔드 서버에 연결할 수 없습니다. 잠시 후 다시 시도하거나 데모 모드를 사용하세요.",
                               retryable=True, details=[{"field": "api_base_url", "reason": "CONNECTION_FAILED"}])
    except httpx.TimeoutException:
        return _error_envelope("UPSTREAM_TIMEOUT",
                               "백엔드 응답이 지연되고 있습니다. 잠시 후 다시 시도하세요.",
                               retryable=True, details=[{"field": "api_base_url", "reason": "TIMEOUT"}])
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


def _error_envelope(code: str, message: str, *, retryable: bool, details: list[dict[str, str]]) -> dict[str, Any]:
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


async def main() -> None:
    # stdio MCP 서버 실행. stdout에는 MCP 프로토콜(JSON-RPC)만 기록한다.
    await server.run_stdio_async()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
