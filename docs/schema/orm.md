# ORM CodeMap

> SQLAlchemy 2.0 async + asyncpg。所有 model 繼承自 `app.models.base.Base`（DeclarativeBase）。
> 欄位完整規格請查 [`tables.md`](tables.md)；Pydantic schemas 請查 [`pydantic.md`](pydantic.md)。

---

## Class → Table 對應

| Class | 檔案 | Schema.Table | PK 型別 | 備註 |
|-------|------|-------------|---------|------|
| `User` | `app/models/user.py` | `public.users` | UUID | fastapi-users 管理，勿直接修改欄位 |
| `Instrument` | `app/models/market.py` | `market.instruments` | VARCHAR(10) | 股票代碼為 PK |
| `MarketQuote` | `app/models/market.py` | `market.market_quotes` | VARCHAR(10) | symbol 同時為 PK 與 FK |
| `IntradayCandle` | `app/models/market.py` | `market.intraday_candles` | BIGSERIAL | 盤中K線 |
| `HistoricalCandle` | `app/models/market.py` | `market.historical_candles` | BIGSERIAL | 歷史K線，永久保留 |
| `Portfolio` | `app/models/portfolio.py` | `trading.portfolios` | SERIAL | UNIQUE(user_id)，每用戶一筆 |
| `Holding` | `app/models/portfolio.py` | `trading.holdings` | SERIAL | UNIQUE(user_id, symbol) |
| `Trade` | `app/models/portfolio.py` | `trading.trades` | BIGSERIAL | 交易紀錄 |
| `AiDecision` | `app/models/portfolio.py` | `trading.ai_decisions` | BIGSERIAL | LangGraph 決策快照 |
| `DailyPerformance` | `app/models/portfolio.py` | `trading.daily_performance` | BIGSERIAL | UNIQUE(user_id, date) |

---

## FK 關係圖

```
public.users (id: UUID PK)
    │
    ├──< trading.portfolios.user_id     [UNIQUE → 每用戶僅一筆]
    │
    ├──< trading.holdings.user_id       [UNIQUE(user_id, symbol)]
    │
    ├──< trading.trades.user_id
    │
    ├──< trading.ai_decisions.user_id
    │
    └──< trading.daily_performance.user_id  [UNIQUE(user_id, date)]

market.instruments (symbol: VARCHAR PK)
    │
    └──1:1 market.market_quotes.symbol  [symbol 同時為 PK + FK]
```

所有 `trading.*` → `public.users` 的 FK 均設定 `ondelete="CASCADE"`（刪用戶自動清除所有交易資料）。

---

## 特殊欄位：GENERATED ALWAYS AS STORED

`trading.holdings` 的兩個欄位由 PostgreSQL 自動計算，**不可手動寫入**：

| 欄位 | 計算式 | SQLAlchemy 宣告 |
|------|--------|----------------|
| `market_value` | `shares × current_price` | `mapped_column(Numeric(15,2), nullable=True)` |
| `unrealized_pnl` | `shares × (current_price − avg_cost)` | `mapped_column(Numeric(15,2), nullable=True)` |

> **實作細節**：Alembic `0001` migration 在 `op.create_table()` 建立基本欄位後，
> 再用 `op.execute("ALTER TABLE trading.holdings ADD COLUMN ... GENERATED ALWAYS AS ... STORED")` 補加。
> SQLAlchemy 端僅宣告為普通欄位（nullable=True），讀取時由 DB 填值，寫入時忽略。

---

## UniqueConstraint 寫法慣例

有 UniqueConstraint 時，`__table_args__` 必須用 tuple：

```python
# 正確
__table_args__ = (UniqueConstraint("user_id", "symbol"), {"schema": "trading"})

# 純 schema，無 constraint
__table_args__ = {"schema": "trading"}
```

---

## 跨 Schema FK 寫法

```python
# trading.* → public.users
ForeignKey("public.users.id", ondelete="CASCADE")

# market.market_quotes → market.instruments
ForeignKey("market.instruments.symbol")
```

---

## 索引彙整

| 資料表 | 索引名稱 | 欄位（順序） | 說明 |
|--------|---------|------------|------|
| `public.users` | `ix_users_email` | (email) UNIQUE | fastapi-users 建立 |
| `market.intraday_candles` | `idx_intraday_symbol_tf` | (symbol, timeframe, ts DESC) | 查詢特定股票特定週期K線 |
| `market.historical_candles` | `idx_historical_symbol_tf` | (symbol, timeframe, date DESC) | 查詢歷史K線 |
| `trading.trades` | `idx_trades_user_symbol` | (user_id, symbol) | 查某用戶某股票交易 |
| `trading.trades` | `idx_trades_created_at` | (created_at DESC) | 按時間排序交易紀錄 |
| `trading.ai_decisions` | `idx_ai_decisions_user` | (user_id, created_at DESC) | 查某用戶AI決策歷史 |

---

## ORM 撰寫 Checklist

新增 model 時確認：

- [ ] 繼承 `Base`（`from app.models.base import Base`）
- [ ] `__table_args__` 包含正確 schema（`{"schema": "market"}` 或 `{"schema": "trading"}`）
- [ ] 有 UniqueConstraint 時改用 tuple 形式
- [ ] 跨 schema FK 用全名（`"public.users.id"`）
- [ ] 時間欄位用 `DateTime(timezone=True)` + `server_default=func.now()`
- [ ] 使用 `Mapped[T]` + `mapped_column()` 寫法（SQLAlchemy 2.0 style）
