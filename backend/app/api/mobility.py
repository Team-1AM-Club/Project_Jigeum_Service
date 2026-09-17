"""Persist interpretation drafts and explicit confirmation separately."""

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.mobility import InterpretRequest
from app.services.confirmation import FIELDS, ConfirmRequest, complete_draft
from app.services.http_state import Operation, StateError
from app.services.interpret_service import InterpretService
from app.services.mock.mock_providers import MockModelProvider, MockPlaceProvider

router = APIRouter()
mock_model_provider = MockModelProvider()
interpret_service = InterpretService(model_provider=mock_model_provider)


@router.post("/mobility/interpret")
async def mobility_interpret(
    request_body: InterpretRequest,
    request: Request,
    idempotency_key: str | None = Header(None),
    db: Session = Depends(get_db),
):
    if not request_body.natural_language.strip():
        raise StateError("VALIDATION_ERROR", message="자연어 입력이 필요합니다.")
    op = Operation(
        db,
        idempotency_key,
        request.url.path,
        await request.json(),
        request_body.conversation_id,
        request_body.expected_revision,
        create=True,
    )
    conv, replay = op.check()
    if replay is not None:
        return replay
    previous = conv.confirmed_conditions if conv else None
    op.release()
    interpreted = await interpret_service.interpret(request_body)
    draft = interpreted.trip_draft.model_dump(mode="json")
    mode = draft.get("transport_mode")
    modes = [{"walking": "walk"}.get(mode, mode)] if mode else ["subway", "bus"]
    draft.update(kind="appointment", service_date=None, transport_modes=modes)
    draft.update({k: v for k, v in request_body.context.items() if k in FIELDS})
    draft["ambiguities"] = request_body.context.get(
        "ambiguities", draft.get("ambiguities", [])
    )
    if "transport_modes" in request_body.context:
        draft["transport_mode"] = None
    normalized = complete_draft(draft)
    unresolved = [
        k for k in ("origin_place_id", "destination_place_id") if not draft.get(k)
    ]
    ambiguities = draft["ambiguities"]
    if not isinstance(ambiguities, list) or any(
        not isinstance(item, str) for item in ambiguities
    ):
        raise StateError(
            "VALIDATION_ERROR", message="ambiguities must be an array of field names"
        )
    unresolved.extend(ambiguities)
    for field in ("origin_place_id", "destination_place_id"):
        if draft.get(field) and not MockPlaceProvider().resolves(draft[field]):
            unresolved.append(field)
    if normalized is None:
        unresolved.append("conditions")
    unchanged = normalized is not None and normalized == previous and not unresolved
    updates = dict(interpret_draft=draft, unresolved_fields=unresolved)
    if not unchanged:
        updates.update(
            confirmed_conditions=None,
            conditions_confirmed=False,
            places_confirmed=False,
        )
    data = dict(
        trip_draft=draft,
        requires_confirmation=True,
        ready_for_plan=normalized is not None and not unresolved,
        missing_fields=unresolved,
        confirmation_questions=[
            q.model_dump(mode="json") for q in interpreted.confirmation_questions
        ],
        next_action="confirm",
    )
    return op.finish(data, updates, status="needs_confirmation")


@router.post("/conversations/{conversation_id}/confirm")
async def confirm(
    conversation_id: str,
    request_body: ConfirmRequest,
    request: Request,
    idempotency_key: str | None = Header(None),
    db: Session = Depends(get_db),
):
    op = Operation(
        db,
        idempotency_key,
        request.url.path,
        await request.json(),
        conversation_id,
        request_body.expected_revision,
    )
    conv, replay = op.check()
    if replay is not None:
        return replay
    conditions = request_body.confirmed_data.model_dump(mode="json")
    if (
        not conv.interpret_draft
        or conv.unresolved_fields
        or complete_draft(conv.interpret_draft) != conditions
    ):
        raise StateError("USER_CONFIRMATION_REQUIRED")
    return op.finish(
        dict(
            confirmed_conditions=conditions,
            conditions_confirmed=True,
            places_confirmed=True,
        ),
        dict(
            confirmed_conditions=conditions,
            conditions_confirmed=True,
            places_confirmed=True,
        ),
    )
