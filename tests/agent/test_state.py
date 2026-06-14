import operator
from app.agent.state import AnalystReport, DebateState, GraphState


def test_analyst_reports_reducer_appends():
    """operator.add reducer must accumulate across parallel nodes, not overwrite."""
    a: list[AnalystReport] = [{"type": "technical", "content": "bullish",
                                "confidence": 0.8, "key_signals": [], "suggested_action": "BUY"}]
    b: list[AnalystReport] = [{"type": "sentiment", "content": "positive",
                                "confidence": 0.7, "key_signals": [], "suggested_action": "BUY"}]
    merged = operator.add(a, b)
    assert len(merged) == 2
    assert merged[0]["type"] == "technical"
    assert merged[1]["type"] == "sentiment"


def test_graph_state_has_required_fields():
    from typing import get_type_hints
    hints = get_type_hints(GraphState, include_extras=True)
    for field in ("symbol", "user_id", "session_id", "analyst_reports",
                  "debate_state", "final_decision", "executed", "execution_note"):
        assert field in hints, f"Missing field: {field}"


def test_debate_state_has_required_fields():
    from typing import get_type_hints
    hints = get_type_hints(DebateState, include_extras=True)
    for field in ("bull_history", "bear_history", "history", "current_response", "count"):
        assert field in hints, f"Missing DebateState field: {field}"
