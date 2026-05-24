# ARQ Worker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立 ARQ Worker（`app/worker.py` + `app/tasks.py`），定時同步台股市場資料（instruments、quotes、intraday candles、historical candles）到 PostgreSQL。

**Architecture:** `app/tasks.py` 包含所有 cron task 函式與共用 helper；`app/worker.py` 只負責 ARQ `WorkerSettings`、`startup`、`shutdown`。Worker 啟動時登入 FBS SDK 並建立 DB engine，所有 task 透過 `ctx["db_factory"]` 取得 DB session、透過全域 `fbs_client` 呼叫 FBS。

**Tech Stack:** ARQ 0.28+、Redis（localhost:6379）、SQLAlchemy 2.0 async、ZoneInfo（stdlib）、pytest-asyncio（asyncio_mode=auto）

---

## 檔案結構

| 動作 | 路徑 | 說明 |
|------|------|------|
| **修改** | `app/services/fbs.py` | 修正 intraday candles timestamp 欄位名稱 bug（`"time"` → `"date"`） |
| **修改** | `tests/test_fbs.py` | 對應 fix test data key |
| **建立** | `app/tasks.py` | TRACE 層級、helper 函式、5 個 cron task |
| **建立** | `app/worker.py` | startup/shutdown hooks + WorkerSettings |
| **建立** | `tests/test_tasks.py` | helpers 與 task 邏輯的單元測試 |

---

### Task 1：修正 `fbs.py` intraday candles timestamp bug

**Files:**
- Modify: `app/services/fbs.py:185,194`
- Modify: `tests/test_fbs.py:157`

FBS `intraday.candles` API 實際回傳欄位名稱是 `"date"`（格式 `"2026-05-22T09:00:00.000+08:00"`），不是 `"time"`。
這個 bug 會讓 Worker 同步盤中 K 棒時全部跳過資料。

- [ ] **Step 1：確認目前 bug 位置**

打開 `app/services/fbs.py`，找到 `sync_intraday_candles` 方法（約 line 181–195）。
確認目前程式是 `r["time"]` 和 `r.get("time")`。

- [ ] **Step 2：修正 `fbs.py`**

將 `sync_intraday_candles` 方法的 `values` list comprehension 改為：

```python
values = [
    {
        "symbol": symbol,
        "timeframe": timeframe,
        "ts": datetime.fromisoformat(r["date"]),
        "open": r.get("open"),
        "high": r.get("high"),
        "low": r.get("low"),
        "close": r.get("close"),
        "volume": r.get("volume"),
        "average": r.get("average"),
    }
    for r in rows
    if r.get("date")  # 跳過無 timestamp 的資料
]
```

- [ ] **Step 3：修正 `tests/test_fbs.py`**

找到 `test_sync_intraday_candles_returns_count`（約 line 151），將 `fake_data` 的兩筆資料 key 從 `"time"` 改成 `"date"`：

```python
fake_data = {
    "data": [
        {"date": "2026-05-24T09:00:00+08:00", "open": 100, "high": 105,
         "low": 99, "close": 103, "volume": 500, "average": 102.0},
        {"date": "2026-05-24T09:05:00+08:00", "open": 103, "high": 106,
         "low": 102, "close": 105, "volume": 300, "average": 104.0},
    ]
}
```

- [ ] **Step 4：跑測試，確認通過**

```bash
uv run pytest tests/test_fbs.py -v
```

預期：全部 PASSED（不應有 FAILED）

- [ ] **Step 5：Ruff 檢查**

```bash
uv run ruff check app/services/fbs.py
```

預期：無輸出（無錯誤）

- [ ] **Step 6：Commit**

```bash
git add app/services/fbs.py tests/test_fbs.py
git commit -m "fix: intraday candles timestamp field 'time' -> 'date'"
```

---

### Task 2：建立 `app/tasks.py` — TRACE 層級 + helper 函式

**Files:**
- Create: `app/tasks.py`
- Create: `tests/test_tasks.py`（helper 的測試）

- [ ] **Step 1：撰寫 `is_trading_hours()` 的失敗測試**

建立 `tests/test_tasks.py`，內容如下：

```python
"""tests/test_tasks.py — ARQ task helpers 單元測試。"""
from datetime import datetime
from unittest.mock import patch

from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Taipei")


# ── is_trading_hours ────────────────────────────────────────────────────────

def _patch_now(dt_str: str):
    """回傳 patch context manager，將 tasks.py 內 datetime.now 固定為 dt_str。"""
    dt = datetime.fromisoformat(dt_str).replace(tzinfo=TZ)
    return patch("app.tasks.datetime")


def test_trading_hours_weekday_inside():
    """週一 09:15 → True。"""
    from app.tasks import is_trading_hours
    dt = datetime(2026, 5, 25, 9, 15, tzinfo=TZ)   # 2026-05-25 is Monday
    with patch("app.tasks.datetime") as mock_dt:
        mock_dt.now.return_value = dt
        assert is_trading_hours() is True


def test_trading_hours_weekday_before_open():
    """週一 08:59 → False。"""
    from app.tasks import is_trading_hours
    dt = datetime(2026, 5, 25, 8, 59, tzinfo=TZ)
    with patch("app.tasks.datetime") as mock_dt:
        mock_dt.now.return_value = dt
        assert is_trading_hours() is False


def test_trading_hours_weekday_after_close():
    """週一 13:31 → False。"""
    from app.tasks import is_trading_hours
    dt = datetime(2026, 5, 25, 13, 31, tzinfo=TZ)
    with patch("app.tasks.datetime") as mock_dt:
        mock_dt.now.return_value = dt
        assert is_trading_hours() is False


def test_trading_hours_weekend():
    """週六 10:00 → False。"""
    from app.tasks import is_trading_hours
    dt = datetime(2026, 5, 23, 10, 0, tzinfo=TZ)   # 2026-05-23 is Saturday
    with patch("app.tasks.datetime") as mock_dt:
        mock_dt.now.return_value = dt
        assert is_trading_hours() is False


def test_trading_hours_boundary_open():
    """09:00 整點 → True（邊界含）。"""
    from app.tasks import is_trading_hours
    dt = datetime(2026, 5, 25, 9, 0, tzinfo=TZ)
    with patch("app.tasks.datetime") as mock_dt:
        mock_dt.now.return_value = dt
        assert is_trading_hours() is True


def test_trading_hours_boundary_close():
    """13:30 整點 → True（邊界含）。"""
    from app.tasks import is_trading_hours
    dt = datetime(2026, 5, 25, 13, 30, tzinfo=TZ)
    with patch("app.tasks.datetime") as mock_dt:
        mock_dt.now.return_value = dt
        assert is_trading_hours() is True


# ── get_watch_symbols ────────────────────────────────────────────────────────

async def test_get_watch_symbols_dedup():
    """holdings 與 watchlist 有重複 symbol 時，回傳去重後的清單。"""
    from unittest.mock import AsyncMock, MagicMock
    from app.tasks import get_watch_symbols

    # DB execute 回傳兩次，模擬 UNION 結果（已去重）
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [("2330",), ("2317",), ("0050",)]
    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_result

    symbols = await get_watch_symbols(mock_db)

    assert symbols == ["2330", "2317", "0050"]
    mock_db.execute.assert_called_once()


async def test_get_watch_symbols_empty():
    """holdings 與 watchlist 都空時，回傳空 list。"""
    from unittest.mock import AsyncMock, MagicMock
    from app.tasks import get_watch_symbols

    mock_result = MagicMock()
    mock_result.fetchall.return_value = []
    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_result

    symbols = await get_watch_symbols(mock_db)

    assert symbols == []
```

- [ ] **Step 2：跑測試確認 FAIL（`app.tasks` 尚未建立）**

```bash
uv run pytest tests/test_tasks.py -v
```

預期：`ModuleNotFoundError: No module named 'app.tasks'`

- [ ] **Step 3：建立 `app/tasks.py`（TRACE 層級 + helper 函式）**

```python
"""app/tasks.py — ARQ cron task 函式與共用 helper。

所有 cron task 接收 ARQ 提供的 ctx: dict，從中取得 db_factory（async_sessionmaker）。
"""
import logging
import traceback as tb
from datetime import datetime, time

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from zoneinfo import ZoneInfo

# ── 自訂 TRACE 層級（level=5，低於 DEBUG=10）────────────────────────────────

TRACE = 5
logging.addLevelName(TRACE, "TRACE")


def _trace(self, msg, *args, **kwargs):  # type: ignore[override]
    if self.isEnabledFor(TRACE):
        self._log(TRACE, msg, args, **kwargs)


logging.Logger.trace = _trace  # type: ignore[attr-defined]

# ── logger ────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── helper 函式 ────────────────────────────────────────────────────────────────

_TZ = ZoneInfo("Asia/Taipei")


def is_trading_hours() -> bool:
    """台股交易時間：週一至週五 09:00–13:30（台北時間）。"""
    now = datetime.now(_TZ)
    if now.weekday() >= 5:  # 5=Sat, 6=Sun
        return False
    return time(9, 0) <= now.time() <= time(13, 30)


async def get_watch_symbols(db: AsyncSession) -> list[str]:
    """查詢 holdings ∪ watchlist 的 symbol 清單（SQL UNION 自動去重）。"""
    result = await db.execute(
        text("""
            SELECT symbol FROM trading.holdings
            UNION
            SELECT symbol FROM trading.watchlist
        """)
    )
    return [row[0] for row in result.fetchall()]
```

- [ ] **Step 4：跑測試，確認 helpers 全部通過**

```bash
uv run pytest tests/test_tasks.py -v
```

預期：全部 PASSED

- [ ] **Step 5：Commit**

```bash
git add app/tasks.py tests/test_tasks.py
git commit -m "feat: add tasks.py skeleton with TRACE level and helpers"
```

---

### Task 3：實作 `task_sync_instruments`

**Files:**
- Modify: `app/tasks.py`
- Modify: `tests/test_tasks.py`

- [ ] **Step 1：撰寫失敗測試**

在 `tests/test_tasks.py` 末尾加入：

```python
# ── task_sync_instruments ────────────────────────────────────────────────────

async def test_task_sync_instruments_calls_fbs(monkeypatch):
    """task_sync_instruments 呼叫 fbs_client.sync_instruments(db)。"""
    from unittest.mock import AsyncMock, MagicMock
    import app.tasks as tasks_module

    mock_sync = AsyncMock(return_value=5)
    monkeypatch.setattr(tasks_module.fbs_client, "sync_instruments", mock_sync)

    mock_db = AsyncMock()
    mock_db_factory = MagicMock()
    mock_db_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db_factory.return_value.__aexit__ = AsyncMock(return_value=False)

    ctx = {"db_factory": mock_db_factory}
    await tasks_module.task_sync_instruments(ctx)

    mock_sync.assert_called_once_with(mock_db)
```

- [ ] **Step 2：跑測試確認 FAIL**

```bash
uv run pytest tests/test_tasks.py::test_task_sync_instruments_calls_fbs -v
```

預期：FAIL（`task_sync_instruments` 尚未定義）

- [ ] **Step 3：在 `app/tasks.py` 加入 `task_sync_instruments`**

在 `get_watch_symbols` 函式後，加入以下 import 與 task（在 `app/tasks.py` 的 import 區段加入 `time as _time` alias，注意原本已有 `from datetime import datetime, time`，所以直接加在 helper 後面即可）：

先在 `app/tasks.py` 頂部 import 區加入：
```python
import time as _time

from app.services.fbs import fbs_client
```

再加入 task 函式（放在 `get_watch_symbols` 之後）：

```python
# ── cron tasks ────────────────────────────────────────────────────────────────


async def task_sync_instruments(ctx: dict) -> None:
    """每日 08:30：全量同步 market.instruments。"""
    t0 = _time.monotonic()
    logger.info("task_sync_instruments: started")
    async with ctx["db_factory"]() as db:
        try:
            n = await fbs_client.sync_instruments(db)
            elapsed = _time.monotonic() - t0
            logger.info("task_sync_instruments: done in %.1fs, wrote=%d instruments", elapsed, n)
        except Exception as e:
            logger.error("task_sync_instruments: unexpected error=%s", e)
            logger.trace(  # type: ignore[attr-defined]
                "task_sync_instruments detail: fbs_connected=%s\n%s",
                fbs_client.is_connected(), tb.format_exc(),
            )
            raise
```

- [ ] **Step 4：跑測試確認通過**

```bash
uv run pytest tests/test_tasks.py::test_task_sync_instruments_calls_fbs -v
```

預期：PASSED

- [ ] **Step 5：Ruff 檢查**

```bash
uv run ruff check app/tasks.py
```

預期：無輸出

---

### Task 4：實作 `task_sync_quotes`

**Files:**
- Modify: `app/tasks.py`
- Modify: `tests/test_tasks.py`

- [ ] **Step 1：撰寫失敗測試（3 個場景）**

在 `tests/test_tasks.py` 末尾加入：

```python
# ── task_sync_quotes ─────────────────────────────────────────────────────────

async def test_task_sync_quotes_skip_outside_hours(monkeypatch):
    """非交易時間 → 直接 return，不查 DB 也不呼叫 FBS。"""
    from unittest.mock import AsyncMock, MagicMock
    import app.tasks as tasks_module

    monkeypatch.setattr(tasks_module, "is_trading_hours", lambda: False)
    mock_db_factory = MagicMock()
    ctx = {"db_factory": mock_db_factory}

    await tasks_module.task_sync_quotes(ctx)

    mock_db_factory.assert_not_called()


async def test_task_sync_quotes_skip_market_closed(monkeypatch):
    """交易時間內但 isClose=True → 跳過，不同步。"""
    from unittest.mock import AsyncMock, MagicMock
    import app.tasks as tasks_module

    monkeypatch.setattr(tasks_module, "is_trading_hours", lambda: True)
    monkeypatch.setattr(
        tasks_module.fbs_client, "fetch_quote",
        AsyncMock(return_value={"isClose": True})
    )

    mock_db_factory = MagicMock()
    ctx = {"db_factory": mock_db_factory}

    await tasks_module.task_sync_quotes(ctx)

    mock_db_factory.assert_not_called()


async def test_task_sync_quotes_syncs_all_symbols(monkeypatch):
    """正常盤中：對每個 symbol 呼叫一次 sync_quote。"""
    from unittest.mock import AsyncMock, MagicMock, call
    import app.tasks as tasks_module

    monkeypatch.setattr(tasks_module, "is_trading_hours", lambda: True)
    monkeypatch.setattr(
        tasks_module.fbs_client, "fetch_quote",
        AsyncMock(return_value={"isClose": False})
    )
    monkeypatch.setattr(tasks_module, "get_watch_symbols", AsyncMock(return_value=["2330", "2317"]))

    mock_sync = AsyncMock(return_value=True)
    monkeypatch.setattr(tasks_module.fbs_client, "sync_quote", mock_sync)

    mock_db = AsyncMock()
    mock_db_factory = MagicMock()
    mock_db_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db_factory.return_value.__aexit__ = AsyncMock(return_value=False)
    ctx = {"db_factory": mock_db_factory}

    await tasks_module.task_sync_quotes(ctx)

    assert mock_sync.call_count == 2
    mock_sync.assert_any_call(mock_db, "2330")
    mock_sync.assert_any_call(mock_db, "2317")
```

- [ ] **Step 2：跑測試確認 FAIL**

```bash
uv run pytest tests/test_tasks.py::test_task_sync_quotes_skip_outside_hours \
              tests/test_tasks.py::test_task_sync_quotes_skip_market_closed \
              tests/test_tasks.py::test_task_sync_quotes_syncs_all_symbols -v
```

預期：全部 FAIL（`task_sync_quotes` 未定義）

- [ ] **Step 3：在 `app/tasks.py` 加入 `task_sync_quotes`**

在 `task_sync_instruments` 後加入：

```python
async def task_sync_quotes(ctx: dict) -> None:
    """每分鐘：同步 holdings∪watchlist 的即時報價（盤中限定）。"""
    if not is_trading_hours():
        logger.info("task_sync_quotes: outside trading hours, skipped")
        return

    # isClose probe：颱風假、國定假日等非交易日判斷
    probe = await fbs_client.fetch_quote("2330")
    if probe and probe.get("isClose"):
        logger.info("task_sync_quotes: market closed (isClose=True), skipped")
        return

    t0 = _time.monotonic()
    async with ctx["db_factory"]() as db:
        symbols = await get_watch_symbols(db)
        logger.info("task_sync_quotes: started, symbols=%d", len(symbols))
        ok = fail = 0
        for symbol in symbols:
            try:
                logger.trace(  # type: ignore[attr-defined]
                    "task_sync_quotes: FBS request symbol=%s method=intraday.quote", symbol
                )
                result = await fbs_client.sync_quote(db, symbol)
                if result:
                    logger.debug("task_sync_quotes: symbol=%s ok", symbol)
                    ok += 1
                else:
                    logger.warning("task_sync_quotes: symbol=%s failed (429 or empty)", symbol)
                    fail += 1
            except Exception as e:
                logger.error("task_sync_quotes: symbol=%s unexpected error=%s", symbol, e)
                logger.trace(  # type: ignore[attr-defined]
                    "task_sync_quotes detail: symbol=%s fbs_connected=%s\n%s",
                    symbol, fbs_client.is_connected(), tb.format_exc(),
                )
                fail += 1

    elapsed = _time.monotonic() - t0
    logger.info(
        "task_sync_quotes: done in %.1fs, success=%d, failed=%d", elapsed, ok, fail
    )
```

- [ ] **Step 4：跑測試確認通過**

```bash
uv run pytest tests/test_tasks.py::test_task_sync_quotes_skip_outside_hours \
              tests/test_tasks.py::test_task_sync_quotes_skip_market_closed \
              tests/test_tasks.py::test_task_sync_quotes_syncs_all_symbols -v
```

預期：全部 PASSED

---

### Task 5：實作 `task_sync_intraday_candles`

**Files:**
- Modify: `app/tasks.py`
- Modify: `tests/test_tasks.py`

- [ ] **Step 1：撰寫失敗測試**

在 `tests/test_tasks.py` 末尾加入：

```python
# ── task_sync_intraday_candles ────────────────────────────────────────────────

async def test_task_sync_intraday_candles_skip_outside_hours(monkeypatch):
    """非交易時間 → 跳過。"""
    from unittest.mock import MagicMock
    import app.tasks as tasks_module

    monkeypatch.setattr(tasks_module, "is_trading_hours", lambda: False)
    mock_db_factory = MagicMock()
    ctx = {"db_factory": mock_db_factory}

    await tasks_module.task_sync_intraday_candles(ctx)

    mock_db_factory.assert_not_called()


async def test_task_sync_intraday_candles_uses_tf5(monkeypatch):
    """盤中 → 以 timeframe='5' 呼叫 sync_intraday_candles。"""
    from unittest.mock import AsyncMock, MagicMock
    import app.tasks as tasks_module

    monkeypatch.setattr(tasks_module, "is_trading_hours", lambda: True)
    monkeypatch.setattr(tasks_module, "get_watch_symbols", AsyncMock(return_value=["2330"]))

    mock_sync = AsyncMock(return_value=12)
    monkeypatch.setattr(tasks_module.fbs_client, "sync_intraday_candles", mock_sync)

    mock_db = AsyncMock()
    mock_db_factory = MagicMock()
    mock_db_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db_factory.return_value.__aexit__ = AsyncMock(return_value=False)
    ctx = {"db_factory": mock_db_factory}

    await tasks_module.task_sync_intraday_candles(ctx)

    mock_sync.assert_called_once_with(mock_db, "2330", "5")
```

- [ ] **Step 2：跑測試確認 FAIL**

```bash
uv run pytest tests/test_tasks.py::test_task_sync_intraday_candles_skip_outside_hours \
              tests/test_tasks.py::test_task_sync_intraday_candles_uses_tf5 -v
```

預期：全部 FAIL

- [ ] **Step 3：在 `app/tasks.py` 加入 `task_sync_intraday_candles`**

```python
async def task_sync_intraday_candles(ctx: dict) -> None:
    """每 5 分鐘：同步 holdings∪watchlist 的今日盤中 5 分 K（盤中限定）。"""
    if not is_trading_hours():
        logger.info("task_sync_intraday_candles: outside trading hours, skipped")
        return

    t0 = _time.monotonic()
    async with ctx["db_factory"]() as db:
        symbols = await get_watch_symbols(db)
        logger.info(
            "task_sync_intraday_candles: started, symbols=%d, timeframe=5", len(symbols)
        )
        for symbol in symbols:
            try:
                logger.trace(  # type: ignore[attr-defined]
                    "task_sync_intraday_candles: FBS request symbol=%s tf=5", symbol
                )
                count = await fbs_client.sync_intraday_candles(db, symbol, "5")
                logger.debug(
                    "task_sync_intraday_candles: symbol=%s wrote=%d", symbol, count
                )
            except Exception as e:
                logger.error(
                    "task_sync_intraday_candles: symbol=%s unexpected error=%s", symbol, e
                )
                logger.trace(  # type: ignore[attr-defined]
                    "task_sync_intraday_candles detail: symbol=%s fbs_connected=%s\n%s",
                    symbol, fbs_client.is_connected(), tb.format_exc(),
                )

    elapsed = _time.monotonic() - t0
    logger.info("task_sync_intraday_candles: done in %.1fs, symbols=%d", elapsed, len(symbols))
```

- [ ] **Step 4：跑測試確認通過**

```bash
uv run pytest tests/test_tasks.py::test_task_sync_intraday_candles_skip_outside_hours \
              tests/test_tasks.py::test_task_sync_intraday_candles_uses_tf5 -v
```

預期：全部 PASSED

---

### Task 6：實作 `task_sync_historical_candles`

**Files:**
- Modify: `app/tasks.py`
- Modify: `tests/test_tasks.py`

- [ ] **Step 1：撰寫失敗測試（3 個場景）**

在 `tests/test_tasks.py` 末尾加入：

```python
# ── task_sync_historical_candles ──────────────────────────────────────────────

async def test_task_sync_historical_candles_initial_load(monkeypatch):
    """首次載入（DB 無資料）→ 補抓 2 年（可能分兩次查）。"""
    from datetime import date, timedelta
    from unittest.mock import AsyncMock, MagicMock, call
    import app.tasks as tasks_module

    monkeypatch.setattr(tasks_module, "get_watch_symbols", AsyncMock(return_value=["2330"]))

    mock_sync = AsyncMock(return_value=50)
    monkeypatch.setattr(tasks_module.fbs_client, "sync_historical_candles", mock_sync)

    # DB scalar 回傳 None → 首次載入
    mock_db = AsyncMock()
    mock_db.scalar.return_value = None
    mock_db_factory = MagicMock()
    mock_db_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db_factory.return_value.__aexit__ = AsyncMock(return_value=False)
    ctx = {"db_factory": mock_db_factory}

    await tasks_module.task_sync_historical_candles(ctx)

    # 2 年 = 730 天 > 365 天限制 → 一定拆兩次
    assert mock_sync.call_count == 2

    # 第一次 from_date 距今 ≥ 729 天
    first_call_from = mock_sync.call_args_list[0].args[3]
    assert (date.today() - first_call_from).days >= 729


async def test_task_sync_historical_candles_incremental(monkeypatch):
    """增量同步：last_date 為昨天 → 只查今天一筆。"""
    from datetime import date, timedelta
    from unittest.mock import AsyncMock, MagicMock
    import app.tasks as tasks_module

    monkeypatch.setattr(tasks_module, "get_watch_symbols", AsyncMock(return_value=["2330"]))

    mock_sync = AsyncMock(return_value=1)
    monkeypatch.setattr(tasks_module.fbs_client, "sync_historical_candles", mock_sync)

    yesterday = date.today() - timedelta(days=1)
    mock_db = AsyncMock()
    mock_db.scalar.return_value = yesterday  # last_date = 昨天
    mock_db_factory = MagicMock()
    mock_db_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db_factory.return_value.__aexit__ = AsyncMock(return_value=False)
    ctx = {"db_factory": mock_db_factory}

    await tasks_module.task_sync_historical_candles(ctx)

    # from_date = yesterday + 1 = today → 只呼叫一次
    assert mock_sync.call_count == 1
    call_args = mock_sync.call_args
    assert call_args.args[3] == date.today()
    assert call_args.args[4] == date.today()


async def test_task_sync_historical_candles_up_to_date(monkeypatch):
    """last_date = 今天 → 已是最新，不呼叫 sync。"""
    from datetime import date
    from unittest.mock import AsyncMock, MagicMock
    import app.tasks as tasks_module

    monkeypatch.setattr(tasks_module, "get_watch_symbols", AsyncMock(return_value=["2330"]))

    mock_sync = AsyncMock(return_value=0)
    monkeypatch.setattr(tasks_module.fbs_client, "sync_historical_candles", mock_sync)

    mock_db = AsyncMock()
    mock_db.scalar.return_value = date.today()  # last_date = 今天
    mock_db_factory = MagicMock()
    mock_db_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db_factory.return_value.__aexit__ = AsyncMock(return_value=False)
    ctx = {"db_factory": mock_db_factory}

    await tasks_module.task_sync_historical_candles(ctx)

    mock_sync.assert_not_called()
```

- [ ] **Step 2：跑測試確認 FAIL**

```bash
uv run pytest tests/test_tasks.py::test_task_sync_historical_candles_initial_load \
              tests/test_tasks.py::test_task_sync_historical_candles_incremental \
              tests/test_tasks.py::test_task_sync_historical_candles_up_to_date -v
```

預期：全部 FAIL

- [ ] **Step 3：在 `app/tasks.py` 加入 import 與 `task_sync_historical_candles`**

在 `app/tasks.py` 頂部 import 區加入（與現有 datetime import 合併）：
```python
from datetime import date, datetime, time, timedelta
```

在 `app/tasks.py` import 區加入：
```python
from sqlalchemy import func, select

from app.models.market import HistoricalCandle
```

然後加入 task 函式（放在 `task_sync_intraday_candles` 之後）：

```python
async def task_sync_historical_candles(ctx: dict) -> None:
    """每日 14:00：增量同步日 K（新 symbol 補 2 年）。"""
    t0 = _time.monotonic()
    async with ctx["db_factory"]() as db:
        symbols = await get_watch_symbols(db)
        logger.info("task_sync_historical_candles: started, symbols=%d", len(symbols))

        for symbol in symbols:
            try:
                last_date: date | None = await db.scalar(
                    select(func.max(HistoricalCandle.date)).where(
                        HistoricalCandle.symbol == symbol,
                        HistoricalCandle.timeframe == "D",
                    )
                )

                to_date = date.today()

                if last_date is None:
                    # 首次載入：補抓 2 年
                    from_date = to_date - timedelta(days=730)
                    logger.info(
                        "task_sync_historical_candles: %s initial load from=%s",
                        symbol, from_date,
                    )
                else:
                    from_date = last_date + timedelta(days=1)
                    if from_date > to_date:
                        logger.debug(
                            "task_sync_historical_candles: %s already up-to-date", symbol
                        )
                        continue

                # FBS 限制單次最多 1 年，超過時拆兩次查詢
                if (to_date - from_date).days > 365:
                    mid = from_date + timedelta(days=365)
                    count1 = await fbs_client.sync_historical_candles(
                        db, symbol, "D", from_date, mid
                    )
                    count2 = await fbs_client.sync_historical_candles(
                        db, symbol, "D", mid + timedelta(days=1), to_date
                    )
                    count = count1 + count2
                else:
                    count = await fbs_client.sync_historical_candles(
                        db, symbol, "D", from_date, to_date
                    )

                logger.info(
                    "task_sync_historical_candles: %s from=%s to=%s wrote=%d",
                    symbol, from_date, to_date, count,
                )

            except Exception as e:
                logger.error(
                    "task_sync_historical_candles: symbol=%s unexpected error=%s", symbol, e
                )
                logger.trace(  # type: ignore[attr-defined]
                    "task_sync_historical_candles detail: symbol=%s fbs_connected=%s\n%s",
                    symbol, fbs_client.is_connected(), tb.format_exc(),
                )

    elapsed = _time.monotonic() - t0
    logger.info("task_sync_historical_candles: done in %.1fs", elapsed)
```

- [ ] **Step 4：跑測試確認通過**

```bash
uv run pytest tests/test_tasks.py::test_task_sync_historical_candles_initial_load \
              tests/test_tasks.py::test_task_sync_historical_candles_incremental \
              tests/test_tasks.py::test_task_sync_historical_candles_up_to_date -v
```

預期：全部 PASSED

---

### Task 7：實作 `task_clear_intraday_candles`

**Files:**
- Modify: `app/tasks.py`
- Modify: `tests/test_tasks.py`

- [ ] **Step 1：撰寫失敗測試**

在 `tests/test_tasks.py` 末尾加入：

```python
# ── task_clear_intraday_candles ───────────────────────────────────────────────

async def test_task_clear_intraday_candles_executes_delete(monkeypatch):
    """task_clear_intraday_candles 呼叫 DELETE FROM market.intraday_candles 並 commit。"""
    from unittest.mock import AsyncMock, MagicMock
    import app.tasks as tasks_module

    mock_db = AsyncMock()
    mock_db_factory = MagicMock()
    mock_db_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db_factory.return_value.__aexit__ = AsyncMock(return_value=False)
    ctx = {"db_factory": mock_db_factory}

    await tasks_module.task_clear_intraday_candles(ctx)

    mock_db.execute.assert_called_once()
    # 確認 SQL 包含 DELETE
    executed_sql = str(mock_db.execute.call_args.args[0])
    assert "DELETE" in executed_sql.upper() or "delete" in executed_sql
    mock_db.commit.assert_called_once()
```

- [ ] **Step 2：跑測試確認 FAIL**

```bash
uv run pytest tests/test_tasks.py::test_task_clear_intraday_candles_executes_delete -v
```

預期：FAIL

- [ ] **Step 3：在 `app/tasks.py` 加入 `task_clear_intraday_candles`**

```python
async def task_clear_intraday_candles(ctx: dict) -> None:
    """每日 14:30：清空全表 market.intraday_candles（每日重建設計）。"""
    async with ctx["db_factory"]() as db:
        await db.execute(text("DELETE FROM market.intraday_candles"))
        await db.commit()
    logger.info("task_clear_intraday_candles: table cleared")
```

- [ ] **Step 4：跑測試確認通過**

```bash
uv run pytest tests/test_tasks.py::test_task_clear_intraday_candles_executes_delete -v
```

預期：PASSED

- [ ] **Step 5：跑全部 tasks 測試**

```bash
uv run pytest tests/test_tasks.py -v
```

預期：全部 PASSED

- [ ] **Step 6：Ruff 檢查**

```bash
uv run ruff check app/tasks.py
```

預期：無輸出

- [ ] **Step 7：Commit**

```bash
git add app/tasks.py tests/test_tasks.py
git commit -m "feat: implement all 5 cron tasks in tasks.py"
```

---

### Task 8：建立 `app/worker.py`（startup / shutdown / WorkerSettings）

**Files:**
- Create: `app/worker.py`
- Modify: `tests/test_tasks.py`

- [ ] **Step 1：撰寫 startup / shutdown 的測試**

在 `tests/test_tasks.py` 末尾加入：

```python
# ── worker startup / shutdown ─────────────────────────────────────────────────

async def test_startup_sets_db_factory(monkeypatch):
    """startup() 成功時 ctx['db_factory'] 被設定。"""
    from unittest.mock import MagicMock, patch
    from app.worker import startup

    monkeypatch.setattr("app.worker.fbs_client.connect", MagicMock())

    ctx: dict = {}
    with patch("app.worker.create_async_engine"), \
         patch("app.worker.async_sessionmaker") as mock_sm:
        mock_sm.return_value = "fake_factory"
        await startup(ctx)

    assert ctx["db_factory"] == "fake_factory"
    assert "engine" in ctx


async def test_startup_raises_on_fbs_failure(monkeypatch):
    """startup() 時 FBS 登入失敗 → 拋 RuntimeError（讓 ARQ 感知）。"""
    import pytest
    from unittest.mock import MagicMock
    from app.worker import startup

    monkeypatch.setattr(
        "app.worker.fbs_client.connect",
        MagicMock(side_effect=RuntimeError("FBS login failed"))
    )

    ctx: dict = {}
    with pytest.raises(RuntimeError, match="FBS login failed"):
        await startup(ctx)


async def test_shutdown_calls_disconnect(monkeypatch):
    """shutdown() 呼叫 fbs_client.disconnect()。"""
    from unittest.mock import AsyncMock, MagicMock
    from app.worker import shutdown

    mock_disconnect = MagicMock()
    monkeypatch.setattr("app.worker.fbs_client.disconnect", mock_disconnect)

    mock_engine = MagicMock()
    mock_engine.dispose = AsyncMock()
    ctx = {"engine": mock_engine}

    await shutdown(ctx)

    mock_disconnect.assert_called_once()
    mock_engine.dispose.assert_called_once()
```

- [ ] **Step 2：跑測試確認 FAIL**

```bash
uv run pytest tests/test_tasks.py::test_startup_sets_db_factory \
              tests/test_tasks.py::test_startup_raises_on_fbs_failure \
              tests/test_tasks.py::test_shutdown_calls_disconnect -v
```

預期：FAIL（`app.worker` 尚未建立）

- [ ] **Step 3：建立 `app/worker.py`**

```python
"""app/worker.py — ARQ WorkerSettings + startup/shutdown hooks。

執行方式（NAS DSM SSH）：
    uv run arq app.worker.WorkerSettings
"""
import logging

from arq import cron
from arq.connections import RedisSettings
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.services.fbs import fbs_client
from app.tasks import (
    task_clear_intraday_candles,
    task_sync_historical_candles,
    task_sync_instruments,
    task_sync_intraday_candles,
    task_sync_quotes,
)

logger = logging.getLogger(__name__)


async def startup(ctx: dict) -> None:
    """Worker 啟動時：登入 FBS + 建立 DB engine。"""
    try:
        fbs_client.connect()
        logger.info("Worker started: FBS connected")
    except RuntimeError as e:
        logger.critical("Worker startup failed: FBS login error - %s", e)
        raise  # 讓 ARQ 感知，終止 Worker

    engine = create_async_engine(settings.database_url, pool_size=5)
    ctx["db_factory"] = async_sessionmaker(engine, expire_on_commit=False)
    ctx["engine"] = engine
    logger.info("Worker startup complete")


async def shutdown(ctx: dict) -> None:
    """Worker 關閉時：清理資源。"""
    fbs_client.disconnect()
    if "engine" in ctx:
        await ctx["engine"].dispose()
    logger.info("Worker shutdown complete")


class WorkerSettings:
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    on_startup = startup
    on_shutdown = shutdown
    cron_jobs = [
        cron(task_sync_instruments, hour=8, minute=30, run_at_startup=False),
        cron(task_sync_quotes, minute=set(range(60))),
        cron(task_sync_intraday_candles, minute={0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55}),
        cron(task_sync_historical_candles, hour=14, minute=0, run_at_startup=False),
        cron(task_clear_intraday_candles, hour=14, minute=30, run_at_startup=False),
    ]
    max_jobs = 10
    job_timeout = 300  # 5 分鐘，避免 task 卡住
```

- [ ] **Step 4：跑測試確認通過**

```bash
uv run pytest tests/test_tasks.py::test_startup_sets_db_factory \
              tests/test_tasks.py::test_startup_raises_on_fbs_failure \
              tests/test_tasks.py::test_shutdown_calls_disconnect -v
```

預期：全部 PASSED

- [ ] **Step 5：Ruff 檢查**

```bash
uv run ruff check app/worker.py app/tasks.py
```

預期：無輸出

---

### Task 9：全量測試 + Commit

**Files:**
- Modify: None（驗證用）

- [ ] **Step 1：跑全部測試**

```bash
uv run pytest -v
```

預期：全部 PASSED（包含 `test_fbs.py` + `test_tasks.py`）

- [ ] **Step 2：確認 worker import 無誤**

```bash
uv run python -c "from app.worker import WorkerSettings; print('OK')"
```

預期：`OK`（無 ImportError）

- [ ] **Step 3：Commit**

```bash
git add app/worker.py tests/test_tasks.py
git commit -m "feat: add worker.py with WorkerSettings, startup/shutdown hooks"
```

---

### Task 10：手動啟動驗證（NAS DSM SSH）

**Files:**
- None（驗證用）

> 此 Task 需在 NAS DSM SSH 執行（Windows 無法啟動 ARQ Worker）。

- [ ] **Step 1：設定環境變數**

```bash
export PATH="/volume1/web/codeserver/.tools:$PATH"
export UV_CACHE_DIR=/volume1/web/codeserver/.uv-cache
export UV_DATA_DIR=/volume1/web/codeserver/.uv-data
export UV_PYTHON_INSTALL_DIR=/volume1/web/codeserver/.uv-python
cd /volume1/web/codeserver/tw_stock_trade
```

- [ ] **Step 2：確認 Redis 容器正在執行**

```bash
sudo docker ps | grep Redis
```

預期：看到 `Redis` container，狀態 `Up`，port `0.0.0.0:6379->6379/tcp`

- [ ] **Step 3：啟動 Worker（Ctrl+C 停止）**

```bash
uv run arq app.worker.WorkerSettings
```

預期日誌（前幾行）：
```
2026-05-24 XX:XX:XX [INFO    ] app.services.fbs: FBS connected, account: ...
2026-05-24 XX:XX:XX [INFO    ] app.worker: Worker started: FBS connected
2026-05-24 XX:XX:XX [INFO    ] app.worker: Worker startup complete
```

- [ ] **Step 4：等待下一個整分鐘，觀察 `task_sync_quotes` 是否觸發**

盤中時間（09:00–13:30）預期看到：
```
2026-05-24 XX:XX:XX [INFO    ] app.tasks: task_sync_quotes: started, symbols=N
2026-05-24 XX:XX:XX [INFO    ] app.tasks: task_sync_quotes: done in X.Xs, success=N, failed=0
```

盤外時間預期看到：
```
2026-05-24 XX:XX:XX [INFO    ] app.tasks: task_sync_quotes: outside trading hours, skipped
```

- [ ] **Step 5：Ctrl+C 停止 Worker，確認 shutdown log**

```
2026-05-24 XX:XX:XX [INFO    ] app.services.fbs: FBS disconnected
2026-05-24 XX:XX:XX [INFO    ] app.worker: Worker shutdown complete
```

- [ ] **Step 6：最終 Commit（如有任何調整）**

```bash
git add -A
git commit -m "feat: Step 5 ARQ Worker complete - tasks.py + worker.py"
```
