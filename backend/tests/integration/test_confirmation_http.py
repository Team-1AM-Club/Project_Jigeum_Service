"""Persisted confirmation must guard the real HTTP calculation boundary."""

import uuid
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db import get_db
from app.models.conversation import Conversation
from app.models.idempotency import IdempotencyRecord


TRIP = dict(
    kind="appointment",
    origin_place_id="place_seoul_station",
    destination_place_id="place_gangnam_station",
    arrival_deadline="2026-09-16T19:00:00+09:00",
    arrival_preference_minutes=10,
    service_date=None,
    transport_modes=["subway", "bus"],
)


@pytest.fixture
def http_state():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Conversation.metadata.create_all(engine)
    IdempotencyRecord.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def session():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = session
    with TestClient(app) as client:
        yield client, factory
    app.dependency_overrides.clear()
    engine.dispose()


def post(client, path, body, key=None):
    return client.post(
        "/api/v1" + path,
        json=body,
        headers={"Idempotency-Key": key or str(uuid.uuid4())},
    )


def draft(client, trip=None, **extra):
    response = post(
        client,
        "/mobility/interpret",
        dict(
            natural_language="서울역에서 강남역으로 이동", context=trip or TRIP, **extra
        ),
    )
    assert response.status_code == 200, response.text
    return response.json()["meta"]


def confirm(client, meta, trip=None, key=None):
    return post(
        client,
        f"/conversations/{meta['conversation_id']}/confirm",
        dict(expected_revision=meta["revision"], confirmed_data=trip or TRIP),
        key,
    )


def plan_body(meta, trip=None):
    return dict(
        trip or TRIP,
        conversation_id=meta["conversation_id"],
        expected_revision=meta["revision"],
    )


def snapshot(factory, cid):
    with factory() as db:
        conv = db.get(Conversation, cid)
        assert conv is not None, "interpret must persist the conversation"
        return deepcopy(conv.to_dict()), len(
            db.scalars(select(IdempotencyRecord)).all()
        )


def test_confirm_plan_and_replay_without_side_effects(http_state, monkeypatch):
    client, factory = http_state
    meta = draft(client)
    from app.api.journeys import plan_service

    original = plan_service.plan
    calls = []

    async def counted(*args, **kwargs):
        calls.append(1)
        return await original(*args, **kwargs)

    monkeypatch.setattr(plan_service, "plan", counted)
    before = snapshot(factory, meta["conversation_id"])
    denied = post(client, "/journeys/plan", plan_body(meta))
    assert denied.status_code == 422
    assert denied.json()["error"]["code"] == "USER_CONFIRMATION_REQUIRED"
    assert snapshot(factory, meta["conversation_id"]) == before
    assert calls == []
    confirmation = confirm(client, meta)
    assert confirmation.status_code == 200, confirmation.text
    meta = confirmation.json()["meta"]
    key = str(uuid.uuid4())
    body = plan_body(meta)
    first = post(client, "/journeys/plan", body, key)
    assert first.status_code == 200, first.text
    before = snapshot(factory, meta["conversation_id"])
    replay = post(client, "/journeys/plan", body, key)
    assert replay.json() == first.json()
    assert snapshot(factory, meta["conversation_id"]) == before
    assert len(calls) == 1
    conflict = post(client, "/journeys/plan", dict(body, max_options=1), key)
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"
    assert snapshot(factory, meta["conversation_id"]) == before
    stale = post(client, "/journeys/plan", body)
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "CONVERSATION_VERSION_CONFLICT"
    assert len(calls) == 1


def test_confirm_cannot_overwrite_draft_and_normalizes_conditions(http_state):
    client, factory = http_state
    meta = draft(client)
    before = snapshot(factory, meta["conversation_id"])
    bad = confirm(client, meta, dict(TRIP, destination_place_id="other"))
    assert bad.status_code == 422
    assert bad.json()["error"]["code"] == "USER_CONFIRMATION_REQUIRED"
    assert snapshot(factory, meta["conversation_id"]) == before
    equivalent = dict(
        TRIP,
        arrival_deadline="2026-09-16T10:00:00Z",
        transport_modes=["bus", "subway", "bus"],
    )
    key = str(uuid.uuid4())
    good = confirm(client, meta, equivalent, key)
    assert good.status_code == 200, good.text
    before = snapshot(factory, meta["conversation_id"])
    assert confirm(client, meta, equivalent, key).json() == good.json()
    assert snapshot(factory, meta["conversation_id"]) == before
    assert confirm(client, meta).status_code == 409


def test_interpret_change_invalidates_but_equal_conditions_preserve(http_state):
    client, factory = http_state
    meta = draft(client)
    meta = confirm(client, meta).json()["meta"]
    meta = draft(
        client,
        conversation_id=meta["conversation_id"],
        expected_revision=meta["revision"],
    )
    with factory() as db:
        assert (
            db.get(Conversation, meta["conversation_id"]).confirmed_conditions
            is not None
        )
    changed = dict(TRIP, arrival_preference_minutes=20)
    meta = draft(
        client,
        changed,
        conversation_id=meta["conversation_id"],
        expected_revision=meta["revision"],
    )
    denied = post(client, "/journeys/plan", plan_body(meta, changed))
    assert denied.status_code == 422
    with factory() as db:
        assert (
            db.get(Conversation, meta["conversation_id"]).confirmed_conditions is None
        )


def test_interpret_replay_creates_one_conversation(http_state):
    client, factory = http_state
    key = str(uuid.uuid4())
    body = dict(natural_language="서울역에서 강남역", context=TRIP)
    first = post(client, "/mobility/interpret", body, key)
    second = post(client, "/mobility/interpret", body, key)
    assert first.json() == second.json()
    with factory() as db:
        assert len(db.scalars(select(Conversation)).all()) == 1
    assert (
        post(
            client, "/mobility/interpret", dict(body, natural_language="changed"), key
        ).status_code
        == 409
    )


def test_replan_uses_confirmed_deadline_and_selected_summary(http_state):
    client, factory = http_state
    meta = confirm(client, draft(client)).json()["meta"]
    previous = dict(
        plan_id="chosen-plan",
        selected_option_id="chosen-option",
        recommended_leave_at="2026-09-16T18:00:00+09:00",
        estimated_arrival_at="2026-09-16T18:40:30+09:00",
    )
    body = dict(
        conversation_id=meta["conversation_id"],
        expected_revision=meta["revision"],
        trip=TRIP,
        previous_plan=previous,
        current_origin_place_id=TRIP["origin_place_id"],
        reason="manual",
        user_confirmed=True,
    )
    before = snapshot(factory, meta["conversation_id"])
    denied = post(
        client, "/journeys/replan", dict(body, current_origin_place_id="changed")
    )
    assert denied.status_code == 422
    assert snapshot(factory, meta["conversation_id"]) == before
    result = post(client, "/journeys/replan", body)
    assert result.status_code == 200, result.text
    comparison = result.json()["data"]["comparison"]
    assert comparison["arrival_change_minutes"] == 9.5
    assert comparison["previous_plan_id"] == "chosen-plan"
    assert comparison["previous_selected_option_id"] == "chosen-option"
    with factory() as db:
        assert (
            db.get(Conversation, meta["conversation_id"]).active_selected_plan is None
        )


@pytest.mark.parametrize(
    "error,code",
    [
        ("LastJourneyUnsupportedError", "LAST_JOURNEY_UNSUPPORTED"),
        ("NoFeasibleJourneyError", "NO_FEASIBLE_JOURNEY"),
    ],
)
def test_unavailable_replayed_without_recalculation(
    http_state, monkeypatch, error, code
):
    client, factory = http_state
    trip = dict(
        TRIP,
        kind="last_journey",
        arrival_deadline=None,
        arrival_preference_minutes=None,
        service_date="2026-09-16",
    )
    meta = confirm(client, draft(client, trip), trip).json()["meta"]
    from app.api.journeys import last_journey_service
    from app.services import last_journey_service as errors

    calls = []

    async def unavailable(*args, **kwargs):
        calls.append(1)
        raise getattr(errors, error)()

    monkeypatch.setattr(last_journey_service, "plan_last_journey", unavailable)
    body, key = plan_body(meta, trip), str(uuid.uuid4())
    first = post(client, "/journeys/plan", body, key)
    assert first.status_code == 200
    assert first.json()["status"] == "unavailable"
    assert first.json()["error"]["code"] == code
    before = snapshot(factory, meta["conversation_id"])
    assert post(client, "/journeys/plan", body, key).json() == first.json()
    assert snapshot(factory, meta["conversation_id"]) == before
    assert len(calls) == 1


def test_provider_failure_preserves_state(http_state, monkeypatch):
    client, factory = http_state
    meta = confirm(client, draft(client)).json()["meta"]
    from app.api.journeys import mock_routing_provider
    from app.services.provider_interfaces import ProviderResult

    async def failed(**kwargs):
        return ProviderResult(
            ok=False, error_code="ROUTING_PROVIDER_UNAVAILABLE", error_message="offline"
        )

    monkeypatch.setattr(mock_routing_provider, "search_options", failed)
    before = snapshot(factory, meta["conversation_id"])
    result = post(client, "/journeys/plan", plan_body(meta))
    assert result.status_code == 503
    assert snapshot(factory, meta["conversation_id"]) == before


def test_new_unresolved_field_revokes_confirmation(http_state):
    client, factory = http_state
    meta = confirm(client, draft(client)).json()["meta"]
    meta = draft(
        client,
        dict(TRIP, origin_place_id=None),
        conversation_id=meta["conversation_id"],
        expected_revision=meta["revision"],
    )
    before = snapshot(factory, meta["conversation_id"])
    assert before[0]["conditions_confirmed"] is False
    assert before[0]["places_confirmed"] is False
    assert confirm(client, meta).status_code == 422
    assert snapshot(factory, meta["conversation_id"]) == before


def test_defaults_and_null_match_explicit_contract_defaults(http_state):
    client, factory = http_state
    trip = dict(TRIP, arrival_preference_minutes=None, transport_modes=None)
    meta = draft(client, trip)
    explicit = dict(TRIP, arrival_preference_minutes=0)
    result = confirm(client, meta, explicit)
    assert result.status_code == 200, result.text
    body = plan_body(result.json()["meta"], trip)
    assert post(client, "/journeys/plan", body).status_code == 200


def test_last_journey_uses_service_date_and_zero_preference(http_state):
    client, _ = http_state
    trip = dict(
        TRIP,
        kind="last_journey",
        service_date="2026-10-01",
        arrival_deadline=None,
        arrival_preference_minutes=0,
    )
    response = confirm(client, draft(client, trip), trip)
    assert response.status_code == 200, response.text
    result = post(client, "/journeys/plan", plan_body(response.json()["meta"], trip))
    assert result.status_code == 200, result.text
    assert result.json()["data"]["operating_date"] == "2026-10-01"


def test_provider_revision_race_discards_calculated_result(http_state, monkeypatch):
    client, factory = http_state
    meta = confirm(client, draft(client)).json()["meta"]
    from app.api.journeys import plan_service

    original = plan_service.plan

    async def competing(*args, **kwargs):
        with factory() as db:
            conv = db.get(Conversation, meta["conversation_id"])
            conv.revision += 1
            conv.candidate_set = {"winner": True}
            db.commit()
        return await original(*args, **kwargs)

    monkeypatch.setattr(plan_service, "plan", competing)
    response = post(client, "/journeys/plan", plan_body(meta))
    assert response.status_code == 409
    state, records = snapshot(factory, meta["conversation_id"])
    assert state["revision"] == meta["revision"] + 1
    assert state["candidate_set"] == {"winner": True}
    assert records == 2


def test_expiry_clears_draft_and_denies_replay(http_state):
    from datetime import datetime, timezone, timedelta

    client, factory = http_state
    meta = draft(client)
    key = str(uuid.uuid4())
    response = confirm(client, meta, key=key)
    assert response.status_code == 200
    with factory() as db:
        conv = db.get(Conversation, meta["conversation_id"])
        conv.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
    result = confirm(client, meta, key=key)
    assert result.status_code == 410
    state, _ = snapshot(factory, meta["conversation_id"])
    assert state["interpret_draft"] is None
    assert state["confirmed_conditions"] is None
    assert state["revision"] == response.json()["meta"]["revision"]


def test_transport_modes_control_provider_results(http_state):
    client, _ = http_state
    trip = dict(TRIP, transport_modes=["bus"])
    meta = confirm(client, draft(client, trip), trip).json()["meta"]
    result = post(client, "/journeys/plan", plan_body(meta, trip))
    assert result.status_code == 200
    # Demo has no bus route. It must not return its subway fixture.
    assert result.json()["status"] == "unavailable"
    assert result.json()["error"]["code"] == "NO_FEASIBLE_JOURNEY"


def test_fresh_server_initializes_database(tmp_path, monkeypatch):
    import app.db as database

    engine = create_engine(
        "sqlite:///" + str(tmp_path / "fresh.db"),
        connect_args={"check_same_thread": False},
    )
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "SessionLocal", sessionmaker(bind=engine))
    with TestClient(app) as client:
        meta = draft(client)
        response = confirm(client, meta)
        assert response.status_code == 200, response.text
    engine.dispose()


def test_unknown_place_cannot_be_confirmed(http_state):
    client, _ = http_state
    trip = dict(TRIP, origin_place_id="invented-place")
    meta = draft(client, trip)
    response = confirm(client, meta, trip)
    assert response.status_code == 422


def test_interpret_provider_failure_does_not_mutate(http_state, monkeypatch):
    client, factory = http_state
    meta = confirm(client, draft(client)).json()["meta"]
    from app.api.mobility import mock_model_provider
    from app.services.provider_interfaces import ProviderResult

    async def failed(**kwargs):
        return ProviderResult(ok=False, error_code="AI_UNAVAILABLE")

    monkeypatch.setattr(mock_model_provider, "interpret", failed)
    before = snapshot(factory, meta["conversation_id"])
    result = post(
        client,
        "/mobility/interpret",
        dict(
            natural_language="서울역에서 강남역",
            conversation_id=meta["conversation_id"],
            expected_revision=meta["revision"],
        ),
    )
    assert result.status_code == 503
    assert snapshot(factory, meta["conversation_id"]) == before


def test_same_conditions_with_new_ambiguity_revoke_consent(http_state):
    client, factory = http_state
    meta = confirm(client, draft(client)).json()["meta"]
    meta = draft(
        client,
        dict(TRIP, ambiguities=["arrival_deadline"]),
        conversation_id=meta["conversation_id"],
        expected_revision=meta["revision"],
    )
    state, _ = snapshot(factory, meta["conversation_id"])
    assert state["conditions_confirmed"] is False
    assert post(client, "/journeys/plan", plan_body(meta)).status_code == 422


@pytest.mark.parametrize(
    "changes",
    [
        {"conditions_confirmed": False},
        {"places_confirmed": False},
        {"confirmed_conditions": None},
    ],
)
def test_each_persisted_prerequisite_is_required(http_state, changes):
    client, factory = http_state
    meta = confirm(client, draft(client)).json()["meta"]
    with factory() as db:
        conv = db.get(Conversation, meta["conversation_id"])
        for field, value in changes.items():
            setattr(conv, field, value)
        db.commit()
    before = snapshot(factory, meta["conversation_id"])
    response = post(client, "/journeys/plan", plan_body(meta))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "USER_CONFIRMATION_REQUIRED"
    assert snapshot(factory, meta["conversation_id"]) == before


def test_deleted_conversation_cannot_replay_old_success(http_state):
    client, factory = http_state
    meta = draft(client)
    key = str(uuid.uuid4())
    assert confirm(client, meta, key=key).status_code == 200
    with factory() as db:
        db.delete(db.get(Conversation, meta["conversation_id"]))
        db.commit()
    response = confirm(client, meta, key=key)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "CONVERSATION_NOT_FOUND"


def test_replan_requires_explicit_user_request(http_state):
    client, factory = http_state
    meta = confirm(client, draft(client)).json()["meta"]
    body = dict(
        conversation_id=meta["conversation_id"],
        expected_revision=meta["revision"],
        trip=TRIP,
        current_origin_place_id=TRIP["origin_place_id"],
        reason="manual",
        previous_plan=dict(
            plan_id="previous",
            selected_option_id="selected",
            recommended_leave_at="2026-09-16T18:00:00+09:00",
            estimated_arrival_at="2026-09-16T18:50:00+09:00",
        ),
    )
    before = snapshot(factory, meta["conversation_id"])
    response = post(client, "/journeys/replan", body)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "USER_CONFIRMATION_REQUIRED"
    assert snapshot(factory, meta["conversation_id"]) == before


def test_whitespace_interpret_is_validation_error(http_state):
    client, _ = http_state
    response = post(client, "/mobility/interpret", {"natural_language": "   "})
    assert response.status_code == 422

def test_candidate_sources_survive_http_and_idempotent_replay(http_state, monkeypatch):
    from unittest.mock import AsyncMock

    from app.api.journeys import plan_service
    from app.domain.transit import Evidence
    from app.services.provider_interfaces import ProviderResult, RoutingProvider

    client, _ = http_state
    source = {
        "provider": "synthetic",
        "basis": "schedule",
        "retrieved_at": "2026-09-16T18:00:00+09:00",
        "service_date": "2026-09-16",
    }
    provider = AsyncMock(spec=RoutingProvider)
    provider.search_options.return_value = ProviderResult(
        ok=True,
        data=[
            {
                "option_id": "synthetic-source",
                "total_duration_minutes": 40,
                "transport_mode": "subway",
                "legs": [],
                "sources": [source],
            }
        ],
        evidence=(
            Evidence.model_validate(
                dict(
                    source,
                    service="synthetic-timetable",
                    operation="synthetic-operation",
                    revision="schedule-r2",
                    reference_date="2026-09-01",
                )
            ),
        ),
    )
    monkeypatch.setattr(plan_service, "routing_provider", provider)
    trip = dict(TRIP, transport_modes=["subway"])
    meta = draft(client, trip)
    denied = post(client, "/journeys/plan", plan_body(meta, trip))
    assert denied.json()["error"]["code"] == "USER_CONFIRMATION_REQUIRED"
    provider.search_options.assert_not_awaited()
    confirmation = confirm(client, meta, trip)
    assert confirmation.status_code == 200
    meta = confirmation.json()["meta"]
    body = plan_body(meta, trip)
    key = str(uuid.uuid4())
    first = post(client, "/journeys/plan", body, key)
    assert first.status_code == 200, first.text
    candidate = first.json()["data"]["comparison"]["options"][0]
    assert candidate["sources"] == [dict(source, basis_at=None)]
    assert any(
        warning["code"] == "SOURCE_REFERENCE" for warning in candidate["warnings"]
    )
    replay = post(client, "/journeys/plan", body, key)
    assert replay.status_code == 200
    assert replay.json() == first.json()
    provider.search_options.assert_awaited_once()
