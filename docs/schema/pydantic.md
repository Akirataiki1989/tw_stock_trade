# Pydantic Schemas CodeMap

> 最後更新：2026-05-23

---

## 目錄結構

```
app/schemas/
├── __init__.py
├── user.py          ← UserRead, UserCreate, UserUpdate（fastapi-users）
├── portfolio.py     ← PortfolioRead, HoldingRead, TradeRead, PerformanceRead, PortfolioStats
├── market.py        ← InstrumentRead, QuoteRead, CandleItem, CandleResponse
└── ai.py            ← AnalyzeRequest, AnalyzeResponse, AiDecisionRead
```

---

## 設計原則

| 規則 | 說明 |
|------|------|
| ORM mode | 所有 Read schema 套用 `model_config = ConfigDict(from_attributes=True)` |
| user_id 排除 | 所有 Read schema 不回傳 `user_id`（從 JWT 取得） |
| GENERATED 欄位 | `market_value`、`unrealized_pnl` 在 `HoldingRead` 中正常讀取，`Optional[float]` |
| JSONB 欄位 | `bids`、`asks`、`total`、`decisions`、`agent_reports` 使用 `Optional[Any]`（FBS 結構待定） |
| 數值型別 | 使用 `float`（與 ORM `Mapped[float]` 一致） |

---

## app/schemas/portfolio.py

| Class | 欄位 | 說明 |
|-------|------|------|
| `PortfolioRead` | id, initial_capital, cash, total_value, created_at, updated_at | 對應 `trading.portfolios` |
| `HoldingRead` | id, symbol, company_name, shares, avg_cost, current_price, market_value, unrealized_pnl, created_at, updated_at | 對應 `trading.holdings`；market_value/unrealized_pnl 為 GENERATED |
| `TradeRead` | id, symbol, company_name, action, shares, price, total_amount, fee, tax, net_amount, decision_reason, realized_pnl, realized_pnl_pct, created_at | 對應 `trading.trades` |
| `PerformanceRead` | id, date, total_value, cash, holdings_value, daily_return_pct, cumulative_return_pct, total_trades, winning_trades, created_at | 對應 `trading.daily_performance` |
| `PortfolioStats` | total_trades, winning_trades, win_rate, total_pnl, total_return_pct | 計算欄位，非 ORM 直接對應 |

---

## app/schemas/market.py

| Class | 欄位 | 說明 |
|-------|------|------|
| `InstrumentRead` | symbol, name, name_en, exchange, market, industry, security_type, board_lot, trading_currency, can_day_trade, can_buy_day_trade, limit_up_price, limit_down_price, reference_price, is_attention, is_disposition, last_synced | 對應 `market.instruments` |
| `QuoteRead` | symbol, reference_price, prev_close, open/high/low/close_price, last_price, last_size, avg_price, change, change_pct, amplitude, bids, asks, total, is_limit_up, is_limit_down, is_trial, fetched_at | 對應 `market.market_quotes` |
| `CandleItem` | ts（盤中）, date（歷史）, open, high, low, close, volume, average（盤中）, turnover/change（歷史） | 盤中與歷史 K 線共用，欄位依 timeframe 填入 |
| `CandleResponse` | symbol, timeframe, data: list[CandleItem] | K 線查詢回應包裝 |

---

## app/schemas/ai.py

| Class | 欄位 | 說明 |
|-------|------|------|
| `AnalyzeRequest` | symbols: list[str], mode: str = "full" | 觸發 AI 分析的請求 body |
| `AnalyzeResponse` | session_id: UUID, status: str | 非同步啟動回應（"running"/"completed"/"failed"） |
| `AiDecisionRead` | id, session_id, analysis, decisions, market_summary, model_used, tokens_used, execution_ms, agent_reports, created_at | 對應 `trading.ai_decisions` |
