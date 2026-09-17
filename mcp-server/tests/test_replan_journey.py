"""RED 단계: replan_journey MCP 도구 계약 테스트.

- pytest 미설치 환경이므로 unittest로 작성
- MCP stdio 서버 기동 → list_tools → call_tool 패턴 사용
- docs/ 계약 기준을 먼저 검증한 뒤, examples.json fixture를 확인한다.
- tools/list에 replan_journey 노출, 정상 fixture 응답이 examples.json replan_late와 일치,
  재탐색 결과가 자동 적용되지 않고 comparison을 포함한 대안으로 반환됨,
  최상위 status/data/error/meta 구조, 기존 4개 도구 회귀를 검증한다.
- examples.json에 replan 전용 오류/불가능 케이스가 없으므로, 이번 RED에서는
  replan_late 성공 계약과 최상위 envelope 구조만 검증한다.
"""

from __future__ import annotations

import unittest
from typing import Any

from test_interpret_mcp_stdio import (
    SERVER_PARAMS,
    case,
    TestMcpStdioInterpretTrip,
)

REPLAN_LATE_CASE_ID = "replan_late"

REPLAN_INPUT_TOP_LEVEL_KEYS = {"trip", "previous_plan", "current_origin_place_id", "reason", "user_confirmed"}
REPLAN_SUCCESS_TOP_LEVEL_KEYS = {"status", "data", "error", "meta"}
COMPARISON_KEYS = {
    "previous_plan_id",
    "previous_selected_option_id",
    "compared_option_id",
    "arrival_change_minutes",
    "leave_change_minutes",
    "summary",
}


def _replan_late_case() -> dict[str, Any]:
    return case(REPLAN_LATE_CASE_ID)


def _build_replan_request(
    trip: dict[str, Any],
    previous_plan: dict[str, Any],
    current_origin_place_id: str,
    reason: str,
    user_confirmed: bool = True,
) -> dict[str, Any]:
    return {
        "trip": trip,
        "previous_plan": previous_plan,
        "current_origin_place_id": current_origin_place_id,
        "reason": reason,
        "user_confirmed": user_confirmed,
    }


class TestReplanJourneyContracts(TestMcpStdioInterpretTrip):
    """replan_journey 도구의 계약 검증.

    현재 시점에서는 도구가 등록돼 있지 않으므로 RED로 실패하는 것을 목표로 한다.
    """

    # ------------------------------------------------------------------
    # 0) 도구 목록 계약
    # ------------------------------------------------------------------

    async def test_tool_list_contains_replan_journey(self):
        names = await self._tool_names()
        self.assertIn("replan_journey", names)

    async def test_tool_list_preserves_existing_four_tools(self):
        names = await self._tool_names()
        for name in ("get_capabilities", "interpret_trip", "search_places", "plan_journey"):
            self.assertIn(name, names, msg=f"기존 도구 {name}가 사라짐")

    # ------------------------------------------------------------------
    # 1) 입력 envelope 최상위 필드 계약 (라이브 검증)
    # ------------------------------------------------------------------

    async def test_input_top_level_keys_contract(self):
        c = _replan_late_case()
        request = _build_replan_request(
            trip=c["request"]["trip"],
            previous_plan=c["request"]["previous_plan"],
            current_origin_place_id=c["request"]["current_origin_place_id"],
            reason=c["request"]["reason"],
            user_confirmed=c["request"]["user_confirmed"],
        )
        unexpected = set(request.keys()) - REPLAN_INPUT_TOP_LEVEL_KEYS
        self.assertEqual(
            unexpected,
            set(),
            msg=f"문서에 없는 입력 최상위 필드: {sorted(unexpected)}",
        )

    # ------------------------------------------------------------------
    # 2) replan_late fixture 응답 계약
    # ------------------------------------------------------------------

    async def test_replan_late_fixture_response(self):
        c = _replan_late_case()
        request = _build_replan_request(
            trip=c["request"]["trip"],
            previous_plan=c["request"]["previous_plan"],
            current_origin_place_id=c["request"]["current_origin_place_id"],
            reason=c["request"]["reason"],
            user_confirmed=c["request"]["user_confirmed"],
        )
        payload = await self._call("replan_journey", request)
        expected = c["response"]

        self.assertIsNotNone(payload)
        self.assertEqual(payload.get("status"), expected.get("status"))
        self.assertIsNone(payload.get("error"))
        self.assertTrue(payload.get("meta", {}).get("is_demo"))

        data = payload.get("data")
        self.assertIsInstance(data, dict)

        # 성공 응답은 plan + comparison
        self.assertIn("plan", data)
        self.assertIn("comparison", data)

        expected_data = expected.get("data", {})
        self.assertEqual(data.get("plan"), expected_data.get("plan"))
        self.assertEqual(data.get("comparison"), expected_data.get("comparison"))

    # ------------------------------------------------------------------
    # 3) 재탐색 결과는 대안으로만 반환 — 자동 적용 표현 없음
    # ------------------------------------------------------------------

    async def test_replan_result_is_alternative_not_auto_applied(self):
        c = _replan_late_case()
        request = _build_replan_request(
            trip=c["request"]["trip"],
            previous_plan=c["request"]["previous_plan"],
            current_origin_place_id=c["request"]["current_origin_place_id"],
            reason=c["request"]["reason"],
            user_confirmed=c["request"]["user_confirmed"],
        )
        payload = await self._call("replan_journey", request)

        self.assertIsNotNone(payload)
        # status=ok, error=null, meta.is_demo=true
        self.assertEqual(payload.get("status"), "ok")
        self.assertIsNone(payload.get("error"))
        self.assertTrue(payload.get("meta", {}).get("is_demo"))

        data = payload.get("data")
        self.assertIsInstance(data, dict)

        # data에는 plan과 comparison만 존재 — 이전 계획을 자동 교체했다는 필드가 없음
        unexpected_data_keys = set(data.keys()) - {"plan", "comparison"}
        self.assertEqual(
            unexpected_data_keys,
            set(),
            msg=f"문서에 없는 data 하위 필드: {sorted(unexpected_data_keys)}",
        )

        # comparison은 이전 계획과 새 권장 후보를 비교하며, 자동 적용을 의미하지 않음
        comparison = data.get("comparison")
        self.assertIsInstance(comparison, dict)
        missing_comparison_keys = COMPARISON_KEYS - set(comparison.keys())
        self.assertEqual(
            missing_comparison_keys,
            set(),
            msg=f"comparison에 계약 키 누락: {sorted(missing_comparison_keys)}",
        )

    # ------------------------------------------------------------------
    # 4) 최상위 status/data/error/meta 구조
    # ------------------------------------------------------------------

    async def test_response_top_level_keys_contract(self):
        c = _replan_late_case()
        request = _build_replan_request(
            trip=c["request"]["trip"],
            previous_plan=c["request"]["previous_plan"],
            current_origin_place_id=c["request"]["current_origin_place_id"],
            reason=c["request"]["reason"],
            user_confirmed=c["request"]["user_confirmed"],
        )
        payload = await self._call("replan_journey", request)
        unexpected = set(payload.keys()) - REPLAN_SUCCESS_TOP_LEVEL_KEYS
        self.assertEqual(
            unexpected,
            set(),
            msg=f"문서에 없는 최상위 필드 포함: {sorted(unexpected)}",
        )

    # ------------------------------------------------------------------
    # 5) meta 구조 확인
    # ------------------------------------------------------------------

    async def test_meta_contains_required_fields(self):
        c = _replan_late_case()
        request = _build_replan_request(
            trip=c["request"]["trip"],
            previous_plan=c["request"]["previous_plan"],
            current_origin_place_id=c["request"]["current_origin_place_id"],
            reason=c["request"]["reason"],
            user_confirmed=c["request"]["user_confirmed"],
        )
        payload = await self._call("replan_journey", request)

        self.assertIsNotNone(payload)
        meta = payload.get("meta")
        self.assertIsInstance(meta, dict)
        for key in ("request_id", "server_time", "api_version", "is_demo"):
            self.assertIn(key, meta, msg=f"meta에 {key} 누락")


if __name__ == "__main__":
    unittest.main()
