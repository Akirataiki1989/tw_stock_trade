# app/worker.py

## 用途

ARQ Worker 的設定進入點。負責初始化所有全域資源，包含資料庫連接、FBS SDK、以及 LangGraph 的持久化後端。

## startup(ctx)

```python
async def startup(ctx: dict) -> None
```

1. **FBS SDK**：`fbs_client.connect()` 登入。
2. **Database**：建立 `async_engine` 並存入 `ctx["db_factory"]`。
3. **AI Checkpointer**：初始化 `AsyncPostgresSaver` (短期記憶/Checkpoints)，手動進入其 `_cm` 非同步上下文。
4. **AI Vector Store**：
   - 初始化 `GoogleGenerativeAIEmbeddings`。
   - 初始化 `AsyncPostgresStore` (長期記憶)，手動進入其 `_cm` 非同步上下文。
5. **Graph**：呼叫 `build_graph` 並編譯後存入 `ctx["agent"]`。

## shutdown(ctx)

```python
async def shutdown(ctx: dict) -> None
```

1. `fbs_client.disconnect()`。
2. 清理 AI 資源：依序執行 `store._cm.__aexit__` 與 `checkpointer._cm.__aexit__`。
3. `await ctx["engine"].dispose()`。

## WorkerSettings

| 屬性 | 值 |
|------|---|
| `redis_settings` | `RedisSettings.from_dsn(settings.redis_url)` |
| `on_startup` | `startup` |
| `on_shutdown` | `shutdown` |
| `max_jobs` | `10` |
| `job_timeout` | `300`（秒） |
| `cron_jobs` | **12 個**（見下方列表） |

## Cron Jobs 列表

1. `task_sync_instruments` (08:30)
2. `task_sync_us_market` (08:30)
3. `task_sync_quotes` (每分鐘)
4. `task_maybe_run_ai` (每分鐘)
5. `task_sync_intraday_candles` (每 5 分鐘)
6. `task_sync_historical_candles` (14:00)
7. `task_clear_intraday_candles` (14:30)
8. `task_sync_institutional_flows` (16:00)
9. `task_sync_margin_trading` (16:05)
10. `task_update_trade_outcomes` (17:00)
11. `task_cleanup_checkpoints` (03:00)
12. `task_prune_store_memories` (每週日 02:00)

## 啟動指令

```bash
uv run arq app.worker.WorkerSettings
```

## 依賴

- `app.core.config.settings`
- `app.services.fbs.fbs_client`
- `app.agent.memory` (Checkpointer / Store)
- `app.agent.graph` (build_graph)
- `app.tasks` (所有 task 函式)
