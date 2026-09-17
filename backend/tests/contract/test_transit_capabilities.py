"""후보 수 안내가 승인 계약 및 실제 요청 제한과 일치해야 한다."""

import json
from pathlib import Path

from app.schemas.journeys import TripRequest
from app.services.provider_client import ProviderClient


def test_capabilities_preserve_approved_candidate_limits_without_provider_calls(
    client, monkeypatch
):
    calls = []

    async def forbidden_call(*args, **kwargs):
        calls.append(True)
        raise AssertionError("capabilities는 외부 조회를 수행하면 안 됩니다.")

    monkeypatch.setattr(ProviderClient, "call", forbidden_call)
    response = client.get("/api/v1/capabilities")
    assert response.status_code == 200
    envelope = response.json()
    limits = TripRequest.model_json_schema()["properties"]["max_options"]
    assert limits["default"] == 3
    assert limits["maximum"] == 5
    assert envelope["data"]["defaults"]["max_options"] == limits["default"]
    assert envelope["data"]["max_options"] == limits["maximum"]
    assert envelope["data"]["appointment"]["max_options"] == limits["maximum"]
    examples = json.loads(
        (Path(__file__).resolve().parents[3] / "Docs/api/examples.json").read_text(
            encoding="utf-8"
        )
    )
    shared = next(case for case in examples["cases"] if case["id"] == "capabilities")
    assert shared["response"]["data"] == envelope["data"]
    assert envelope["meta"]["is_demo"] is True
    assert calls == []
