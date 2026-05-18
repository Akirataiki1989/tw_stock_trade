# DB Schema 規格

## Schema 分層

| Schema | 用途 |
|--------|------|
| `public` | 認證（fastapi-users 管理） |
| `market` | 純市場資料，共享，無 user_id |
| `trading` | AI 模擬交易，含 user_id FK |

---

## public.users

由 fastapi-users 自動管理，勿手動修改欄位。

| 欄位 | 型別 | 說明 |
|------|------|------|
| id | UUID PK | |
| email | VARCHAR(320) | unique |
| hashed_password | VARCHAR(1024) | |
| is_active | BOOLEAN | 預設 true |
| is_superuser | BOOLEAN | 預設 false |
| is_verified | BOOLEAN | 預設 false |

---

## market.instruments

來源：FBS `/intraday/ticker/{symbol}`，每日開盤前同步。

| 欄位 | 型別 | FBS 欄位 | 說明 |
|------|------|---------|------|
| symbol | VARCHAR(10) PK | symbol | 股票代碼 |
| name | VARCHAR(100) | name | 股票簡稱 |
| name_en | VARCHAR(100) | nameEn | 英文簡稱 |
| exchange | VARCHAR(10) | exchange | TWSE / TPEx |
| market | VARCHAR(10) | market | TSE / OTC / ESB... |
| industry | VARCHAR(50) | industry | 產業別 |
| security_type | VARCHAR(20) | securityType | 證券別 |
| board_lot | INTEGER | boardLot | 交易單位 |
| trading_currency | VARCHAR(10) | tradingCurrency | 交易幣別 |
| can_day_trade | BOOLEAN | canDayTrade | 可現沖 |
| can_buy_day_trade | BOOLEAN | canBuyDayTrade | 可先買現沖 |
| limit_up_price | NUMERIC(10,2) | limitUpPrice | 漲停價 |
| limit_down_price | NUMERIC(10,2) | limitDownPrice | 跌停價 |
| reference_price | NUMERIC(10,2) | referencePrice | 參考價 |
| is_attention | BOOLEAN | isAttention | 注意股 |
| is_disposition | BOOLEAN | isDisposition | 處置股 |
| last_synced | TIMESTAMPTZ | — | 最後同步時間 |

---

## market.market_quotes

來源：FBS `/intraday/quote/{symbol}`，盤中定期更新（WebSocket 或輪詢）。

| 欄位 | 型別 | FBS 欄位 | 說明 |
|------|------|---------|------|
| symbol | VARCHAR(10) PK FK→instruments | symbol | |
| reference_price | NUMERIC(10,2) | referencePrice | 今日參考價 |
| prev_close | NUMERIC(10,2) | previousClose | 昨收 |
| open_price | NUMERIC(10,2) | openPrice | 開盤價 |
| high_price | NUMERIC(10,2) | highPrice | 最高價 |
| low_price | NUMERIC(10,2) | lowPrice | 最低價 |
| close_price | NUMERIC(10,2) | closePrice | 收盤價 |
| last_price | NUMERIC(10,2) | lastPrice | 最新成交價 |
| last_size | INTEGER | lastSize | 最新成交量（張） |
| avg_price | NUMERIC(10,2) | avgPrice | 均價 |
| change | NUMERIC(10,2) | change | 漲跌 |
| change_pct | NUMERIC(8,4) | changePercent | 漲跌幅% |
| amplitude | NUMERIC(8,4) | amplitude | 振幅 |
| bids | JSONB | bids | 委買五檔 [{price,volume},...] |
| asks | JSONB | asks | 委賣五檔 |
| total | JSONB | total | 成交統計 {tradeValue,tradeVolume,...} |
| is_limit_up | BOOLEAN | isLimitUpPrice | 漲停 |
| is_limit_down | BOOLEAN | isLimitDownPrice | 跌停 |
| is_trial | BOOLEAN | isTrial | 試撮階段 |
| fetched_at | TIMESTAMPTZ | — | 快取時間 |

---

## market.intraday_candles

來源：FBS `/intraday/candles/{symbol}`。每日盤後可清除或封存。

| 欄位 | 型別 | 說明 |
|------|------|------|
| id | BIGSERIAL PK | |
| symbol | VARCHAR(10) | 股票代碼 |
| timeframe | VARCHAR(5) | `1`/`5`/`10`/`15`/`30`/`60`（分鐘） |
| ts | TIMESTAMPTZ | K 線時間戳 |
| open | NUMERIC(10,2) | 開盤價 |
| high | NUMERIC(10,2) | 最高價 |
| low | NUMERIC(10,2) | 最低價 |
| close | NUMERIC(10,2) | 收盤價 |
| volume | BIGINT | 成交量（整股：張；零股：股） |
| average | NUMERIC(10,2) | 均價 |

UNIQUE: (symbol, timeframe, ts)
INDEX: idx_intraday_symbol_tf ON (symbol, timeframe, ts DESC)

---

## market.historical_candles

來源：FBS `/historical/candles/{symbol}`。永久保留，回測基準。

| 欄位 | 型別 | 說明 |
|------|------|------|
| id | BIGSERIAL PK | |
| symbol | VARCHAR(10) | 股票代碼 |
| timeframe | VARCHAR(5) | `D`/`W`/`M` |
| date | DATE | K 線日期 |
| open | NUMERIC(10,2) | 開盤價 |
| high | NUMERIC(10,2) | 最高價 |
| low | NUMERIC(10,2) | 最低價 |
| close | NUMERIC(10,2) | 收盤價 |
| volume | BIGINT | 成交量（張） |
| turnover | NUMERIC(20,2) | 成交額 |
| change | NUMERIC(10,2) | 漲跌 |

UNIQUE: (symbol, timeframe, date)
INDEX: idx_historical_symbol_tf ON (symbol, timeframe, date DESC)

---

## trading.portfolios

每位用戶一筆，記錄資金狀態。

| 欄位 | 型別 | 說明 |
|------|------|------|
| id | SERIAL PK | |
| user_id | UUID FK→public.users | UNIQUE |
| initial_capital | NUMERIC(15,2) | 初始資金 |
| cash | NUMERIC(15,2) | 可用現金 |
| total_value | NUMERIC(15,2) | 總資產（現金＋持倉市值） |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |

---

## trading.holdings

持倉紀錄。`market_value` 與 `unrealized_pnl` 為 DB 自動計算欄位。

| 欄位 | 型別 | 說明 |
|------|------|------|
| id | SERIAL PK | |
| user_id | UUID FK→public.users | |
| symbol | VARCHAR(10) | |
| company_name | VARCHAR(100) | |
| shares | INTEGER | CHECK > 0 |
| avg_cost | NUMERIC(10,2) | 平均成本 |
| current_price | NUMERIC(10,2) | 現價（定期更新） |
| market_value | NUMERIC(15,2) | **GENERATED**: shares × current_price |
| unrealized_pnl | NUMERIC(15,2) | **GENERATED**: shares × (current_price − avg_cost) |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |

UNIQUE: (user_id, symbol)

---

## trading.trades

每筆買賣紀錄，含手續費與稅。

| 欄位 | 型別 | 說明 |
|------|------|------|
| id | BIGSERIAL PK | |
| user_id | UUID FK→public.users | |
| symbol | VARCHAR(10) | |
| company_name | VARCHAR(100) | |
| action | VARCHAR(4) | `BUY` / `SELL` |
| shares | INTEGER | 股數 |
| price | NUMERIC(10,2) | 成交價 |
| total_amount | NUMERIC(15,2) | 成交金額（price × shares） |
| fee | NUMERIC(10,2) | 手續費 |
| tax | NUMERIC(10,2) | 交易稅（賣出才有） |
| net_amount | NUMERIC(15,2) | 實際金額（含費用） |
| decision_reason | TEXT | AI 決策理由 |
| realized_pnl | NUMERIC(15,2) | 已實現損益（SELL 才有意義） |
| realized_pnl_pct | NUMERIC(8,4) | 已實現損益% |
| created_at | TIMESTAMPTZ | |

INDEX: (user_id, symbol), (created_at DESC)

---

## trading.ai_decisions

LangGraph Agent 每次執行的完整快照。

| 欄位 | 型別 | 說明 |
|------|------|------|
| id | BIGSERIAL PK | |
| user_id | UUID FK→public.users | |
| session_id | UUID | 本次執行 ID |
| analysis | TEXT | 整體市場分析文字 |
| decisions | JSONB | `[{symbol, action, shares, reason}, ...]` |
| market_summary | TEXT | 市場摘要 |
| model_used | VARCHAR(100) | 使用的 AI 模型 |
| tokens_used | INTEGER | 消耗 token 數 |
| execution_ms | INTEGER | 執行時間（毫秒） |
| agent_reports | JSONB | 各 Agent 詳細報告 |
| created_at | TIMESTAMPTZ | |

INDEX: (user_id, created_at DESC)

---

## trading.daily_performance

每日收盤後寫入一筆，用於績效圖表。

| 欄位 | 型別 | 說明 |
|------|------|------|
| id | BIGSERIAL PK | |
| user_id | UUID FK→public.users | |
| date | DATE | |
| total_value | NUMERIC(15,2) | 當日總資產 |
| cash | NUMERIC(15,2) | 當日現金 |
| holdings_value | NUMERIC(15,2) | 當日持倉市值 |
| daily_return_pct | NUMERIC(8,4) | 當日報酬率% |
| cumulative_return_pct | NUMERIC(8,4) | 累計報酬率% |
| total_trades | INTEGER | 當日總交易次數 |
| winning_trades | INTEGER | 當日獲利交易次數 |
| created_at | TIMESTAMPTZ | |

UNIQUE: (user_id, date)
