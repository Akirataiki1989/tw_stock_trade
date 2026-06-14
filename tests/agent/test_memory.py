import pytest
from langgraph.store.memory import InMemoryStore
from app.agent.memory import save_pattern, search_patterns, format_memories


@pytest.mark.asyncio
async def test_save_and_retrieve_by_symbol():
    store = InMemoryStore()
    await save_pattern(store, symbol="2330", session_id="sess-001", value={
        "situation": "法人大量買超，外資同步，RSI=55，台指強勁",
        "decision": "BUY",
        "reasoning": "多方訊號強烈",
        "outcome_score": 0.032,
        "market_phase": "uptrend",
        "confidence": 0.8,
    })
    results = await search_patterns(store, symbol="2330", query="法人買超外資買進")
    assert len(results) >= 1
    assert results[0].value["decision"] == "BUY"


@pytest.mark.asyncio
async def test_different_symbol_not_returned():
    store = InMemoryStore()
    await save_pattern(store, symbol="2330", session_id="sess-002", value={
        "situation": "法人買超", "decision": "BUY", "reasoning": "...",
        "outcome_score": None, "market_phase": "uptrend", "confidence": 0.7,
    })
    results = await search_patterns(store, symbol="2317", query="法人買超")
    assert len(results) == 0


def test_format_memories_empty():
    assert format_memories([]) == "（無足夠相似的歷史情境）"


def test_format_memories_includes_key_fields():
    class FakeItem:
        value = {"situation": "法人買超", "decision": "BUY",
                 "outcome_score": 0.03, "reasoning": "強勢訊號"}
        score = 0.88
        key = "2330_sess-001"
    out = format_memories([FakeItem()])
    assert "BUY" in out
    assert "3.00%" in out
