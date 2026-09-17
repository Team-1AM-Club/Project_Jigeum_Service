"""운영자 검증은 합성 키와 MockTransport로 먼저 검증한다."""

import io
import json
import logging
import subprocess
import sys
from contextlib import redirect_stderr, redirect_stdout
from urllib.parse import quote

import httpx
import pytest

from app.config import Settings
from app.integrations.verify_transit import CATALOG, cli_main, verify_service

SENTINEL = "synthetic-secret/key+and=encoded"


def settings():
    return Settings(
        _env_file=None,
        secret_key="synthetic",
        **{spec.key_field: SENTINEL for spec in CATALOG.values()},
    )


def document(alias):
    spec = CATALOG[alias]
    if spec.family == "bus":
        return "<ServiceResult><msgHeader><headerCd>0</headerCd></msgHeader><msgBody><itemList><busRouteId>100100118</busRouteId></itemList></msgBody></ServiceResult>"
    if spec.family == "path":
        return "<document><header><resultCode>00</resultCode></header><body><paths><path><reqHr>120</reqHr></path></paths></body></document>"
    return f"<{spec.operation}><RESULT><CODE>INFO-000</CODE></RESULT><row><STATION_CD>0309</STATION_CD></row></{spec.operation}>"


def test_requires_live_before_loading_keys(capsys):
    def must_not_load(*args, **kwargs):
        pytest.fail("--live 없이 설정을 읽으면 안 됩니다.")

    assert (
        cli_main(["--service", "subway-stations"], settings_loader=must_not_load) == 2
    )
    assert json.loads(capsys.readouterr().out)["state"] == "requires_live"


def test_fresh_module_import_without_live_never_imports_settings():
    program = """
import sys
from importlib.abc import MetaPathFinder
class BlockSettings(MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "app.config":
            raise AssertionError("Settings imported before --live")
sys.meta_path.insert(0, BlockSettings())
from app.integrations.verify_transit import cli_main
assert cli_main(["--service", "subway-stations"]) == 2
"""
    result = subprocess.run(
        [sys.executable, "-c", program], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["state"] == "requires_live"


@pytest.mark.parametrize("alias", list(CATALOG))
@pytest.mark.asyncio
async def test_each_service_uses_its_fixed_host_and_separate_key(alias):
    calls = []

    def respond(request):
        calls.append(request)
        return httpx.Response(200, text=document(alias))

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        report = await verify_service(alias, settings(), http_client=http)
    assert report["state"] == "real_call_verified"
    assert report["row_count"] == 1
    assert report["verified_for_planning"] is False
    assert len(calls) == 1
    assert calls[0].url.host in {
        "openapi.seoul.go.kr",
        "swopenapi.seoul.go.kr",
        "ws.bus.go.kr",
    }
    if CATALOG[alias].family == "bus":
        assert calls[0].url.params["serviceKey"] == SENTINEL
        assert "%252F" not in str(calls[0].url)
    else:
        assert quote(SENTINEL, safe="") in str(calls[0].url)
    assert SENTINEL not in json.dumps(report)


@pytest.mark.asyncio
async def test_missing_key_does_not_send_request():
    calls = []
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: calls.append(request))
    ) as http:
        report = await verify_service(
            "subway-stations",
            Settings(_env_file=None, secret_key="synthetic"),
            http_client=http,
        )
    assert report["state"] == "missing_key"
    assert calls == []


@pytest.mark.parametrize(
    "alias", ["subway-timetable", "subway-last-train", "subway-path"]
)
@pytest.mark.asyncio
async def test_auth_error_never_retries_or_swaps_keys(alias):
    calls = []

    def respond(request):
        calls.append(request)
        return httpx.Response(
            200,
            text="<RESULT><CODE>INFO-100</CODE><MESSAGE>"
            + SENTINEL
            + "</MESSAGE></RESULT>",
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        report = await verify_service(alias, settings(), http_client=http)
    assert report["state"] == "authentication_failed"
    assert len(calls) == 1
    assert SENTINEL not in json.dumps(report)


@pytest.mark.parametrize(
    "failure", ["network", "xml", "business", "redirect", "unknown_header"]
)
@pytest.mark.asyncio
async def test_output_and_debug_logs_never_expose_secret(failure, caplog):
    calls = []

    def respond(request):
        calls.append(request)
        if failure == "network":
            raise httpx.ConnectError(SENTINEL + str(request.url), request=request)
        if failure == "redirect":
            return httpx.Response(
                302, headers={"Location": "https://other.test/" + SENTINEL}
            )
        if failure == "xml":
            return httpx.Response(200, text=SENTINEL)
        code = SENTINEL if failure == "unknown_header" else "INFO-100"
        return httpx.Response(
            200,
            text=f"<RESULT><CODE>{code}</CODE><MESSAGE>{SENTINEL}</MESSAGE></RESULT>",
        )

    caplog.set_level(logging.DEBUG)
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(respond), follow_redirects=True
    ) as http:
        report = await verify_service("subway-timetable", settings(), http_client=http)
    rendered = caplog.text + json.dumps(report)
    assert SENTINEL not in rendered
    assert quote(SENTINEL, safe="") not in rendered
    assert "serviceKey=" not in rendered
    assert report["state"] != "real_call_verified"
    assert len(calls) <= 2


@pytest.mark.parametrize(
    "args",
    [
        ["--unknown", SENTINEL],
        ["--service", SENTINEL, "--live"],
        ["--service", "subway-stations", "--live", "--env-file", SENTINEL],
    ],
)
def test_cli_argument_errors_never_echo_input(args):
    output, errors = io.StringIO(), io.StringIO()
    with redirect_stdout(output), redirect_stderr(errors):
        code = cli_main(args, settings_loader=lambda *args, **kwargs: settings())
    assert code == 2
    assert SENTINEL not in output.getvalue() + errors.getvalue()


def test_cli_settings_exception_is_safe():
    def fail(*args, **kwargs):
        raise ValueError(SENTINEL)

    output, errors = io.StringIO(), io.StringIO()
    with redirect_stdout(output), redirect_stderr(errors):
        code = cli_main(
            ["--service", "subway-stations", "--live"], settings_loader=fail
        )
    assert code == 2
    assert SENTINEL not in output.getvalue() + errors.getvalue()


@pytest.mark.asyncio
async def test_unknown_service_fails_without_request_and_does_not_echo_value():
    report = await verify_service(SENTINEL, settings())
    assert report["state"] == "invalid_input"
    assert SENTINEL not in json.dumps(report)


@pytest.mark.asyncio
async def test_known_empty_result_is_not_provider_failure():
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, text="<RESULT><CODE>INFO-200</CODE></RESULT>"
            )
        )
    ) as http:
        report = await verify_service("subway-stations", settings(), http_client=http)
    assert report["state"] == "empty"
    assert report["row_count"] == 0


@pytest.mark.asyncio
async def test_unknown_business_diagnostics_never_echo_response(caplog):
    caplog.set_level(logging.DEBUG)
    body = f"<RESULT><CODE>{SENTINEL}</CODE><MESSAGE>{SENTINEL}</MESSAGE></RESULT>"
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, text=body))
    ) as http:
        report = await verify_service("subway-stations", settings(), http_client=http)
    assert report["response_shape"] == "business_result"
    assert report["business_code"] == "unknown"
    assert SENTINEL not in json.dumps(report) + caplog.text


@pytest.mark.parametrize(
    "alias, tag",
    [
        ("subway-arrivals", "realtimeArrivalList"),
        ("subway-positions", "realtimePositionList"),
    ],
)
@pytest.mark.asyncio
async def test_realtime_xml_uses_error_message_and_service_list(alias, tag):
    operation = CATALOG[alias].operation
    body = f"<{operation}><errorMessage><code>INFO-000</code><status>200</status></errorMessage><{tag}><recptnDt>2026-09-16 23:00:00</recptnDt></{tag}></{operation}>"
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, text=body))
    ) as http:
        report = await verify_service(alias, settings(), http_client=http)
    assert report["state"] == "real_call_verified"
    assert report["row_count"] == 1
    assert report["verified_for_planning"] is False


@pytest.mark.asyncio
async def test_static_utf8_encoding_label_is_uncompressed_xml():
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                text=document("subway-stations"),
                headers={"Content-Encoding": "UTF-8"},
            )
        )
    ) as http:
        report = await verify_service("subway-stations", settings(), http_client=http)
    assert report["state"] == "real_call_verified"


@pytest.mark.asyncio
async def test_realtime_xml_result_uses_lowercase_code_and_rows():
    body = "<realtimeStationArrival><RESULT><code>INFO-000</code></RESULT><row><recptnDt>2026-09-16 23:00:00</recptnDt></row></realtimeStationArrival>"
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, text=body))
    ) as http:
        report = await verify_service("subway-arrivals", settings(), http_client=http)
    assert report["state"] == "real_call_verified"
