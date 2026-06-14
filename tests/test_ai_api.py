"""Tests for app/api/ai.py — uses mocked ARQ pool and DB."""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import StaticPool

from app.database import AsyncSessionLocal
from app.main import app
from app.models.base import Base
from app.models.portfolio import AiDecision
from app.models.user import User
from app.users import current_active_user


@pytest.fixture
async def test_db():
    """Create an in-memory SQLite database for testing."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def override_get_db():
        async with AsyncSessionLocal() as session:
            yield session

    app.dependency_overrides[AsyncSessionLocal] = override_get_db

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
def mock_arq_pool():
    """Mock ARQ pool for testing."""
    pool = AsyncMock()
    pool.enqueue_job = AsyncMock(return_value=None)
    pool.aclose = AsyncMock(return_value=None)
    return pool


@pytest.fixture
def mock_user():
    """Create a mock user for testing."""
    user = MagicMock(spec=User)
    user.id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    return user


@pytest.fixture
def override_user_dependency(mock_user):
    """Override current_active_user dependency."""
    def _override():
        return mock_user

    app.dependency_overrides[current_active_user] = _override
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_analyze_enqueues_jobs(mock_arq_pool, override_user_dependency):
    """POST /ai/analyze: enqueues one ARQ job per symbol."""
    app.state.arq = mock_arq_pool

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            "/ai/analyze",
            json={
                "symbols": ["2330", "2454"],
                "mode": "full"
            }
        )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["status"] == "running"
    assert data[1]["status"] == "running"

    # Verify enqueue_job was called twice
    assert mock_arq_pool.enqueue_job.call_count == 2
    # Verify function name and arguments structure
    calls = mock_arq_pool.enqueue_job.call_args_list
    for i, call in enumerate(calls):
        assert call[0][0] == "task_run_ai_on_demand"  # function name
        assert call[0][1] == "00000000-0000-0000-0000-000000000001"  # user_id
        assert call[0][2] in ["2330", "2454"]  # symbol
        # call[0][3] is session_id (UUID string)


@pytest.mark.asyncio
async def test_analyze_single_symbol(mock_arq_pool, override_user_dependency):
    """POST /ai/analyze: single symbol."""
    app.state.arq = mock_arq_pool

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            "/ai/analyze",
            json={"symbols": ["2330"]}
        )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert mock_arq_pool.enqueue_job.call_count == 1


@pytest.mark.asyncio
async def test_analyze_empty_symbols(mock_arq_pool, override_user_dependency):
    """POST /ai/analyze: empty symbols list."""
    app.state.arq = mock_arq_pool

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            "/ai/analyze",
            json={"symbols": []}
        )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 0
    assert mock_arq_pool.enqueue_job.call_count == 0


@pytest.mark.asyncio
async def test_get_decisions_empty(override_user_dependency):
    """GET /ai/decisions: returns empty list when no decisions exist."""
    app.state.arq = AsyncMock()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/ai/decisions")

    assert response.status_code == 200
    data = response.json()
    assert data == []


@pytest.mark.asyncio
async def test_get_decision_not_found(override_user_dependency):
    """GET /ai/decisions/{session_id}: returns 404 for unknown session."""
    from app.database import get_db

    fake_session_id = uuid.uuid4()
    app.state.arq = AsyncMock()

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    async def mock_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = mock_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get(f"/ai/decisions/{fake_session_id}")
        assert response.status_code == 404
        assert response.json()["detail"] == "Decision not found"
    finally:
        del app.dependency_overrides[get_db]


@pytest.mark.asyncio
async def test_analyze_symbol_case_insensitive(mock_arq_pool, override_user_dependency):
    """POST /ai/analyze: symbols should be converted to uppercase."""
    app.state.arq = mock_arq_pool

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            "/ai/analyze",
            json={"symbols": ["tsm", "2454"]}
        )

    assert response.status_code == 200
    assert mock_arq_pool.enqueue_job.call_count == 2
    # Check that symbols are uppercase
    calls = mock_arq_pool.enqueue_job.call_args_list
    symbols = [call[0][2] for call in calls]
    assert all(sym == sym.upper() for sym in symbols)
