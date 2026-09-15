"""표준 라이브러리 unittest 기반 MCP stdio 클라이언트 검증 스크립트.
새 서버 코드를 별도 프로세스로 띄워 MCP 프로토콜 기준으로 확인.
E:\\MABC 및 현재 워크트리 외 절대 경로는 참조하지 않음.
pytest 미설치 환경이므로 unittest + asyncio 사용.
"""
from __future__ import annotations

import asyncio
import json
import sys
import unittest
from typing import Any
from pathlib import Path

# pip를 통한 새 설치는 하지 않음 — mcp-server/requirements.txt 기준 의존성에 의존
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.session import ClientSession
from mcp.types import TextContent

HERE = Path(__file__).resolve().parent
SERVER_PATH = HERE.parent / "jigeum_mcp_server.py"
EXAMPLES_PATH = HERE.parent.parent / "Docs" / "api" / "examples.json"

SERVER_PARAMS = StdioServerParameters(
    command=sys.executable,
    args=[str(SERVER_PATH)],
)


def load_examples() -> list[dict[str, Any]]:
    raw = json.loads(EXAMPLES_PATH.read_text(encoding="utf-8"))
    return list(raw["cases"])


def case(id_: str) -> dict[str, Any]:
    for c in load_examples():
        if c["id"] == id_:
            return c
    raise KeyError(id_)


def text_from(result: Any) -> str | None:
    blocks = getattr(result, "content", None)
    if blocks is None:
        return None
    for block in blocks:
        if isinstance(block, TextContent):
            return block.text
    return None


def norm_payload(obj: dict[str, Any]) -> dict[str, Any]:
    out = dict(obj)
    meta = dict(out.get("meta", {}))

    # 요청마다 바뀌는 필드는 비교에서 제외
    for key in ("request_id", "server_time"):
        meta.pop(key, None)
    out["meta"] = meta

    # summary는 계약상 자유 문장이므로 정규화 비교에서 제외
    data = out.get("data")
    if isinstance(data, dict) and "summary" in data:
        out = dict(out)
        out["data"] = dict(data)
        out["data"].pop("summary", None)
    return out


class TestMcpStdioInterpretTrip(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        if not SERVER_PATH.exists():
            raise unittest.SkipTest(f"서버 파일을 찾지 못함: {SERVER_PATH}")

    async def _session_once(self, fn):
        async with stdio_client(SERVER_PARAMS) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                return await fn(session)

    async def _tool_names(self) -> list[str]:
        async def work(s):
            tools = await s.list_tools()
            return [t.name for t in tools.tools]
        return await self._session_once(work)

    async def _call(self, name: str, arguments: dict[str, Any]) -> dict[str, Any] | None:
        def work(session):
            result = asyncio.run(session.call_tool(name, arguments)) if False else None
            return None
        async def runner(session):
            r = await session.call_tool(name, arguments)
            text = text_from(r)
            if text is None:
                return None
            return json.loads(text)

        return await self._session_once(runner)

    async def test_list_contains_capabilities_and_interpret(self):
        names = await self._tool_names()
        self.assertIn("get_capabilities", names)
        self.assertIn("interpret_trip", names)

    async def test_interpret_needs_confirmation(self):
        c = case("interpret_needs_confirmation")
        payload = await self._call("interpret_trip", c["request"])
        expected = c["response"]

        self.assertIsNotNone(payload)
        self.assertEqual(payload.get("status"), "needs_confirmation")
        self.assertIsNone(payload.get("error"))
        self.assertTrue(payload.get("meta", {}).get("is_demo"))

        data = payload.get("data")
        self.assertIsInstance(data, dict)
        self.assertFalse(data.get("ready_for_plan"))
        self.assertIn("missing_fields", data)
        self.assertIn("questions", data)
        self.assertIn("draft", data)
        self.assertIn("applied_defaults", data)
        self.assertIn("summary", data)

        self.assertEqual(norm_payload(payload), norm_payload(expected))

    async def test_interpret_ready(self):
        c = case("interpret_ready")
        payload = await self._call("interpret_trip", c["request"])
        expected = c["response"]

        self.assertIsNotNone(payload)
        self.assertEqual(payload.get("status"), "ok")
        self.assertIsNone(payload.get("error"))
        self.assertTrue(payload.get("meta", {}).get("is_demo"))

        data = payload.get("data")
        self.assertIsInstance(data, dict)
        self.assertTrue(data.get("ready_for_plan"))
        self.assertEqual(data.get("missing_fields"), [])
        self.assertEqual(data.get("questions"), [])
        self.assertIn("draft", data)
        self.assertIn("applied_defaults", data)
        self.assertIn("summary", data)

        self.assertEqual(norm_payload(payload), norm_payload(expected))

    async def test_empty_text_rejected(self):
        payload = await self._call(
            "interpret_trip",
            {
                "text": "",
                "reference_time": "2026-09-13T18:00:00+09:00",
                "timezone": "Asia/Seoul",
                "context": None,
            },
        )
        self.assertIsNotNone(payload)
        self.assertEqual(payload.get("status"), "error")
        self.assertIsNone(payload.get("data"))
        error = payload.get("error")
        self.assertIsInstance(error, dict)
        self.assertIn("text는 필수 문자열", error.get("message", ""))

    async def test_top_level_keys_contract(self):
        c = case("interpret_ready")
        payload = await self._call("interpret_trip", c["request"])
        allowed = {"status", "data", "error", "meta"}
        unexpected = set(payload.keys()) - allowed
        self.assertEqual(unexpected, set(), f"허용되지 않은 최상위 필드: {sorted(unexpected)}")


if __name__ == "__main__":
    unittest.main()
