import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock
from langgraph.store.memory import InMemoryStore
from app.agent.state import DebateState


def _base_state() -> dict:
    return {
        "symbol": "2330",
        "user_id": str(uuid.uuid4()),
        "session_id": str(uuid.uuid4()),
        "quote": {"price": 850.0, "change": 5.0, "volume": 12000},
        "historical_candles": [{"date": "2026-06-07", "close": 845.0}] * 20,
        "us_market": {"sp500": {"close": 5400.0, "change": 0.5}},
        "institutional_flow": {"foreign": 1200, "investment_trust": 300, "dealer": -100},
        "margin_trading": {"margin_balance": 5000000, "short_balance": 200000},
        "portfolio": {"cash": 500000.0, "holdings": [{"symbol": "2330", "shares": 1000, "avg_cost": 800.0}]},
        "market_phase": "uptrend",
        "analyst_reports": [],
        "debate_state": DebateState(bull_history="", bear_history="", history="",
                                    current_response="", count=0),
        "final_decision": None,
        "executed": False,
        "execution_note": "",
    }


def _mock_llm(response_json: str):
    llm = AsyncMock()
    llm.ainvoke.return_value = MagicMock(content=response_json)
    llm.bind_tools = MagicMock(return_value=llm)
    return llm


@pytest.mark.asyncio
async def test_technical_analyst_returns_one_report():
    from app.agent.nodes import make_technical_analyst
    llm = _mock_llm(
        '{"type":"technical","content":"多頭趨勢","confidence":0.8,"key_signals":["MACD黃金交叉"],"suggested_action":"BUY"}'
    )
    node = make_technical_analyst(llm, InMemoryStore())
    result = await node(_base_state())
    assert len(result["analyst_reports"]) == 1
    assert result["analyst_reports"][0]["type"] == "technical"


@pytest.mark.asyncio
async def test_debate_init_no_circuit_breaker():
    from app.agent.nodes import debate_init
    state = _base_state()
    state["analyst_reports"] = [
        {"type": "technical", "content": "bullish", "confidence": 0.8,
         "key_signals": [], "suggested_action": "BUY"},
        {"type": "sentiment", "content": "positive", "confidence": 0.7,
         "key_signals": [], "suggested_action": "BUY"},
        {"type": "risk", "content": "ok", "confidence": 0.6,
         "key_signals": [], "suggested_action": "BUY", "max_shares": 2000, "stop_loss": 820.0},
    ]
    result = await debate_init(state)
    assert result["final_decision"] is None
    assert result["debate_state"]["count"] == 0
    assert result["debate_state"]["history"] == ""


@pytest.mark.asyncio
async def test_debate_init_triggers_circuit_breaker():
    """Risk analyst HOLD with confidence>=0.8 must set final_decision to HOLD."""
    from app.agent.nodes import debate_init
    state = _base_state()
    state["analyst_reports"] = [
        {"type": "technical", "content": "ok", "confidence": 0.7,
         "key_signals": [], "suggested_action": "BUY"},
        {"type": "sentiment", "content": "ok", "confidence": 0.7,
         "key_signals": [], "suggested_action": "BUY"},
        {"type": "risk", "content": "法人連賣10天，熔斷", "confidence": 0.85,
         "key_signals": ["外資連賣"], "suggested_action": "HOLD",
         "max_shares": 0, "stop_loss": 0.0},
    ]
    result = await debate_init(state)
    assert result["final_decision"]["action"] == "HOLD"
    assert result["final_decision"]["confidence"] == 0.85


@pytest.mark.asyncio
async def test_bull_researcher_increments_count():
    from app.agent.nodes import make_bull_researcher
    llm = _mock_llm("Bull: 外資連買5天，技術面突破，應積極做多。")
    state = _base_state()
    state["analyst_reports"] = [
        {"type": "technical", "content": "bullish", "confidence": 0.8,
         "key_signals": [], "suggested_action": "BUY"},
        {"type": "sentiment", "content": "positive", "confidence": 0.7,
         "key_signals": [], "suggested_action": "BUY"},
        {"type": "risk", "content": "ok", "confidence": 0.6,
         "key_signals": [], "suggested_action": "BUY", "max_shares": 2000, "stop_loss": 820.0},
    ]
    node = make_bull_researcher(llm)
    result = await node(state)
    assert result["debate_state"]["count"] == 1
    assert result["debate_state"]["current_response"].startswith("Bull:")
    assert "Bull:" in result["debate_state"]["bull_history"]


@pytest.mark.asyncio
async def test_research_manager_sets_final_decision():
    from app.agent.nodes import make_research_manager
    state = _base_state()
    state["analyst_reports"] = [
        {"type": "technical", "content": "bullish", "confidence": 0.8,
         "key_signals": [], "suggested_action": "BUY"},
        {"type": "sentiment", "content": "positive", "confidence": 0.7,
         "key_signals": [], "suggested_action": "BUY"},
        {"type": "risk", "content": "ok", "confidence": 0.7,
         "key_signals": [], "suggested_action": "BUY", "max_shares": 2000, "stop_loss": 820.0},
    ]
    state["debate_state"] = DebateState(
        bull_history="Bull: 外資買超，強烈看多。",
        bear_history="Bear: 估值偏高，謹慎。",
        history="Bull: 外資買超。\nBear: 估值偏高。",
        current_response="Bear: 估值偏高，謹慎。",
        count=2,
    )
    llm = _mock_llm(
        '{"action":"BUY","confidence":0.78,"shares":1000,"target_price":880.0,"stop_loss":820.0,"reasoning":"多方論點較強"}'
    )
    node = make_research_manager(llm)
    result = await node(state)
    assert result["final_decision"]["action"] == "BUY"
    assert result["final_decision"]["confidence"] == 0.78


@pytest.mark.asyncio
async def test_execute_or_preview_skips_low_confidence():
    from app.agent.nodes import execute_or_preview
    state = _base_state()
    state["final_decision"] = {"action": "BUY", "confidence": 0.5, "shares": 1000,
                                "target_price": 880.0, "stop_loss": 820.0, "reasoning": "ok"}
    result = await execute_or_preview(state)
    assert result["executed"] is False
    assert "PREVIEW" in result["execution_note"]
