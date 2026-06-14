# API 規格

Base URL: `https://api.guieunuch.cc/api/v1`

- Swagger UI: `https://api.guieunuch.cc/api/v1/docs`
- Health check: `https://api.guieunuch.cc/health`
- 所有需要認證的 endpoint 帶 `Authorization: Bearer <JWT>` header。

---

## 認證（fastapi-users）

| Method | Path | 說明 | 認證 |
|--------|------|------|------|
| POST | `/api/v1/auth/register` | 註冊 | 否 |
| POST | `/api/v1/auth/jwt/login` | 登入，回傳 JWT（form-urlencoded） | 否 |
| POST | `/api/v1/auth/jwt/logout` | 登出 | 是 |
| GET | `/api/v1/users/me` | 取得當前用戶資訊 | 是 |
| PATCH | `/api/v1/users/me` | 更新用戶資訊 | 是 |

---

## 投資組合

| Method | Path | 說明 |
|--------|------|------|
| GET | `/api/v1/portfolio` | 取得投資組合（現金、總資產） |
| POST | `/api/v1/portfolio/init` | 初始化投資組合（設定初始資金） |
| GET | `/api/v1/portfolio/holdings` | 取得持倉列表 |
| GET | `/api/v1/portfolio/trades` | 取得交易紀錄（支援分頁） |
| GET | `/api/v1/portfolio/performance` | 取得每日績效歷史 |
| GET | `/api/v1/portfolio/stats` | 取得交易統計（勝率、總損益） |

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
| GET | `/api/v1/market/quote/{symbol}` | 取得即時報價 |
| GET | `/api/v1/market/candles/{symbol}` | 取得 K 線（盤中或歷史） |
| GET | `/api/v1/market/search` | 搜尋股票代碼/名稱 |

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
| POST | `/api/v1/ai/analyze` | 觸發 LangGraph Agent 分析（非同步，立即回傳 session_id） |
| GET | `/api/v1/ai/decisions` | 取得 AI 決策歷史（?limit=20&symbol=2330） |
| GET | `/api/v1/ai/decisions/{session_id}` | 取得單筆 AI 決策詳情 |

### POST /ai/analyze
Request:
```json
{
  "symbols": ["2330", "2454"],
  "mode": "full"
}
```
Response（list，每 symbol 一筆）:
```json
[
  {
    "session_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
    "status": "running"
  },
  {
    "session_id": "yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy",
    "status": "running"
  }
]
```

### GET /ai/decisions
Response（其中 decisions 是 JSONB）:
```json
[
  {
    "id": 1,
    "session_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
    "analysis": "技術面偏多...",
    "decisions": {
      "2330": {
        "action": "BUY",
        "confidence": 0.82,
        "shares": 1000,
        "target_price": 950.0,
        "stop_loss": 840.0,
        "reasoning": "..."
      }
    },
    "market_summary": "bull",
    "model_used": "gemini-2.0-flash",
    "tokens_used": 0,
    "execution_ms": 0,
    "agent_reports": {
      "analyst_reports": [],
      "debate_history": ""
    },
    "created_at": "2026-06-14T10:00:00+08:00"
  }
]
```

---

## WebSocket

### WS /ws/quotes 端點
- **URL**: `wss://api.guieunuch.cc/ws/quotes?token=<JWT>`
- **說明**: 訂閱即時報價推送。
- **認證**: 透過 `token` query parameter 傳遞 JWT，`audience='fastapi-users:auth'`。

#### Client → Server (訂閱/取消)
```json
{
  "action": "subscribe",
  "symbols": ["2330", "2454"]
}
```
```json
{
  "action": "unsubscribe",
  "symbols": ["2330"]
}
```

#### Server → Client (推送報價)
```json
{
  "type": "quote",
  "symbol": "2330",
  "last_price": 900.0,
  "change": 10.0,
  "change_pct": 1.12,
  "volume": 35000,
  "is_limit_up": false,
  "is_limit_down": false,
  "ts": "2026-06-14T10:30:00+08:00"
}
```

---

### WS /ws/ai-stream 端點
- **URL**: `wss://api.guieunuch.cc/ws/ai-stream?token=<JWT>&session_id=<UUID>`
- **說明**: 訂閱 AI 分析進度推送，收到終端事件（completed/failed）後會自動關閉連線。
- **認證**: 透過 `token` query parameter 傳遞 JWT。

#### Server → Client (分析進度事件)
```json
{
  "type": "ai_event",
  "session_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "event": "started",
  "symbol": "2330"
}
```
```json
{
  "type": "ai_event",
  "session_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "event": "completed",
  "symbol": "2330"
}
```
```json
{
  "type": "ai_event",
  "session_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "event": "failed",
  "error": "Timeout or model error..."
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
