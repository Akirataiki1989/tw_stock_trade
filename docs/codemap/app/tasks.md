# app/tasks.py

## 用途

ARQ cron task 函式與共用 helper。所有排程任務接收 ARQ 提供的 `ctx: dict`，從中取得 `db_factory`（`async_sessionmaker`）。

## 自訂 TRACE 層級

```python
TRACE = 5
logging.addLevelName(TRACE, "TRACE")
logging.Logger.trace = _trace  # level < DEBUG，記錄 SDK raw request + 錯誤 traceback
```

## Helper 函式

| 函式 | 簽名 | 說明 |
|------|------|------|
| `is_trading_hours()` | `() -> bool` | 週一至五 09:00–13:30 台北時間 |
| `get_watch_symbols(db)` | `(AsyncSession) -> list[str]` | SQL UNION holdings + watchlist，自動去重 |

## Cron Tasks

| 函式 | 排程 | 說明 |
|------|------|------|
| `task_sync_instruments(ctx)` | 每日 08:30 | 全量 upsert market.instruments |
| `task_sync_quotes(ctx)` | 每分鐘 | 盤中才執行；isClose probe 跳過假日 |
| `task_sync_intraday_candles(ctx)` | 每 5 分鐘 | 盤中；timeframe="5" |
| `task_sync_historical_candles(ctx)` | 每日 14:00 | 增量；首次補 2 年；FBS 限 1 年/次拆兩次 |
| `task_clear_intraday_candles(ctx)` | 每日 14:30 | DELETE FROM market.intraday_candles |

## 依賴

- `app.services.fbs.fbs_client`（全域 singleton）
- `app.models.market.HistoricalCandle`（歷史 K 增量查詢）
- `sqlalchemy.text`（UNION 查詢、DELETE）
