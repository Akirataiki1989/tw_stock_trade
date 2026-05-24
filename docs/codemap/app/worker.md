# app/worker.py

## 用途

ARQ Worker 的設定進入點。只包含 `WorkerSettings`、`startup`、`shutdown`，無業務邏輯。

## startup(ctx)

```python
async def startup(ctx: dict) -> None
```

1. `fbs_client.connect()` — 登入 FBS SDK；失敗 → `logger.critical` + `raise`（讓 ARQ 終止）
2. `create_async_engine(settings.database_url, pool_size=5)`
3. 將 `async_sessionmaker` 存入 `ctx["db_factory"]`，`engine` 存入 `ctx["engine"]`

## shutdown(ctx)

```python
async def shutdown(ctx: dict) -> None
```

1. `fbs_client.disconnect()`
2. `await ctx["engine"].dispose()`

## WorkerSettings

| 屬性 | 值 |
|------|---|
| `redis_settings` | `RedisSettings.from_dsn(settings.redis_url)` |
| `on_startup` | `startup` |
| `on_shutdown` | `shutdown` |
| `max_jobs` | `10` |
| `job_timeout` | `300`（秒） |
| `cron_jobs` | 5 個（見 tasks.py codemap） |

## 啟動指令

```bash
uv run arq app.worker.WorkerSettings
```

## 依賴

- `app.core.config.settings`
- `app.services.fbs.fbs_client`
- `app.tasks`（5 個 task 函式）
