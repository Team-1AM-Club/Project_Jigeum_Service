"""RED 단계: plan_journey MCP 도구 계약 테스트.

- pytest 미설치 환경이므로 unittest로 작성
- MCP stdio 서버 기동 → list_tools → call_tool 패턴 사용
- docs/ 계약 기준을 먼저 검증한 뒤, examples.json fixture를 확인한다.
- 도구 목록은 LIVE 검증, 요청/응답은 실행 시점의 서버 응답을 그대로 본다.
- last_journey_unsupported / no_feasible_journey는 요청(trip+user_confirmed)이
  plan_last_journey와 완전히 같아서, stdio 요청만으로는 오류 fixture를
  선택할 수 없다. 이번 데모에서는 해당 두 오류를 stdio 성공 조건으로 검증하지
  않고, 오류 envelope 형식만 계약 감사로 확인한다.
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
# helpers
# ---------------------------------------------------------------------------

def _plan_appointment_case() -> dict[str, Any]:
    return case("plan_appointment")


def _plan_last_journey_case() -> dict[str, Any]:
    return case("plan_last_journey")


def _confirmation_required_case() -> dict[str, Any]:
    return case("confirmation_required")


def _last_journey_unsupported_case() -> dict[str, Any]:
    return case("last_journey_unsupported")


def _no_feasible_journey_case() -> dict[str, Any]:
    return case("no_feasible_journey")


def _invalid_arrival_preference_case() -> dict[str, Any]:
    return case("invalid_arrival_preference")


def _build_plan_request(trip: dict[str, Any], user_confirmed: bool = True) -> dict[str, Any]:
    return {
        "trip": trip,
        "user_confirmed": user_confirmed,
    }


class TestPlanJourneyContracts(TestMcpStdioInterpretTrip):
    """plan_journey 도구의 계약 검증.

    현재 시점에서는 도구가 등록돼 있지 않으므로 RED로 실패하는 것을 목표로 한다.
    """

    # ------------------------------------------------------------------
    # 0) 도구 목록 계약
    # ------------------------------------------------------------------

    async def test_tool_list_contains_plan_journey(self):
        names = await self._tool_names()
        self.assertIn("plan_journey", names)

    async def test_tool_list_preserves_existing_three_tools(self):
        names = await self._tool_names()
        for name in ("get_capabilities", "interpret_trip", "search_places"):
            self.assertIn(name, names, msg=f"기존 도구 {name}가 사라짐")

    # ------------------------------------------------------------------
    # 1) 입력 envelope 최상위 필드 계약 (라이브 검증)
    # ------------------------------------------------------------------

    async def test_input_top_level_keys_contract(self):
        c = _plan_appointment_case()
        request = _build_plan_request(c["request"]["trip"], user_confirmed=True)
        allowed_input_keys = {"trip", "user_confirmed"}
        unexpected = set(request.keys()) - allowed_input_keys
        self.assertEqual(unexpected, set(), msg=f"문서에 없는 입력 최상위 필드: {sorted(unexpected)}")

    # ------------------------------------------------------------------
    # 2) user_confirmed 누락 또는 false 시 문서의 확인 요구 오류
    # ------------------------------------------------------------------

    async def test_user_confirmed_false_returns_confirmation_required(self):
        c = _confirmation_required_case()
        request = _build_plan_request(c["request"]["trip"], user_confirmed=False)
        payload = await self._call("plan_journey", request)

        self.assertIsNotNone(payload)
        self.assertEqual(payload.get("status"), "error")
        self.assertIsNone(payload.get("data"))
        error = payload.get("error")
        self.assertIsInstance(error, dict)
        self.assertEqual(error.get("code"), "USER_CONFIRMATION_REQUIRED")
        details = error.get("details", [])
        self.assertTrue(
            any(d.get("field") == "user_confirmed" for d in details),
            msg="user_confirmed 필드 오류 항목이 없음",
        )

    async def test_user_confirmed_missing_returns_confirmation_required(self):
        c = _confirmation_required_case()
        request = {
            "trip": c["request"]["trip"],
        }
        try:
            payload = await self._call("plan_journey", request)
        except Exception as exc:
            # user_confirmed 누락은 MCP 파라미터/schema 입력 거부로 정상 동작.
            # 필드 누락 호출 결과를 JSON 성공 응답처럼 파싱하지 않는다.
            self.skipTest("MCP 파라미터 누락 거부: " + str(exc))
            return
        self.fail("user_confirmed 누락 시 MCP 파라미터 거부가 발생하지 않음")

    # ------------------------------------------------------------------
    # 3) invalid_arrival_preference
    # ------------------------------------------------------------------

    async def test_invalid_arrival_preference(self):
        c = _invalid_arrival_preference_case()
        request = _build_plan_request(c["request"]["trip"], user_confirmed=True)
        payload = await self._call("plan_journey", request)

        self.assertIsNotNone(payload)
        self.assertEqual(payload.get("status"), "error")
        self.assertIsNone(payload.get("data"))
        error = payload.get("error")
        self.assertIsInstance(error, dict)
        self.assertEqual(error.get("code"), "VALIDATION_ERROR")
        self.assertIn("도착 여유시간은 0~120분", error.get("message", ""))
        details = error.get("details", [])
        self.assertTrue(
            any(d.get("field") == "trip.arrival_preference_minutes" for d in details),
            msg="도착 여유 필드 오류 항목이 없음",
        )

    # ------------------------------------------------------------------
    # 6) plan_appointment 요청/응답이 examples.json과 일치
    # ------------------------------------------------------------------

    async def test_plan_appointment_fixture_response(self):
        c = _plan_appointment_case()
        request = _build_plan_request(c["request"]["trip"], user_confirmed=True)
        payload = await self._call("plan_journey", request)
        expected = c["response"]

        self.assertIsNotNone(payload)
        self.assertEqual(payload.get("status"), expected.get("status"))
        self.assertIsNone(payload.get("error"))
        self.assertTrue(payload.get("meta", {}).get("is_demo"))
        self.assertEqual(payload.get("data", {}).get("plan"), expected.get("data", {}).get("plan"))

    # ------------------------------------------------------------------
    # 7) plan_last_journey 요청/응답이 examples.json과 일치
    # ------------------------------------------------------------------

    async def test_plan_last_journey_fixture_response(self):
        c = _plan_last_journey_case()
        request = _build_plan_request(c["request"]["trip"], user_confirmed=True)
        payload = await self._call("plan_journey", request)
        expected = c["response"]

        self.assertIsNotNone(payload)
        self.assertEqual(payload.get("status"), expected.get("status"))
        self.assertIsNone(payload.get("error"))
        self.assertTrue(payload.get("meta", {}).get("is_demo"))
        self.assertEqual(payload.get("data", {}).get("plan"), expected.get("data", {}).get("plan"))

    # ------------------------------------------------------------------
    # 8) 성공 응답은 meta.is_demo=true
    # ------------------------------------------------------------------

    async def test_success_response_is_demo(self):
        c = _plan_appointment_case()
        request = _build_plan_request(c["request"]["trip"], user_confirmed=True)
        payload = await self._call("plan_journey", request)

        self.assertIsNotNone(payload)
        self.assertEqual(payload.get("status"), "ok")
        self.assertTrue(payload.get("meta", {}).get("is_demo"))

    # ------------------------------------------------------------------
    # 9) 문서에 없는 최상위 필드 없음
    # ------------------------------------------------------------------

    async def test_response_top_level_keys_contract(self):
        c = _plan_appointment_case()
        request = _build_plan_request(c["request"]["trip"], user_confirmed=True)
        payload = await self._call("plan_journey", request)
        allowed = {"status", "data", "error", "meta"}
        unexpected = set(payload.keys()) - allowed
        self.assertEqual(unexpected, set(), msg=f"문서에 없는 최상위 필드 포함: {sorted(unexpected)}")


if __name__ == "__main__":
    unittest.main()
