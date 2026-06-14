import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore
from app.agent.state import DebateState


def _llm_side_effects():
    """Six sequential LLM responses for a full 1-round debate:
    technical analyst, sentiment analyst, risk analyst,
    bull researcher, bear researcher, research manager.
    """
    return [
        MagicMock(content='{"type":"technical","content":"多頭趨勢","confidence":0.8,"key_signals":["MACD黃金交叉"],"suggested_action":"BUY"}'),
        MagicMock(content='{"type":"sentiment","content":"外資買超","confidence":0.75,"key_signals":["外資+1200張"],"suggested_action":"BUY"}'),
        MagicMock(content='{"type":"risk","content":"部位合理","confidence":0.65,"key_signals":[],"suggested_action":"BUY","max_shares":2000,"stop_loss":820.0}'),
        MagicMock(content="Bull: 技術面突破，外資持續買超，應積極做多。"),
        MagicMock(content="Bear: 估值偏高，注意回調風險，建議謹慎。"),
        MagicMock(content='{"action":"BUY","confidence":0.78,"shares":1000,"target_price":880.0,"stop_loss":820.0,"reasoning":"多方論點較強，風險可控"}'),
    ]


def _circuit_breaker_side_effects():
    """Three LLM responses: risk says HOLD with confidence 0.9 → debate skipped."""
    return [
        MagicMock(content='{"type":"technical","content":"OK","confidence":0.7,"key_signals":[],"suggested_action":"BUY"}'),
        MagicMock(content='{"type":"sentiment","content":"OK","confidence":0.7,"key_signals":[],"suggested_action":"BUY"}'),
        MagicMock(content='{"type":"risk","content":"法人連賣10天，熔斷觸發","confidence":0.9,"key_signals":["外資連賣"],"suggested_action":"HOLD","max_shares":0,"stop_loss":0.0}'),
    ]


def _make_mock_db():
    mock_db = AsyncMock()
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=False)
    mock_db.scalar.return_value = None
    mock_db.execute.return_value = MagicMock(
        scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))),
        fetchone=MagicMock(return_value=None),
    )
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()
    return MagicMock(return_value=mock_db)


def _initial_state():
    return {
        "symbol": "2330",
        "user_id": str(uuid.uuid4()),
        "session_id": str(uuid.uuid4()),
        "analyst_reports": [],
        "debate_state": DebateState(bull_history="", bear_history="", history="",
                                    current_response="", count=0),
        "final_decision": None,
        "executed": False,
        "execution_note": "",
    }


@pytest.mark.asyncio
async def test_graph_completes_with_debate():
    """Full flow: 3 analysts → debate (1 round) → research manager → decision."""
    from app.agent.graph import build_graph

    mock_llm = AsyncMock()
    mock_llm.ainvoke.side_effect = _llm_side_effects()
    mock_llm.bind_tools = MagicMock(return_value=mock_llm)

    graph = build_graph(
        db_factory=_make_mock_db(),
        checkpointer=InMemorySaver(),
        store=InMemoryStore(),
        llm=mock_llm,
    )
    result = await graph.ainvoke(
        _initial_state(),
        {"configurable": {"thread_id": f"test_{uuid.uuid4()}"}},
    )

    assert result["final_decision"] is not None
    assert result["final_decision"]["action"] in {"BUY", "SELL", "HOLD"}
    assert len(result["analyst_reports"]) == 3
    assert result["debate_state"]["count"] == 2  # Bull + Bear each spoke once


@pytest.mark.asyncio
async def test_graph_circuit_breaker_skips_debate():
    """Risk HOLD (conf>=0.8) must skip Bull/Bear and go directly to execute."""
    from app.agent.graph import build_graph

    mock_llm = AsyncMock()
    mock_llm.ainvoke.side_effect = _circuit_breaker_side_effects()
    mock_llm.bind_tools = MagicMock(return_value=mock_llm)

    graph = build_graph(
        db_factory=_make_mock_db(),
        checkpointer=InMemorySaver(),
        store=InMemoryStore(),
        llm=mock_llm,
    )
    result = await graph.ainvoke(
        _initial_state(),
        {"configurable": {"thread_id": f"test_{uuid.uuid4()}"}},
    )

    assert result["final_decision"]["action"] == "HOLD"
    assert result["debate_state"]["count"] == 0   # debate was never entered
    assert mock_llm.ainvoke.call_count == 3        # only 3 analyst LLM calls
