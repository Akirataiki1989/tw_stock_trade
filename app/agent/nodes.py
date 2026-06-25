"""LangGraph node factories for the trading agent.

Each make_*() returns an async node function with dependencies injected.
This keeps nodes testable without a real DB or LLM.
"""
from __future__ import annotations

import json
import logging
import time
import uuid as _uuid
from typing import Callable
from zoneinfo import ZoneInfo

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.agent.memory import NAMESPACE, format_memories, save_pattern, search_patterns
from app.agent.prompts import (
    BEAR_RESEARCHER_PROMPT,
    BULL_RESEARCHER_PROMPT,
    RESEARCH_MANAGER_PROMPT,
    RISK_ANALYST_PROMPT,
    SENTIMENT_ANALYST_PROMPT,
    TECHNICAL_ANALYST_PROMPT,
)
from app.agent.state import DebateState, GraphState
from app.models.market import HistoricalCandle, MarketQuote
from app.models.portfolio import AiDecision, Holding, Portfolio

logger = logging.getLogger(__name__)
_TZ = ZoneInfo("Asia/Taipei")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _parse_json(content: str, fallback: dict) -> dict:
    s = content.strip()
    if s.startswith("```"):
        parts = s.split("```")
        s = parts[1].lstrip("json").strip() if len(parts) > 1 else s
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        logger.warning("nodes._parse_json: parse failed, using fallback")
        return fallback


def _situation_text(state: GraphState) -> str:
    q = state.get("quote", {})
    inst = state.get("institutional_flow", {})
    us = state.get("us_market", {})
    return (
        f"股票{state['symbol']} 市場:{state.get('market_phase', '?')} "
        f"價:{q.get('price', 0)} 漲跌:{q.get('change', 0)} "
        f"外資:{inst.get('foreign', 0)} 投信:{inst.get('investment_trust', 0)} "
        f"美股SP500:{us.get('sp500', {}).get('change', 0)}%"
    )


def _classify_phase(candles: list[dict]) -> str:
    if len(candles) < 20:
        return "unknown"
    closes = [c["close"] for c in candles[:20]]
    chg = (closes[0] - closes[-1]) / closes[-1] if closes[-1] else 0
    if chg > 0.05:
        return "uptrend"
    if chg < -0.05:
        return "downtrend"
    if max(closes) / min(closes) > 1.08:
        return "volatile"
    return "sideways"


def _format_analyst_reports(reports: list) -> str:
    return "\n\n".join(
        f"### {r['type'].upper()}\n{r.get('content', '')}" for r in reports
    )


# ── fetch_context ──────────────────────────────────────────────────────────────

def make_fetch_context(db_factory: async_sessionmaker) -> Callable:
    async def fetch_context(state: GraphState) -> dict:
        symbol = state["symbol"]
        user_id = _uuid.UUID(state["user_id"])
        t0 = time.monotonic()

        async with db_factory() as db:
            quote_row = await db.scalar(select(MarketQuote).where(MarketQuote.symbol == symbol))
            quote = ({"price": float(quote_row.last_price or 0),
                      "change": float(quote_row.change_pct or 0),
                      "volume": int(quote_row.volume or 0)}
                     if quote_row else {})

            candle_rows = (await db.execute(
                select(HistoricalCandle)
                .where(HistoricalCandle.symbol == symbol, HistoricalCandle.timeframe == "D")
                .order_by(HistoricalCandle.date.desc()).limit(60)
            )).scalars().all()
            candles = [{"date": str(r.date), "open": float(r.open or 0),
                        "high": float(r.high or 0), "low": float(r.low or 0),
                        "close": float(r.close or 0), "volume": int(r.volume or 0)}
                       for r in candle_rows]

            us_row = (await db.execute(text(
                "SELECT sp500_close, sp500_change, nasdaq_close, nasdaq_change "
                "FROM market.us_market_daily ORDER BY date DESC LIMIT 1"
            ))).fetchone()
            us_market = ({"sp500": {"close": float(us_row[0] or 0), "change": float(us_row[1] or 0)},
                          "nasdaq": {"close": float(us_row[2] or 0), "change": float(us_row[3] or 0)}}
                         if us_row else {})

            inst_row = (await db.execute(text(
                "SELECT foreign_net, investment_trust_net, dealer_net "
                "FROM market.institutional_flows WHERE symbol=:s ORDER BY date DESC LIMIT 1"
            ), {"s": symbol})).fetchone()
            institutional_flow = ({"foreign": int(inst_row[0] or 0),
                                    "investment_trust": int(inst_row[1] or 0),
                                    "dealer": int(inst_row[2] or 0)}
                                   if inst_row else {})

            margin_row = (await db.execute(text(
                "SELECT margin_balance, short_balance FROM market.margin_trading "
                "WHERE symbol=:s ORDER BY date DESC LIMIT 1"
            ), {"s": symbol})).fetchone()
            margin_trading = ({"margin_balance": int(margin_row[0] or 0),
                                "short_balance": int(margin_row[1] or 0)}
                               if margin_row else {})

            port_row = await db.scalar(select(Portfolio).where(Portfolio.user_id == user_id))
            holding_rows = (await db.execute(
                select(Holding).where(Holding.user_id == user_id)
            )).scalars().all()
            portfolio = {
                "cash": float(port_row.cash) if port_row else 0.0,
                "holdings": [{"symbol": h.symbol, "shares": h.shares,
                               "avg_cost": float(h.avg_cost)} for h in holding_rows],
            }

        logger.debug("fetch_context: symbol=%s elapsed=%.2fs", symbol, time.monotonic() - t0)
        return {
            "quote": quote,
            "historical_candles": candles,
            "us_market": us_market,
            "institutional_flow": institutional_flow,
            "margin_trading": margin_trading,
            "portfolio": portfolio,
            "market_phase": _classify_phase(candles),
        }
    return fetch_context


# ── Analyst nodes ──────────────────────────────────────────────────────────────

def make_technical_analyst(llm_with_grounding, store) -> Callable:
    async def technical_analyst(state: GraphState) -> dict:
        memories = await search_patterns(store, symbol=state["symbol"],
                                         query=_situation_text(state))
        prompt = TECHNICAL_ANALYST_PROMPT.format(
            symbol=state["symbol"],
            quote=state["quote"],
            candles=state["historical_candles"][:20],
            memories=format_memories(memories),
        )
        resp = await llm_with_grounding.ainvoke(prompt)
        parsed = _parse_json(resp.content, {
            "type": "technical", "content": resp.content,
            "confidence": 0.5, "key_signals": [], "suggested_action": "HOLD",
        })
        return {"analyst_reports": [parsed]}
    return technical_analyst


def make_sentiment_analyst(llm_with_grounding, store) -> Callable:
    async def sentiment_analyst(state: GraphState) -> dict:
        memories = await search_patterns(store, symbol=state["symbol"],
                                         query=_situation_text(state))
        prompt = SENTIMENT_ANALYST_PROMPT.format(
            symbol=state["symbol"],
            institutional_flow=state["institutional_flow"],
            margin_trading=state["margin_trading"],
            us_market=state["us_market"],
            memories=format_memories(memories),
        )
        resp = await llm_with_grounding.ainvoke(prompt)
        parsed = _parse_json(resp.content, {
            "type": "sentiment", "content": resp.content,
            "confidence": 0.5, "key_signals": [], "suggested_action": "HOLD",
        })
        return {"analyst_reports": [parsed]}
    return sentiment_analyst


def make_risk_analyst(llm_plain, store) -> Callable:
    async def risk_analyst(state: GraphState) -> dict:
        memories = await search_patterns(store, symbol=state["symbol"],
                                         query=_situation_text(state))
        prompt = RISK_ANALYST_PROMPT.format(
            symbol=state["symbol"],
            quote=state["quote"],
            portfolio=state["portfolio"],
            us_market=state["us_market"],
            institutional_flow=state["institutional_flow"],
            memories=format_memories(memories),
        )
        resp = await llm_plain.ainvoke(prompt)
        parsed = _parse_json(resp.content, {
            "type": "risk", "content": resp.content,
            "confidence": 0.5, "key_signals": [], "suggested_action": "HOLD",
            "max_shares": 0, "stop_loss": 0.0,
        })
        return {"analyst_reports": [parsed]}
    return risk_analyst


# ── debate_init: fan-in node + circuit breaker ─────────────────────────────────

async def debate_init(state: GraphState) -> dict:
    """Fan-in point after parallel analysts. Initializes DebateState.

    Circuit breaker: if risk analyst says HOLD with confidence >= 0.8,
    pre-set final_decision to HOLD so graph skips debate entirely.
    """
    risk_report = next(
        (r for r in state["analyst_reports"] if r["type"] == "risk"), None
    )

    if (risk_report
            and risk_report.get("suggested_action") == "HOLD"
            and risk_report.get("confidence", 0) >= 0.8):
        logger.info("debate_init: circuit breaker triggered, skipping debate")
        return {
            "debate_state": DebateState(bull_history="", bear_history="", history="",
                                        current_response="", count=0),
            "final_decision": {
                "action": "HOLD",
                "confidence": risk_report["confidence"],
                "shares": 0,
                "target_price": 0.0,
                "stop_loss": risk_report.get("stop_loss", 0.0),
                "reasoning": f"熔斷觸發：{risk_report.get('content', '')}",
            },
        }

    return {
        "debate_state": DebateState(bull_history="", bear_history="", history="",
                                    current_response="", count=0),
        "final_decision": None,
    }


# ── Bull Researcher ────────────────────────────────────────────────────────────

def make_bull_researcher(llm_plain) -> Callable:
    async def bull_researcher(state: GraphState) -> dict:
        debate = state["debate_state"]
        reports_text = _format_analyst_reports(state["analyst_reports"])
        prompt = BULL_RESEARCHER_PROMPT.format(
            analyst_reports=reports_text,
            bear_current=debate["current_response"] or "（空頭尚未發言）",
        )
        resp = await llm_plain.ainvoke(prompt)
        content = resp.content.strip()
        if not content.startswith("Bull:"):
            content = f"Bull: {content}"
        new_debate = DebateState(
            bull_history=debate["bull_history"] + content + "\n",
            bear_history=debate["bear_history"],
            history=debate["history"] + content + "\n",
            current_response=content,
            count=debate["count"] + 1,
        )
        logger.debug("bull_researcher: count=%d", new_debate["count"])
        return {"debate_state": new_debate}
    return bull_researcher


# ── Bear Researcher ────────────────────────────────────────────────────────────

def make_bear_researcher(llm_plain) -> Callable:
    async def bear_researcher(state: GraphState) -> dict:
        debate = state["debate_state"]
        reports_text = _format_analyst_reports(state["analyst_reports"])
        prompt = BEAR_RESEARCHER_PROMPT.format(
            analyst_reports=reports_text,
            bull_current=debate["current_response"] or "（多頭尚未發言）",
        )
        resp = await llm_plain.ainvoke(prompt)
        content = resp.content.strip()
        if not content.startswith("Bear:"):
            content = f"Bear: {content}"
        new_debate = DebateState(
            bull_history=debate["bull_history"],
            bear_history=debate["bear_history"] + content + "\n",
            history=debate["history"] + content + "\n",
            current_response=content,
            count=debate["count"] + 1,
        )
        logger.debug("bear_researcher: count=%d", new_debate["count"])
        return {"debate_state": new_debate}
    return bear_researcher


# ── Research Manager ───────────────────────────────────────────────────────────

def make_research_manager(llm_plain) -> Callable:
    async def research_manager(state: GraphState) -> dict:
        prompt = RESEARCH_MANAGER_PROMPT.format(
            analyst_reports=_format_analyst_reports(state["analyst_reports"]),
            debate_history=state["debate_state"]["history"] or "（辯論被跳過）",
            portfolio=state["portfolio"],
            quote=state["quote"],
        )
        resp = await llm_plain.ainvoke(prompt)
        parsed = _parse_json(resp.content, {
            "action": "HOLD", "confidence": 0.5, "shares": 0,
            "target_price": 0.0, "stop_loss": 0.0,
            "reasoning": "JSON解析失敗，預設持有",
        })
        return {"final_decision": parsed}
    return research_manager


# ── Execute or Preview ─────────────────────────────────────────────────────────

async def execute_or_preview(state: GraphState) -> dict:
    """Preview-only stub. Step 7 will add real FBS order placement."""
    d = state.get("final_decision") or {}
    action = d.get("action", "HOLD")
    shares = d.get("shares", 0)
    confidence = d.get("confidence", 0.0)

    if action == "HOLD" or shares == 0 or confidence < 0.7:
        note = f"PREVIEW: {action} skipped (shares={shares}, conf={confidence:.2f})"
    else:
        note = (f"PREVIEW: {action} {shares}股 @~{state['quote'].get('price', 0)} "
                f"(conf={confidence:.2f}, order NOT placed)")

    logger.info("execute_or_preview: %s symbol=%s", note, state["symbol"])
    return {"executed": False, "execution_note": note}


# ── Persist Result ─────────────────────────────────────────────────────────────

def make_persist_result(db_factory: async_sessionmaker, store) -> Callable:
    async def persist_result(state: GraphState) -> dict:
        d = state.get("final_decision") or {}
        symbol = state["symbol"]
        session_id = state["session_id"]

        async with db_factory() as db:
            record = AiDecision(
                user_id=_uuid.UUID(state["user_id"]),
                session_id=_uuid.UUID(session_id),
                analysis=d.get("reasoning", ""),
                decisions={symbol: d},
                market_summary=state.get("market_phase", ""),
                model_used="gemini-2.0-flash",
                tokens_used=0,
                execution_ms=0,
                agent_reports={
                    "analyst_reports": state.get("analyst_reports", []),
                    "debate_history": state.get("debate_state", {}).get("history", ""),
                },
            )
            db.add(record)
            await db.commit()

        await save_pattern(store, symbol=symbol, session_id=session_id, value={
            "situation": _situation_text(state),
            "decision": d.get("action", "HOLD"),
            "reasoning": d.get("reasoning", ""),
            "outcome_score": None,
            "market_phase": state.get("market_phase", "unknown"),
            "confidence": d.get("confidence", 0.0),
        })

        logger.info("persist_result: symbol=%s action=%s conf=%.2f",
                    symbol, d.get("action"), d.get("confidence", 0))
        return {}
    return persist_result
