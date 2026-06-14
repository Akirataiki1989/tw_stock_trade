import operator
from typing import Annotated, Optional
from typing_extensions import TypedDict


class AnalystReport(TypedDict):
    type: str             # "technical" | "sentiment" | "risk"
    content: str
    confidence: float
    key_signals: list[str]
    suggested_action: str  # "BUY" | "SELL" | "HOLD"


class DebateState(TypedDict):
    bull_history: str      # accumulated Bull arguments
    bear_history: str      # accumulated Bear arguments
    history: str           # full interleaved debate transcript
    current_response: str  # latest message (prefixed "Bull: " or "Bear: ")
    count: int             # incremented after each speaker; stops at 2*max_rounds


class FinalDecision(TypedDict):
    action: str            # "BUY" | "SELL" | "HOLD"
    confidence: float
    shares: int
    target_price: float
    stop_loss: float
    reasoning: str


class GraphState(TypedDict):
    # ── Inputs ──────────────────────────────────────────────────────────────────
    symbol: str
    user_id: str
    session_id: str

    # ── Context (filled by fetch_context) ───────────────────────────────────────
    quote: dict
    historical_candles: list
    us_market: dict
    institutional_flow: dict
    margin_trading: dict
    portfolio: dict
    market_phase: str   # "uptrend" | "downtrend" | "sideways" | "volatile"

    # ── Analyst outputs: operator.add reducer so parallel nodes don't overwrite ──
    analyst_reports: Annotated[list[AnalystReport], operator.add]

    # ── Debate (filled by debate_init, bull_researcher, bear_researcher) ─────────
    debate_state: DebateState

    # ── Decision & execution ─────────────────────────────────────────────────────
    final_decision: Optional[FinalDecision]
    executed: bool
    execution_note: str
