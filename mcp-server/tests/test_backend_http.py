"""HTTP adapter safety, state and retry contract."""

import asyncio
import json
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import UUID

import backend_mcp_server as adapter
import httpx


class HTTPAdapterTests(unittest.TestCase):
    def test_approved_source_fixture_reaches_mcp_without_loss(self):
        fixture = (
            Path(__file__).resolve().parents[2]
            / "specs/004-public-transit-api-integration/contracts/flat-plan-proposal.json"
        )
        expected = json.loads(fixture.read_text(encoding="utf-8"))
        with patch.object(
            adapter.httpx,
            "request",
            return_value=httpx.Response(200, json=expected),
        ) as request:
            result = adapter.plan_journey({}, "synthetic-conversation", 2)
        self.assertEqual(request.call_count, 1)
        self.assertEqual(result, expected)
        candidate = result["data"]["comparison"]["options"][0]
        self.assertIn("basis_at", candidate["sources"][0])
        self.assertIsNone(candidate["sources"][0]["basis_at"])
        self.assertEqual(candidate["sources"][0]["basis"], "demo")
        self.assertTrue(result["meta"]["is_demo"])
        self.assertEqual(json.loads(json.dumps(result, ensure_ascii=False)), expected)


    def test_source_transition_survives_sdk_text_and_structured_content(self):
        fixture = (
            Path(__file__).resolve().parents[2]
            / "specs/004-public-transit-api-integration/contracts/flat-plan-proposal.json"
        )
        for basis_time in ("2026-09-16T17:59:00+09:00", None, "missing"):
            with self.subTest(basis_time=basis_time):
                expected = json.loads(fixture.read_text(encoding="utf-8"))
                source = expected["data"]["comparison"]["options"][0]["sources"][0]
                if basis_time == "missing":
                    source.pop("basis_at")
                else:
                    source["basis_at"] = basis_time
                with patch.object(
                    adapter.httpx,
                    "request",
                    return_value=httpx.Response(200, json=expected),
                ):
                    result = asyncio.run(
                        adapter.server.call_tool(
                            "plan_journey",
                            {
                                "trip": {},
                                "conversation_id": "synthetic-conversation",
                                "expected_revision": 2,
                            },
                        )
                    )
                wire = result.model_dump(by_alias=True)
                self.assertFalse(wire["isError"])
                self.assertEqual(wire["structuredContent"], expected)
                text_result = next(
                    item["text"] for item in wire["content"] if item["type"] == "text"
                )
                self.assertEqual(json.loads(text_result), expected)


    def test_invalid_source_or_warning_is_rejected_without_retry_or_raw_details(self):
        fixture = (
            Path(__file__).resolve().parents[2]
            / "specs/004-public-transit-api-integration/contracts/flat-plan-proposal.json"
        )
        changes = [
            ("sources", [{"provider": "private-sentinel"}]),
            ("sources", None),
            ("warnings", [{"code": "X", "message": "private-sentinel", "extra": 1}]),
            ("warnings", "private-sentinel"),
        ]
        for field, value in changes:
            for replan in (False, True):
                with self.subTest(field=field, value=value, replan=replan):
                    expected = json.loads(fixture.read_text(encoding="utf-8"))
                    expected["data"]["comparison"]["options"][0][field] = value
                    if replan:
                        expected["data"] = {
                            "comparison": {"new_plan": expected["data"]}
                        }
                    with patch.object(
                        adapter.httpx,
                        "request",
                        return_value=httpx.Response(200, json=expected),
                    ) as request:
                        result = adapter._request(
                            "POST", "/journeys/replan" if replan else "/journeys/plan"
                        )
                    self.assertEqual(result["status"], "error")
                    self.assertEqual(
                        result["error"]["code"], "UPSTREAM_RESPONSE_INVALID"
                    )
                    self.assertNotIn("private-sentinel", json.dumps(result))
                    request.assert_called_once()


    def test_source_datetime_and_date_formats_are_checked(self):
        fixture = (
            Path(__file__).resolve().parents[2]
            / "specs/004-public-transit-api-integration/contracts/flat-plan-proposal.json"
        )
        for field, value in [
            ("basis_at", "2026-09-16"),
            ("basis_at", "2026-09-16T12:00:00"),
            ("basis_at", "2026-99-99T12:00:00+09:00"),
            ("retrieved_at", None),
            ("service_date", "2026-99-99"),
        ]:
            with self.subTest(field=field, value=value):
                expected = json.loads(fixture.read_text(encoding="utf-8"))
                expected["data"]["comparison"]["options"][0]["sources"][0][field] = (
                    value
                )
                with patch.object(
                    adapter.httpx,
                    "request",
                    return_value=httpx.Response(200, json=expected),
                ):
                    result = adapter.plan_journey({}, "synthetic", 2)
                self.assertEqual(result["error"]["code"], "UPSTREAM_RESPONSE_INVALID")


    def setUp(self):
        self.env = patch.dict('os.environ', {'JIGEUM_API_BASE_URL': 'http://localhost:8000/api/v1'})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_retry_preserves_key_and_body(self):
        expected = {'status': 'ok', 'data': {}, 'error': None,
                    'meta': {'conversation_id': 'c', 'revision': 3, 'is_demo': True}}
        with patch.object(adapter.httpx, 'request', side_effect=[
            httpx.ReadTimeout('lost response'), httpx.Response(200, json=expected)
        ]) as request:
            result = adapter.interpret_trip('서울역', context={})
        self.assertEqual(result, expected)
        self.assertEqual(request.call_count, 2)
        first, second = request.call_args_list
        self.assertEqual(first, second)
        self.assertEqual(UUID(first.kwargs['headers']['Idempotency-Key']).version, 4)

    def test_confirm_requires_explicit_consent_without_request(self):
        with patch.object(adapter.httpx, 'request') as request:
            result = adapter.confirm_trip('c', 1, {}, False)
        request.assert_not_called()
        self.assertEqual(result['error']['code'], 'USER_CONFIRMATION_REQUIRED')

    def test_backend_conflict_is_not_retried_or_replaced(self):
        expected = {'status': 'error', 'data': None,
                    'error': {'code': 'CONVERSATION_VERSION_CONFLICT', 'retryable': False},
                    'meta': {'conversation_id': 'c', 'revision': 4, 'is_demo': True}}
        with patch.object(adapter.httpx, 'request', return_value=httpx.Response(409, json=expected)) as request:
            result = adapter.plan_journey({}, 'c', 2)
        self.assertEqual(result, expected)
        self.assertEqual(request.call_count, 1)

    def test_invalid_upstream_never_becomes_demo_success(self):
        with patch.object(adapter.httpx, 'request', return_value=httpx.Response(200, json={'hello': 'world'})):
            result = adapter.get_capabilities()
        self.assertEqual(result['error']['code'], 'UPSTREAM_RESPONSE_INVALID')

    def test_plan_cannot_override_revision_via_trip(self):
        with patch.object(adapter.httpx, 'request', return_value=httpx.Response(200, json={
            'status': 'ok', 'data': {}, 'error': None, 'meta': {}})) as request:
            adapter.plan_journey({'conversation_id': 'other', 'expected_revision': 999}, 'c', 2)
        self.assertEqual(request.call_args.kwargs['json']['conversation_id'], 'c')
        self.assertEqual(request.call_args.kwargs['json']['expected_revision'], 2)


if __name__ == '__main__':
    unittest.main()
