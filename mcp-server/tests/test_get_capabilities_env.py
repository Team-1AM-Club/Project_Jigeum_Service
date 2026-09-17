"""RED 단계: get_capabilities HTTP 모드에서 JIGEUM_API_TIMEOUT 파싱 결함 검증.

- pytest 미설치 환경이므로 unittest로 작성
- MCP stdio/subprocess/fake HTTPServer 기반 헬퍼를 사용하지 않음
- 목적은 timeout 환경변수 파싱과 HTTP 호출 전달값 검증
- _parse_timeout_env는 제품 모듈에서 직접 임포트해 검증
- HTTP 호출 경계는 jigeum_mcp_server.httpx.get을 mock해 timeout 전달값을 검증
- 환경변수는 patch.dict로 격리하고 종료 후 복원
"""

from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import patch, Mock
from typing import Any
from pathlib import Path

# 제품 코드를 수정하지 않고 제품 모듈을 직접 검증하기 위해
# 테스트 파일이 위치한 디렉터리의 부모(mcp-server/)를 임포트 경로에 추가
_SERVER_DIR = Path(__file__).resolve().parent.parent
if str(_SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(_SERVER_DIR))

import jigeum_mcp_server as _jigeum_server

_parse_timeout_env = _jigeum_server._parse_timeout_env


# 계약-valid 최소 성공 응답 fixture.
# HTTP 백엔드가 반환한 성공 envelope를 MCP가 그대로 pass-through하는지
# 검증할 때 가짜 서버가 이 응답을 그대로 반환하고, MCP 응답과
# 일치하는지 비교하는 용도로 사용한다.
SUCCESS_CAPABILITIES_FIXTURE: dict[str, Any] = {
    "status": "ok",
    "data": {"status": "ok"},
    "error": None,
    "meta": {
        "request_id": "fixture-capabilities",
        "server_time": "2026-09-13T18:00:00+09:00",
        "api_version": "v1",
        "is_demo": True,
    },
}


def _mock_httpx_get_success() -> Mock:
    """status_code=200이고 json()이 SUCCESS_CAPABILITIES_FIXTURE를 반환하는 MockResponse를 반환."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = SUCCESS_CAPABILITIES_FIXTURE
    return mock_response


class TestParseTimeoutEnv(unittest.TestCase):
    """_parse_timeout_env가 비정수/빈 문자열을 기본값으로 안전하게 대체하는지 검증."""

    def test_none_falls_back_to_default(self):
        self.assertEqual(_parse_timeout_env(None, 15), 15)

    def test_empty_string_falls_back_to_default(self):
        self.assertEqual(_parse_timeout_env("", 15), 15)

    def test_invalid_string_falls_back_to_default(self):
        self.assertEqual(_parse_timeout_env("foo", 15), 15)

    def test_valid_integer_is_used(self):
        self.assertEqual(_parse_timeout_env("7", 15), 7)


class TestCapabilitiesHttpTimeoutDelivery(unittest.TestCase):
    """JIGEUM_API_TIMEOUT에 따라 _capabilities_http가 httpx.get에 전달하는 timeout을 검증."""

    def _call_capabilities_http_with_env(
        self, timeout_env: str, base_url_env: str
    ) -> tuple[Any, Any]:
        """_capabilities_http(base_url)를 호출하고 (반환값, httpx.get에 전달된 timeout)을 반환."""
        with patch.dict(os.environ, {
            "JIGEUM_API_BASE_URL": base_url_env,
            "JIGEUM_API_TIMEOUT": timeout_env,
        }):
            captured_timeout: dict[str, Any] = {}
            def capture_get(url: str, *, timeout: Any, headers: Any) -> Mock:
                captured_timeout["timeout"] = timeout
                return _mock_httpx_get_success()

            with patch.object(_jigeum_server.httpx, "get", side_effect=capture_get):
                result = _jigeum_server._capabilities_http(base_url_env)
                return result, captured_timeout["timeout"]

    def test_invalid_timeout_falls_back_to_default(self):
        result, timeout = self._call_capabilities_http_with_env("foo", "http://127.0.0.1:9/")
        self.assertEqual(result, SUCCESS_CAPABILITIES_FIXTURE)
        self.assertEqual(timeout, 15)

    def test_empty_timeout_falls_back_to_default(self):
        result, timeout = self._call_capabilities_http_with_env("", "http://127.0.0.1:9/")
        self.assertEqual(result, SUCCESS_CAPABILITIES_FIXTURE)
        self.assertEqual(timeout, 15)

    def test_valid_timeout_is_used(self):
        result, timeout = self._call_capabilities_http_with_env("42", "http://127.0.0.1:9/")
        self.assertEqual(result, SUCCESS_CAPABILITIES_FIXTURE)
        self.assertEqual(timeout, 42)

    def test_env_isolation_and_restoration(self):
        sentinel_timeout = "pytest-sentinel-timeout"
        sentinel_base_url = "http://127.0.0.1:999/"

        self.assertNotEqual(os.environ.get("JIGEUM_API_TIMEOUT"), sentinel_timeout)
        self.assertNotEqual(os.environ.get("JIGEUM_API_BASE_URL"), sentinel_base_url)

        with patch.dict(os.environ, {
            "JIGEUM_API_TIMEOUT": sentinel_timeout,
            "JIGEUM_API_BASE_URL": sentinel_base_url,
        }):
            self.assertEqual(os.environ["JIGEUM_API_TIMEOUT"], sentinel_timeout)
            self.assertEqual(os.environ["JIGEUM_API_BASE_URL"], sentinel_base_url)

        self.assertNotEqual(os.environ.get("JIGEUM_API_TIMEOUT"), sentinel_timeout)
        self.assertNotEqual(os.environ.get("JIGEUM_API_BASE_URL"), sentinel_base_url)


class TestGetCapabilitiesHttpTimeoutDelivery(unittest.TestCase):
    """get_capabilities(mode="http") 전체 경로에서 timeout 전달을 검증."""

    def _call_get_capabilities_http_with_env(
        self, timeout_env: str, base_url_env: str
    ) -> tuple[Any, Any]:
        """get_capabilities(mode="http")를 호출하고 (반환값, httpx.get에 전달된 timeout)을 반환."""
        with patch.dict(os.environ, {
            "JIGEUM_API_BASE_URL": base_url_env,
            "JIGEUM_API_TIMEOUT": timeout_env,
        }):
            captured_timeout: dict[str, Any] = {}
            def capture_get(url: str, *, timeout: Any, headers: Any) -> Mock:
                captured_timeout["timeout"] = timeout
                return _mock_httpx_get_success()

            with patch.object(_jigeum_server.httpx, "get", side_effect=capture_get):
                result = _jigeum_server.get_capabilities(mode="http")
                return result, captured_timeout["timeout"]

    def test_invalid_timeout_falls_back_to_default(self):
        result, timeout = self._call_get_capabilities_http_with_env("foo", "http://127.0.0.1:9/")
        self.assertEqual(result, SUCCESS_CAPABILITIES_FIXTURE)
        self.assertEqual(timeout, 15)

    def test_empty_timeout_falls_back_to_default(self):
        result, timeout = self._call_get_capabilities_http_with_env("", "http://127.0.0.1:9/")
        self.assertEqual(result, SUCCESS_CAPABILITIES_FIXTURE)
        self.assertEqual(timeout, 15)

    def test_valid_timeout_is_used(self):
        result, timeout = self._call_get_capabilities_http_with_env("42", "http://127.0.0.1:9/")
        self.assertEqual(result, SUCCESS_CAPABILITIES_FIXTURE)
        self.assertEqual(timeout, 42)
