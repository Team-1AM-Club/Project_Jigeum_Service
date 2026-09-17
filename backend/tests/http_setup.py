"""Explicit HTTP prerequisites for the existing calculation fixtures.

Each caller requests setup; TestClient itself never inserts consent.
"""

import uuid


def interpreted_request(client, body):
    body = dict(body)
    body.pop("conversation_id", None)
    body.pop("expected_revision", None)
    return body


def confirmed_request(client, body, *, last=False, replan=False, confirm=True):
    source = body.get("trip", {}) if replan else body
    conditions = dict(
        kind="last_journey" if last else "appointment",
        origin_place_id=source.get("origin_place_id") or "place_seoul_station",
        destination_place_id=source.get("destination_place_id")
        or "place_gangnam_station",
        arrival_deadline=source.get("arrival_deadline") or "2026-09-16T19:00:00+09:00",
        arrival_preference_minutes=source.get("arrival_preference_minutes", 10),
        service_date=None,
        transport_modes=[
            {"walking": "walk"}.get(
                source.get("transport_mode"), source.get("transport_mode")
            )
        ]
        if source.get("transport_mode") in ("subway", "bus")
        else ["subway", "bus"],
    )
    if replan:
        source.setdefault("arrival_deadline", conditions["arrival_deadline"])
        source.setdefault("arrival_preference_minutes", 10)
        source.setdefault("kind", "appointment")
        body.setdefault("current_origin_place_id", conditions["origin_place_id"])
        conditions["origin_place_id"] = (
            body["current_origin_place_id"] or conditions["origin_place_id"]
        )
        previous = body.get("previous_plan")
        if "previous_plan" not in body:
            body["previous_plan"] = dict(
                plan_id="previous-plan",
                selected_option_id="selected-option",
                estimated_arrival_at="2026-09-16T18:50:00+09:00",
                recommended_leave_at="2026-09-16T18:03:00+09:00",
            )
        if previous:
            previous["estimated_arrival_at"] = previous.pop(
                "target_arrival_at", previous.get("estimated_arrival_at")
            )
            previous.setdefault("selected_option_id", "selected-option")
            previous.pop("total_duration_minutes", None)
    if last:
        conditions.update(
            arrival_deadline=None,
            arrival_preference_minutes=None,
            service_date="2026-09-16",
        )
        body.update(
            {
                k: conditions[k]
                for k in (
                    "kind",
                    "arrival_deadline",
                    "arrival_preference_minutes",
                    "service_date",
                    "transport_modes",
                )
            }
        )
    headers = lambda: {"Idempotency-Key": str(uuid.uuid4())}
    response = client.post(
        "/api/v1/mobility/interpret",
        json={"natural_language": "확인할 이동 조건", "context": conditions},
        headers=headers(),
    )
    assert response.status_code == 200, response.text
    meta = response.json()["meta"]
    if confirm:
        response = client.post(
            f"/api/v1/conversations/{meta['conversation_id']}/confirm",
            json={"expected_revision": meta["revision"], "confirmed_data": conditions},
            headers=headers(),
        )
        assert response.status_code == 200, response.text
        meta = response.json()["meta"]
    body.update(
        conversation_id=meta["conversation_id"], expected_revision=meta["revision"]
    )
    return body
