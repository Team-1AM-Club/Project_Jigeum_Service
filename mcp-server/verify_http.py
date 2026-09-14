"""mcp-server capabilities 계약 검증 + HTTP 모드 처리 확인.

- MCP stdio 서버 기동
- list_tools → get_capabilities 등록 확인
- get_capabilities(demo) 호출: capabilities 응답 구조·타입·상태별 envelope 검증
- get_capabilities(http, 실제 백엔드 없음): 연결 실패 / 비정상 응답 처리 확인
- get_capabilities(http, 가짜 성공 백엔드): 백엔드 응답 envelope 보존 확인
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any

from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession
from mcp.types import CallToolResult, TextContent

HERE = Path(__file__).resolve().parent
SERVER_PATH = HERE / "jigeum_mcp_server.py"

FIXTURE = json.loads(
    (HERE.parent / "Docs" / "api" / "examples.json").read_text(encoding="utf-8")
)["cases"][1]["response"]


# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------

def text_from(result: CallToolResult) -> str | None:
    for block in result.content:
        if isinstance(block, TextContent):
            return block.text
    return None


def norm(p: dict[str, Any]) -> dict[str, Any]:
    meta = dict(p.get("meta", {}))
    meta.pop("request_id", None)
    meta.pop("server_time", None)
    return {**p, "meta": meta}


def validate_capabilities(payload: dict[str, Any]) -> list[str]:
    errs: list[str] = []
    if payload.get("status") != "ok":
        errs.append(f"status가 ok가 아님: {payload.get('status')!r}")
    if payload.get("error") is not None:
        errs.append(f"error가 null이 아님: {payload.get('error')!r}")

    data = payload.get("data")
    if not isinstance(data, dict):
        errs.append(f"data 타입 이상: {type(data)}")
        return errs

    required_data_keys = [
        "timezone", "place_search", "interpretation", "appointment",
        "last_journey", "transport_modes", "max_options", "defaults",
        "buffer_policy", "limitations",
    ]
    for k in required_data_keys:
        if k not in data:
            errs.append(f"data에 필수 키 누락: {k}")

    if data.get("timezone") != "Asia/Seoul":
        errs.append(f"timezone 이상: {data.get('timezone')!r}")

    ps = data.get("place_search")
    if not isinstance(ps, dict) or ps.get("available") is not True:
        errs.append(f"place_search 이상: {ps}")

    if not isinstance(data.get("transport_modes"), list):
        errs.append("transport_modes가 리스트 아님")
    else:
        for m in data["transport_modes"]:
            if m not in ("subway", "bus"):
                errs.append(f"transport_modes에 비정상 값: {m!r}")

    if data.get("max_options") != 3:
        errs.append(f"max_options 이상: {data.get('max_options')!r}")

    defs = data.get("defaults")
    if not isinstance(defs, dict):
        errs.append("defaults가 dict 아님")
    else:
        if defs.get("arrival_preference_minutes") != 0:
            errs.append("defaults.arrival_preference_minutes 이상")
        if not isinstance(defs.get("transport_modes"), list):
            errs.append("defaults.transport_modes가 리스트 아님")

    lim = data.get("limitations")
    if not isinstance(lim, list) or len(lim) == 0:
        errs.append("limitations 이상")

    bp = data.get("buffer_policy")
    if not isinstance(bp, dict):
        errs.append("buffer_policy가 dict 아님")
    else:
        if not isinstance(bp.get("version"), str) or not isinstance(bp.get("label"), str):
            errs.append("buffer_policy 필드 이상")

    # 상태별 envelope: ok이면 data 있음, error null, meta 포함
    meta = payload.get("meta")
    if not isinstance(meta, dict):
        errs.append("meta가 dict 아님")
    else:
        for k in ("api_version", "is_demo"):
            if k not in meta:
                errs.append(f"meta에 {k} 누락")
        if meta.get("is_demo") is not True:
            errs.append("is_demo가 true가 아님")

    return errs


def validate_error_envelope(payload: dict[str, Any], expected_code: str, expect_retryable: bool | None = None) -> list[str]:
    errs: list[str] = []
    if payload.get("status") != "error":
        errs.append(f"status가 error가 아님: {payload.get('status')!r}")
    if payload.get("data") is not None:
        errs.append(f"error 응답인데 data가 null이 아님")
    error = payload.get("error")
    if not isinstance(error, dict):
        errs.append(f"error가 dict 아님: {type(error)}")
        return errs
    if error.get("code") != expected_code:
        errs.append(f"error.code 불일치: 기대 {expected_code!r}, 실제 {error.get('code')!r}")
    if not isinstance(error.get("message"), str):
        errs.append("error.message가 문자열 아님")
    if expect_retryable is not None and error.get("retryable") is not expect_retryable:
        errs.append(f"retryable 불일치: 기대 {expect_retryable}, 실제 {error.get('retryable')}")
    if not isinstance(error.get("details"), list):
        errs.append("error.details가 리스트 아님")

    meta = payload.get("meta")
    if not isinstance(meta, dict):
        errs.append("meta가 dict 아님")
    else:
        if meta.get("is_demo") is not False:
            errs.append("error 응답인데 is_demo가 false가 아님")
        for k in ("request_id", "server_time", "api_version"):
            if k not in meta:
                errs.append(f"error 응답 meta에 {k} 누락")
    return errs


# ---------------------------------------------------------------------------
# 가짜 백엔드 프로세스 관리
# ---------------------------------------------------------------------------

class FakeBackend:
    """임시 HTTP 서버를 별도 프로세스로 띄우고 관리."""

    def __init__(self, port: int, handler_code: str):
        self.port = port
        self.handler_code = handler_code
        self.proc = None

    async def start(self):
        import subprocess
        self.proc = subprocess.Popen(
            [sys.executable, "-c", self.handler_code],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        await asyncio.sleep(0.5)
        return self

    async def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()


def make_handler_success(port: int, fixture: dict):
    body = json.dumps(fixture, ensure_ascii=False, indent=2)
    return f"""
import json
from http.server import HTTPServer, BaseHTTPRequestHandler

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/v1/capabilities":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write({body!r}.encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()
    def log_message(self, *a): pass

HTTPServer(("127.0.0.1", {port}), H).serve_forever()
"""


def make_handler_bad_json(port: int):
    return f"""
from http.server import HTTPServer, BaseHTTPRequestHandler

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/v1/capabilities":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"not json")
        else:
            self.send_response(404)
            self.end_headers()
    def log_message(self, *a): pass

HTTPServer(("127.0.0.1", {port}), H).serve_forever()
"""


def make_handler_non_dict(port: int):
    return f"""
from http.server import HTTPServer, BaseHTTPRequestHandler

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/v1/capabilities":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b"[1,2,3]")
        else:
            self.send_response(404)
            self.end_headers()
    def log_message(self, *a): pass

HTTPServer(("127.0.0.1", {port}), H).serve_forever()
"""


def make_handler_backend_error(port: int):
    body = json.dumps({
        "status": "error",
        "data": None,
        "error": {"code": "ROUTE_NOT_FOUND", "message": "백엔드 측 오류", "retryable": False, "details": []},
        "meta": {"request_id": "backend-err-001", "server_time": "2026-09-13T18:00:00+09:00", "api_version": "v1", "is_demo": False},
    }, ensure_ascii=False)
    return f"""
import json
from http.server import HTTPServer, BaseHTTPRequestHandler

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/v1/capabilities":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write({body!r}.encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()
    def log_message(self, *a): pass

HTTPServer(("127.0.0.1", {port}), H).serve_forever()
"""


def make_handler_slow(port: int, delay: float):
    body = json.dumps({
        "status": "ok",
        "data": {},
        "error": None,
        "meta": {
            "request_id": "slow",
            "server_time": "2026-09-13T18:00:00+09:00",
            "api_version": "v1",
            "is_demo": False,
        },
    }, ensure_ascii=False)
    return f"""
import time
from http.server import HTTPServer, BaseHTTPRequestHandler

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/v1/capabilities":
            time.sleep({delay})
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write({body!r}.encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()
    def log_message(self, *a): pass

HTTPServer(("127.0.0.1", {port}), H).serve_forever()
"""


# ---------------------------------------------------------------------------
# 메인 검증
# ---------------------------------------------------------------------------

async def run_demo_check(session: ClientSession) -> int:
    call = await session.call_tool("get_capabilities", {"mode": "demo"})
    if call.is_error:
        print("FAIL: 도구 호출 자체가 error")
        return 1
    text = text_from(call)
    if text is None:
        print("FAIL: 도구 응답에 텍스트 블록 없음")
        return 1
    payload = json.loads(text)
    errs = validate_capabilities(payload)
    if errs:
        print("FAIL: capabilities 응답 구조 검증 실패")
        for e in errs:
            print(" -", e)
        return 1
    if norm(payload) != norm(FIXTURE):
        print("FAIL: capabilities 응답이 fixture와 다름")
        return 1
    print("PASS: capabilities demo 응답 구조·값 검증 통과")
    return 0


async def run_http_check(base_url: str, timeout_s: int, expect_code: str, expect_retryable: bool | None, label: str) -> int:
    env = {"JIGEUM_API_BASE_URL": base_url, "JIGEUM_API_TIMEOUT": str(timeout_s)}
    params = StdioServerParameters(command=sys.executable, args=[str(SERVER_PATH)], env=env)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as sess:
            await sess.initialize()
            call = await sess.call_tool("get_capabilities", {"mode": "http"})
            if call.is_error:
                print(f"FAIL [{label}]: http 도구 호출 자체가 error")
                return 1
            text = text_from(call)
            if text is None:
                print(f"FAIL [{label}]: http 응답에 텍스트 블록 없음")
                return 1
            payload = json.loads(text)
            errs = validate_error_envelope(payload, expect_code, expect_retryable)
            if errs:
                print(f"FAIL [{label}]: http 오류 envelope 검증 실패")
                for e in errs:
                    print(" -", e)
                return 1
            print(f"PASS [{label}]: code={expect_code}, retryable={expect_retryable}")
            return 0


async def run_http_success_check(port: int, fixture: dict) -> int:
    base_url = f"http://127.0.0.1:{port}/api/v1"
    env = {"JIGEUM_API_BASE_URL": base_url, "JIGEUM_API_TIMEOUT": "5"}
    params = StdioServerParameters(command=sys.executable, args=[str(SERVER_PATH)], env=env)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as sess:
            await sess.initialize()
            call = await sess.call_tool("get_capabilities", {"mode": "http"})
            if call.is_error:
                print("FAIL [http-success]: 도구 호출 자체가 error")
                return 1
            text = text_from(call)
            if text is None:
                print("FAIL [http-success]: 응답에 텍스트 블록 없음")
                return 1
            payload = json.loads(text)
            # 성공 응답은 백엔드 응답을 그대로 전달 → fixture와 같아야 함 (request_id 등 제외)
            # 백엔드가 생성한 request_id를 사용했을 것이므로, request_id/server_time 제외한 비교
            if norm(payload) != norm(fixture):
                print("FAIL [http-success]: 백엔드 응답과 fixture 불일치")
                print("  payload:", json.dumps(payload, ensure_ascii=False))
                print("  fixture:", json.dumps(fixture, ensure_ascii=False))
                return 1
            print("PASS [http-success]: 백엔드 응답 envelope 보존 확인")
            return 0


async def main() -> int:
    # 1) 도구 목록 + demo
    params = StdioServerParameters(command=sys.executable, args=[str(SERVER_PATH)])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = [t.name for t in tools.tools]
            if "get_capabilities" not in names:
                print("FAIL: get_capabilities 도구 없음")
                return 1
            print(f"도구 목록: {names}")
            rc = await run_demo_check(session)
            if rc != 0:
                return rc

    # 2) HTTP 실패 케이스
    print("\n=== HTTP 연결 실패 ===")
    rc = await run_http_check("http://127.0.0.1:1/", 3, "ROUTING_PROVIDER_UNAVAILABLE", True, "연결실패")
    if rc != 0:
        return rc

    print("\n=== HTTP timeout ===")
    # 느린 서버 띄우기
    slow_port = 9200
    backend = await FakeBackend(slow_port, make_handler_slow(slow_port, 10)).start()
    try:
        rc = await run_http_check(f"http://127.0.0.1:{slow_port}/api/v1", 2, "UPSTREAM_TIMEOUT", True, "타임아웃")
    finally:
        await backend.stop()
    if rc != 0:
        return rc

    print("\n=== HTTP INVALID_JSON ===")
    bad_json_port = 9400
    backend = await FakeBackend(bad_json_port, make_handler_bad_json(bad_json_port)).start()
    try:
        rc = await run_http_check(f"http://127.0.0.1:{bad_json_port}/api/v1", 5, "UPSTREAM_RESPONSE_INVALID", False, "INVALID_JSON")
    finally:
        await backend.stop()
    if rc != 0:
        return rc

    print("\n=== HTTP NOT_OBJECT ===")
    non_dict_port = 9500
    backend = await FakeBackend(non_dict_port, make_handler_non_dict(non_dict_port)).start()
    try:
        rc = await run_http_check(f"http://127.0.0.1:{non_dict_port}/api/v1", 5, "UPSTREAM_RESPONSE_INVALID", False, "NOT_OBJECT")
    finally:
        await backend.stop()
    if rc != 0:
        return rc

    print("\n=== HTTP 백엔드 error envelope 전달 ===")
    be_err_port = 9600
    backend = await FakeBackend(be_err_port, make_handler_backend_error(be_err_port)).start()
    try:
        rc = await run_http_check(f"http://127.0.0.1:{be_err_port}/api/v1", 5, "ROUTE_NOT_FOUND", False, "백엔드오류전달")
    finally:
        await backend.stop()
    if rc != 0:
        return rc

    print("\n=== HTTP 성공 ===")
    success_port = 9800
    backend = await FakeBackend(success_port, make_handler_success(success_port, FIXTURE)).start()
    try:
        rc = await run_http_success_check(success_port, FIXTURE)
    finally:
        await backend.stop()
    if rc != 0:
        return rc

    print("\n=== 결과 ===")
    print("demo 응답 구조 검증: 통과")
    print("HTTP 연결 실패 / 타임아웃 / INVALID_JSON / NOT_OBJECT / 백엔드 오류 전달 / 성공: 모두 확인 완료")
    print("실제 백엔드 연결: 미검증 (가짜 백엔드 사용)")
    return 0


if __name__ == "__main__":
    rc = asyncio.run(main())
    sys.exit(rc)
