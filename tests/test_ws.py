"""Tests for app/api/ws.py WebSocket endpoints."""
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from jose import jwt

from app.core.config import settings


def make_token(user_id: str) -> str:
    """Generate a valid JWT token for testing."""
    return jwt.encode(
        {"sub": user_id, "aud": ["fastapi-users:auth"]},
        settings.secret_key,
        algorithm=settings.jwt_algorithm,
    )


@pytest.mark.asyncio
async def test_get_ws_user_valid_token():
    """Valid JWT token returns a user."""
    from unittest.mock import AsyncMock
    from app.api.ws import _get_ws_user

    user_id = str(uuid.uuid4())
    token = make_token(user_id)

    mock_user = MagicMock()
    mock_user.is_active = True

    mock_db = AsyncMock()
    mock_db.get = AsyncMock(return_value=mock_user)

    result = await _get_ws_user(token, mock_db)
    assert result == mock_user


@pytest.mark.asyncio
async def test_get_ws_user_invalid_token():
    """Invalid JWT raises WebSocketException."""
    from fastapi import WebSocketException
    from app.api.ws import _get_ws_user

    mock_db = AsyncMock()

    with pytest.raises(WebSocketException):
        await _get_ws_user("invalid.token.here", mock_db)


@pytest.mark.asyncio
async def test_publish_quote_no_op_when_redis_none():
    """publish_quote does nothing when redis_client is None."""
    from app.services.pubsub import publish_quote
    # Should not raise
    await publish_quote(None, "2330", {"last_price": 900.0})


@pytest.mark.asyncio
async def test_publish_ai_event_publishes_to_channel():
    """publish_ai_event calls redis.publish with correct channel."""
    from app.services.pubsub import publish_ai_event

    mock_redis = AsyncMock()
    session_id = str(uuid.uuid4())

    await publish_ai_event(mock_redis, session_id, {"event": "started", "symbol": "2330"})

    mock_redis.publish.assert_called_once()
    call_args = mock_redis.publish.call_args
    channel = call_args[0][0]
    payload = json.loads(call_args[0][1])

    assert channel == f"ai:stream:{session_id}"
    assert payload["type"] == "ai_event"
    assert payload["event"] == "started"
    assert payload["symbol"] == "2330"
