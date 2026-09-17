"""백엔드 lifespan의 공통 AsyncClient 종료와 무조회 health 확인."""

import httpx
import pytest

from app.main import app


def test_lifespan_owns_shared_client_and_health_does_not_call_provider(client):
    http = getattr(app.state, "provider_http_client", None)
    assert isinstance(http, httpx.AsyncClient)
    assert http.is_closed is False
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert app.state.provider_client.http_client is http


@pytest.mark.asyncio
async def test_lifespan_closes_shared_client(monkeypatch):
    from app.db import get_db
    from app.main import lifespan

    monkeypatch.setitem(app.dependency_overrides, get_db, lambda: None)
    async with lifespan(app):
        http = app.state.provider_http_client
        assert http.is_closed is False
    assert http.is_closed is True
