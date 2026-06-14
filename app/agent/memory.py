"""Store wrappers for trading pattern memory.

Production: AsyncPostgresStore with pgvector (semantic search).
Tests: InMemoryStore (filter-only, no real embeddings).
All public functions are store-agnostic.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

NAMESPACE = ("trading", "patterns")


async def save_pattern(store, *, symbol: str, session_id: str, value: dict[str, Any]) -> None:
    value = {**value, "symbol": symbol}
    key = f"{symbol}_{session_id}"
    await store.aput(NAMESPACE, key, value)
    logger.debug("memory.save_pattern: key=%s", key)


async def search_patterns(
    store,
    *,
    symbol: str,
    query: str,
    limit: int = 10,
    threshold: float = 0.75,
) -> list:
    """Semantic search filtered by symbol.

    InMemoryStore returns score=1.0 for all items (no real vectors).
    AsyncPostgresStore returns cosine similarity (0–1); items below threshold are dropped.
    """
    results = await store.asearch(
        NAMESPACE,
        query=query,
        filter={"symbol": symbol},
        limit=limit,
    )
    relevant = [r for r in results if (r.score if r.score is not None else 1.0) >= threshold]
    logger.debug("memory.search: symbol=%s found=%d relevant=%d", symbol, len(results), len(relevant))
    return relevant


def format_memories(memories: list) -> str:
    if not memories:
        return "（無足夠相似的歷史情境）"
    lines = []
    for m in memories:
        v = m.value
        outcome = v.get("outcome_score")
        outcome_str = f"{outcome:+.2%}" if outcome is not None else "結果未知"
        score = getattr(m, "score", None)
        score_str = f"{score:.2f}" if score is not None else "?"
        lines.append(
            f"- 情境：{v.get('situation', '')} | "
            f"決策：{v.get('decision', '')} | "
            f"損益：{outcome_str} | "
            f"理由：{v.get('reasoning', '')} | "
            f"相似度：{score_str}"
        )
    return "\n".join(lines)


async def make_prod_store(pg_url: str, embed_fn) -> Any:
    """Create AsyncPostgresStore with pgvector. Call once at worker startup."""
    from langgraph.store.postgres.aio import AsyncPostgresStore

    store = AsyncPostgresStore(
        pg_url,
        index={
            "dims": 768,              # text-embedding-004 output dimension
            "embed": embed_fn,
            "fields": ["situation"],  # only embed the situation description
        },
    )
    await store.setup()
    return store


async def make_prod_checkpointer(pg_url: str) -> Any:
    """Create AsyncPostgresSaver. Call once at worker startup."""
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    cm = AsyncPostgresSaver.from_conn_string(pg_url)
    checkpointer = await cm.__aenter__()
    await checkpointer.setup()
    checkpointer._cm = cm   # keep reference for teardown in shutdown()
    return checkpointer
