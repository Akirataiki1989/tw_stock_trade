# app/api/ws.py

## 用途

提供 WebSocket 連線，支援即時報價訂閱與 AI 分析進度推送。

## Endpoints

| Endpoint | 說明 | Auth |
|----------|------|------|
| `WS /ws/quotes` | 即時報價訂閱。Client 發送 `subscribe`/`unsubscribe` 指令。 | 是 (Query Param) |
| `WS /ws/ai-stream` | AI 分析進度。監聽特定 `session_id` 的進度事件。 | 是 (Query Param) |

## 訊息格式

### /ws/quotes
- **訂閱**: `{"action": "subscribe", "symbols": ["2330"]}`
- **推送**: `{"type": "quote", "symbol": "2330", "last_price": 900.0, ...}`

### /ws/ai-stream
- **事件**: `{"type": "ai_event", "session_id": "...", "event": "started/completed/failed", ...}`
- **自動關閉**: 收到 `completed` 或 `failed` 事件後，伺服器會主動關閉連線。

## JWT 驗證

由於 WebSocket 原生 API 在瀏覽器端難以攜帶自訂 Header，因此採用 Query Parameter 方式傳遞 Token：
- 參數名: `token`
- 驗證方式: 與 REST API 相同，但 `audience` 設為 `fastapi-users:auth`。

## 依賴

- `app.services.pubsub`：Redis Pub/Sub 訂閱機制。
- `app.users.current_active_user`：驗證 Token 並取得使用者。
- `request.app.state.redis`：Redis 連線實例。
