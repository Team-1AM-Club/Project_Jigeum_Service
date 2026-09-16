"""HTTP adapter safety, state and retry contract."""
import unittest
from unittest.mock import patch
from uuid import UUID

import httpx
import backend_mcp_server as adapter


class HTTPAdapterTests(unittest.TestCase):
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
