# app/services/pubsub.py

## 用途

Redis Pub/Sub 封裝，用於在不同進程（如 ARQ Worker 與 FastAPI）之間傳遞即時訊息。

## Channel 命名規則

- **報價**: `quotes:{symbol}` (例如 `quotes:2330`)
- **AI 進度**: `ai:stream:{session_id}`

## 函式表格

| 函式 | 說明 |
|------|------|
| `publish_quote(redis, symbol, data)` | 發佈報價資料至對應的 symbol channel。 |
| `publish_ai_event(redis, session_id, event_type, data)` | 發佈 AI 分析事件（started/completed/failed）。 |

## 設計考量

- **Fire-and-forget**: 所有發佈操作均不等待訂閱者回應。
- **錯誤處理**: 若 Redis 連線失敗，僅記錄 Warning 避免影響主流程。
- **序列化**: 使用 `json.dumps` 將資料轉為字串後發佈。

## 依賴

- `redis.asyncio`：非同步 Redis 客戶端。
