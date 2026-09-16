"""Local demo database startup and bounded conversation retention."""

import asyncio
from contextlib import asynccontextmanager, suppress
from sqlalchemy import inspect, select, text
from app import db as database
from app.models.conversation import Conversation
from app.models.idempotency import IdempotencyRecord
from app.models.plan import Plan
from app.services.conversation_service import (
    check_and_handle_expiry,
    hard_delete_if_eligible,
)


def initialize_database():
    for model in (Conversation, IdempotencyRecord, Plan):
        model.metadata.create_all(database.engine)
    existing = {
        column["name"]
        for column in inspect(database.engine).get_columns("conversations")
    }
    additions = {
        "interpret_draft": "JSON",
        "unresolved_fields": "JSON",
        "conditions_confirmed": "BOOLEAN NOT NULL DEFAULT FALSE",
        "places_confirmed": "BOOLEAN NOT NULL DEFAULT FALSE",
    }
    with database.engine.begin() as connection:
        for name, sql_type in additions.items():
            if name not in existing:
                connection.execute(
                    text(f"ALTER TABLE conversations ADD COLUMN {name} {sql_type}")
                )


def cleanup():
    with database.SessionLocal() as db:
        ids = list(db.scalars(select(Conversation.conversation_id)))
        for cid in ids:
            check_and_handle_expiry(db, cid)
            hard_delete_if_eligible(db, cid)


async def cleanup_loop():
    while True:
        await asyncio.sleep(60)
        await asyncio.to_thread(cleanup)


@asynccontextmanager
async def lifespan(app):
    if database.get_db in app.dependency_overrides:
        yield
        return
    initialize_database()
    cleanup()
    task = asyncio.create_task(cleanup_loop())
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
