# tw_stock_trade — Claude 工作指引

## 專案概述
台股 AI 模擬交易平台後端。FastAPI + PostgreSQL + Redis + LangGraph。
前端（React）獨立部署於 Vercel，本專案為純後端。

## 環境

| 項目 | 值 |
|------|-----|
| NAS 路徑 | `/volume1/web/codeserver/tw_stock_trade` |
| Python | 3.12（NAS 本機） |
| 套件管理 | `uv`（必須在 NAS 終端機執行，不能從 Windows） |
| venv | `.venv/bin/python`、`.venv/bin/alembic` |

### 常用指令
```bash
# 安裝依賴
uv sync

# DB migration
.venv/bin/alembic upgrade head
.venv/bin/alembic downgrade base

# Ruff 檢查
uv run ruff check app/

# 啟動開發伺服器
.venv/bin/uvicorn app.main:app --reload
```

## DB Schema 結構

```
public.users                  ← fastapi-users 管理，JWT 認證
market.instruments            ← 股票基本資料（來自 FBS /intraday/ticker）
market.market_quotes          ← 即時報價快取（來自 FBS /intraday/quote）
market.intraday_candles       ← 盤中 K 線，每日盤後可清除（timeframe: 1/5/10/15/30/60）
market.historical_candles     ← 歷史 K 線，永久保留（timeframe: D/W/M）
trading.portfolios            ← 每用戶一筆，現金與總資產
trading.holdings              ← 持倉，market_value/unrealized_pnl 為 GENERATED ALWAYS AS STORED
trading.trades                ← 交易紀錄，含手續費/稅/已實現損益
trading.ai_decisions          ← LangGraph Agent 決策快照
trading.daily_performance     ← 每日績效紀錄
```

跨 schema FK 寫法：`ForeignKey("public.users.id")`、`ForeignKey("market.instruments.symbol")`

## 技術棧

| 層 | 套件 |
|----|------|
| Web | FastAPI + Uvicorn |
| ORM | SQLAlchemy 2.0 async + asyncpg |
| Migration | Alembic（async engine） |
| 認證 | fastapi-users（JWT） |
| 任務佇列 | ARQ + Redis |
| AI | LangGraph + LangChain + Google Gemini |
| 監控 | Langfuse |
| 排程 | APScheduler |
| 加密 | Fernet（AES-256，用於存 API Key） |

## 已知限制與慣例

- `model_config` 在 pydantic-settings 不能加型別注解，否則會被當成欄位
- `arq` 要求 `redis<6`，不要在 pyproject.toml 明確指定 redis 版本
- `uv sync` 必須在 NAS 終端機執行，從 Windows 執行會建立 Windows 格式 venv（無 `bin/`）
- Ruff `line-length = 100`，`select = ["E", "F", "I"]`
- 所有 model 的 `__table_args__` 需包含 `{"schema": "market"}` 或 `{"schema": "trading"}`
- 有 UniqueConstraint 時寫法：`__table_args__ = (UniqueConstraint(...), {"schema": "trading"})`

## 目錄結構

```
tw_stock_trade/
├── app/
│   ├── core/
│   │   └── config.py          ← pydantic-settings，讀 .env
│   ├── models/
│   │   ├── base.py            ← DeclarativeBase
│   │   ├── user.py            ← fastapi-users User（public schema）
│   │   ├── portfolio.py       ← trading schema 的所有 model
│   │   └── market.py          ← market schema 的所有 model
│   ├── api/                   ← 路由（待建）
│   ├── schemas/               ← Pydantic request/response schemas（待建）
│   ├── services/              ← 業務邏輯（待建）
│   └── database.py            ← async engine + session
├── alembic/
│   ├── env.py                 ← include_schemas=True，version_table_schema="public"
│   └── versions/
│       └── 0001_initial_schema.py
├── docs/
│   ├── api.md                 ← API endpoint 規格
│   ├── schema.md              ← DB schema 詳細說明
│   └── fbs_api.md             ← FBS SDK 用法（API Key 生效後補）
├── pyproject.toml
├── alembic.ini
└── .env                       ← 不進 git
```

## 開發進度

- [x] DB Schema 設計與 migration
- [x] SQLAlchemy models
- [x] pydantic-settings config
- [ ] fastapi-users 認證（下一步）
- [ ] portfolio / market API 路由
- [ ] FBS SDK 接入（API Key 待生效）
- [ ] ARQ Worker
- [ ] LangGraph Agent
- [ ] WebSocket 推送
- [ ] Docker Compose
