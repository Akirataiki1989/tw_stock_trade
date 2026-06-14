# 專案概覽

> **新 Session Agent 入口**：讀完本頁即可掌握 80% 狀況。需要細節時按下方表格按需載入。

---

## 目前狀態

| | 項目 | 說明 |
|--|------|------|
| ✅ | DB migration | `alembic/versions/0001_initial_schema.py`，3 schema × 9 資料表 |
| ✅ | SQLAlchemy models | `app/models/`，market + trading + public |
| ✅ | pydantic-settings | `app/core/config.py`，讀 `.env` |
| ✅ | fastapi-users 認證 | `app/main.py`, `app/users.py`, `app/schemas/user.py` |
| ✅ | Pydantic Schemas | `app/schemas/portfolio.py` / `market.py` / `ai.py` |
| ✅ | portfolio / market API | `app/api/`, `app/services/`，6 個 endpoint |
| ✅ | FBS SDK 接入 | `app/services/fbs.py` 實作完成：FbsClient singleton、sync_* / fetch_* 方法；`trading.watchlist` 表（migration 0002） |
| ✅ | ARQ Worker | `app/worker.py` (WorkerSettings + startup/shutdown) + `app/tasks.py` (8 個 cron tasks：instruments/quotes/intraday_candles/historical_candles/clear_intraday/us_market/institutional_flows/margin_trading) |
| ✅ | 外部數據同步（Step 5.5） | yfinance + TWSE T86/MI_MARGN → 3 張新表；3 個 cron tasks（08:30/16:00/16:05）；`app/services/external_data.py` |
| ⏳ | LangGraph Agent | 待 ARQ Worker |
| ⏳ | WebSocket 推送 | 待 market API + LangGraph |
| ⏳ | Docker Compose | 最終整合 |

---

## 程式碼地圖

| 檔案 | 用途 |
|------|------|
| `app/database.py` | `engine`、`AsyncSessionLocal`、`get_db()` FastAPI dependency |
| `app/core/config.py` | `Settings`（pydantic-settings），讀 `.env`，全域 `settings` 單例 |
| `app/models/base.py` | `Base`（DeclarativeBase），所有 model 的基底 |
| `app/models/user.py` | `User`，`public.users`，fastapi-users 管理 |
| `app/models/market.py` | `Instrument` / `MarketQuote` / `IntradayCandle` / `HistoricalCandle` / `UsMarketDaily` / `InstitutionalFlow` / `MarginTrading` |
| `app/models/portfolio.py` | `Portfolio` / `Holding` / `Trade` / `AiDecision` / `DailyPerformance` / `Watchlist` |
| `app/main.py` | FastAPI 進入點，lifespan + router 掛載 |
| `app/users.py` | UserManager、JWTStrategy、auth_backend、fastapi_users 實例 |
| `app/schemas/user.py` | UserRead / UserCreate / UserUpdate Pydantic schemas |
| `app/schemas/portfolio.py` | PortfolioRead / HoldingRead / TradeRead / PerformanceRead / PortfolioStats |
| `app/schemas/market.py` | InstrumentRead / QuoteRead / CandleItem / CandleResponse |
| `app/schemas/ai.py` | AnalyzeRequest / AnalyzeResponse / AiDecisionRead |
| `app/services/portfolio.py` | Portfolio / Holding / Trade / Performance 查詢，stats 計算 |
| `app/services/market.py` | Quote / Candle 查詢，Instrument 搜尋 |
| `app/services/fbs.py` | FbsClient singleton：connect/disconnect、sync_instruments/quote/candles、fetch_quote/candles |
| `app/services/external_data.py` | yfinance + TWSE API fetch/parse/upsert；clean_number()、parse_institutional_row()、parse_margin_row_full() 等純函式 |
| `app/agent/state.py` | LangGraph State 定義，含平行節點 reducer |
| `app/agent/memory.py` | 長短期記憶管理：Checkpointer 與 Vector Store (pgvector) 初始化 |
| `app/agent/prompts.py` | AI 角色提示詞常數 |
| `app/agent/nodes.py` | Graph 節點工廠與業務邏輯、熔斷機制 |
| `app/agent/graph.py` | LangGraph 編排與 LLM 初始化 |
| `app/api/ai.py` | POST /ai/analyze（觸發分析）、GET /ai/decisions（決策歷史）、GET /ai/decisions/{session_id}（單筆詳情） |
| `app/tasks.py` | 自訂 TRACE 層級、`is_trading_hours()`、`get_watch_symbols()`、AI 相關 4 個 cron tasks (總計 12 個) |
| `app/worker.py` | ARQ `WorkerSettings`（redis、cron_jobs、max_jobs=10、job_timeout=300）、`startup`/`shutdown` hooks |
| `alembic/versions/0002_add_watchlist.py` | 新增 `trading.watchlist` 表 migration |
| `alembic/versions/0003_add_external_data_tables.py` | migration 0003：新增 `market.us_market_daily`、`institutional_flows`、`margin_trading` |
| `app/api/portfolio.py` | GET /portfolio, /holdings, /trades, /performance, /stats；POST /portfolio/init |
| `app/api/market.py` | GET /market/quote/{symbol}, /candles/{symbol}, /search |
| `alembic/env.py` | async migration 設定，`include_schemas=True` |
| `alembic/versions/0001_initial_schema.py` | 初始 migration，建立所有資料表 |

---

## DB 結構

| Schema.Table | 說明 |
|-------------|------|
| `public.users` | fastapi-users 管理，UUID PK，JWT 認證主體 |
| `market.instruments` | 股票基本資料，`symbol` PK，來自 FBS `/intraday/ticker` |
| `market.market_quotes` | 即時報價快取，1:1 instruments，來自 FBS `/intraday/quote` |
| `market.intraday_candles` | 盤中K線，每日盤後可清除，timeframe: 1/5/10/15/30/60 |
| `market.historical_candles` | 歷史K線，永久保留，timeframe: D/W/M |
| `market.us_market_daily` | 美股指數昨收（S&P500/NASDAQ/TSM ADR/SOX/DXY/US10Y），每日一筆 |
| `market.institutional_flows` | TWSE 三大法人買賣超，每日全市場，per symbol |
| `market.margin_trading` | TWSE 融資融券餘額，每日全市場，per symbol |
| `trading.portfolios` | 每用戶一筆，現金與總資產 |
| `trading.holdings` | 持倉，`market_value` / `unrealized_pnl` 為 GENERATED ALWAYS AS STORED |
| `trading.trades` | 每筆買賣紀錄，含手續費 / 稅 / 已實現損益 |
| `trading.ai_decisions` | LangGraph Agent 每次執行的決策快照 |
| `trading.daily_performance` | 每日收盤後績效紀錄 |

---

## 需要深入時載入

| 需求 | 文件 |
|------|------|
| FK 關係圖 / ORM 撰寫慣例 | [`docs/schema/orm.md`](schema/orm.md) |
| DB 欄位完整規格 | [`docs/schema/tables.md`](schema/tables.md) |
| 某個 .py 的 class 與依賴 | [`docs/codemap/directory.md`](codemap/directory.md) |
| 完整開發計畫 / 任務依賴 | [`docs/progress/roadmap.md`](progress/roadmap.md) |
| API endpoint 規格 | [`docs/api.md`](api.md) |
| Pydantic schemas 設計 | [`docs/schema/pydantic.md`](schema/pydantic.md) |
| 版本更新記錄 | [`docs/changelog/Index.md`](changelog/Index.md) |
