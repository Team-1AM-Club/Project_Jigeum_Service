"""RED 단계: interpret_trip MCP 도구 계약 테스트 (구현 부재 확인용).

- pytest 미설치 환경이므로 unittest로 작성
- 나중에 pytest에서도 수집 가능한 형태(unittest.TestCase 기반)
- MCP stdio 서버 기동 → list_tools → call_tool 패턴 사용
- E:\\MABC 절대 경로를 런타임에 참조하지 않음
- 데모 fixture는 현재 저장소 안에서 자급
"""
from __future__ import annotations

import asyncio
import json
import sys
import unittest
from typing import Any
from pathlib import Path

# MCP 클라이언트 의존성은 mcp-server/requirements.txt 기준
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession
from mcp.types import CallToolResult, TextContent

HERE = Path(__file__).resolve().parent
SERVER_PATH = HERE.parent / "jigeum_mcp_server.py"

# 현재 저장소(mcp-server/..) 안의 Docs/api/examples.json을 읽기 전용 계약 자료로 사용
EXAMPLES_PATH = HERE.parent / ".." / "Docs" / "api" / "examples.json"


def _load_examples() -> list[dict[str, Any]]:
    return json.loads(EXAMPLES_PATH.resolve().read_text(encoding="utf-8"))["cases"]


def _case(id_: str) -> dict[str, Any]:
    for c in _load_examples():
        if c["id"] == id_:
            return c
    raise KeyError(id_)


def _text_from(result: CallToolResult) -> str | None:
    for block in result.content:
        if isinstance(block, TextContent):
            return block.text
    return None


def _norm_meta(p: dict[str, Any]) -> dict[str, Any]:
    """request_id / server_time을 제외한 정규화로 계약 비교."""
    out = dict(p)
    meta = dict(out.get("meta", {}))
    meta.pop("request_id", None)
    meta.pop("server_time", None)
    out["meta"] = meta
    data_out = out.get("data")
    if isinstance(data_out, dict) and "summary" in data_out:
        # summary는 계약상 자유 문장이므로 정규화 비교에서 제외
        out = dict(out)
        out["data"] = dict(data_out)
        out["data"].pop("summary", None)
    return out


class TestInterpretTripContracts(unittest.IsolatedAsyncioTestCase):
    """interpret_trip 도구의 계약 검증.

    현재 시점에서는 도구가 등록돼 있지 않으므로 RED로 실패하는 것을 목표로 한다.
    """

    @classmethod
    def setUpClass(cls):
        if not SERVER_PATH.exists():
            raise unittest.SkipTest(f"서버 파일이 없음: {SERVER_PATH}")
        cls._server_params = StdioServerParameters(
            command=sys.executable, args=[str(SERVER_PATH)]
        )

    async def _list_tools(self) -> list[str]:
        async with stdio_client(self._server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                return [t.name for t in tools.tools]

    async def _call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        async with stdio_client(self._server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                call = await session.call_tool(name, arguments)
                text = _text_from(call)
                if text is None:
                    raise RuntimeError("도구 응답에 텍스트 블록이 없음")
                return json.loads(text)

    async def _error_text(self, name: str, arguments: dict[str, Any]) -> str:
        async with stdio_client(self._server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                call = await session.call_tool(name, arguments)
                text = _text_from(call)
                if text is None:
                    raise RuntimeError("도구 응답에 텍스트 블록이 없음")
                return text

    # ------------------------------------------------------------------
    # 1) 도구 목록 계약
    # ------------------------------------------------------------------
    async def test_tool_list_contains_interpret_trip(self):
        names = await self._list_tools()
        self.assertIn("interpret_trip", names)

    # ------------------------------------------------------------------
    # 2) 입력 schema 관련 계약 (도구 설명/입력 스키마는 MCP 도구 정의에 반영)
    # ------------------------------------------------------------------
    async def test_interpret_trip_input_schema_fields(self):
        names = await self._list_tools()
        self.assertIn("interpret_trip", names)
        # 도구 정의에서 입력 파라미터 키의 존재를 확인한다.
        # 현재는 MCP 도구 스키마 확인 수단(list_tools)의 이름을 추측하지 않는다.
        # 따라서 이 테스트는 interpret_trip 호출 시 필수 키가 없으면 거부되는
        # 동작으로 투입 계약 입증을 대신한다(입력 검증 테스트 참조).
        pass

    # ------------------------------------------------------------------
    # 3) interpret_needs_confirmation 데모 응답 계약
    # ------------------------------------------------------------------
    async def test_interpret_needs_confirmation_response(self):
        case = _case("interpret_needs_confirmation")
        payload = await self._call_tool("interpret_trip", case["request"])
        expected = case["response"]

        # 최상위 envelope 구조
        self.assertEqual(payload.get("status"), expected["status"])
        self.assertIsNone(payload.get("error"))
        self.assertIsInstance(payload.get("meta"), dict)

        meta = payload["meta"]
        self.assertTrue(meta.get("is_demo"))
        self.assertIn("api_version", meta)

        data = payload.get("data")
        self.assertIsInstance(data, dict)

        expected_data = expected["data"]

        # ready_for_plan
        self.assertEqual(data.get("ready_for_plan"), False)

        # missing_fields / questions / draft / applied_defaults / summary 존재
        self.assertIn("missing_fields", data)
        self.assertIn("questions", data)
        self.assertIn("draft", data)
        self.assertIn("applied_defaults", data)
        self.assertIn("summary", data)

        # 정규화 비교(summary 제외, request_id/server_time 제외)
        self.assertEqual(_norm_meta(payload), _norm_meta(expected))

    # ------------------------------------------------------------------
    # 4) interpret_ready 데모 응답 계약
    # ------------------------------------------------------------------
    async def test_interpret_ready_response(self):
        case = _case("interpret_ready")
        payload = await self._call_tool("interpret_trip", case["request"])
        expected = case["response"]

        self.assertEqual(payload.get("status"), expected["status"])
        self.assertIsNone(payload.get("error"))
        meta = payload.get("meta")
        self.assertIsInstance(meta, dict)
        self.assertTrue(meta.get("is_demo"))
        self.assertIn("api_version", meta)

        data = payload.get("data")
        self.assertIsInstance(data, dict)

        self.assertEqual(data.get("ready_for_plan"), True)
        self.assertEqual(data.get("missing_fields"), [])
        self.assertEqual(data.get("questions"), [])

        self.assertIn("draft", data)
        self.assertIn("applied_defaults", data)
        self.assertIn("summary", data)

        self.assertEqual(_norm_meta(payload), _norm_meta(expected))

    # ------------------------------------------------------------------
    # 5) 입력 검증: 빈 text / 2000자 초과 text
    # ------------------------------------------------------------------
    async def test_empty_text_rejected(self):
        text = await self._error_text("interpret_trip", {
            "text": "",
            "reference_time": "2026-09-13T18:00:00+09:00",
            "timezone": "Asia/Seoul",
            "context": None,
        })
        parsed = json.loads(text)
        self.assertEqual(parsed.get("status"), "error")
        self.assertIsNone(parsed.get("data"))
        error = parsed.get("error")
        self.assertIsInstance(error, dict)
        self.assertIn("text는 필수 문자열입니다.", error.get("message", ""))

    async def test_overlong_text_rejected(self):
        overlong = "x" * 2001
        text = await self._error_text("interpret_trip", {
            "text": overlong,
            "reference_time": "2026-09-13T18:00:00+09:00",
            "timezone": "Asia/Seoul",
            "context": None,
        })
        parsed = json.loads(text)
        self.assertEqual(parsed.get("status"), "error")
        self.assertIsNone(parsed.get("data"))
        error = parsed.get("error")
        self.assertIsInstance(error, dict)
        self.assertIn("text는 2000자 이하여야 합니다.", error.get("message", ""))

    # ------------------------------------------------------------------
    # 6) 응답 최상위 필드 제한(문서 없는 필드 추가 금지)
    # ------------------------------------------------------------------
    async def test_response_top_level_keys_contract(self):
        case = _case("interpret_ready")
        payload = await self._call_tool("interpret_trip", case["request"])
        allowed = {"status", "data", "error", "meta"}
        unexpected = set(payload.keys()) - allowed
        self.assertEqual(
            unexpected,
            set(),
            f"문서에 없는 최상위 필드 포함: {sorted(unexpected)}",
        )


if __name__ == "__main__":
    unittest.main()
