"""RED 단계: get_capabilities HTTP 모드에서 JIGEUM_API_TIMEOUT 파싱 결함 검증.

- pytest 미설치 환경이므로 unittest로 작성
- MCP stdio 서버를 별도 프로세스로 띄워 call_tool 패턴 사용
- 환경변수 JIGEUM_API_TIMEOUT이 비정수일 때 ValueError가 서버 프로세스 밖으로
  전파되어 세션이 끊기는 현상을 재현한다.
- 유효한 정수 timeout은 그대로 전달되고, 비정수/빈 문자열은 기본값으로
  안전하게 대체되어야 한다.
- 테스트용 mock HTTP 서버를 통해 유효한 timeout 전달도 검증한다.
- 환경변수와 mock서버는 각 테스트 후 복구/종료된다.
- subprocess/stdio 서버는 finally 등에서 반드시 종료된다.
"""

from __future__ import annotations

import asyncio
import http.server
import json
import os
import socket
import sys
import threading
import unittest
from typing import Any
from pathlib import Path

from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.session import ClientSession
from mcp.types import TextContent

HERE = Path(__file__).resolve().parent
SERVER_PATH = HERE.parent / "jigeum_mcp_server.py"
EXAMPLES_PATH = HERE.parent.parent / "Docs" / "api" / "examples.json"


def text_from(result: Any) -> str | None:
    """MCP call_tool 결과에서 텍스트 블록을 추출한다."""
    blocks = getattr(result, "content", None)
    if blocks is None:
        return None
    for block in blocks:
        if isinstance(block, TextContent):
            return block.text
    return None


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _start_fake_http_server(port: int, body: dict[str, Any]) -> tuple[threading.Thread, http.server.HTTPServer]:
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/capabilities":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(body).encode("utf-8"))
            else:
                self.send_response(404)
                self.end_headers()

        def logMessage(self, format, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", port), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return thread, server


def _server_params_with_env(extra_env: dict[str, str]) -> StdioServerParameters:
    env = os.environ.copy()
    env.update(extra_env)
    return StdioServerParameters(
        command=sys.executable,
        args=[str(SERVER_PATH)],
        env=env,
    )


async def _call_get_capabilities_http(server_params: StdioServerParameters) -> dict[str, Any] | None:
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("get_capabilities", {"mode": "http"})
            text = text_from(result)
            if text is None:
                return None
            return json.loads(text)


class TestGetCapabilitiesEnv(unittest.IsolatedAsyncioTestCase):
    """get_capabilities HTTP 모드의 환경변수 파싱과 복구 검증."""

    async def test_invalid_timeout_does_not_break_session(self):
        """JIGEUM_API_TIMEOUT="foo"일 때 ValueError가 세션 밖으로 전파되지 않아야 한다.

        현재는 int(...) 변환에서 ValueError가 발생해 툴 호출이 실패한다.
        수정 후에는 기본 타임아웃으로 대체하고, 가짜 서버 응답을 받아온다.
        """
        port = _free_port()
        thread, server = _start_fake_http_server(port, {"status": "ok"})
        try:
            params = _server_params_with_env(
                {
                    "JIGEUM_API_BASE_URL": f"http://127.0.0.1:{port}",
                    "JIGEUM_API_TIMEOUT": "foo",
                }
            )
            payload = await _call_get_capabilities_http(params)
            self.assertIsNotNone(
                payload,
                "get_capabilities 호출 결과가 없음 — 서버가 ValueError로 중단됐을 가능성이 있음",
            )
            self.assertEqual(payload.get("status"), "ok")
            self.assertEqual(payload.get("data"), {"status": "ok"})
        finally:
            server.shutdown()
            thread.join(timeout=2)

    async def test_valid_timeout_is_used(self):
        """JIGEUM_API_TIMEOUT=42일 때 타임아웃이 그대로 전달되고 정상 응답을 받는다."""
        port = _free_port()
        capabilities_body = {
            "status": "ok",
            "data": {"timezone": "Asia/Seoul"},
            "error": None,
            "meta": {"api_version": "v1", "is_demo": False},
        }
        thread, server = _start_fake_http_server(port, capabilities_body)
        try:
            params = _server_params_with_env(
                {
                    "JIGEUM_API_BASE_URL": f"http://127.0.0.1:{port}",
                    "JIGEUM_API_TIMEOUT": "42",
                }
            )
            payload = await _call_get_capabilities_http(params)
            self.assertIsNotNone(payload)
            self.assertEqual(payload.get("status"), "ok")
            self.assertEqual(payload.get("data"), {"timezone": "Asia/Seoul"})
            self.assertFalse(payload.get("meta", {}).get("is_demo"))
        finally:
            server.shutdown()
            thread.join(timeout=2)

    async def test_empty_timeout_falls_back_to_default(self):
        """JIGEUM_API_TIMEOUT이 빈 문자열이면 기본값 15로 대체된다."""
        port = _free_port()
        thread, server = _start_fake_http_server(port, {"status": "ok"})
        try:
            params = _server_params_with_env(
                {
                    "JIGEUM_API_BASE_URL": f"http://127.0.0.1:{port}",
                    "JIGEUM_API_TIMEOUT": "",
                }
            )
            payload = await _call_get_capabilities_http(params)
            self.assertIsNotNone(payload)
            self.assertEqual(payload.get("status"), "ok")
            self.assertEqual(payload.get("data"), {"status": "ok"})
        finally:
            server.shutdown()
            thread.join(timeout=2)

    async def test_env_isolation(self):
        """테스트에서 설정한 환경변수가 다른 테스트에 누출되지 않는다."""
        port = _free_port()
        thread, server = _start_fake_http_server(port, {"status": "ok"})
        try:
            params = _server_params_with_env(
                {
                    "JIGEUM_API_BASE_URL": f"http://127.0.0.1:{port}",
                    "JIGEUM_API_TIMEOUT": "99",
                }
            )
            payload = await _call_get_capabilities_http(params)
            self.assertIsNotNone(payload)
            self.assertEqual(payload.get("status"), "ok")
        finally:
            server.shutdown()
            thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
