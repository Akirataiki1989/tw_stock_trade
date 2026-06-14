# 開發路線圖

> 最後更新：2026-06-14

## 任務依賴圖

```
[DB Schema + Migration] ✅
        │
        ▼
[SQLAlchemy Models] ✅
        │
        ▼
[pydantic-settings config] ✅
        │
        ▼
[fastapi-users 認證] ◀── 下一步
        │
        ├──▶ [Pydantic Schemas（app/schemas/）]
        │           │
        │           ▼
        │    [portfolio / market API 路由]
        │           │
        │           └──▶ [WebSocket 推送]
        │
        └──▶ [FBS SDK 接入] ◀── 需等 API Key 生效（外部依賴）
                    │
                    ▼
              [ARQ Worker]  ← 定時抓取報價 / 盤後清除
                    │
                    ▼
              [LangGraph Agent]
                    │
                    ├──▶ [app/api/ai.py]（trigger + history）
                    │
                    └──▶ [WebSocket AI stream]
                                │
                                ▼
                          [Docker Compose] ← 最終整合
```

---

## 詳細進度

### ✅ 已完成

| 項目 | 關鍵檔案 | 說明 |
|------|---------|------|
| DB Schema 設計與 migration | `alembic/versions/0001_initial_schema.py` | 建立 market / trading / public 三層，共 9 張資料表 |
| SQLAlchemy models | `app/models/` | Mapped + mapped_column（2.0 style），含 GENERATED ALWAYS AS |
| pydantic-settings config | `app/core/config.py` | 讀 .env，Fernet 加密金鑰管理 |
| fastapi-users 認證 | `app/main.py`, `app/users.py`, `app/schemas/user.py` | JWT Bearer 認證，register / login / logout / me 端點 |
| Pydantic Schemas | `app/schemas/portfolio.py`, `market.py`, `ai.py` | Read schemas + PortfolioStats / CandleResponse / AnalyzeRequest |
| portfolio / market API | `app/api/portfolio.py`, `app/api/market.py`, `app/services/portfolio.py`, `app/services/market.py` | 6 個 REST endpoint，含 portfolio init / stats / candle timeframe 路由 |
| FBS SDK 接入 | `app/services/fbs.py` | FbsClient singleton、sync_*/fetch_* 方法、isClose probe |
| ARQ Worker | `app/tasks.py`, `app/worker.py` | 8 個 cron tasks：instruments（08:30）、quotes（每分鐘）、intraday_candles（每 5 分）、historical_candles（14:00）、clear_intraday（14:30）、us_market（08:30）、institutional_flows（16:00）、margin_trading（16:05） |
| 外部數據同步（Step 5.5） | `app/services/external_data.py`、`alembic/versions/0003_add_external_data_tables.py`、`app/models/market.py`、`pyproject.toml` | 整合 yfinance + TWSE T86/MI_MARGN API；新增 `market.us_market_daily`、`institutional_flows`、`margin_trading` 三張表；新增 3 個 cron tasks |

---

### 🔜 待辦（依優先順序）

#### Step 1：fastapi-users 認證
**前置條件**：✅ 全部完成  
**後置任務**：所有需要 `current_user` 的 API 路由  

- [x] 建立 `app/main.py`（FastAPI 進入點，lifespan 設定）
- [x] 設定 fastapi-users（UserManager、JWT backend、auth router）
- [x] 掛載 `/auth/register`、`/auth/jwt/login`、`/auth/jwt/logout`、`/users/me`
- [x] 撰寫 `User` Create/Update Pydantic schema
- [x] 手動測試 JWT 登入流程

---

#### Step 2：Pydantic Schemas（app/schemas/）
**前置條件**：Step 1  
**後置任務**：Step 3 API 路由  

- [x] `app/schemas/portfolio.py`（PortfolioRead, HoldingRead, TradeRead, PerformanceRead）
- [x] `app/schemas/market.py`（QuoteRead, CandleRead, InstrumentRead）
- [x] `app/schemas/ai.py`（AnalyzeRequest, AiDecisionRead）
- [x] 更新 `docs/schema/pydantic.md`

---

#### Step 3：portfolio / market API 路由
**前置條件**：Step 1（認證）、Step 2（schemas）  
**後置任務**：前端串接、LangGraph 執行交易  

- [x] `app/services/portfolio.py`（買賣邏輯、持倉更新、績效記錄）
- [x] `app/services/market.py`（報價查詢、K線查詢、搜尋）
- [x] `app/api/portfolio.py`（GET /portfolio, /holdings, /trades, /performance, /stats）
- [x] `app/api/market.py`（GET /market/quote/{symbol}, /candles/{symbol}, /search）
- [x] 在 `app/main.py` 掛載 router

---

#### Step 4：FBS SDK 接入
**前置條件**：FBS API Key 生效（外部）✅  
**後置任務**：Step 5 ARQ Worker  

- [x] 安裝 FBS SDK（fubon_neo 2.2.8，whl 安裝）
- [x] 補充 `docs/fbs_api.md`（實際 SDK 呼叫範例）
- [x] 實作 `app/services/fbs.py`（連線、ticker 同步、quote 拉取、candles 拉取）

---

#### Step 5：ARQ Worker
**前置條件**：Step 4 FBS SDK  
**後置任務**：Step 6 LangGraph Agent  

- [x] 建立 Redis Docker container（port 6379:6379，docker-compose.yaml）
- [x] `app/tasks.py`（TRACE 層級、is_trading_hours()、get_watch_symbols()、5 個 cron task）
- [x] `app/worker.py`（WorkerSettings + startup/shutdown hooks）
- [x] 設定 Redis 連線（`settings.redis_url`）
- [x] NAS DSM SSH 手動驗證：Worker 啟動、cron 觸發正常

---

#### Step 5.5：外部數據同步
**前置條件**：Step 5 ARQ Worker  
**後置任務**：Step 6 LangGraph Agent  

- [x] 安裝 `yfinance>=0.2.54`
- [x] 實作 `app/services/external_data.py`（fetch_us_market_data、fetch_twse_institutional、fetch_twse_margin、upsert_* 三個函式、pure parsing functions）
- [x] 新增 migration 0003（`market.us_market_daily`、`institutional_flows`、`margin_trading`）
- [x] 新增 ORM models（`UsMarketDaily`、`InstitutionalFlow`、`MarginTrading`）
- [x] 掛載 3 個 cron tasks：us_market（08:30）、institutional_flows（16:00）、margin_trading（16:05）
- [x] 撰寫 `tests/test_external_data.py` 單元測試

---

#### Step 6：LangGraph Agent
**前置條件**：Step 5 ARQ Worker（市場資料來源）、Step 5.5 外部數據同步、Step 3 portfolio API（交易執行）  
**後置任務**：Step 7 WebSocket、前端 AI 功能  

- [ ] `app/agents/` graph 定義（nodes + edges）
- [ ] 整合 Gemini（`langchain-google-genai`）+ Langfuse 監控
- [ ] `app/api/ai.py`（POST /ai/analyze, GET /ai/decisions）
- [ ] 寫入 `trading.ai_decisions` 快照

---

#### Step 7：WebSocket 推送
**前置條件**：Step 3 market API、Step 6 LangGraph Agent  

- [ ] `app/api/ws.py`（`WS /ws/quotes`、`WS /ws/ai-stream`）
- [ ] 即時報價訂閱機制（Redis pub/sub 或 ARQ 推送）
- [ ] AI 分析進度 stream

---

#### Step 8：部署設定
**前置條件**：Step 1–7 全部完成  
**架構決策**：FastAPI + ARQ Worker 直接跑在 NAS DSM；PostgreSQL + Redis 跑在 Docker 容器

- [ ] Synology Task Scheduler 設定 uvicorn 開機自動啟動
- [ ] Synology Task Scheduler 設定 ARQ Worker 開機自動啟動
- [ ] Redis Docker 容器設定
- [ ] Cloudflare Tunnel 連通測試
- [ ] `.env` 生產環境設定
ARQ Worker 開機自動啟動
- [ ] Redis Docker 容器設定
- [ ] Cloudflare Tunnel 連通測試
- [ ] `.env` 生產環境設定
