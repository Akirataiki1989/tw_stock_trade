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
| `app/schemas/ai.py` | — | AnalyzeRequest / AnalyzeResponse / AiDecisionRead |
| `app/services/portfolio.py` | — | Portfolio / Holding / Trade / Performance 查詢；stats 聚合計算 |
| `app/services/market.py` | — | Quote / Candle 查詢（自動路由歷史/盤中）；Instrument 搜尋 |
| `app/services/fbs.py` | [fbs.md](app/services/fbs.md) | `FbsClient` singleton：connect/disconnect/is_connected；sync_instruments/quote/intraday_candles/historical_candles；fetch_quote/candles |
| `app/services/external_data.py` | — | yfinance + TWSE API fetch/parse/upsert；clean_number()、parse_institutional_row()、parse_margin_row_full() 等純函式 |
| `app/tasks.py` | [tasks.md](app/tasks.md) | TRACE 層級、is_trading_hours()、get_watch_symbols()、8 個 cron tasks |
| `app/worker.py` | [worker.md](app/worker.md) | ARQ WorkerSettings + startup/shutdown hooks |
| `app/api/portfolio.py` | — | GET /portfolio, /holdings, /trades, /performance, /stats；POST /portfolio/init |
| `app/api/market.py` | — | GET /market/quote/{symbol}, /candles/{symbol}, /search |

## alembic/

| 原始碼路徑 | CodeMap | 簡介 |
|-----------|---------|------|
| `alembic/env.py` | [env.md](alembic/env.md) | async migration 設定，`include_schemas=True` |
| `alembic/versions/0001_initial_schema.py` | [0001.md](alembic/versions/0001.md) | 初始 migration：建立 3 schema × 9 資料表 |
| `alembic/versions/0002_add_watchlist.py` | [0002.md](alembic/versions/0002.md) | migration 0002：新增 `trading.watchlist` 表 |
| `alembic/versions/0003_add_external_data_tables.py` | [0003.md](alembic/versions/0003.md) | migration 0003：新增 `market.us_market_daily`、`institutional_flows`、`margin_trading` |

## 待建模組（尚無對應 CodeMap）

| 路徑 | 說明 | 前置條件 |
|------|------|---------|
| `app/agents/` | LangGraph Agent | ARQ Worker |
