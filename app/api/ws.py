"""WebSocket endpoints: /ws/quotes and /ws/ai-stream."""
import asyncio
import uuid
import logging

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, WebSocketException
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from app.core.config import settings
from app.database import get_db
from app.models.user import User

router = APIRouter(tags=["websocket"])
logger = logging.getLogger(__name__)


async def _get_ws_user(token: str, db: AsyncSession) -> User:
    """Decode JWT token and return active user. Raises WebSocketException on failure."""
    try:
        payload = jwt.decode(
            token, settings.secret_key,
            algorithms=[settings.jwt_algorithm],
            audience="fastapi-users:auth",
        )
        user_id: str | None = payload.get("sub")
        if not user_id:
            raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)
        user = await db.get(User, uuid.UUID(user_id))
        if not user or not user.is_active:
            raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)
        return user
    except JWTError:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)


@router.websocket("/ws/quotes")
async def ws_quotes(
    websocket: WebSocket,
    token: str = Query(..., description="JWT Bearer token"),
    db: AsyncSession = Depends(get_db),
):
    """
    Subscribe to real-time quote updates.

    Client sends: {"action": "subscribe", "symbols": ["2330", "2454"]}
    Server pushes: {"type": "quote", "symbol": "2330", "last_price": 900.0, ...}
    Client sends: {"action": "unsubscribe", "symbols": ["2330"]} to stop a symbol.
    """
    user = await _get_ws_user(token, db)
    await websocket.accept()
    logger.info("ws_quotes: user=%s connected", str(user.id)[:8])

    r = aioredis.from_url(str(settings.redis_url), decode_responses=True)
    pubsub = r.pubsub()

    async def _receive():
        async for data in websocket.iter_json():
            action = data.get("action", "")
            symbols = [s.upper() for s in data.get("symbols", [])]
            if not symbols:
                continue
            channels = [f"quotes:{s}" for s in symbols]
            if action == "subscribe":
                await pubsub.subscribe(*channels)
                logger.debug("ws_quotes: user=%s subscribed=%s", str(user.id)[:8], symbols)
            elif action == "unsubscribe":
                await pubsub.unsubscribe(*channels)

    async def _forward():
        # pubsub.listen() returns immediately while nothing is subscribed yet
        # (subscribe() is only called once _receive() processes the client's
        # first "subscribe" message), so poll until there's something to listen to.
        while True:
            if not pubsub.subscribed:
                await asyncio.sleep(0.05)
                continue
            async for message in pubsub.listen():
                if message["type"] == "message":
                    await websocket.send_text(message["data"])

    receive_task = asyncio.create_task(_receive())
    forward_task = asyncio.create_task(_forward())
    try:
        await asyncio.wait({receive_task, forward_task}, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for t in (receive_task, forward_task):
            t.cancel()
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass
        await pubsub.reset()
        await r.aclose()
        logger.info("ws_quotes: user=%s disconnected", str(user.id)[:8])


@router.websocket("/ws/ai-stream")
async def ws_ai_stream(
    websocket: WebSocket,
    session_id: uuid.UUID = Query(..., description="AI analysis session_id"),
    token: str = Query(..., description="JWT Bearer token"),
    db: AsyncSession = Depends(get_db),
):
    """
    Subscribe to AI analysis progress for a specific session.

    Server pushes events:
      {"type": "ai_event", "session_id": "...", "event": "started", "symbol": "2330"}
      {"type": "ai_event", "session_id": "...", "event": "completed", "symbol": "2330"}
      {"type": "ai_event", "session_id": "...", "event": "failed", "error": "..."}
    Connection closes after receiving "completed" or "failed" event.
    """
    user = await _get_ws_user(token, db)
    await websocket.accept()
    channel = f"ai:stream:{session_id}"
    logger.info("ws_ai_stream: user=%s session=%s connected", str(user.id)[:8], str(session_id)[:8])

    r = aioredis.from_url(str(settings.redis_url), decode_responses=True)
    pubsub = r.pubsub()
    await pubsub.subscribe(channel)

    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                await websocket.send_text(message["data"])
                import json as _json
                data = _json.loads(message["data"])
                if data.get("event") in ("completed", "failed"):
                    break  # auto-close after terminal event
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        await pubsub.unsubscribe(channel)
        await r.aclose()
        logger.info("ws_ai_stream: user=%s session=%s disconnected", str(user.id)[:8], str(session_id)[:8])
