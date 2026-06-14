"""Redis pub/sub channel helpers."""
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

CHANNEL_QUOTE = "quotes:{symbol}"
CHANNEL_AI_STREAM = "ai:stream:{session_id}"


async def publish_quote(redis_client, symbol: str, data: dict[str, Any]) -> None:
    """Publish quote update to Redis. No-op if redis_client is None."""
    if redis_client is None:
        return
    payload = json.dumps({"type": "quote", "symbol": symbol, **data})
    try:
        await redis_client.publish(CHANNEL_QUOTE.format(symbol=symbol), payload)
    except Exception as e:
        logger.warning("publish_quote failed: %s", e)


async def publish_ai_event(redis_client, session_id: str, event: dict[str, Any]) -> None:
    """Publish AI analysis progress event. No-op if redis_client is None."""
    if redis_client is None:
        return
    payload = json.dumps({"type": "ai_event", "session_id": session_id, **event})
    try:
        await redis_client.publish(CHANNEL_AI_STREAM.format(session_id=session_id), payload)
    except Exception as e:
        logger.warning("publish_ai_event failed: %s", e)
