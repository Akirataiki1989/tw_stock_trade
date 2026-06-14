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
| `task_sync_us_market(ctx)` | 每日 08:30 | 拉取美股指數昨收 (Step 5.5) |
| `task_sync_institutional_flows(ctx)` | 每日 16:00 | 拉取三大法人買賣超 (Step 5.5) |
| `task_sync_margin_trading(ctx)` | 每日 16:05 | 拉取融資融券餘額 (Step 5.5) |
| `task_maybe_run_ai(ctx)` | 每分鐘 | 檢查 `ai_interval_minutes` 並觸發 LangGraph Agent 決策 |
| `task_update_trade_outcomes(ctx)` | 每日 17:00 | 更新過去 1/3/5 日決策的 `outcome_score` |
| `task_cleanup_checkpoints(ctx)` | 每日 03:00 | 刪除過期的 LangGraph checkpoints (短期記憶) |
| `task_prune_store_memories(ctx)` | 每週日 02:00 | 刪除單一標的過量的向量記憶 (長期記憶) |

## 依賴

- `app.services.fbs.fbs_client`（全域 singleton）
- `app.models.market.HistoricalCandle`（歷史 K 增量查詢）
- `app.agent.graph.build_graph`（執行 AI 決策）
- `sqlalchemy.text`（UNION 查詢、DELETE）
