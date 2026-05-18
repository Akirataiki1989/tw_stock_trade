# API 規格

Base URL: `https://<cloudflare-tunnel-domain>/api`

所有需要認證的 endpoint 帶 `Authorization: Bearer <JWT>` header。

---

## 認證（fastapi-users）

| Method | Path | 說明 | 認證 |
|--------|------|------|------|
| POST | `/auth/register` | 註冊 | 否 |
| POST | `/auth/jwt/login` | 登入，回傳 JWT | 否 |
| POST | `/auth/jwt/logout` | 登出 | 是 |
| GET | `/users/me` | 取得當前用戶資訊 | 是 |
| PATCH | `/users/me` | 更新用戶資訊 | 是 |

---

## 投資組合

| Method | Path | 說明 |
|--------|------|------|
| GET | `/portfolio` | 取得投資組合（現金、總資產） |
| POST | `/portfolio/init` | 初始化投資組合（設定初始資金） |
| GET | `/portfolio/holdings` | 取得持倉列表 |
| GET | `/portfolio/trades` | 取得交易紀錄（支援分頁） |
| GET | `/portfolio/performance` | 取得每日績效歷史 |
| GET | `/portfolio/stats` | 取得交易統計（勝率、總損益） |

### GET /portfolio
```json
{
  "initial_capital": 1000000,
  "cash": 850000,
  "total_value": 1023500,
  "updated_at": "2026-05-18T15:30:00+08:00"
}
```

### GET /portfolio/holdings
```json
[
  {
    "symbol": "2330",
    "company_name": "台積電",
    "shares": 1000,
    "avg_cost": 850.00,
    "current_price": 900.00,
    "market_value": 900000,
    "unrealized_pnl": 50000,
    "unrealized_pnl_pct": 5.88
  }
]
```

### GET /portfolio/trades?limit=50&offset=0
```json
[
  {
    "id": 1,
    "symbol": "2330",
    "company_name": "台積電",
    "action": "BUY",
    "shares": 1000,
    "price": 850.00,
    "total_amount": 850000,
    "fee": 1221,
    "tax": 0,
    "net_amount": 851221,
    "decision_reason": "技術面突破，AI 建議買入",
    "realized_pnl": 0,
    "realized_pnl_pct": 0,
    "created_at": "2026-05-18T09:15:00+08:00"
  }
]
```

---

## 市場資料

| Method | Path | 說明 |
|--------|------|------|
| GET | `/market/quote/{symbol}` | 取得即時報價 |
| GET | `/market/candles/{symbol}` | 取得 K 線（盤中或歷史） |
| GET | `/market/search` | 搜尋股票代碼/名稱 |

### GET /market/quote/2330
```json
{
  "symbol": "2330",
  "name": "台積電",
  "last_price": 900.00,
  "change": 10.00,
  "change_pct": 1.12,
  "open_price": 895.00,
  "high_price": 905.00,
  "low_price": 890.00,
  "volume": 35000,
  "is_limit_up": false,
  "is_limit_down": false,
  "fetched_at": "2026-05-18T10:30:00+08:00"
}
```

### GET /market/candles/2330?timeframe=D&from=2026-01-01&to=2026-05-18
```json
{
  "symbol": "2330",
  "timeframe": "D",
  "data": [
    {
      "date": "2026-05-18",
      "open": 895.00,
      "high": 905.00,
      "low": 890.00,
      "close": 900.00,
      "volume": 35000,
      "turnover": 31500000,
      "change": 10.00
    }
  ]
}
```

---

## AI 決策

| Method | Path | 說明 |
|--------|------|------|
| POST | `/ai/analyze` | 觸發 LangGraph Agent 分析 |
| GET | `/ai/decisions` | 取得 AI 決策歷史 |
| GET | `/ai/decisions/{id}` | 取得單筆 AI 決策詳情 |

### POST /ai/analyze
Request:
```json
{
  "symbols": ["2330", "2317", "0050"],
  "mode": "full"
}
```
Response（streaming via WebSocket，HTTP 只回執行 ID）:
```json
{
  "session_id": "uuid",
  "status": "running"
}
```

---

## WebSocket

| Path | 說明 |
|------|------|
| `WS /ws/quotes` | 訂閱即時報價推送 |
| `WS /ws/ai-stream` | 訂閱 AI 分析進度推送 |

### WS /ws/quotes 訊息格式
```json
{
  "type": "quote",
  "symbol": "2330",
  "last_price": 900.00,
  "change_pct": 1.12,
  "ts": "2026-05-18T10:30:05+08:00"
}
```

### WS /ws/ai-stream 訊息格式
```json
{
  "type": "agent_progress",
  "session_id": "uuid",
  "agent": "technical_analyst",
  "status": "completed",
  "summary": "技術面偏多，建議持有 2330"
}
```

---

## 錯誤格式

所有錯誤統一格式：
```json
{
  "detail": "錯誤說明"
}
```

| HTTP Code | 情境 |
|-----------|------|
| 400 | 參數錯誤 |
| 401 | 未認證或 JWT 過期 |
| 403 | 無權限 |
| 404 | 資源不存在 |
| 422 | Pydantic 驗證失敗 |
| 500 | 伺服器內部錯誤 |
