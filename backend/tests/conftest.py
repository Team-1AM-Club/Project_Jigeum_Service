"""테스트 픽스처: FastAPI TestClient, Mock 제공자, DB 세션."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

from app.services.mock.mock_providers import (
    MockModelProvider,
    MockPlaceProvider,
    MockRoutingProvider,
    MockTransitProvider,
)

# ─────────────────────────────────────────────
# 테스트용 인메모리 SQLite DB
# ─────────────────────────────────────────────
TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

Base = declarative_base()


# 모든 모델 테이블 생성 (테스트 전용)
def create_test_tables():
    from app.models.conversation import Base as ConvBase
    from app.models.idempotency import Base as IdemBase
    from app.models.plan import Base as PlanBase

    # 메타데이터 병합
    ConvBase.metadata.create_all(test_engine)
    PlanBase.metadata.create_all(test_engine)
    IdemBase.metadata.create_all(test_engine)


@pytest.fixture(scope="session")
def test_db_engine():
    """테스트 DB 엔진 (세션 범위)."""
    create_test_tables()
    yield test_engine


@pytest.fixture(scope="function")
def db_session(test_db_engine):
    """테스트 DB 세션 (함수 범위, 롤백)."""
    connection = test_db_engine.connect()
    transaction = connection.begin()
    session = TestSessionLocal(
        bind=connection, join_transaction_mode="create_savepoint"
    )

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def mock_providers():
    """Mock 제공자 인스턴스."""
    return {
        "place": MockPlaceProvider(),
        "routing": MockRoutingProvider(),
        "transit": MockTransitProvider(),
        "model": MockModelProvider(),
    }


@pytest.fixture(scope="function")
def client(db_session):
    """FastAPI TestClient with overridden DB session.

    주의: 실제 app은 get_db 의존성 사용. 테스트에서는 의존성 오버라이드 필요.
    간단한 테스트를 위해 app을 직접 사용.
    """
    from app.db import get_db
    from app.main import app

    app.dependency_overrides[get_db] = lambda: db_session

    # 테스트용 클라이언트는 app 전역 사용
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture(scope="function")
def sample_conversation_data():
    """샘플 대화 데이터."""
    return {
        "conversation_id": "test_conv_001",
        "revision": 1,
        "status": "active",
        "expires_at": "2026-09-17T00:00:00+09:00",
        "confirmed_conditions": {
            "origin": "place_seoul_station",
            "destination": "place_gangnam_station",
            "arrival_deadline": "2026-09-16T10:00:00+09:00",
        },
    }


@pytest.fixture(scope="function")
def sample_place_search_query():
    """샘플 장소 검색 쿼리."""
    from app.schemas.places import PlaceSearchQuery

    return PlaceSearchQuery(
        query="서울역",
        latitude=37.5546,
        longitude=126.9708,
        radius_meters=5000,
        limit=5,
        offset=0,
    )


# ─────────────────────────────────────────────
# 막차 서비스 픽스처 (T044)
# ─────────────────────────────────────────────
@pytest.fixture(scope="function")
def mock_routing_provider_last_journey():
    """Mock RoutingProvider for last journey tests."""
    from unittest.mock import AsyncMock

    from app.services.provider_interfaces import RoutingProvider

    provider = AsyncMock(spec=RoutingProvider)
    provider.health.return_value = True
    return provider


@pytest.fixture(scope="function")
def last_journey_service(mock_routing_provider_last_journey):
    """LastJourneyService fixture."""
    from app.services.last_journey_service import LastJourneyService

    return LastJourneyService(routing_provider=mock_routing_provider_last_journey)


# ─────────────────────────────────────────────
# 재탐색 서비스 픽스처 (T051)
# ─────────────────────────────────────────────
@pytest.fixture(scope="function")
def mock_plan_service():
    """Mock PlanService for replan tests."""
    from unittest.mock import AsyncMock

    from app.services.plan_service import PlanService
    from app.services.provider_interfaces import RoutingProvider

    service = AsyncMock(spec=PlanService)
    service.plan = AsyncMock()
    service.routing_provider = AsyncMock(spec=RoutingProvider)
    service.routing_provider.search_options = AsyncMock()
    return service


@pytest.fixture(scope="function")
def replan_service(mock_plan_service):
    """ReplanService fixture."""
    from app.services.replan_service import ReplanService

    return ReplanService(plan_service=mock_plan_service)
