# 目錄樹索引

> 點擊連結查看該檔案的詳細 CodeMap。`__init__.py` 省略（空白或僅含 import）。
> 路徑對應 `docs/codemap/` 下的同名 `.md`。

## app/

| 原始碼路徑 | CodeMap | 簡介 |
|-----------|---------|------|
| `app/database.py` | [database.md](app/database.md) | `engine`、`AsyncSessionLocal`、`get_db()` dependency |
| `app/core/config.py` | [config.md](app/core/config.md) | `Settings`（pydantic-settings），讀 `.env` |
| `app/models/base.py` | [base.md](app/models/base.md) | `Base`（DeclarativeBase），所有 model 的基底 |
| `app/models/user.py` | [user.md](app/models/user.md) | `User`，`public.users`，fastapi-users 管理 |
| `app/models/market.py` | [market.md](app/models/market.md) | `Instrument` / `MarketQuote` / `IntradayCandle` / `HistoricalCandle` |
| `app/models/portfolio.py` | [portfolio.md](app/models/portfolio.md) | `Portfolio` / `Holding` / `Trade` / `AiDecision` / `DailyPerformance` / `Watchlist` |
| `app/main.py` | — | FastAPI 進入點，lifespan + auth / users router 掛載 |
| `app/users.py` | — | UserManager、JWTStrategy、auth_backend、fastapi_users、current_active_user |
| `app/schemas/user.py` | — | UserRead / UserCreate / UserUpdate（fastapi-users schemas） |
| `app/schemas/portfolio.py` | — | PortfolioRead / HoldingRead / TradeRead / PerformanceRead / PortfolioStats |
| `app/schemas/market.py` | — | InstrumentRead / QuoteRead / CandleItem / CandleResponse |
| `app/api/ai.py` | [ai.md](app/api/ai.md) | POST /ai/analyze（觸發）、GET /ai/decisions（歷史、單筆） |
| `app/api/ws.py` | [ws.md](app/api/ws.md) | WS /ws/quotes（報價）、WS /ws/ai-stream（AI 進度） |
| `app/services/portfolio.py` | — | Portfolio / Holding / Trade / Performance 查詢；stats 聚合計算 |
| `app/services/market.py` | — | Quote / Candle 查詢（自動路由歷史/盤中）；Instrument 搜尋 |
| `app/services/fbs.py` | [fbs.md](app/services/fbs.md) | `FbsClient` singleton：connect/disconnect/is_connected；sync_instruments/quote/intraday_candles/historical_candles；fetch_quote/candles |
| `app/services/pubsub.py` | [pubsub.md](app/services/pubsub.md) | Redis Pub/Sub 封裝（報價與 AI 事件發佈） |
| `app/services/external_data.py` | — | yfinance + TWSE API fetch/parse/upsert；clean_number()、parse_institutional_row()、parse_margin_row_full() 等純函式 |

| `app/tasks.py` | [tasks.md](app/tasks.md) | TRACE 層級、is_trading_hours()、get_watch_symbols()、13 個 cron tasks + task_run_ai_on_demand |
| `app/worker.py` | [worker.md](app/worker.md) | ARQ WorkerSettings + startup/shutdown hooks（含 Redis pub/sub client） |
| `app/api/portfolio.py` | — | GET /api/v1/portfolio, /holdings, /trades, /performance, /stats；POST /portfolio/init |
| `app/api/market.py` | — | GET /api/v1/market/quote/{symbol}, /candles/{symbol}, /search |
| `app/agent/state.py` | [agent/state.md](app/agent/state.md) | DebateState TypedDict |
| `app/agent/memory.py` | [agent/memory.md](app/agent/memory.md) | AsyncPostgresSaver / AsyncPostgresStore 初始化 |
| `app/agent/prompts.py` | [agent/prompts.md](app/agent/prompts.md) | 各分析師 system prompt |
| `app/agent/nodes.py` | [agent/nodes.md](app/agent/nodes.md) | 各 node 函式（analyst / bull / bear / risk / decide / persist） |
| `app/agent/graph.py` | [agent/graph.md](app/agent/graph.md) | build_graph()、熔斷機制、conditional edges |

## alembic/

| 原始碼路徑 | CodeMap | 簡介 |
|-----------|---------|------|
| `alembic/env.py` | [env.md](alembic/env.md) | async migration 設定，`include_schemas=True` |
| `alembic/versions/0001_initial_schema.py` | [0001.md](alembic/versions/0001.md) | 初始 migration：建立 3 schema × 9 資料表 |
| `alembic/versions/0002_add_watchlist.py` | [0002.md](alembic/versions/0002.md) | migration 0002：新增 `trading.watchlist` 表 |
| `alembic/versions/0003_add_external_data_tables.py` | [0003.md](alembic/versions/0003.md) | migration 0003：新增 `market.us_market_daily`、`institutional_flows`、`margin_trading` |

## scripts/

| 路徑 | 說明 |
|------|------|
| `scripts/start_api.sh` | FastAPI server 開機啟動腳本（Task Scheduler `tw-stock-api`） |
| `scripts/start_worker.sh` | ARQ Worker 開機啟動腳本（Task Scheduler `tw-stock-worker`） |
| `scripts/start_tunnel.sh` | Cloudflare Tunnel 開機啟動腳本（Task Scheduler `tw-stock-tunnel`） |
