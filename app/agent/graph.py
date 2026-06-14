"""Trading agent graph factory.

build_graph() is the only public entry point.
All dependencies are injected — no globals — making it fully testable.
"""
from __future__ import annotations

import logging
from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from app.agent.nodes import (
    debate_init,
    execute_or_preview,
    make_bear_researcher,
    make_bull_researcher,
    make_fetch_context,
    make_persist_result,
    make_research_manager,
    make_risk_analyst,
    make_sentiment_analyst,
    make_technical_analyst,
)
from app.agent.state import GraphState

logger = logging.getLogger(__name__)


def build_graph(*, db_factory, checkpointer, store, llm=None) -> Any:
    """Build and compile the trading StateGraph.

    llm=None uses the production Gemini model from settings.
    Pass a mock LLM in tests.
    """
    if llm is None:
        llm = _make_llm()

    llm_grounding = llm.bind_tools([{"google_search": {}}])

    builder = StateGraph(GraphState)

    # ── Nodes ──────────────────────────────────────────────────────────────────
    builder.add_node("fetch_context",      make_fetch_context(db_factory))
    builder.add_node("technical_analyst",  make_technical_analyst(llm_grounding, store))
    builder.add_node("sentiment_analyst",  make_sentiment_analyst(llm_grounding, store))
    builder.add_node("risk_analyst",       make_risk_analyst(llm, store))
    builder.add_node("debate_init",        debate_init)
    builder.add_node("bull_researcher",    make_bull_researcher(llm))
    builder.add_node("bear_researcher",    make_bear_researcher(llm))
    builder.add_node("research_manager",   make_research_manager(llm))
    builder.add_node("execute_or_preview", execute_or_preview)
    builder.add_node("persist_result",     make_persist_result(db_factory, store))

    # ── Fan-out: fetch_context → 3 parallel analysts via Send API ───────────────
    def _dispatch(state: GraphState) -> list:
        return [
            Send("technical_analyst", state),
            Send("sentiment_analyst", state),
            Send("risk_analyst",      state),
        ]

    builder.add_conditional_edges(
        "fetch_context", _dispatch,
        ["technical_analyst", "sentiment_analyst", "risk_analyst"],
    )

    # ── Fan-in: all 3 analysts → debate_init ───────────────────────────────────
    builder.add_edge("technical_analyst", "debate_init")
    builder.add_edge("sentiment_analyst", "debate_init")
    builder.add_edge("risk_analyst",      "debate_init")

    # ── Circuit breaker: debate_init → debate or execute_or_preview ────────────
    def _route_after_debate_init(state: GraphState) -> str:
        if state.get("final_decision") is not None:
            return "execute_or_preview"   # circuit breaker fired
        return "bull_researcher"

    builder.add_conditional_edges(
        "debate_init", _route_after_debate_init,
        ["bull_researcher", "execute_or_preview"],
    )

    # ── Debate loop ─────────────────────────────────────────────────────────────
    def _route_after_bull(state: GraphState) -> str:
        from app.core.config import settings
        if state["debate_state"]["count"] >= 2 * settings.ai_max_debate_rounds:
            return "research_manager"
        return "bear_researcher"

    def _route_after_bear(state: GraphState) -> str:
        from app.core.config import settings
        if state["debate_state"]["count"] >= 2 * settings.ai_max_debate_rounds:
            return "research_manager"
        return "bull_researcher"

    builder.add_conditional_edges(
        "bull_researcher", _route_after_bull,
        ["bear_researcher", "research_manager"],
    )
    builder.add_conditional_edges(
        "bear_researcher", _route_after_bear,
        ["bull_researcher", "research_manager"],
    )

    # ── Linear tail ────────────────────────────────────────────────────────────
    builder.add_edge(START,                "fetch_context")
    builder.add_edge("research_manager",   "execute_or_preview")
    builder.add_edge("execute_or_preview", "persist_result")
    builder.add_edge("persist_result",     END)

    return builder.compile(checkpointer=checkpointer, store=store)


def get_pg_url() -> str:
    """Return a psycopg3-compatible URL (strips +asyncpg suffix)."""
    from app.core.config import settings
    return settings.database_url.replace("+asyncpg", "")


def _make_llm():
    from langchain_google_genai import ChatGoogleGenerativeAI
    from app.core.config import settings
    return ChatGoogleGenerativeAI(
        model=settings.gemini_chat_model,
        google_api_key=settings.gemini_api_key,
        temperature=0.1,
    )
