# ARQ Worker Design Spec

> 建立日期：2026-05-24  
> 狀態：已核准，待實作

---

## 背景

ARQ Worker 是市場資料同步的核心引擎，運行於 NAS DSM，使用 Redis 作為 task queue。  
Worker 啟動時透過 `fbs_client.connect()` 登入 FBS SDK，並依排程定時執行市場資料同步任務。

---

## 範圍

本次實作包含：
1. Redis Docker container 建立（Synology Container Manager）
2. `app/tasks.py`（所有 cron task 函式）
3. `app/worker.py`（WorkerSettings + startup/shutdown hooks）

---

## 一、Redis 設定

| 設定項 | 值 |
|--------|---|
| Image | `redis:7-alpine` |
| Container 名稱 | `Redis` |
| Port mapping | `6379:6379`（host:container） |
| 重啟政策 | Always |
| Volume | 不需要（ARQ 只用 Redis 做 task queue，重啟資料清空無影響） |

`.env` 的 `redis_url = "redis://localhost:6379"` 預設值直接可用，不需修改。

---

## 二、檔案結構

```
app/worker.py   ← ARQ WorkerSettings + startup/shutdown hooks（僅設定，無業務邏輯）
app/tasks.py    ← 所有 cron task 函式 + 共用 helper
```

---

## 三、Logging 策略

### 自訂 TRACE 層級

Python 無內建 TRACE，需在 `app/tasks.py` 頂部自訂：

```python
import logging
import traceback as tb

TRACE = 5
logging.addLevelName(TRACE, "TRACE")

def _trace(self, msg, *args, **kwargs):
    if self.isEnabledFor(TRACE):
        self._log(TRACE, msg, args, **kwargs)

logging.Logger.trace = _trace
```

### 完整層級定義

| 層級 | Level | 用途 |
|------|-------|------|
| `CRITICAL` | 50 | 致命錯誤：FBS 登入失敗、DB 完全無法連線 → Worker 必須停止 |
| `ERROR` | 40 | 嚴重但可繼續：DB 寫入失敗、FBS 非預期例外 |
| `WARNING` | 30 | 預期內異常：429、空資料、單支 symbol 失敗 |
| `INFO` | 20 | 正常流程：task 開始/結束摘要、休市跳過、Worker 啟動 |
| `DEBUG` | 10 | 除錯：每支股票成功細節 |
| `TRACE` | 5 | 最細：SDK 原始 request/response；錯誤時的完整 traceback + 狀態 |

### Log 格式

```python
logging.basicConfig(
    level=logging.INFO,   # 生產環境；除錯時改 TRACE
    format="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
```

### 錯誤發生時 TRACE 用法

```python
except Exception as e:
    logger.error("task_sync_quotes: symbol=%s unexpected error=%s", symbol, e)
    logger.trace(                                          # type: ignore[attr-defined]
        "task_sync_quotes detail: symbol=%s fbs_connected=%s db_ok=%s\n%s",
        symbol, fbs_client.is_connected(), db is not None, tb.format_exc(),
    )
```

---

## 四、共用 Helper

### `is_trading_hours()`

```python
from datetime import time
from zoneinfo import ZoneInfo

def is_trading_hours() -> bool:
    """台股交易時間：週一至週五 09:00–13:30（台北時間）。"""
    now = datetime.now(ZoneInfo("Asia/Taipei"))
    if now.weekday() >= 5:
        return False
    return time(9, 0) <= now.time() <= time(13, 30)
```

### `get_watch_symbols(db)`

查詢 holdings ∪ watchlist 的 symbol 清單（自動去重）：

```python
async def get_watch_symbols(db: AsyncSession) -> list[str]:
    result = await db.execute(
        text("""
            SELECT symbol FROM trading.holdings
            UNION
            SELECT symbol FROM trading.watchlist
        """)
    )
    return [row[0] for row in result.fetchall()]
```

---

## 五、Task 設計

### 排程總覽

| Task | 觸發時間 | 說明 |
|------|---------|------|
| `task_sync_instruments` | 每日 08:30 | 全量同步 market.instruments |
| `task_sync_quotes` | 每分鐘 | 盤中同步 holdings∪watchlist 報價 |
| `task_sync_intraday_candles` | 每 5 分鐘 | 盤中同步 5 分 K |
| `task_sync_historical_candles` | 每日 14:00 | 增量同步日 K（2 年初始） |
| `task_clear_intraday_candles` | 每日 14:30 | 清空全表 intraday_candles |

---

### `task_sync_instruments`

```
[INFO] task_sync_instruments: started
  → fbs_client.sync_instruments(db)
[INFO] task_sync_instruments: done in {t}s, wrote={n} instruments
```

---

### `task_sync_quotes`

```
is_trading_hours() = False → [INFO] outside trading hours, skipped → return

fetch_quote("2330") → isClose=True → [INFO] market closed, skipped → return

symbols = get_watch_symbols(db)
[INFO] task_sync_quotes: started, symbols={n}

for symbol in symbols:
    [TRACE] FBS request: symbol={symbol} method=intraday.quote
    result = await fbs_client.sync_quote(db, symbol)
    if result:
        [DEBUG] task_sync_quotes: symbol={symbol} ok
    else:
        [WARNING] task_sync_quotes: symbol={symbol} failed (429 or empty)

[INFO] task_sync_quotes: done in {t}s, success={ok}, failed={fail}
```

---

### `task_sync_intraday_candles`

```
is_trading_hours() = False → [INFO] outside trading hours, skipped → return

symbols = get_watch_symbols(db)
[INFO] task_sync_intraday_candles: started, symbols={n}, timeframe=5

for symbol in symbols:
    [TRACE] FBS request: symbol={symbol} method=intraday.candles tf=5
    count = await fbs_client.sync_intraday_candles(db, symbol, "5")
    [DEBUG] task_sync_intraday_candles: symbol={symbol} wrote={count}

[INFO] task_sync_intraday_candles: done in {t}s, symbols={n}
```

---

### `task_sync_historical_candles`

增量邏輯：

```python
last_date = await db.scalar(
    select(func.max(HistoricalCandle.date))
    .where(HistoricalCandle.symbol == symbol, HistoricalCandle.timeframe == "D")
)

if last_date is None:
    # 首次載入：補抓 2 年
    from_date = date.today() - timedelta(days=730)
    logger.info("task_sync_historical_candles: %s initial load from=%s", symbol, from_date)
else:
    from_date = last_date + timedelta(days=1)
    if from_date > date.today():
        logger.debug("task_sync_historical_candles: %s already up-to-date", symbol)
        continue

# FBS 限制單次最多 1 年，超過分兩次查
to_date = date.today()
if (to_date - from_date).days > 365:
    mid = from_date + timedelta(days=365)
    count1 = await fbs_client.sync_historical_candles(db, symbol, "D", from_date, mid)
    count2 = await fbs_client.sync_historical_candles(db, symbol, "D", mid + timedelta(days=1), to_date)
    count = count1 + count2
else:
    count = await fbs_client.sync_historical_candles(db, symbol, "D", from_date, to_date)

logger.info(
    "task_sync_historical_candles: %s from=%s to=%s wrote=%d",
    symbol, from_date, to_date, count,
)
```

---

### `task_clear_intraday_candles`

```python
await db.execute(text("DELETE FROM market.intraday_candles"))
await db.commit()
logger.info("task_clear_intraday_candles: table cleared")
```

---

## 六、WorkerSettings

```python
from arq import cron
from arq.connections import RedisSettings

class WorkerSettings:
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    on_startup = startup
    on_shutdown = shutdown
    cron_jobs = [
        cron(task_sync_instruments,        hour=8,  minute=30, run_at_startup=False),
        cron(task_sync_quotes,             minute=set(range(60))),
        cron(task_sync_intraday_candles,   minute={0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55}),
        cron(task_sync_historical_candles, hour=14, minute=0,  run_at_startup=False),
        cron(task_clear_intraday_candles,  hour=14, minute=30, run_at_startup=False),
    ]
    max_jobs = 10
    job_timeout = 300   # 5 分鐘，避免 task 卡住
```

---

## 七、startup / shutdown Hooks

```python
async def startup(ctx: dict) -> None:
    """Worker 啟動時：登入 FBS + 建立 DB engine。"""
    try:
        fbs_client.connect()
        logger.info("Worker started: FBS connected")
    except RuntimeError as e:
        logger.critical("Worker startup failed: FBS login error - %s", e)
        raise   # 讓 ARQ 感知，終止 Worker

    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
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
```

---

## 八、啟動指令

```bash
# NAS DSM SSH（手動測試）
export PATH="/volume1/web/codeserver/.tools:$PATH"
export UV_CACHE_DIR=/volume1/web/codeserver/.uv-cache
cd /volume1/web/codeserver/tw_stock_trade
uv run arq app.worker.WorkerSettings
```

Step 8 用 Synology Task Scheduler 設定開機自動啟動。

---

## 九、不在本次範圍

- Synology Task Scheduler 設定（Step 8）
- WebSocket 即時推送（Step 7）
- 週 K / 月 K 歷史資料（日 K 優先，後續擴充）
