"""URL/업무 오류/HTTP 예외/debug 로깅의 합성 sentinel 비노출 검증."""

import inspect
import logging
import traceback
from urllib.parse import quote

import httpx
import pytest

from app.services.provider_client import ProviderClient, ProviderClientError

SENTINEL = "synthetic-secret/key+with=encoding"


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [SENTINEL, {"private": SENTINEL}, True, 999])
async def test_untrusted_business_status_cannot_escape_or_enable_retry(status):
    calls = []

    def respond(request):
        calls.append(request)
        return httpx.Response(
            200, json={"error": {"status_code": status, "retryable": True}}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        client = ProviderClient(base_url="https://provider.test", http_client=http)
        with pytest.raises(ProviderClientError) as caught:
            await client.call("GET", "/station")
    assert caught.value.status_code is None
    assert caught.value.retryable is False
    assert SENTINEL not in repr(vars(caught.value))
    assert len(calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["http", "business", "network", "parser"])
async def test_path_query_body_and_exception_never_escape(failure, caplog):
    calls = []

    async def respond(request):
        calls.append(request)
        if failure == "network":
            raise httpx.ConnectError(
                f"private URL={request.url} {SENTINEL}", request=request
            )
        if failure == "parser":
            return httpx.Response(200, content=SENTINEL.encode())
        return httpx.Response(
            403 if failure == "http" else 200,
            json={"error": {"message": SENTINEL, "retryable": False}},
        )

    def validate(data):
        raise ProviderClientError(SENTINEL, status_code=403, retryable=False)

    caplog.set_level(logging.DEBUG)
    assert "http_client" in inspect.signature(ProviderClient).parameters
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        client = ProviderClient(base_url="https://provider.test", http_client=http)
        with pytest.raises(ProviderClientError) as caught:
            await client.call(
                "GET",
                "/" + quote(SENTINEL, safe="") + "/station",
                params={"serviceKey": SENTINEL},
                validate_response=validate if failure == "business" else None,
            )
    rendered = "\n".join(
        [
            caplog.text,
            str(caught.value),
            repr(caught.value),
            "".join(traceback.format_exception(caught.value)),
        ]
    )
    assert calls
    assert SENTINEL not in rendered
    assert quote(SENTINEL, safe="") not in rendered
    assert "provider.test" not in rendered
    assert "serviceKey=" not in rendered


@pytest.mark.asyncio
async def test_unimplemented_or_unexpected_transport_error_is_safe(caplog):
    caplog.set_level(logging.DEBUG)
    client = ProviderClient(base_url="https://provider.test")

    async def fail(**kwargs):
        raise RuntimeError(SENTINEL)

    client._execute_request = fail
    with pytest.raises(ProviderClientError) as caught:
        await client.call("GET", "/" + SENTINEL)
    rendered = caplog.text + "".join(traceback.format_exception(caught.value))
    assert SENTINEL not in rendered
    assert "provider.test" not in rendered
    if hasattr(client, "aclose"):
        await client.aclose()
