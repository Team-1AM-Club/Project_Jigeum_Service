"""RED 단계: search_places MCP 도구 계약 테스트.

- pytest 미설치 환경이므로 unittest로 작성
- MCP stdio 서버 기동 → list_tools → call_tool 패턴 사용
- E:\\MABC 절대 경로를 런타임에 참조하지 않음
- 데모 fixture는 현재 저장소 안에서 자급
- 기존 test_interpret_mcp_stdio.py의 stdio 도우미를 재사용
"""

from __future__ import annotations

import json
import unittest
from typing import Any

from test_interpret_mcp_stdio import (
    SERVER_PARAMS,
    case,
    load_examples,
    norm_payload,
    text_from,
    TestMcpStdioInterpretTrip,
)

# ---------------------------------------------------------------------------
# search_places 전용 헬퍼
# ---------------------------------------------------------------------------


def _places_found_case() -> dict[str, Any]:
    return case("places_found")


def _expected_response(case_obj: dict[str, Any]) -> dict[str, Any]:
    return case_obj["response"]


def _expected_request(case_obj: dict[str, Any]) -> dict[str, Any]:
    return case_obj["request"]


def _build_search_places_request(query: str, limit: int | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"query": query}
    if limit is not None:
        payload["limit"] = limit
    return payload


class TestSearchPlacesContracts(TestMcpStdioInterpretTrip):
    """search_places 도구의 계약 검증.

    현재 시점에서는 도구가 등록돼 있지 않으므로 RED로 실패하는 것을 목표로 한다.
    """

    # ------------------------------------------------------------------
    # 1) 도구 목록 계약
    # ------------------------------------------------------------------
    async def test_tool_list_contains_search_places(self):
        names = await self._tool_names()
        self.assertIn("search_places", names)

    # ------------------------------------------------------------------
    # 2) places_found 데모 응답 계약
    # ------------------------------------------------------------------
    async def test_places_found_fixture_response(self):
        c = _places_found_case()
        expected_resp = _expected_response(c)
        request = {"query": "테스트", "limit": 5}
        payload = await self._call("search_places", request)
        expected = expected_resp

        self.assertIsNotNone(payload)
        self.assertEqual(payload.get("status"), expected.get("status"))
        self.assertIsNone(payload.get("error"))
        self.assertTrue(payload.get("meta", {}).get("is_demo"))

        data = payload.get("data")
        self.assertIsInstance(data, dict)

        expected_data = expected.get("data")
        self.assertEqual(data.get("query"), expected_data.get("query"))
        self.assertEqual(len(data.get("places", [])), len(expected_data.get("places", [])))
        self.assertIn("source", data)
        self.assertIn("has_more", data)

        self.assertEqual(norm_payload(payload), norm_payload(expected))

    # ------------------------------------------------------------------
    # 3) 빈 검색 결과
    # ------------------------------------------------------------------
    async def test_empty_result(self):
        request = {"query": "찾지않는가상장소xyz"}
        payload = await self._call("search_places", request)

        self.assertIsNotNone(payload)
        self.assertEqual(payload.get("status"), "ok")
        self.assertIsNone(payload.get("error"))
        data = payload.get("data")
        self.assertIsInstance(data, dict)
        self.assertEqual(data.get("query"), "찾지않는가상장소xyz")
        self.assertEqual(data.get("places"), [])
        self.assertFalse(data.get("has_more"))

    # ------------------------------------------------------------------
    # 4) query 공백 제거와 길이 검증
    # ------------------------------------------------------------------
    async def test_query_whitespace_stripped(self):
        request = {"query": "  테스트  ", "limit": 5}
        payload = await self._call("search_places", request)
        data = payload.get("data")
        self.assertIsNotNone(data)
        self.assertEqual(data.get("query"), "테스트")

    async def test_query_empty_after_strip_rejected(self):
        request = {"query": "   ", "limit": 5}
        payload = await self._call("search_places", request)
        self.assertIsNotNone(payload)
        self.assertEqual(payload.get("status"), "error")
        self.assertIsNone(payload.get("data"))
        error = payload.get("error")
        self.assertIsInstance(error, dict)
        self.assertIn("VALIDATION_ERROR", error.get("code", ""))

    async def test_query_too_long_rejected(self):
        request = {"query": "x" * 101, "limit": 5}
        payload = await self._call("search_places", request)
        self.assertIsNotNone(payload)
        self.assertEqual(payload.get("status"), "error")
        error = payload.get("error")
        self.assertIn("VALIDATION_ERROR", error.get("code", ""))

    async def test_query_within_limit_ok(self):
        request = {"query": "x" * 100, "limit": 5}
        payload = await self._call("search_places", request)
        self.assertIsNotNone(payload)
        self.assertEqual(payload.get("status"), "ok")

    # ------------------------------------------------------------------
    # 5) limit 기본값 및 경계값 검증
    # ------------------------------------------------------------------
    async def test_limit_default_five(self):
        request = {"query": "테스트"}
        payload = await self._call("search_places", request)
        data = payload.get("data")
        self.assertIsNotNone(data)
        self.assertIsInstance(data.get("places"), list)
        self.assertLessEqual(len(data.get("places", [])), 5)

    async def test_limit_one(self):
        request = {"query": "테스트", "limit": 1}
        payload = await self._call("search_places", request)
        data = payload.get("data")
        self.assertIsNotNone(data)
        self.assertLessEqual(len(data.get("places", [])), 1)

    async def test_limit_ten(self):
        request = {"query": "테스트", "limit": 10}
        payload = await self._call("search_places", request)
        data = payload.get("data")
        self.assertIsNotNone(data)
        self.assertLessEqual(len(data.get("places", [])), 10)

    async def test_limit_zero_rejected(self):
        request = {"query": "테스트", "limit": 0}
        payload = await self._call("search_places", request)
        self.assertIsNotNone(payload)
        self.assertEqual(payload.get("status"), "error")
        error = payload.get("error")
        self.assertIn("VALIDATION_ERROR", error.get("code", ""))

    async def test_limit_negative_rejected(self):
        request = {"query": "테스트", "limit": -1}
        payload = await self._call("search_places", request)
        self.assertIsNotNone(payload)
        self.assertEqual(payload.get("status"), "error")
        error = payload.get("error")
        self.assertIn("VALIDATION_ERROR", error.get("code", ""))

    async def test_limit_over_ten_rejected(self):
        request = {"query": "테스트", "limit": 11}
        payload = await self._call("search_places", request)
        self.assertIsNotNone(payload)
        self.assertEqual(payload.get("status"), "error")
        error = payload.get("error")
        self.assertIn("VALIDATION_ERROR", error.get("code", ""))

    async def test_limit_non_integer_rejected(self):
        for bad in (1.5, "5", True):
            request = {"query": "테스트", "limit": bad}
            payload = await self._call("search_places", request)
            self.assertIsNotNone(payload)
            self.assertEqual(payload.get("status"), "error")
            error = payload.get("error")
            self.assertIn("VALIDATION_ERROR", error.get("code", ""), msg=f"limit={bad!r} 거부 실패")

    # ------------------------------------------------------------------
    # 6) 응답 최상위 필드 제한
    # ------------------------------------------------------------------
    async def test_response_top_level_keys_contract(self):
        c = _places_found_case()
        expected_resp = _expected_response(c)
        request = {"query": "테스트", "limit": 5}
        payload = await self._call("search_places", request)
        allowed = {"status", "data", "error", "meta"}
        unexpected = set(payload.keys()) - allowed
        self.assertEqual(unexpected, set(), f"문서에 없는 최상위 필드 포함: {sorted(unexpected)}")

    # ------------------------------------------------------------------
    # 7) Place 필드 계약 검증
    # ------------------------------------------------------------------
    async def test_place_fields_contract(self):
        c = _places_found_case()
        request = {"query": "테스트", "limit": 5}
        payload = await self._call("search_places", request)
        places = payload.get("data", {}).get("places", [])
        self.assertTrue(len(places) > 0, "places_found fixture가 빈 결과를 반환함")

        for p in places:
            self.assertIsInstance(p, dict)
            self.assertIn("place_id", p)
            self.assertIn("name", p)
            self.assertIn("address", p)
            self.assertIn("latitude", p)
            self.assertIn("longitude", p)
            self.assertIsInstance(p["place_id"], str)
            self.assertIsInstance(p["name"], str)
            self.assertIsInstance(p["latitude"], (int, float))
            self.assertIsInstance(p["longitude"], (int, float))
            self.assertTrue(-90 <= p["latitude"] <= 90, f"위도 범위 이탈: {p['latitude']}")
            self.assertTrue(-180 <= p["longitude"] <= 180, f"경도 범위 이탈: {p['longitude']}")


if __name__ == "__main__":
    unittest.main()
