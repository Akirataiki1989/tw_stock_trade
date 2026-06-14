# Step 6: LangGraph Trading Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a LangGraph StateGraph agent with 3 parallel analysts → Bull/Bear debate → research manager decision, with semantic long-term memory via pgvector, and ARQ cron-based execution at configurable intervals.

**Architecture:** `StateGraph` with parallel fan-out via `Send` API (technical/sentiment/risk analysts run concurrently). After fan-in, a `debate_init` node checks circuit breaker; if clear, `bull_researcher` and `bear_researcher` exchange one round of arguments before `research_manager` synthesizes a final decision. `AsyncPostgresSaver` provides short-term checkpointing (TTL 7 days); `AsyncPostgresStore` with `text-embedding-004` provides long-term semantic memory (similarity threshold 0.75). ARQ triggers every minute but the graph only executes at configurable intervals (15/30/45/60 min) read from `trading.settings` table.

**Tech Stack:** `langgraph>=1.2.0` (already in project), `psycopg[binary,pool]>=3.0` (new — for AsyncPostgresSaver/Store), `langchain-google-genai>=4.2.2` (already in project, Gemini 2.0 Flash + Google Search Grounding + text-embedding-004)

**Graph Flow:**
```
START → fetch_context
  → Send("technical_analyst"), Send("sentiment_analyst"), Send("risk_analyst")   [parallel]
  → debate_init          ← fan-in; initializes DebateState; checks circuit breaker
  ├─ [circuit_breaker] → execute_or_preview   (HOLD forced, skip debate)
  └─ [continue]        → bull_researcher
                             ↓ (route_after_bull)
                           bear_researcher
                             ↓ (route_after_bear, default max_rounds=1 → done)
                           research_manager   ← synthesizes debate → final_decision
                             ↓
                           execute_or_preview
                             ↓
                           persist_result → END
```

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `pyproject.toml` | Modify | Add `psycopg[binary,pool]>=3.0` |
| `app/core/config.py` | Modify | Add AI config fields incl. `ai_max_debate_rounds` |
| `alembic/versions/0004_add_pgvector_settings.py` | Create | `pgvector` extension + `trading.settings` table |
| `app/agent/__init__.py` | Create | Package marker |
| `app/agent/state.py` | Create | `GraphState` + `DebateState` TypedDicts |
| `app/agent/memory.py` | Create | Store wrappers: `save_pattern`, `search_patterns`, `format_memories` |
| `app/agent/prompts.py` | Create | System prompts for all 6 node types |
| `app/agent/nodes.py` | Create | All node factory functions |
| `app/agent/graph.py` | Create | `build_graph()`, `get_pg_url()` |
| `app/tasks.py` | Modify | Add `get_ai_interval`, `task_maybe_run_ai`, `task_update_trade_outcomes`, `task_cleanup_checkpoints`, `task_prune_store_memories` |
| `app/worker.py` | Modify | Updated startup/shutdown + new cron registrations |
| `tests/agent/__init__.py` | Create | Package marker |
| `tests/agent/test_state.py` | Create | State reducer + DebateState field tests |
| `tests/agent/test_memory.py` | Create | Memory ops tests (InMemoryStore) |
| `tests/agent/test_nodes.py` | Create | Node factory tests (mocked LLM) |
| `tests/agent/test_graph.py` | Create | Integration test (InMemorySaver + InMemoryStore) |

---

### Task 1: Dependencies + Config

**Files:**
- Modify: `pyproject.toml`
- Modify: `app/core/config.py`

- [ ] **Step 1: Add psycopg3 to pyproject.toml**

In `pyproject.toml`, inside the `dependencies` list, add after `"asyncpg>=0.30.0"`:
```toml
"psycopg[binary,pool]>=3.0",
```

- [ ] **Step 2: Add AI fields to Settings**

In `app/core/config.py`, add after `gemini_api_key: str = ""`:
```python
# AI Agent
gemini_embedding_model: str = "models/text-embedding-004"
gemini_chat_model: str = "gemini-2.0-flash"
ai_max_debate_rounds: int = 1          # Bull/Bear exchange rounds (1 = Bull→Bear→done)
store_similarity_threshold: float = 0.75
store_max_results: int = 10
store_max_per_symbol: int = 100
checkpoint_ttl_days: int = 7
```

- [ ] **Step 3: Sync and verify**

Run on the NAS (via `ssh` or in code-server terminal):
```bash
uv sync
uv run python -c "import psycopg; print('psycopg ok')"
```
Expected: `psycopg ok`

- [ ] **Step 4: Commit**
```bash
git add pyproject.toml app/core/config.py
git commit -m "feat: add psycopg3 dep and AI config fields (ai_max_debate_rounds)"
```

---

### Task 2: DB Migration — pgvector + Settings Table

**Files:**
- Create: `alembic/versions/0004_add_pgvector_settings.py`

- [ ] **Step 1: Create migration file**

`alembic/versions/0004_add_pgvector_settings.py`:
```python
"""add pgvector extension and trading.settings table

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-08
"""
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("""
        CREATE TABLE IF NOT EXISTS trading.settings (
            key        VARCHAR(100) PRIMARY KEY,
            value      TEXT         NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """)
    op.execute("""
        INSERT INTO trading.settings (key, value)
        VALUES ('ai_interval_minutes', '30')
        ON CONFLICT (key) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS trading.settings")
    op.execute("DROP EXTENSION IF EXISTS vector")
```

- [ ] **Step 2: Run migration**
```bash
uv run alembic upgrade head
```
Expected output contains: `Running upgrade 0003 -> 0004`

- [ ] **Step 3: Verify**
```bash
uv run python -c "
import asyncio, asyncpg
from app.core.config import settings

async def check():
    url = settings.database_url.replace('+asyncpg', '')
    conn = await asyncpg.connect(url)
    ext = await conn.fetchval(\"SELECT extname FROM pg_extension WHERE extname='vector'\")
    tbl = await conn.fetchval(\"SELECT to_regclass('trading.settings')\")
    print('vector:', ext, '| settings:', tbl)
    await conn.close()

asyncio.run(check())
"
```
Expected: `vector: vector | settings: trading.settings`

- [ ] **Step 4: Commit**
```bash
git add alembic/versions/0004_add_pgvector_settings.py
git commit -m "feat: migration 0004 - pgvector extension and trading.settings table"
```

---

### Task 3: GraphState + DebateState

**Files:**
- Create: `app/agent/__init__.py`
- Create: `app/agent/state.py`
- Create: `tests/agent/__init__.py`
- Create: `tests/agent/test_state.py`

- [ ] **Step 1: Write failing tests**

`tests/agent/test_state.py`:
```python
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
```

- [ ] **Step 2: Run to see failure**
```bash
uv run pytest tests/agent/test_state.py -v
```
Expected: `ModuleNotFoundError: No module named 'app.agent'`

- [ ] **Step 3: Implement**

`app/agent/__init__.py` — empty file

`tests/agent/__init__.py` — empty file

`app/agent/state.py`:
```python
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
```

- [ ] **Step 4: Run tests**
```bash
uv run pytest tests/agent/test_state.py -v
```
Expected: `3 passed`

- [ ] **Step 5: Commit**
```bash
git add app/agent/ tests/agent/
git commit -m "feat: add GraphState + DebateState TypedDicts with operator.add reducer"
```

---

### Task 4: Memory Layer

**Files:**
- Create: `app/agent/memory.py`
- Create: `tests/agent/test_memory.py`

- [ ] **Step 1: Write failing tests**

`tests/agent/test_memory.py`:
```python
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
```

- [ ] **Step 2: Run to see failure**
```bash
uv run pytest tests/agent/test_memory.py -v
```
Expected: `ModuleNotFoundError: No module named 'app.agent.memory'`

- [ ] **Step 3: Implement**

`app/agent/memory.py`:
```python
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
    relevant = [r for r in results if getattr(r, "score", 1.0) >= threshold]
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
```

- [ ] **Step 4: Run tests**
```bash
uv run pytest tests/agent/test_memory.py -v
```
Expected: `4 passed`

- [ ] **Step 5: Commit**
```bash
git add app/agent/memory.py tests/agent/test_memory.py
git commit -m "feat: add memory layer (save_pattern, search_patterns, format_memories)"
```

---

### Task 5: Prompts

**Files:**
- Create: `app/agent/prompts.py`

No tests — pure string templates.

- [ ] **Step 1: Create prompts.py**

`app/agent/prompts.py`:
```python
"""System prompts for LangGraph agent nodes.

All prompts use str.format() placeholders.
JSON output instructions are explicit: no markdown code fences.
"""

TECHNICAL_ANALYST_PROMPT = """\
你是一位資深技術分析師，專注台股技術面。

## 股票資料
代碼：{symbol}
即時報價：{quote}
近20日K線（最新在前）：{candles}

## 過去相似情境（語意搜尋）
{memories}

## 任務
分析趨勢、量價關係、支撐阻力、K線型態。
可用 Google Search 搜尋「{symbol} 技術面」補充最新資訊。

回傳 JSON（不要有 markdown code fence）：
{{"type":"technical","content":"分析內容（繁體中文）","confidence":0.0-1.0,"key_signals":["..."],"suggested_action":"BUY|SELL|HOLD"}}
"""

SENTIMENT_ANALYST_PROMPT = """\
你是一位市場情緒分析師，專注法人籌碼與市場氛圍。

## 股票資料
代碼：{symbol}
三大法人買賣超（張數，正=買超 負=賣超）：{institutional_flow}
融資融券餘額：{margin_trading}
美股昨收環境：{us_market}

## 過去相似情境（語意搜尋）
{memories}

## 任務
分析法人動向、融資融券趨勢、美股對台股的影響。
用 Google Search 搜尋「{symbol} 法人 籌碼」補充資訊。

回傳 JSON（不要有 markdown code fence）：
{{"type":"sentiment","content":"分析內容（繁體中文）","confidence":0.0-1.0,"key_signals":["..."],"suggested_action":"BUY|SELL|HOLD"}}
"""

RISK_ANALYST_PROMPT = """\
你是一位風險管理師，只做純計算，不使用搜尋工具。

## 投資組合狀態
{portfolio}

## 股票報價
代碼：{symbol}，報價：{quote}

## 市場環境
美股：{us_market}
法人籌碼：{institutional_flow}

## 任務
1. 計算合理部位大小（單一標的不超過總資產 10%）
2. 設定停損位置（最大虧損 3%）
3. 若持倉已達上限、法人連續賣超5天以上、或市場波動異常則建議 HOLD

若判定需要 HOLD 且 confidence >= 0.8，後續辯論會被跳過（熔斷觸發）。

回傳 JSON（不要有 markdown code fence）：
{{"type":"risk","content":"風險評估（繁體中文）","confidence":0.0-1.0,"key_signals":["..."],"suggested_action":"BUY|SELL|HOLD","max_shares":整數,"stop_loss":浮點數}}
"""

BULL_RESEARCHER_PROMPT = """\
你是一位多頭研究員，職責是為「做多」立場辯護。

## 三位分析師報告
{analyst_reports}

## 對方（空頭）最新論點
{bear_current}

## 任務
基於上方分析師報告，提出最有力的買進論據。
若對方已有論點，必須用具體數據駁斥，而非重複己方論點。
不可迴避對方的主要攻擊點。

以「Bull:」開頭回答，繁體中文，200字以內。
"""

BEAR_RESEARCHER_PROMPT = """\
你是一位空頭研究員，職責是提出「做空或觀望」的理由。

## 三位分析師報告
{analyst_reports}

## 對方（多頭）最新論點
{bull_current}

## 任務
基於上方分析師報告，指出最重要的風險與反對買進的理由。
若對方已有論點，必須用具體數據反駁，不可忽視對方的強點。
著重：法人賣超趨勢、估值風險、宏觀威脅、技術面警訊。

以「Bear:」開頭回答，繁體中文，200字以內。
"""

RESEARCH_MANAGER_PROMPT = """\
你是研究部總監，負責評估多空辯論並做出最終交易建議。

## 三位分析師原始報告
{analyst_reports}

## 完整辯論記錄
{debate_history}

## 投資組合現況
{portfolio}

## 當前報價
{quote}

## 任務
綜合分析師報告與辯論內容，做出明確且可執行的交易決策。
風險管理師若建議 HOLD，需要多頭提出特別強力的論點才能推翻。
shares 請根據 risk_analyst 的 max_shares 決定（若 HOLD 則填 0）。

回傳 JSON（不要有 markdown code fence）：
{{"action":"BUY|SELL|HOLD","confidence":0.0-1.0,"shares":整數,"target_price":浮點數,"stop_loss":浮點數,"reasoning":"決策理由（繁體中文）"}}
"""
```

- [ ] **Step 2: Commit**
```bash
git add app/agent/prompts.py
git commit -m "feat: add analyst + Bull/Bear debate + research manager prompts"
```

---

### Task 6: Node Functions

**Files:**
- Create: `app/agent/nodes.py`
- Create: `tests/agent/test_nodes.py`

- [ ] **Step 1: Write failing tests**

`tests/agent/test_nodes.py`:
```python
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
```

- [ ] **Step 2: Run to see failure**
```bash
uv run pytest tests/agent/test_nodes.py -v
```
Expected: `ModuleNotFoundError: No module named 'app.agent.nodes'`

- [ ] **Step 3: Implement nodes.py**

`app/agent/nodes.py`:
```python
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
                "FROM market.us_market_daily ORDER BY trade_date DESC LIMIT 1"
            ))).fetchone()
            us_market = ({"sp500": {"close": float(us_row[0] or 0), "change": float(us_row[1] or 0)},
                          "nasdaq": {"close": float(us_row[2] or 0), "change": float(us_row[3] or 0)}}
                         if us_row else {})

            inst_row = (await db.execute(text(
                "SELECT foreign_net, investment_trust_net, dealer_net "
                "FROM market.institutional_flows WHERE symbol=:s ORDER BY trade_date DESC LIMIT 1"
            ), {"s": symbol})).fetchone()
            institutional_flow = ({"foreign": int(inst_row[0] or 0),
                                    "investment_trust": int(inst_row[1] or 0),
                                    "dealer": int(inst_row[2] or 0)}
                                   if inst_row else {})

            margin_row = (await db.execute(text(
                "SELECT margin_balance, short_balance FROM market.margin_trading "
                "WHERE symbol=:s ORDER BY trade_date DESC LIMIT 1"
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
```

- [ ] **Step 4: Run tests**
```bash
uv run pytest tests/agent/test_nodes.py -v
```
Expected: `6 passed`

- [ ] **Step 5: Commit**
```bash
git add app/agent/nodes.py tests/agent/test_nodes.py
git commit -m "feat: add all node factories incl. debate_init, bull/bear researchers, research_manager"
```

---

### Task 7: Graph Compilation

**Files:**
- Create: `app/agent/graph.py`
- Create: `tests/agent/test_graph.py`

- [ ] **Step 1: Write failing integration test**

`tests/agent/test_graph.py`:
```python
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
```

- [ ] **Step 2: Run to see failure**
```bash
uv run pytest tests/agent/test_graph.py -v
```
Expected: `ModuleNotFoundError: No module named 'app.agent.graph'`

- [ ] **Step 3: Implement graph.py**

`app/agent/graph.py`:
```python
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
```

- [ ] **Step 4: Run all agent tests**
```bash
uv run pytest tests/agent/ -v
```
Expected: all tests pass (12 total across 4 test files)

- [ ] **Step 5: Commit**
```bash
git add app/agent/graph.py tests/agent/test_graph.py
git commit -m "feat: add build_graph() with parallel fan-out, Bull/Bear debate loop, circuit breaker"
```

---

### Task 8: ARQ — AI Execution + Maintenance Tasks

**Files:**
- Modify: `app/tasks.py`

- [ ] **Step 1: Add `get_ai_interval` helper**

In `app/tasks.py`, add after the `get_watch_symbols` function (after line ~69):
```python
async def get_ai_interval(db: AsyncSession) -> int:
    """Read ai_interval_minutes from trading.settings. Default: 30."""
    val = await db.scalar(
        text("SELECT value FROM trading.settings WHERE key = 'ai_interval_minutes'")
    )
    return int(val) if val else 30
```

- [ ] **Step 2: Add `task_maybe_run_ai` at end of tasks.py**

```python
async def task_maybe_run_ai(ctx: dict) -> None:
    """每分鐘觸發：依 ai_interval_minutes 設定決定是否執行 AI 分析。"""
    import uuid as _uuid
    from app.agent.graph import build_graph
    from app.models.portfolio import Holding, Portfolio
    from sqlalchemy import select as _select

    now = datetime.now(_TZ)
    if not is_trading_hours():
        return

    async with ctx["db_factory"]() as db:
        interval = await get_ai_interval(db)

    if now.minute % interval != 0:
        return

    logger.info("task_maybe_run_ai: interval=%d min, starting at %s", interval, now.strftime("%H:%M"))
    t0 = _time.monotonic()

    graph = build_graph(
        db_factory=ctx["db_factory"],
        checkpointer=ctx["checkpointer"],
        store=ctx["store"],
    )

    async with ctx["db_factory"]() as db:
        portfolios = (await db.execute(_select(Portfolio))).scalars().all()

    ok = fail = 0
    for port in portfolios:
        async with ctx["db_factory"]() as db:
            holdings = (await db.execute(
                _select(Holding).where(Holding.user_id == port.user_id)
            )).scalars().all()

        for h in holdings:
            session_id = str(_uuid.uuid4())
            thread_id = f"ai_{port.user_id}_{h.symbol}_{now.strftime('%Y%m%d_%H%M')}"
            try:
                from app.agent.state import DebateState
                await graph.ainvoke(
                    {
                        "symbol": h.symbol,
                        "user_id": str(port.user_id),
                        "session_id": session_id,
                        "analyst_reports": [],
                        "debate_state": DebateState(bull_history="", bear_history="",
                                                    history="", current_response="", count=0),
                        "final_decision": None,
                        "executed": False,
                        "execution_note": "",
                    },
                    {"configurable": {"thread_id": thread_id}},
                )
                ok += 1
            except Exception as e:
                fail += 1
                logger.error("task_maybe_run_ai: user=%s symbol=%s error=%s",
                             str(port.user_id)[:8], h.symbol, e)

    logger.info("task_maybe_run_ai: done in %.1fs ok=%d fail=%d",
                _time.monotonic() - t0, ok, fail)
```

- [ ] **Step 3: Add `task_update_trade_outcomes` at end of tasks.py**

```python
async def task_update_trade_outcomes(ctx: dict) -> None:
    """每日 17:00：將 7 天前的 AI 決策損益結果回填至 Store 記憶。"""
    from datetime import timedelta
    from app.agent.memory import NAMESPACE

    store = ctx["store"]
    target_date = datetime.now(_TZ).date() - timedelta(days=7)
    logger.info("task_update_trade_outcomes: backfilling outcomes for %s", target_date)

    async with ctx["db_factory"]() as db:
        rows = (await db.execute(text("""
            SELECT session_id, decisions, created_at
            FROM trading.ai_decisions
            WHERE DATE(created_at AT TIME ZONE 'Asia/Taipei') = :d
        """), {"d": target_date})).fetchall()

    updated = 0
    for row in rows:
        session_id = str(row[0])
        decisions = row[1] or {}
        for symbol, decision in decisions.items():
            entry_price = decision.get("target_price", 0)
            action = decision.get("action", "HOLD")
            if not entry_price or action == "HOLD":
                continue
            async with ctx["db_factory"]() as db:
                current = await db.scalar(text(
                    "SELECT last_price FROM market.market_quotes WHERE symbol=:s"
                ), {"s": symbol})
            if not current:
                continue
            raw_return = (float(current) - entry_price) / entry_price
            outcome = -raw_return if action == "SELL" else raw_return

            all_items = await store.asearch(NAMESPACE, filter={"symbol": symbol}, limit=500)
            for item in all_items:
                if session_id in item.key:
                    await store.aput(NAMESPACE, item.key, {**item.value, "outcome_score": round(outcome, 4)})
                    updated += 1
                    break

    logger.info("task_update_trade_outcomes: updated %d store entries", updated)
```

- [ ] **Step 4: Add `task_cleanup_checkpoints` at end of tasks.py**

```python
async def task_cleanup_checkpoints(ctx: dict) -> None:
    """每日 03:00：刪除 checkpoint_ttl_days 天前的 checkpoint 記錄。"""
    from app.core.config import settings
    ttl = settings.checkpoint_ttl_days
    async with ctx["db_factory"]() as db:
        r = await db.execute(text(
            f"DELETE FROM checkpoints WHERE thread_ts < NOW() - INTERVAL '{ttl} days'"
        ))
        deleted = r.rowcount
        await db.execute(text("""
            DELETE FROM checkpoint_blobs
            WHERE thread_id NOT IN (SELECT thread_id FROM checkpoints)
        """))
        await db.execute(text("""
            DELETE FROM checkpoint_writes
            WHERE thread_id NOT IN (SELECT thread_id FROM checkpoints)
        """))
        await db.commit()
    logger.info("task_cleanup_checkpoints: deleted %d rows older than %d days", deleted, ttl)
```

- [ ] **Step 5: Add `task_prune_store_memories` at end of tasks.py**

```python
async def task_prune_store_memories(ctx: dict) -> None:
    """每週日 02:00：每個 symbol 只保留 top N 筆記憶（按 outcome_score 排序）。"""
    from app.core.config import settings
    from app.agent.memory import NAMESPACE

    store = ctx["store"]
    async with ctx["db_factory"]() as db:
        symbols = await get_watch_symbols(db)

    total_deleted = 0
    for symbol in symbols:
        try:
            items = await store.asearch(NAMESPACE, filter={"symbol": symbol}, limit=1000)
            scored = sorted(
                [i for i in items if i.value.get("outcome_score") is not None],
                key=lambda x: x.value["outcome_score"], reverse=True,
            )
            unscored = [i for i in items if i.value.get("outcome_score") is None]
            keep = settings.store_max_per_symbol
            to_delete = scored[keep:] + unscored[max(0, keep - len(scored)):]
            for item in to_delete:
                await store.adelete(NAMESPACE, item.key)
                total_deleted += 1
        except Exception as e:
            logger.error("task_prune_store_memories: symbol=%s error=%s", symbol, e)

    logger.info("task_prune_store_memories: deleted %d memory entries", total_deleted)
```

- [ ] **Step 6: Commit**
```bash
git add app/tasks.py
git commit -m "feat: add AI cron tasks (maybe_run_ai, update_outcomes, cleanup_checkpoints, prune_store)"
```

---

### Task 9: Worker — Startup/Shutdown + Cron Registration

**Files:**
- Modify: `app/worker.py`

- [ ] **Step 1: Replace app/worker.py entirely**

`app/worker.py`:
```python
"""app/worker.py — ARQ WorkerSettings + startup/shutdown."""
import logging

from arq import cron
from arq.connections import RedisSettings
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.agent.graph import build_graph, get_pg_url
from app.agent.memory import make_prod_checkpointer, make_prod_store
from app.core.config import settings
from app.services.fbs import fbs_client
from app.tasks import (
    task_cleanup_checkpoints,
    task_clear_intraday_candles,
    task_maybe_run_ai,
    task_prune_store_memories,
    task_sync_historical_candles,
    task_sync_institutional_flows,
    task_sync_instruments,
    task_sync_intraday_candles,
    task_sync_margin_trading,
    task_sync_quotes,
    task_sync_us_market,
    task_update_trade_outcomes,
)

logger = logging.getLogger(__name__)


async def startup(ctx: dict) -> None:
    try:
        fbs_client.connect()
        logger.info("Worker startup: FBS connected")
    except RuntimeError as e:
        logger.critical("Worker startup: FBS login failed - %s", e)
        raise

    engine = create_async_engine(settings.database_url, pool_size=5)
    ctx["db_factory"] = async_sessionmaker(engine, expire_on_commit=False)
    ctx["engine"] = engine

    pg_url = get_pg_url()

    ctx["checkpointer"] = await make_prod_checkpointer(pg_url)
    logger.info("Worker startup: AsyncPostgresSaver ready")

    from langchain_google_genai import GoogleGenerativeAIEmbeddings
    embeddings = GoogleGenerativeAIEmbeddings(
        model=settings.gemini_embedding_model,
        google_api_key=settings.gemini_api_key,
    )
    ctx["store"] = await make_prod_store(pg_url, embeddings.aembed_documents)
    logger.info("Worker startup: AsyncPostgresStore (pgvector) ready")
    logger.info("Worker startup complete")


async def shutdown(ctx: dict) -> None:
    fbs_client.disconnect()
    checkpointer = ctx.get("checkpointer")
    if checkpointer and hasattr(checkpointer, "_cm"):
        try:
            await checkpointer._cm.__aexit__(None, None, None)
        except Exception:
            pass
    if "engine" in ctx:
        await ctx["engine"].dispose()
    logger.info("Worker shutdown complete")


class WorkerSettings:
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    on_startup = startup
    on_shutdown = shutdown
    cron_jobs = [
        # ── Data sync ──────────────────────────────────────────────────────
        cron(task_sync_instruments,         hour=8,  minute=30, run_at_startup=False),
        cron(task_sync_us_market,           hour=8,  minute=30, run_at_startup=False),
        cron(task_sync_quotes,              minute=set(range(60))),
        cron(task_sync_intraday_candles,    minute={0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55}),
        cron(task_sync_historical_candles,  hour=14, minute=0,  run_at_startup=False),
        cron(task_clear_intraday_candles,   hour=14, minute=30, run_at_startup=False),
        cron(task_sync_institutional_flows, hour=16, minute=0,  run_at_startup=False),
        cron(task_sync_margin_trading,      hour=16, minute=5,  run_at_startup=False),
        # ── AI Agent ───────────────────────────────────────────────────────
        cron(task_maybe_run_ai,             minute=set(range(60))),
        # ── Memory maintenance ─────────────────────────────────────────────
        cron(task_update_trade_outcomes,    hour=17, minute=0,  run_at_startup=False),
        cron(task_cleanup_checkpoints,      hour=3,  minute=0,  run_at_startup=False),
        cron(task_prune_store_memories,     hour=2,  minute=0,  weekday=6, run_at_startup=False),
    ]
    max_jobs = 10
    job_timeout = 300
```

- [ ] **Step 2: Run full test suite**
```bash
uv run pytest tests/agent/ -v
```
Expected: all 12 tests pass

- [ ] **Step 3: Final commit**
```bash
git add app/worker.py
git commit -m "feat: Step 6 complete - LangGraph agent with Bull/Bear debate and semantic memory"
```

---

## Self-Review

**Spec coverage:**
- ✅ LangGraph StateGraph with parallel fan-out via Send API (3 analysts)
- ✅ Bull/Bear debate loop (configurable rounds via `ai_max_debate_rounds`, default=1)
- ✅ Circuit breaker: risk HOLD + confidence≥0.8 skips debate, forces HOLD
- ✅ Research manager synthesizes debate → `final_decision`
- ✅ `DebateState` captures bull_history, bear_history, full history, count
- ✅ `AsyncPostgresSaver` checkpointer (TTL 7 days via `task_cleanup_checkpoints`)
- ✅ `AsyncPostgresStore` with pgvector + `text-embedding-004`
- ✅ Similarity threshold 0.75 in `search_patterns`
- ✅ Outcome feedback loop (`task_update_trade_outcomes`, 7-day lookback)
- ✅ Score-based memory pruning (`task_prune_store_memories`, weekly)
- ✅ Dynamic interval from `trading.settings.ai_interval_minutes`
- ✅ Google Search Grounding on technical + sentiment analysts only
- ✅ Risk analyst uses plain LLM (純計算，不搜尋)
- ✅ `execute_or_preview` preview-only stub (real FBS execution is Step 7)
- ✅ `persist_result` saves debate history in `agent_reports` JSONB column
- ✅ Full test coverage: 3 unit test files + 1 integration test, 12 tests total

**Known limitations / next steps:**
- `execute_or_preview` is preview-only; real FBS order placement is Step 7
- `task_update_trade_outcomes` uses `market_quotes.last_price` as current price — only accurate during trading hours; Step 7 should use previous day's close for after-hours runs
- `AsyncPostgresStore.adelete` API — verify it exists in the installed langgraph version; if not, use `store.aput(NAMESPACE, key, {"_deleted": True})` as a tombstone workaround
- Bull/Bear prompts are in Traditional Chinese; if the backbone LLM responds in English, prompts may need `"請務必用繁體中文回答"` appended
