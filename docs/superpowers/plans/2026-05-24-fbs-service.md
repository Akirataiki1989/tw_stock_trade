# FBS Service Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 實作 `trading.watchlist` 資料表與 `FbsClient` class，提供 ARQ Worker 背景同步及 FastAPI endpoint on-demand 查詢所需的 FBS SDK 封裝。

**Architecture:** `FbsClient` 為全域 singleton，啟動時呼叫 `connect()` 登入 FBS SDK，取得 REST client。所有 SDK 呼叫（同步）透過 `asyncio.to_thread()` 包裝成 async。背景 `sync_*` 方法直接 upsert DB；on-demand `fetch_*` 方法直接回傳 dict，不存 DB。

**Tech Stack:** fubon_neo SDK、SQLAlchemy 2.0 async、PostgreSQL pg_insert（ON CONFLICT）、pytest + pytest-asyncio、unittest.mock

---

## 檔案異動總覽

| 動作 | 路徑 | 說明 |
|------|------|------|
| Modify | `app/models/portfolio.py` | 新增 `Watchlist` ORM class |
| Modify | `app/models/__init__.py` | export `Watchlist` |
| Create | `alembic/versions/0002_add_watchlist.py` | DB migration |
| Create | `app/services/fbs.py` | `FbsClient` class + singleton |
| Create | `tests/__init__.py` | pytest 套件標記 |
| Create | `tests/conftest.py` | 共用 fixtures |
| Create | `tests/test_fbs.py` | FbsClient 單元測試 |

---

## Task 1：Watchlist ORM Model

**Files:**
- Modify: `app/models/portfolio.py`
- Modify: `app/models/__init__.py`

- [ ] **Step 1：在 `app/models/portfolio.py` 尾端加入 `Watchlist` class**

在檔案最後加入（`import uuid`, `BigInteger`, `UniqueConstraint`, `func` 已在檔首 import）：

```python
class Watchlist(Base):
    __tablename__ = "watchlist"
    __table_args__ = (UniqueConstraint("user_id", "symbol"), {"schema": "trading"})

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("public.users.id", ondelete="CASCADE"), nullable=False
    )
    symbol: Mapped[str] = mapped_column(
        String(10), ForeignKey("market.instruments.symbol"), nullable=False
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
```

- [ ] **Step 2：更新 `app/models/__init__.py`，export `Watchlist`**

```python
from app.models.base import Base
from app.models.market import HistoricalCandle, Instrument, IntradayCandle, MarketQuote
from app.models.portfolio import (
    AiDecision,
    DailyPerformance,
    Holding,
    Portfolio,
    Trade,
    Watchlist,
)
from app.models.user import User

__all__ = [
    "Base",
    "User",
    "Portfolio",
    "Holding",
    "Trade",
    "Watchlist",
    "AiDecision",
    "DailyPerformance",
    "Instrument",
    "MarketQuote",
    "IntradayCandle",
    "HistoricalCandle",
]
```

- [ ] **Step 3：確認 import 正常（NAS SSH）**

```bash
uv run python -c "from app.models import Watchlist; print(Watchlist.__table_args__)"
```

期望輸出：`({'schema': 'trading'},)` 或含 `UniqueConstraint` 的 tuple

- [ ] **Step 4：commit**

```bash
git add app/models/portfolio.py app/models/__init__.py
git commit -m "feat: add Watchlist ORM model"
```

---

## Task 2：Migration 0002_add_watchlist

**Files:**
- Create: `alembic/versions/0002_add_watchlist.py`

- [ ] **Step 1：建立 migration 檔案**

新建 `alembic/versions/0002_add_watchlist.py`：

```python
"""add watchlist table

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-24
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "watchlist",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("public.users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "symbol",
            sa.String(10),
            sa.ForeignKey("market.instruments.symbol"),
            nullable=False,
        ),
        sa.Column("added_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "symbol"),
        schema="trading",
    )
    op.create_index(
        "idx_watchlist_user", "watchlist", ["user_id"], schema="trading"
    )


def downgrade() -> None:
    op.drop_index("idx_watchlist_user", table_name="watchlist", schema="trading")
    op.drop_table("watchlist", schema="trading")
```

- [ ] **Step 2：執行 migration（NAS SSH）**

```bash
export PATH="/volume1/web/codeserver/.tools:$PATH"
export UV_CACHE_DIR=/volume1/web/codeserver/.uv-cache
export UV_DATA_DIR=/volume1/web/codeserver/.uv-data
export UV_PYTHON_INSTALL_DIR=/volume1/web/codeserver/.uv-python
cd /volume1/web/codeserver/tw_stock_trade
.venv/bin/alembic upgrade head
```

期望輸出：`Running upgrade 0001 -> 0002, add watchlist table`

- [ ] **Step 3：commit**

```bash
git add alembic/versions/0002_add_watchlist.py
git commit -m "feat: add trading.watchlist migration"
```

---

## Task 3：FbsClient 骨架 + 連線管理

**Files:**
- Create: `app/services/fbs.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/test_fbs.py`

- [ ] **Step 1：建立 `tests/__init__.py`（空檔）**

```python
```

- [ ] **Step 2：建立 `tests/conftest.py`**

```python
import pytest
from unittest.mock import MagicMock

from app.services.fbs import FbsClient


@pytest.fixture
def client() -> FbsClient:
    """回傳一個已注入 mock _sdk / _rest 的 FbsClient（不實際登入）。"""
    c = FbsClient()
    c._sdk = MagicMock()
    c._rest = MagicMock()
    return c
```

- [ ] **Step 3：寫 connect/disconnect 的失敗測試**

建立 `tests/test_fbs.py`：

```python
import pytest
from unittest.mock import MagicMock, patch

from app.services.fbs import FbsClient


# ── connect ────────────────────────────────────────────────────────────────


def test_connect_success():
    """登入成功時 is_connected() 回傳 True。"""
    mock_sdk = MagicMock()
    mock_accounts = MagicMock()
    mock_accounts.is_success = True
    mock_accounts.data = [MagicMock()]
    mock_sdk.login.return_value = mock_accounts
    mock_sdk.exchange_realtime_token.return_value = "fake-token"

    with (
        patch("app.services.fbs.FubonSDK", return_value=mock_sdk),
        patch("app.services.fbs.build_rest_client", return_value=MagicMock()),
    ):
        c = FbsClient()
        c.connect()

    assert c.is_connected() is True


def test_connect_login_failure_raises():
    """登入失敗時 connect() 拋 RuntimeError。"""
    mock_sdk = MagicMock()
    mock_accounts = MagicMock()
    mock_accounts.is_success = False
    mock_sdk.login.return_value = mock_accounts

    with (
        patch("app.services.fbs.FubonSDK", return_value=mock_sdk),
        patch("app.services.fbs.build_rest_client", return_value=MagicMock()),
        pytest.raises(RuntimeError, match="FBS login failed"),
    ):
        c = FbsClient()
        c.connect()


def test_disconnect_clears_state():
    """disconnect() 後 is_connected() 回傳 False。"""
    c = FbsClient()
    c._sdk = MagicMock()
    c._rest = MagicMock()
    c.disconnect()
    assert c.is_connected() is False
```

- [ ] **Step 4：執行測試，確認全部 FAIL（模組尚未存在）**

```bash
uv run pytest tests/test_fbs.py -v 2>&1 | head -30
```

期望：`ModuleNotFoundError: No module named 'app.services.fbs'`

- [ ] **Step 5：實作 `app/services/fbs.py` 骨架**

```python
"""FBS Fubon Neo SDK 封裝。

使用方式：
    from app.services.fbs import fbs_client

    # ARQ on_startup
    fbs_client.connect()

    # ARQ task
    await fbs_client.sync_quote(db, "2330")

    # FastAPI endpoint
    quote = await fbs_client.fetch_quote("2330")
"""

import asyncio
import logging
from datetime import date, datetime, timezone
from typing import Any

from fubon_neo.adapter import build_rest_client
from fubon_neo.sdk import FubonSDK
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.market import HistoricalCandle, Instrument, IntradayCandle, MarketQuote

logger = logging.getLogger(__name__)


class FbsClient:
    """FBS SDK singleton 封裝。

    在 ARQ Worker on_startup 呼叫 connect()；
    所有 sync_* / fetch_* 方法供 Worker 任務與 FastAPI endpoint 使用。
    """

    def __init__(self) -> None:
        self._sdk: FubonSDK | None = None
        self._rest: Any | None = None

    # ── 連線管理 ──────────────────────────────────────────────────────────

    def connect(self) -> None:
        """登入 FBS SDK，建立 REST client。登入失敗拋 RuntimeError。"""
        sdk = FubonSDK()
        accounts = sdk.login(settings.fbs_account, settings.fbs_password, settings.fbs_cert_path)
        if not accounts.is_success:
            raise RuntimeError("FBS login failed")
        token = sdk.exchange_realtime_token()
        self._sdk = sdk
        self._rest = build_rest_client(token)
        logger.info("FBS connected, account: %s", accounts.data[0].account)

    def disconnect(self) -> None:
        """清除 SDK 連線狀態（SDK 無明確 logout API）。"""
        self._sdk = None
        self._rest = None
        logger.info("FBS disconnected")

    def is_connected(self) -> bool:
        return self._sdk is not None and self._rest is not None


# 模組層級 singleton — ARQ Worker 與 FastAPI endpoint import 這個
fbs_client = FbsClient()
```

- [ ] **Step 6：執行測試，確認 connect 相關測試通過**

```bash
uv run pytest tests/test_fbs.py -v -k "connect or disconnect"
```

期望：`3 passed`

- [ ] **Step 7：commit**

```bash
git add app/services/fbs.py tests/__init__.py tests/conftest.py tests/test_fbs.py
git commit -m "feat: add FbsClient skeleton with connect/disconnect"
```

---

## Task 4：sync_instruments()

**Files:**
- Modify: `app/services/fbs.py`
- Modify: `tests/test_fbs.py`

- [ ] **Step 1：新增 sync_instruments 測試**

在 `tests/test_fbs.py` 尾端加入：

```python
# ── sync_instruments ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sync_instruments_returns_count(client):
    """sync_instruments() 回傳寫入筆數，並呼叫 db.execute + db.commit。"""
    from unittest.mock import AsyncMock, patch

    fake_data = {
        "data": [
            {"symbol": "2330", "name": "台積電", "industry": "24"},
            {"symbol": "2317", "name": "鴻海", "industry": "28"},
        ]
    }
    mock_db = AsyncMock()

    with patch("app.services.fbs.asyncio.to_thread", new=AsyncMock(return_value=fake_data)):
        count = await client.sync_instruments(mock_db)

    assert count == 2
    mock_db.execute.assert_called_once()
    mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_sync_instruments_empty_data(client):
    """data 為空時回傳 0，不呼叫 db.execute。"""
    from unittest.mock import AsyncMock, patch

    with patch("app.services.fbs.asyncio.to_thread", new=AsyncMock(return_value={"data": []})):
        mock_db = AsyncMock()
        count = await client.sync_instruments(mock_db)

    assert count == 0
    mock_db.execute.assert_not_called()
```

- [ ] **Step 2：執行測試，確認 FAIL**

```bash
uv run pytest tests/test_fbs.py -v -k "sync_instruments"
```

期望：`AttributeError: 'FbsClient' object has no attribute 'sync_instruments'`

- [ ] **Step 3：在 `FbsClient` 中實作 `sync_instruments()`**

在 `fbs_client = FbsClient()` 這行之前，`is_connected()` 之後加入：

```python
    # ── 背景同步（存 DB）────────────────────────────────────────────────────

    async def sync_instruments(self, db: AsyncSession) -> int:
        """從 FBS 拉取全部股票清單，批次 upsert 到 market.instruments。

        Returns:
            寫入（新增 + 更新）的筆數。
        """
        raw: dict = await asyncio.to_thread(
            self._rest.stock.intraday.tickers, type="EQUITY"
        )
        rows: list[dict] = raw.get("data", [])
        if not rows:
            logger.warning("sync_instruments: FBS returned empty ticker list")
            return 0

        values = [
            {
                "symbol": r["symbol"],
                "name": r.get("name"),
                "industry": r.get("industry"),
            }
            for r in rows
        ]

        stmt = pg_insert(Instrument).values(values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["symbol"],
            set_={
                "name": stmt.excluded.name,
                "industry": stmt.excluded.industry,
                "last_synced": func.now(),
            },
        )
        await db.execute(stmt)
        await db.commit()
        logger.info("sync_instruments: upserted %d instruments", len(values))
        return len(values)
```

- [ ] **Step 4：執行測試，確認通過**

```bash
uv run pytest tests/test_fbs.py -v -k "sync_instruments"
```

期望：`2 passed`

- [ ] **Step 5：commit**

```bash
git add app/services/fbs.py tests/test_fbs.py
git commit -m "feat: implement FbsClient.sync_instruments()"
```

---

## Task 5：sync_quote()

**Files:**
- Modify: `app/services/fbs.py`
- Modify: `tests/test_fbs.py`

- [ ] **Step 1：新增 sync_quote 測試**

在 `tests/test_fbs.py` 尾端加入：

```python
# ── sync_quote ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sync_quote_success(client):
    """正常回傳時 sync_quote() 回傳 True，呼叫 db.execute + db.commit。"""
    from unittest.mock import AsyncMock, patch

    fake_quote = {
        "referencePrice": 2230, "previousClose": 2230,
        "openPrice": 2245, "highPrice": 2260, "lowPrice": 2225,
        "closePrice": 2255, "lastPrice": 2255, "lastSize": 3821,
        "avgPrice": 2243.86, "change": 25, "changePercent": 1.12,
        "amplitude": 1.57, "bids": [], "asks": [], "total": {},
    }
    mock_db = AsyncMock()

    with patch("app.services.fbs.asyncio.to_thread", new=AsyncMock(return_value=fake_quote)):
        result = await client.sync_quote(mock_db, "2330")

    assert result is True
    mock_db.execute.assert_called_once()
    mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_sync_quote_429_returns_false(client):
    """SDK 拋 429 例外時，sync_quote() 回傳 False 而非往上拋。"""
    from unittest.mock import AsyncMock, patch

    async def raise_429(*args, **kwargs):
        raise Exception("429 Rate limit exceeded")

    mock_db = AsyncMock()

    with patch("app.services.fbs.asyncio.to_thread", new=raise_429):
        result = await client.sync_quote(mock_db, "2330")

    assert result is False
    mock_db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_sync_quote_other_exception_propagates(client):
    """非 429 例外應往上拋，讓 ARQ 重試機制感知。"""
    from unittest.mock import AsyncMock, patch

    async def raise_conn_err(*args, **kwargs):
        raise ConnectionError("SDK connection lost")

    mock_db = AsyncMock()

    with (
        patch("app.services.fbs.asyncio.to_thread", new=raise_conn_err),
        pytest.raises(ConnectionError),
    ):
        await client.sync_quote(mock_db, "2330")
```

- [ ] **Step 2：執行測試，確認 FAIL**

```bash
uv run pytest tests/test_fbs.py -v -k "sync_quote"
```

- [ ] **Step 3：實作 `sync_quote()`**

在 `sync_instruments()` 之後加入：

```python
    async def sync_quote(self, db: AsyncSession, symbol: str) -> bool:
        """從 FBS 拉取單一股票即時報價，upsert 到 market.market_quotes。

        Returns:
            True=成功寫入；False=429 或資料為空（跳過，不拋例外）。
        """
        try:
            raw: dict = await asyncio.to_thread(
                self._rest.stock.intraday.quote, symbol=symbol
            )
        except Exception as e:
            msg = str(e).lower()
            if "429" in msg or "rate limit" in msg:
                logger.warning("FBS 429 rate limit for symbol=%s, skipping", symbol)
                return False
            raise

        if not raw:
            logger.warning("sync_quote: empty response for symbol=%s", symbol)
            return False

        now = datetime.now(timezone.utc)
        stmt = pg_insert(MarketQuote).values(
            symbol=symbol,
            reference_price=raw.get("referencePrice"),
            prev_close=raw.get("previousClose"),
            open_price=raw.get("openPrice"),
            high_price=raw.get("highPrice"),
            low_price=raw.get("lowPrice"),
            close_price=raw.get("closePrice"),
            last_price=raw.get("lastPrice"),
            last_size=raw.get("lastSize"),
            avg_price=raw.get("avgPrice"),
            change=raw.get("change"),
            change_pct=raw.get("changePercent"),
            amplitude=raw.get("amplitude"),
            bids=raw.get("bids"),
            asks=raw.get("asks"),
            total=raw.get("total"),
            is_limit_up=False,
            is_limit_down=False,
            is_trial=False,
            fetched_at=now,
        )
        update_cols = [
            "reference_price", "prev_close", "open_price", "high_price", "low_price",
            "close_price", "last_price", "last_size", "avg_price", "change",
            "change_pct", "amplitude", "bids", "asks", "total",
            "is_limit_up", "is_limit_down", "is_trial", "fetched_at",
        ]
        stmt = stmt.on_conflict_do_update(
            index_elements=["symbol"],
            set_={col: getattr(stmt.excluded, col) for col in update_cols},
        )
        await db.execute(stmt)
        await db.commit()
        return True
```

- [ ] **Step 4：執行測試，確認通過**

```bash
uv run pytest tests/test_fbs.py -v -k "sync_quote"
```

期望：`3 passed`

- [ ] **Step 5：commit**

```bash
git add app/services/fbs.py tests/test_fbs.py
git commit -m "feat: implement FbsClient.sync_quote()"
```

---

## Task 6：sync_intraday_candles()

> ⚠️ **前置確認**：FBS intraday candles API 的 timestamp 欄位名稱需要在 NAS 上實際驗證。

**Files:**
- Modify: `app/services/fbs.py`
- Modify: `tests/test_fbs.py`

- [ ] **Step 1：在 NAS SSH 驗證 candle response 實際欄位**

```bash
cd /volume1/web/codeserver/tw_stock_trade
uv run python - <<'EOF'
from fubon_neo.sdk import FubonSDK
from fubon_neo.adapter import build_rest_client
import os, json

sdk = FubonSDK()
acc = sdk.login(os.environ["FBS_ACCOUNT"], os.environ["FBS_PASSWORD"],
                os.environ["FBS_CERT_PATH"])
rest = build_rest_client(sdk.exchange_realtime_token())
result = rest.stock.intraday.candles(symbol="2330", timeframe="1")
# 印出前 2 筆，確認欄位
print(json.dumps(result.get("data", [])[:2], ensure_ascii=False, indent=2))
EOF
```

**確認回傳的 dict 有哪些 key**。若有時間欄位（可能叫 `time`、`ts`、`datetime`），記下欄位名稱後繼續；若沒有，跳到 Step 1b。

- [ ] **Step 1b（若無 timestamp）：暫時跳過 intraday_candles 實作**

若 API 回傳的 candle 無法對應到 `ts`，在 `sync_intraday_candles()` 中記錄 warning 並回傳 0，等 WebSocket 實作（Step 7）時補充：

```python
    async def sync_intraday_candles(
        self, db: AsyncSession, symbol: str, timeframe: str
    ) -> int:
        logger.warning(
            "sync_intraday_candles: timestamp field not confirmed in FBS API, skipping"
        )
        return 0
```

跳至 Step 5（commit）。

- [ ] **Step 2：新增 sync_intraday_candles 測試**

（假設 timestamp 欄位名為 `"time"`，若不同請替換）

在 `tests/test_fbs.py` 尾端加入：

```python
# ── sync_intraday_candles ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sync_intraday_candles_returns_count(client):
    """回傳今日全部 K 棒數量，不重複插入已存在的資料。"""
    from unittest.mock import AsyncMock, patch

    fake_data = {
        "data": [
            {"time": "2026-05-24T09:00:00+08:00", "open": 100, "high": 105,
             "low": 99, "close": 103, "volume": 500, "average": 102.0},
            {"time": "2026-05-24T09:01:00+08:00", "open": 103, "high": 106,
             "low": 102, "close": 105, "volume": 300, "average": 104.0},
        ]
    }
    mock_db = AsyncMock()

    with patch("app.services.fbs.asyncio.to_thread", new=AsyncMock(return_value=fake_data)):
        count = await client.sync_intraday_candles(mock_db, "2330", "1")

    assert count == 2
    mock_db.execute.assert_called_once()
    mock_db.commit.assert_called_once()
```

- [ ] **Step 3：執行測試，確認 FAIL**

```bash
uv run pytest tests/test_fbs.py -v -k "sync_intraday"
```

- [ ] **Step 4：實作 `sync_intraday_candles()`**

（若 timestamp 欄位名為 `"time"`，若不同依 Step 1 實際欄位替換）

在 `sync_quote()` 之後加入：

```python
    async def sync_intraday_candles(
        self, db: AsyncSession, symbol: str, timeframe: str
    ) -> int:
        """從 FBS 拉取今日盤中 K 棒，upsert 到 market.intraday_candles。

        使用 ON CONFLICT DO NOTHING：已存在的 K 棒不覆蓋，新的才寫入。

        Returns:
            嘗試插入的筆數（含已存在的，實際新增筆數可能更少）。
        """
        raw: dict = await asyncio.to_thread(
            self._rest.stock.intraday.candles, symbol=symbol, timeframe=timeframe
        )
        rows: list[dict] = raw.get("data", [])
        if not rows:
            return 0

        # ⚠️ "time" 欄位名稱請依 Step 1 實際驗證結果調整
        values = [
            {
                "symbol": symbol,
                "timeframe": timeframe,
                "ts": datetime.fromisoformat(r["time"]),
                "open": r.get("open"),
                "high": r.get("high"),
                "low": r.get("low"),
                "close": r.get("close"),
                "volume": r.get("volume"),
                "average": r.get("average"),
            }
            for r in rows
            if r.get("time")  # 跳過無 timestamp 的資料
        ]
        if not values:
            return 0

        stmt = pg_insert(IntradayCandle).values(values)
        stmt = stmt.on_conflict_do_nothing()
        await db.execute(stmt)
        await db.commit()
        logger.debug("sync_intraday_candles: %s tf=%s, %d rows", symbol, timeframe, len(values))
        return len(values)
```

- [ ] **Step 5：執行測試，確認通過**

```bash
uv run pytest tests/test_fbs.py -v -k "sync_intraday"
```

期望：`1 passed`

- [ ] **Step 6：commit**

```bash
git add app/services/fbs.py tests/test_fbs.py
git commit -m "feat: implement FbsClient.sync_intraday_candles()"
```

---

## Task 7：sync_historical_candles()

**Files:**
- Modify: `app/services/fbs.py`
- Modify: `tests/test_fbs.py`

- [ ] **Step 1：新增 sync_historical_candles 測試**

在 `tests/test_fbs.py` 尾端加入：

```python
# ── sync_historical_candles ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sync_historical_candles_returns_count(client):
    """回傳正確筆數，並以 ON CONFLICT DO UPDATE 覆蓋舊資料。"""
    from datetime import date
    from unittest.mock import AsyncMock, patch

    fake_data = {
        "data": [
            {"date": "2026-05-22", "open": 2245, "high": 2260, "low": 2225,
             "close": 2255, "volume": 26823133, "turnover": 60188140377, "change": 25},
            {"date": "2026-05-21", "open": 2210, "high": 2240, "low": 2205,
             "close": 2230, "volume": 20000000, "turnover": 44600000000, "change": -10},
        ]
    }
    mock_db = AsyncMock()

    with patch("app.services.fbs.asyncio.to_thread", new=AsyncMock(return_value=fake_data)):
        count = await client.sync_historical_candles(
            mock_db, "2330", "D",
            date(2026, 5, 21), date(2026, 5, 22),
        )

    assert count == 2
    mock_db.execute.assert_called_once()
    mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_sync_historical_candles_empty(client):
    """data 為空時回傳 0，不呼叫 db.execute。"""
    from datetime import date
    from unittest.mock import AsyncMock, patch

    mock_db = AsyncMock()
    with patch("app.services.fbs.asyncio.to_thread", new=AsyncMock(return_value={"data": []})):
        count = await client.sync_historical_candles(
            mock_db, "2330", "D", date(2026, 5, 1), date(2026, 5, 22)
        )

    assert count == 0
    mock_db.execute.assert_not_called()
```

- [ ] **Step 2：執行測試，確認 FAIL**

```bash
uv run pytest tests/test_fbs.py -v -k "sync_historical"
```

- [ ] **Step 3：實作 `sync_historical_candles()`**

在 `sync_intraday_candles()` 之後加入：

```python
    async def sync_historical_candles(
        self,
        db: AsyncSession,
        symbol: str,
        timeframe: str,
        from_date: date,
        to_date: date,
    ) -> int:
        """從 FBS 拉取歷史 K 棒，upsert 到 market.historical_candles。

        使用 ON CONFLICT DO UPDATE：補資料時覆蓋，確保資料正確性。

        Returns:
            寫入筆數。
        """
        raw: dict = await asyncio.to_thread(
            self._rest.stock.historical.candles,
            **{
                "symbol": symbol,
                "from": from_date.isoformat(),
                "to": to_date.isoformat(),
                "timeframe": timeframe,
                "fields": "open,high,low,close,volume,turnover,change",
            },
        )
        rows: list[dict] = raw.get("data", [])
        if not rows:
            return 0

        values = [
            {
                "symbol": symbol,
                "timeframe": timeframe,
                "date": date.fromisoformat(r["date"]),
                "open": r.get("open"),
                "high": r.get("high"),
                "low": r.get("low"),
                "close": r.get("close"),
                "volume": r.get("volume"),
                "turnover": r.get("turnover"),
                "change": r.get("change"),
            }
            for r in rows
        ]

        stmt = pg_insert(HistoricalCandle).values(values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["symbol", "timeframe", "date"],
            set_={
                col: getattr(stmt.excluded, col)
                for col in ["open", "high", "low", "close", "volume", "turnover", "change"]
            },
        )
        await db.execute(stmt)
        await db.commit()
        logger.info(
            "sync_historical_candles: %s tf=%s %s~%s, %d rows",
            symbol, timeframe, from_date, to_date, len(values),
        )
        return len(values)
```

- [ ] **Step 4：執行測試，確認通過**

```bash
uv run pytest tests/test_fbs.py -v -k "sync_historical"
```

期望：`2 passed`

- [ ] **Step 5：commit**

```bash
git add app/services/fbs.py tests/test_fbs.py
git commit -m "feat: implement FbsClient.sync_historical_candles()"
```

---

## Task 8：fetch_quote() + fetch_candles()（on-demand）

**Files:**
- Modify: `app/services/fbs.py`
- Modify: `tests/test_fbs.py`

- [ ] **Step 1：新增 fetch 測試**

在 `tests/test_fbs.py` 尾端加入：

```python
# ── fetch_quote / fetch_candles ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fetch_quote_returns_dict(client):
    """fetch_quote() 直接回傳 SDK dict，不寫 DB。"""
    from unittest.mock import AsyncMock, patch

    fake_quote = {"symbol": "2330", "lastPrice": 2255}
    with patch("app.services.fbs.asyncio.to_thread", new=AsyncMock(return_value=fake_quote)):
        result = await client.fetch_quote("2330")

    assert result == fake_quote


@pytest.mark.asyncio
async def test_fetch_quote_none_on_exception(client):
    """SDK 拋例外時 fetch_quote() 回傳 None（不拋）。"""
    from unittest.mock import AsyncMock, patch

    async def raise_err(*args, **kwargs):
        raise Exception("network error")

    with patch("app.services.fbs.asyncio.to_thread", new=raise_err):
        result = await client.fetch_quote("2330")

    assert result is None


@pytest.mark.asyncio
async def test_fetch_candles_returns_list(client):
    """fetch_candles() 直接回傳 K 棒 list，不寫 DB。"""
    from datetime import date
    from unittest.mock import AsyncMock, patch

    fake_data = {"data": [{"date": "2026-05-22", "close": 2255}]}
    with patch("app.services.fbs.asyncio.to_thread", new=AsyncMock(return_value=fake_data)):
        result = await client.fetch_candles("2330", "D", date(2026, 5, 1), date(2026, 5, 22))

    assert len(result) == 1
    assert result[0]["date"] == "2026-05-22"


@pytest.mark.asyncio
async def test_fetch_candles_empty_on_exception(client):
    """SDK 拋例外時 fetch_candles() 回傳空 list。"""
    from datetime import date
    from unittest.mock import AsyncMock, patch

    async def raise_err(*args, **kwargs):
        raise Exception("timeout")

    with patch("app.services.fbs.asyncio.to_thread", new=raise_err):
        result = await client.fetch_candles("2330", "D", date(2026, 5, 1), date(2026, 5, 22))

    assert result == []
```

- [ ] **Step 2：執行測試，確認 FAIL**

```bash
uv run pytest tests/test_fbs.py -v -k "fetch"
```

- [ ] **Step 3：實作 `fetch_quote()` + `fetch_candles()`**

在 `sync_historical_candles()` 之後、`fbs_client = FbsClient()` 之前加入：

```python
    # ── On-demand 查詢（不存 DB）────────────────────────────────────────────

    async def fetch_quote(self, symbol: str) -> dict | None:
        """即時拉取單一股票報價，不存 DB。

        供 FastAPI /market/search 預覽 與 /market/quote/{symbol} DB miss 時使用。

        Returns:
            FBS 回傳的 quote dict；例外時回傳 None。
        """
        try:
            return await asyncio.to_thread(
                self._rest.stock.intraday.quote, symbol=symbol
            )
        except Exception:
            logger.warning("fetch_quote failed for symbol=%s", symbol, exc_info=True)
            return None

    async def fetch_candles(
        self,
        symbol: str,
        timeframe: str,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> list[dict]:
        """即時拉取 K 棒資料，不存 DB。

        timeframe in {"D","W","M"} 走 historical；其他走 intraday。

        Returns:
            K 棒 list；例外時回傳空 list。
        """
        try:
            if timeframe in {"D", "W", "M"}:
                raw = await asyncio.to_thread(
                    self._rest.stock.historical.candles,
                    **{
                        "symbol": symbol,
                        "from": (from_date or date.today()).isoformat(),
                        "to": (to_date or date.today()).isoformat(),
                        "timeframe": timeframe,
                        "fields": "open,high,low,close,volume,turnover,change",
                    },
                )
            else:
                raw = await asyncio.to_thread(
                    self._rest.stock.intraday.candles,
                    symbol=symbol,
                    timeframe=timeframe,
                )
            return raw.get("data", [])
        except Exception:
            logger.warning("fetch_candles failed for symbol=%s tf=%s", symbol, timeframe, exc_info=True)
            return []
```

- [ ] **Step 4：執行測試，確認通過**

```bash
uv run pytest tests/test_fbs.py -v -k "fetch"
```

期望：`4 passed`

- [ ] **Step 5：執行全部測試**

```bash
uv run pytest tests/test_fbs.py -v
```

期望：全部 pass（至少 15 個測試）

- [ ] **Step 6：Ruff lint 檢查**

```bash
uv run ruff check app/services/fbs.py
```

期望：無錯誤輸出

- [ ] **Step 7：commit**

```bash
git add app/services/fbs.py tests/test_fbs.py
git commit -m "feat: implement FbsClient.fetch_quote() and fetch_candles()"
```

---

## Task 9：整合驗證（NAS SSH）

**Files:** 無異動

- [ ] **Step 1：在 NAS SSH 手動驗證 connect()**

```bash
cd /volume1/web/codeserver/tw_stock_trade
uv run python - <<'EOF'
from app.services.fbs import fbs_client
fbs_client.connect()
print("connected:", fbs_client.is_connected())
EOF
```

期望：`connected: True`

- [ ] **Step 2：驗證 fetch_quote()**

```bash
uv run python - <<'EOF'
import asyncio
from app.services.fbs import fbs_client
fbs_client.connect()
quote = asyncio.run(fbs_client.fetch_quote("2330"))
print("lastPrice:", quote.get("lastPrice") if quote else "None")
EOF
```

期望：印出台積電最新價格

- [ ] **Step 3：驗證 fetch_candles()（歷史）**

```bash
uv run python - <<'EOF'
import asyncio
from datetime import date
from app.services.fbs import fbs_client
fbs_client.connect()
candles = asyncio.run(fbs_client.fetch_candles("2330", "D",
    date(2026, 5, 1), date(2026, 5, 23)))
print(f"got {len(candles)} candles, first:", candles[0] if candles else "empty")
EOF
```

期望：至少回傳幾筆歷史 K 棒

- [ ] **Step 4：最終 commit**

```bash
git add .
git commit -m "feat: Step 4 complete - FBS service + watchlist table"
```

---

## 完成標準

- [ ] `uv run pytest tests/test_fbs.py` 全部通過
- [ ] `uv run ruff check app/services/fbs.py` 無錯誤
- [ ] NAS SSH 上 `connect()` + `fetch_quote()` + `fetch_candles()` 均正常執行
- [ ] `alembic upgrade head` 在 NAS 成功執行，`trading.watchlist` 表存在
