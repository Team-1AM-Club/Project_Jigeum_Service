"""공동 승인 Source의 전환 입력과 신규 출력 계약."""

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from app.domain.transit import Evidence
from app.schemas.common import DataWarning, Source
from app.schemas.journeys import Plan, ReplanRequest, TripRequest
from app.services.http_state import StateError
from app.services.last_journey_service import LastJourneyService, NoFeasibleJourneyError
from app.services.plan_service import PlanService
from app.services.provider_interfaces import ProviderResult, RoutingProvider
from app.services.replan_service import ReplanService


def source_data(**changes):
    data = {
        "provider": "synthetic",
        "basis": "schedule",
        "retrieved_at": "2026-09-16T18:00:00+09:00",
        "service_date": "2026-09-16",
    }
    data.update(changes)
    return data


def test_missing_basis_time_is_accepted_and_new_output_always_contains_null():
    result = Source.model_validate(source_data()).model_dump(mode="json")
    assert "basis_at" in result
    assert result["basis_at"] is None


def test_null_never_uses_retrieved_time_as_substitute():
    source = Source.model_validate(source_data(basis="realtime", basis_at=None))
    assert source.basis_at is None
    assert source.retrieved_at is not None


def test_basis_and_retrieved_time_remain_separate_and_output_is_seoul():
    result = Source.model_validate(
        source_data(basis="realtime", basis_at="2026-09-16T08:59:00Z")
    ).model_dump(mode="json")
    assert result["basis_at"] == "2026-09-16T17:59:00+09:00"
    assert result["retrieved_at"] == "2026-09-16T18:00:00+09:00"


@pytest.mark.parametrize("value", ["2026-09-16", "2026-09-16T18:00:00"])
def test_date_only_or_naive_timestamp_does_not_create_basis_time(value):
    with pytest.raises(ValidationError):
        Source.model_validate(source_data(basis_at=value))


def test_approved_fixture_is_demo_and_matches_shared_example():
    root = Path(__file__).resolve().parents[3]
    approved = json.loads(
        (
            root
            / "specs/004-public-transit-api-integration/contracts/flat-plan-proposal.json"
        ).read_text(encoding="utf-8")
    )
    cases = json.loads((root / "Docs/api/examples.json").read_text(encoding="utf-8"))[
        "cases"
    ]
    shared = next(case for case in cases if case["id"] == "transit_flat_plan_004")
    assert shared["response"] == approved
    assert approved["meta"]["is_demo"] is True
    assert "plan" not in approved["data"]
    assert approved["data"]["comparison"]["selected_option_id"] is None
    for candidate in approved["data"]["comparison"]["options"]:
        for source in candidate["sources"]:
            assert Source.model_validate(source).basis == "demo"


def test_plan_schema_preserves_candidate_sources_and_explicit_unknown_time():
    root = Path(__file__).resolve().parents[3]
    approved = json.loads(
        (
            root
            / "specs/004-public-transit-api-integration/contracts/flat-plan-proposal.json"
        ).read_text(encoding="utf-8")
    )
    result = Plan.model_validate(approved["data"]).model_dump(mode="json")
    candidate = result["comparison"]["options"][0]
    assert (
        candidate["sources"] == approved["data"]["comparison"]["options"][0]["sources"]
    )
    assert (
        candidate["warnings"]
        == approved["data"]["comparison"]["options"][0]["warnings"]
    )


def routing_option(option_id, sources):
    return {
        "option_id": option_id,
        "total_duration_minutes": 40,
        "transport_mode": "subway",
        "legs": [],
        "sources": sources,
    }


def appointment():
    return TripRequest(
        conversation_id="synthetic-conversation",
        origin_place_id="synthetic-origin",
        destination_place_id="synthetic-destination",
        arrival_deadline="2026-09-16T19:00:00+09:00",
        arrival_preference_minutes=10,
        transport_mode="subway",
    )


@pytest.mark.asyncio
async def test_schedule_source_survives_plan_and_warns_without_inventing_basis_time():
    option = routing_option("schedule", [source_data()])
    provider = AsyncMock(spec=RoutingProvider)
    provider.search_options.return_value = ProviderResult(ok=True, data=[option])
    result = (await PlanService(provider).plan(appointment())).model_dump(mode="json")
    candidate = result["comparison"]["options"][0]
    assert candidate["sources"][0] == dict(source_data(), basis_at=None)
    assert any("2026-09-16" in warning["message"] for warning in candidate["warnings"])
    assert "basis_at" not in option["sources"][0]  # provider 자료를 변형하지 않음


@pytest.mark.parametrize("basis_at", [None, "2026-09-16T18:01:00+09:00"])
@pytest.mark.asyncio
async def test_unverified_realtime_candidate_is_excluded_not_relabelled_schedule(
    basis_at,
):
    provider = AsyncMock(spec=RoutingProvider)
    provider.search_options.return_value = ProviderResult(
        ok=True,
        data=[
            routing_option(
                "unverified", [source_data(basis="realtime", basis_at=basis_at)]
            ),
            routing_option("documented", [source_data()]),
        ],
    )
    result = await PlanService(provider).plan(appointment())
    assert [candidate.option_id for candidate in result.comparison.options] == [
        "documented"
    ]


@pytest.mark.asyncio
async def test_all_unverified_realtime_returns_unavailable_without_mock_fallback():
    provider = AsyncMock(spec=RoutingProvider)
    provider.search_options.return_value = ProviderResult(
        ok=True, data=[routing_option("unverified", [source_data(basis="realtime")])]
    )
    with pytest.raises(NoFeasibleJourneyError):
        await PlanService(provider).plan(appointment())


def verified_evidence(source, **changes):
    return Evidence.model_validate(
        dict(
            source,
            service="synthetic-arrival",
            operation="synthetic-observation",
            usage_rules_verified=True,
            verification_state="normalized",
        )
        | changes
    )


@pytest.mark.asyncio
async def test_matching_verified_realtime_is_preserved_without_relabelling():
    source = source_data(basis="realtime", basis_at="2026-09-16T17:59:00+09:00")
    provider = AsyncMock(spec=RoutingProvider)
    provider.search_options.return_value = ProviderResult(
        ok=True,
        data=[routing_option("verified", [source])],
        evidence=(verified_evidence(source),),
    )
    plan = await PlanService(provider).plan(appointment())
    assert plan.comparison.options[0].sources[0].model_dump(mode="json") == source


@pytest.mark.parametrize(
    "changes",
    [
        {"provider": "different-provider"},
        {"service_date": "2026-09-15"},
        {"basis_at": "2026-09-16T17:58:00+09:00"},
        {"retrieved_at": "2026-09-16T18:01:00+09:00"},
        {"usage_rules_verified": False},
        {"verification_state": "documented"},
    ],
)
@pytest.mark.asyncio
async def test_unrelated_or_unverified_evidence_cannot_approve_realtime(changes):
    source = source_data(basis="realtime", basis_at="2026-09-16T17:59:00+09:00")
    provider = AsyncMock(spec=RoutingProvider)
    provider.search_options.return_value = ProviderResult(
        ok=True,
        data=[routing_option("unverified", [source])],
        evidence=(verified_evidence(source, **changes),),
    )
    with pytest.raises(NoFeasibleJourneyError):
        await PlanService(provider).plan(appointment())


@pytest.mark.parametrize(
    "changes",
    [
        {"sources": None},
        {"sources": [source_data(basis_at="synthetic-private-sentinel")]},
        {"warnings": "synthetic-private-sentinel"},
        {"warnings": [{"message": "synthetic-private-sentinel"}]},
    ],
)
@pytest.mark.asyncio
async def test_invalid_metadata_returns_safe_error(changes):
    provider = AsyncMock(spec=RoutingProvider)
    provider.search_options.return_value = ProviderResult(
        ok=True, data=[routing_option("invalid", []) | changes]
    )
    with pytest.raises(StateError) as caught:
        await PlanService(provider).plan(appointment())
    assert caught.value.code == "UPSTREAM_RESPONSE_INVALID"
    assert "synthetic-private-sentinel" not in str(caught.value)


@pytest.mark.asyncio
async def test_legacy_option_has_empty_sources_without_fabricated_provenance():
    option = routing_option("legacy", [])
    del option["sources"]
    provider = AsyncMock(spec=RoutingProvider)
    provider.search_options.return_value = ProviderResult(ok=True, data=[option])
    plan = await PlanService(provider).plan(appointment())
    assert plan.comparison.options[0].sources == []
    assert plan.comparison.options[0].warnings == []


@pytest.mark.parametrize("kind", ["appointment", "last_journey"])
@pytest.mark.asyncio
async def test_sources_survive_last_plan_and_both_replan_branches(kind):
    source = source_data(basis="demo", basis_at=None)
    option = routing_option("synthetic", [source])
    warning = {"code": "SYNTHETIC", "message": "합성 데이터입니다."}
    option["warnings"] = [warning]
    provider = AsyncMock(spec=RoutingProvider)
    provider.health.return_value = True
    provider.search_options.return_value = ProviderResult(ok=True, data=[option])
    trip = appointment().model_dump(mode="json")
    trip.update(kind=kind, service_date="2026-09-16")
    if kind == "last_journey":
        plan = await LastJourneyService(provider).plan_last_journey(
            TripRequest.model_validate(trip)
        )
        assert plan.comparison.options[0].sources[0].basis == "demo"
    response = await ReplanService(PlanService(provider)).replan(
        ReplanRequest(
            conversation_id="synthetic-conversation",
            trip=trip,
            reason="manual",
            user_confirmed=True,
        )
    )
    candidate = response.comparison.new_plan.comparison.options[0].model_dump(
        mode="json"
    )
    assert candidate["sources"] == [source]
    assert candidate["warnings"] == [warning]
    assert response.comparison.previous_plan_preserved is True
    assert "_calculated_arrival" not in option


def test_plan_schema_declares_strict_source_and_nullable_basis_time():
    definitions = Plan.model_json_schema()["$defs"]
    assert definitions["PlanSummary"]["properties"]["sources"]["items"] == {
        "$ref": "#/$defs/Source"
    }
    assert definitions["Source"]["additionalProperties"] is False
    assert {"type": "null"} in definitions["Source"]["properties"]["basis_at"]["anyOf"]
    assert "retrieved_at" in definitions["Source"]["required"]


def test_shared_source_schema_matches_backend_models():
    root = Path(__file__).resolve().parents[3]
    schema = json.loads(
        (root / "Docs/api/source-envelope.schema.json").read_text(encoding="utf-8")
    )
    assert schema["$defs"]["Source"] == Source.model_json_schema()
    assert schema["$defs"]["DataWarning"] == DataWarning.model_json_schema()


@pytest.mark.parametrize("basis", ["static", "schedule"])
@pytest.mark.asyncio
async def test_static_reference_revision_and_validity_are_preserved_as_warnings(basis):
    source = source_data()
    evidence = verified_evidence(
        source,
        basis=basis,
        reference_date="2026-09-01",
        revision="schedule-r2",
        valid_from="2026-09-01",
        valid_until="2026-09-30",
    )
    option = routing_option("documented", [source])
    provider = AsyncMock(spec=RoutingProvider)
    provider.search_options.return_value = ProviderResult(
        ok=True, data=[option], evidence=(evidence, evidence)
    )
    plan = await PlanService(provider).plan(appointment())
    candidate = plan.comparison.options[0]
    warnings = [w for w in candidate.warnings if w.code == "SOURCE_REFERENCE"]
    assert len(warnings) == 1
    assert "synthetic" in warnings[0].message
    assert "기준일: 2026-09-01" in warnings[0].message
    assert "개정: schedule-r2" in warnings[0].message
    assert "적용 시작일: 2026-09-01" in warnings[0].message
    assert "적용 종료일: 2026-09-30" in warnings[0].message
    assert candidate.sources[0].basis_at is None
    assert "warnings" not in option


@pytest.mark.asyncio
async def test_partial_static_metadata_does_not_invent_other_bounds():
    source = source_data()
    provider = AsyncMock(spec=RoutingProvider)
    provider.search_options.return_value = ProviderResult(
        ok=True,
        data=[routing_option("partial", [source])],
        evidence=(verified_evidence(source, reference_date="2026-09-01"),),
    )
    plan = await PlanService(provider).plan(appointment())
    warning = next(
        w for w in plan.comparison.options[0].warnings if w.code == "SOURCE_REFERENCE"
    )
    assert "기준일: 2026-09-01" in warning.message
    assert "개정:" not in warning.message
    assert "적용 시작일:" not in warning.message
    assert "적용 종료일:" not in warning.message


@pytest.mark.parametrize(
    "changes",
    [
        {"provider": "another-provider"},
        {"service_date": "2026-09-15"},
        {"retrieved_at": "2026-09-16T17:00:00+09:00"},
        {"basis": "demo"},
    ],
)
@pytest.mark.asyncio
async def test_static_metadata_from_other_source_is_not_attached(changes):
    source = source_data()
    provider = AsyncMock(spec=RoutingProvider)
    provider.search_options.return_value = ProviderResult(
        ok=True,
        data=[routing_option("documented", [source])],
        evidence=(verified_evidence(source, revision="unrelated-revision", **changes),),
    )
    plan = await PlanService(provider).plan(appointment())
    assert all(
        w.code != "SOURCE_REFERENCE" for w in plan.comparison.options[0].warnings
    )
