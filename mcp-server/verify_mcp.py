"""MCP stdio 클라이언트 세션 내부 호출 검증: 도구 목록·도구 호출·응답 텍스트 추출.

- MCP stdio 서버 기동
- ClientSession(list_tools, call_tool) 사용 확인
- get_capabilities(demo) 응답 텍스트 추출 및 JSON 파싱
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession
from mcp.types import CallToolResult, TextContent

HERE = Path(__file__).resolve().parent
SERVER_PATH = HERE / "jigeum_mcp_server.py"

FIXTURE = json.loads(
    (HERE / "tests" / "fixtures" / "demo_examples.json").read_text(encoding="utf-8")
)["cases"][1]["response"]


def _text(result: CallToolResult) -> str | None:
    for block in result.content:
        if isinstance(block, TextContent):
            return block.text
    return None


def _norm(p: dict) -> dict:
    meta = dict(p.get("meta", {}))
    meta.pop("request_id", None)
    meta.pop("server_time", None)
    return {**p, "meta": meta}


async def main() -> int:
    params = StdioServerParameters(command=sys.executable, args=[str(SERVER_PATH)])
    try:
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                tools = await session.list_tools()
                tool_list = list(tools.tools)
                print(f"도구 수: {len(tool_list)}")
                for t in tool_list:
                    print(f"- {t.name}: {t.description}")

                if not any(t.name == "get_capabilities" for t in tools.tools):
                    print("FAIL: get_capabilities 도구가 없음")
                    return 1

                call = await session.call_tool("get_capabilities", {"mode": "demo"})
                if call.is_error:
                    print("FAIL: 도구 호출이 error 결과")
                    return 1
                text = _text(call)
                if text is None:
                    print("FAIL: 도구 응답에 텍스트 블록이 없음")
                    return 1
                payload = json.loads(text)
                print("=== demo 응답 ===")
                print(json.dumps(payload, ensure_ascii=False, indent=2))

                if _norm(payload) != _norm(FIXTURE):
                    print("FAIL: demo 응답이 capabilities fixture와 다름")
                    return 1
                print("PASS: demo 응답 == capabilities fixture (request_id/server_time 제외)")
                return 0

    except Exception as e:
        print("예외:", type(e).__name__, str(e)[:400])
        import traceback
        traceback.print_exc()
        return 2


if __name__ == "__main__":
    rc = asyncio.run(main())
    sys.exit(rc)
