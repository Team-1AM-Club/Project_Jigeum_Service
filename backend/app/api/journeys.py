"""Calculation endpoints guarded by persisted confirmation."""

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.journeys import ReplanRequest, TripRequest
from app.services.confirmation import PreviousSelection, canonical
from app.services.http_state import Operation, StateError, require_confirmed
from app.services.last_journey_service import (
    LastJourneyService,
    LastJourneyUnsupportedError,
    NoFeasibleJourneyError,
)
from app.services.mock.mock_providers import MockRoutingProvider
from app.services.plan_service import PlanService
from app.services.replan_service import ReplanService

router = APIRouter()
mock_routing_provider = MockRoutingProvider()
plan_service = PlanService(routing_provider=mock_routing_provider)
last_journey_service = LastJourneyService(routing_provider=mock_routing_provider)
replan_service = ReplanService(plan_service=plan_service)


async def calculate(body, request, key, db, *, replan=False, last=False):
    if replan and (
        not body.trip.get("origin_place_id")
        or not body.trip.get("destination_place_id")
    ):
        raise StateError(
            "VALIDATION_ERROR", message="trip origin and destination are required"
        )
    op = Operation(
        db,
        key,
        request.url.path,
        await request.json(),
        body.conversation_id,
        body.expected_revision,
    )
    conv, replay = op.check()
    if replay is not None:
        return replay
    raw = dict(body.trip) if replan else body.model_dump(mode="json")
    if replan:
        if not body.user_confirmed or not body.current_origin_place_id:
            raise StateError("USER_CONFIRMATION_REQUIRED")
        raw["origin_place_id"] = body.current_origin_place_id
        try:
            PreviousSelection.model_validate(body.previous_plan)
        except ValueError as exc:
            raise StateError("VALIDATION_ERROR", message=str(exc)) from exc
    if last and raw.get("kind") != "last_journey":
        raise StateError(
            "VALIDATION_ERROR", message="This endpoint requires kind=last_journey"
        )
    try:
        conditions = canonical(raw)
    except ValueError as exc:
        raise StateError("USER_CONFIRMATION_REQUIRED", message=str(exc)) from exc
    require_confirmed(conv, conditions)
    op.release()
    try:
        if replan:
            body = body.model_copy(update={"trip": conditions})
            result = await replan_service.replan(body, buffer_minutes=5)
        else:
            body = TripRequest.model_validate(
                dict(body.model_dump(mode="json"), **conditions)
            )
            if conditions["kind"] == "last_journey":
                result = await last_journey_service.plan_last_journey(
                    body, buffer_minutes=5
                )
            else:
                result = await plan_service.plan(body, buffer_minutes=5)
        data = result.model_dump(mode="json")
    except LastJourneyUnsupportedError as exc:
        return op.finish(
            None,
            status="unavailable",
            code="LAST_JOURNEY_UNSUPPORTED",
            message=str(exc),
        )
    except NoFeasibleJourneyError as exc:
        return op.finish(
            None, status="unavailable", code="NO_FEASIBLE_JOURNEY", message=str(exc)
        )
    except ValueError as exc:
        raise StateError("VALIDATION_ERROR", message=str(exc)) from exc
    return op.finish(data, dict(candidate_set=data))


@router.post("/journeys/plan")
async def journeys_plan(
    request_body: TripRequest,
    request: Request,
    idempotency_key: str | None = Header(None),
    db: Session = Depends(get_db),
):
    return await calculate(request_body, request, idempotency_key, db)


@router.post("/journeys/plan/last_journey")
async def journeys_plan_last_journey(
    request_body: TripRequest,
    request: Request,
    idempotency_key: str | None = Header(None),
    db: Session = Depends(get_db),
):
    return await calculate(request_body, request, idempotency_key, db, last=True)


@router.post("/journeys/replan")
async def journeys_replan(
    request_body: ReplanRequest,
    request: Request,
    idempotency_key: str | None = Header(None),
    db: Session = Depends(get_db),
):
    return await calculate(request_body, request, idempotency_key, db, replan=True)
