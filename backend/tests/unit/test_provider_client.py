"""실제 전송 경계를 합성 transport로 검증한다. 실제 제공처를 호출하지 않는다."""

import asyncio
import inspect
import time

import httpx
import pytest

from app.services import provider_client as module
from app.services.provider_client import ProviderClient, ProviderClientError


def client_for(http_client, **kwargs):
    assert "http_client" in inspect.signature(ProviderClient).parameters
    return ProviderClient(http_client=http_client, **kwargs)


def budget_for(seconds=1, attempts=4, concurrency=2):
    assert hasattr(module, "RequestBudget"), "공유 deadline/시도 예산이 필요합니다."
    return module.RequestBudget(seconds, attempts, concurrency)


@pytest.mark.asyncio
async def test_json_success_keeps_query_serialization_and_business_data():
    requests = []

    async def respond(request):
        requests.append(request)
        return httpx.Response(200, json={"RESULT": {"CODE": "INFO-000"}, "rows": []})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        client = client_for(http, base_url="https://provider.test")
        result = await client.call("GET", "/station", params={"name": "시연 역"})
    assert result == {"RESULT": {"CODE": "INFO-000"}, "rows": []}
    assert len(requests) == 1
    assert requests[0].url.params["name"] == "시연 역"


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [401, 403, 429, 502, 503, 504])
async def test_explicit_nonretryable_overrides_status(status):
    requests = []

    async def respond(request):
        requests.append(request)
        return httpx.Response(status, json={"error": {"retryable": False}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        client = client_for(http)
        with pytest.raises(ProviderClientError) as caught:
            await client.call("GET", "/station", retryable=True)
    assert len(requests) == 1
    assert caught.value.status_code == status
    assert caught.value.retryable is False


@pytest.mark.asyncio
async def test_retryable_failure_waits_500ms_and_retries_only_once(monkeypatch):
    requests, delays = [], []

    async def respond(request):
        requests.append(request)
        return httpx.Response(503, json={"error": {"retryable": True}})

    async def record_sleep(delay):
        delays.append(delay)

    monkeypatch.setattr(module.asyncio, "sleep", record_sleep)
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        client = client_for(http)
        with pytest.raises(ProviderClientError):
            await client.call("GET", "/station")
    assert len(requests) == 2
    assert delays == [0.5]


@pytest.mark.asyncio
async def test_http_200_business_error_is_validated_without_retry():
    requests = []

    async def respond(request):
        requests.append(request)
        return httpx.Response(200, json={"business": "auth_denied"})

    def validate(data):
        if data["business"] == "auth_denied":
            raise ProviderClientError("인증 실패", status_code=403, retryable=False)

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        client = client_for(http)
        with pytest.raises(ProviderClientError) as caught:
            await client.call("GET", "/station", validate_response=validate)
    assert len(requests) == 1
    assert caught.value.status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [b"broken", b"[]", b'{"value":NaN}'])
async def test_invalid_json_is_never_retried(payload):
    requests = []

    async def respond(request):
        requests.append(request)
        return httpx.Response(200, content=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        client = client_for(http)
        with pytest.raises(ProviderClientError) as caught:
            await client.call("GET", "/station")
    assert len(requests) == 1
    assert caught.value.error_code == "UPSTREAM_RESPONSE_INVALID"
    assert caught.value.retryable is False


@pytest.mark.asyncio
async def test_xml_preserves_nested_header_and_repeated_rows():
    content = b"<document><header><code>ok</code></header><body><row><id>001</id></row><row><id>002</id></row></body></document>"
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, content=content)
        )
    ) as http:
        result = await client_for(http).call("GET", "/station", response_format="xml")
    assert result == {
        "document": {
            "header": {"code": "ok"},
            "body": {"row": [{"id": "001"}, {"id": "002"}]},
        }
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "content",
    [
        b'<!DOCTYPE r [<!ENTITY secret "value">]><r>&secret;</r>',
        b"<r>unclosed",
        "<r/>".encode("utf-16"),
    ],
)
async def test_xml_entities_and_invalid_encodings_are_rejected(content):
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, content=content)
        )
    ) as http:
        with pytest.raises(ProviderClientError) as caught:
            await client_for(http).call("GET", "/station", response_format="xml")
    assert caught.value.error_code == "UPSTREAM_RESPONSE_INVALID"


@pytest.mark.asyncio
async def test_redirect_is_not_followed_even_if_injected_client_enables_it():
    requests = []

    async def respond(request):
        requests.append(request)
        return httpx.Response(302, headers={"Location": "https://other.test/key"})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(respond), follow_redirects=True
    ) as http:
        with pytest.raises(ProviderClientError):
            await client_for(http).call("GET", "/station")
    assert len(requests) == 1


@pytest.mark.asyncio
async def test_response_size_limit_rejects_body_before_parsing():
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, content=b"x" * 33)
        )
    ) as http:
        with pytest.raises(ProviderClientError) as caught:
            await client_for(http, max_response_bytes=32).call("GET", "/station")
    assert caught.value.error_code == "UPSTREAM_RESPONSE_INVALID"


@pytest.mark.asyncio
async def test_whole_attempt_deadline_stops_slow_transport():
    requests = []

    async def respond(request):
        requests.append(request)
        await asyncio.sleep(1)
        return httpx.Response(200, json={})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        client = client_for(http, timeout_seconds=0.02)
        started = time.monotonic()
        with pytest.raises(ProviderClientError) as caught:
            await client.call("GET", "/station", budget=budget_for(seconds=0.04))
        elapsed = time.monotonic() - started
    assert elapsed < 0.5
    assert len(requests) == 1
    assert caught.value.error_code == "UPSTREAM_TIMEOUT"


@pytest.mark.asyncio
async def test_shared_attempt_budget_counts_page_and_retry_without_extra_call():
    requests = []

    async def respond(request):
        requests.append(request)
        return httpx.Response(200, json={"rows": []})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        client, budget = client_for(http), budget_for(attempts=1)
        await client.call("GET", "/page/1", budget=budget)
        with pytest.raises(ProviderClientError) as caught:
            await client.call("GET", "/page/2", budget=budget)
    assert len(requests) == 1
    assert caught.value.error_code == "UPSTREAM_TIMEOUT"


@pytest.mark.asyncio
async def test_request_dedup_and_concurrency_apply_only_within_shared_budget():
    requests, active, peak = [], 0, 0

    async def respond(request):
        nonlocal active, peak
        requests.append(request)
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.01)
        active -= 1
        return httpx.Response(200, json={"ok": True})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        client, budget = client_for(http), budget_for(attempts=3, concurrency=1)
        results = await asyncio.gather(
            client.call("GET", "/a", budget=budget),
            client.call("GET", "/a", budget=budget),
            client.call("GET", "/b", budget=budget),
        )
        await client.call("GET", "/a", budget=budget_for())
    assert results == [{"ok": True}, {"ok": True}, {"ok": True}]
    assert len(requests) == 3
    assert peak == 1


@pytest.mark.asyncio
async def test_cancelled_caller_is_not_retried():
    started, cancelled = asyncio.Event(), asyncio.Event()

    async def respond(request):
        started.set()
        try:
            await asyncio.sleep(10)
        finally:
            cancelled.set()
        return httpx.Response(200, json={})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        task = asyncio.create_task(client_for(http).call("GET", "/station"))
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert cancelled.is_set()


@pytest.mark.asyncio
async def test_cached_result_cannot_bypass_expired_request_deadline():
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={"ok": True})
        )
    ) as http:
        client, budget = client_for(http), budget_for(seconds=0.01)
        await client.call("GET", "/station", budget=budget)
        await asyncio.sleep(0.02)
        with pytest.raises(ProviderClientError) as caught:
            await client.call("GET", "/station", budget=budget)
    assert caught.value.error_code == "UPSTREAM_TIMEOUT"


@pytest.mark.asyncio
async def test_business_auth_error_cannot_enable_retry():
    requests = []

    async def respond(request):
        requests.append(request)
        return httpx.Response(
            200, json={"error": {"status_code": 403, "retryable": True}}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        with pytest.raises(ProviderClientError) as caught:
            await client_for(http).call("GET", "/station")
    assert len(requests) == 1
    assert caught.value.retryable is False


@pytest.mark.asyncio
async def test_sync_validation_cannot_publish_success_after_deadline():
    import time

    def validate(data):
        time.sleep(0.03)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={}))
    ) as http:
        budget = budget_for(seconds=0.01)
        with pytest.raises(ProviderClientError) as caught:
            await client_for(http).call(
                "GET", "/station", budget=budget, validate_response=validate
            )
    assert caught.value.error_code == "UPSTREAM_TIMEOUT"
    assert budget.results == {}
    assert budget.inflight == {}


@pytest.mark.asyncio
async def test_compressed_body_is_rejected_before_reading_stream():
    calls, reads = [], []

    class UnreadStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            reads.append(True)
            yield b""

    def respond(request):
        calls.append(request)
        return httpx.Response(
            200, headers={"Content-Encoding": "gzip"}, stream=UnreadStream()
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        with pytest.raises(ProviderClientError) as caught:
            await client_for(http).call("GET", "/station")
    assert caught.value.error_code == "UPSTREAM_RESPONSE_INVALID"
    assert len(calls) == 1
    assert calls[0].headers["Accept-Encoding"] == "identity"
    assert reads == []


@pytest.mark.asyncio
async def test_mutating_owner_result_does_not_change_duplicate_result():
    async def respond(request):
        await asyncio.sleep(0.01)
        return httpx.Response(200, json={"rows": ["original"]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        client, budget = client_for(http), budget_for()

        async def owner():
            result = await client.call("GET", "/station", budget=budget)
            result["rows"].clear()

        _, duplicate = await asyncio.gather(
            owner(), client.call("GET", "/station", budget=budget)
        )
    assert duplicate == {"rows": ["original"]}
