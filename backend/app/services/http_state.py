"""Check, release DB, calculate, compare-and-swap state and replay record."""

import json
import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from app.models.conversation import Conversation, ConversationStatus
from app.services.conversation_service import check_and_handle_expiry
from app.services.idempotency_service import (
    compute_payload_hash,
    get_idempotency_record,
    save_idempotency_record,
    validate_idempotency_key_format,
)


class StateError(Exception):
    def __init__(self, code, status=422, message=None):
        self.code, self.status, self.message = code, status, message or code


def envelope(data=None, *, conv=None, status="ok", code=None, message=None):
    meta = dict(
        request_id=str(uuid.uuid4()),
        server_time=datetime.now(timezone.utc).isoformat(),
        api_version="v1",
        is_demo=True,
    )
    if conv is not None:
        meta.update(
            conversation_id=conv.conversation_id,
            revision=conv.revision,
            expires_at=conv.expires_at.isoformat(),
        )
    return dict(
        status=status,
        data=data,
        error=None
        if code is None
        else dict(
            code=code,
            message=message or code,
            retryable=code
            in ("AI_UNAVAILABLE", "ROUTING_PROVIDER_UNAVAILABLE", "UPSTREAM_TIMEOUT"),
            details=[],
        ),
        meta=meta,
    )


class Operation:
    def __init__(self, db, key, path, body, cid, revision, *, create=False):
        self.db, self.path, self.body, self.revision = db, path, body, revision
        try:
            self.key = validate_idempotency_key_format(key).lower()
        except ValueError as exc:
            raise StateError("VALIDATION_ERROR", message=str(exc)) from exc
        self.cid = cid or str(
            uuid.uuid5(uuid.NAMESPACE_URL, "jigeum:interpret:" + self.key)
        )
        self.create = create and cid is None
        self.hash = compute_payload_hash("POST", path, self.cid, revision, body)

    def check(self):
        conv, expired = check_and_handle_expiry(self.db, self.cid)
        if expired:
            raise StateError("CONVERSATION_EXPIRED", 410)
        record = get_idempotency_record(self.db, self.cid, self.key)
        if record is not None:
            if conv is None:
                raise StateError("CONVERSATION_NOT_FOUND", 404)
            if record.payload_hash != self.hash:
                raise StateError("IDEMPOTENCY_KEY_REUSED", 409)
            return conv, json.loads(record.response_data)
        if conv is None:
            if not self.create:
                raise StateError("CONVERSATION_NOT_FOUND", 404)
            if self.revision is not None:
                raise StateError(
                    "VALIDATION_ERROR",
                    message="New conversations must omit expected_revision",
                )
            return None, None
        if self.revision is None:
            raise StateError(
                "VALIDATION_ERROR", message="expected_revision is required"
            )
        if conv.revision != self.revision:
            raise StateError("CONVERSATION_VERSION_CONFLICT", 409)
        return conv, None

    def release(self):
        self.db.rollback()

    def finish(self, data, updates=None, status="ok", code=None, message=None):
        conv, replay = self.check()
        if replay is not None:
            return replay
        now = datetime.now(timezone.utc)
        updates = dict(updates or {})
        if conv is None:
            conv = Conversation(
                conversation_id=self.cid,
                revision=1,
                created_at=now,
                updated_at=now,
                expires_at=now + timedelta(hours=24),
                **updates,
            )
            self.db.add(conv)
        else:
            changed = self.db.execute(
                update(Conversation)
                .where(
                    Conversation.conversation_id == self.cid,
                    Conversation.revision == self.revision,
                    Conversation.status == ConversationStatus.ACTIVE,
                    Conversation._expires_at > now,
                )
                .values(**updates, revision=self.revision + 1, updated_at=now)
                .execution_options(synchronize_session=False)
            )
            if changed.rowcount != 1:
                self.db.rollback()
                _, replay = self.check()
                if replay is not None:
                    return replay
                raise StateError("CONVERSATION_VERSION_CONFLICT", 409)
            self.db.refresh(conv)
        try:
            self.db.flush()
            result = envelope(
                data, conv=conv, status=status, code=code, message=message
            )
            save_idempotency_record(
                self.db,
                self.cid,
                self.key,
                "POST",
                self.path,
                self.revision,
                self.body,
                result,
                200,
            )
            self.db.commit()
            return result
        except IntegrityError:
            self.db.rollback()
            _, replay = self.check()
            if replay is not None:
                return replay
            raise


def require_confirmed(conv, conditions):
    if (
        conv is None
        or not conv.conditions_confirmed
        or not conv.places_confirmed
        or not conv.confirmed_conditions
        or conv.unresolved_fields
        or conv.confirmed_conditions != conditions
    ):
        raise StateError("USER_CONFIRMATION_REQUIRED")
