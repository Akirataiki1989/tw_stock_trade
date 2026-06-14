# app/api/ai.py

## 用途

AI 分析觸發與決策歷史查詢。非同步設計：`POST /ai/analyze` 立即回傳 `session_id`，實際分析在 ARQ worker 執行。

## Endpoints

| Method | Path | Auth | 說明 |
|--------|------|------|------|
| POST | `/ai/analyze` | 是 | 觸發指定標的的 AI 分析。每個標的獨立一個 `session_id`，非同步在 worker 執行。 |
| GET | `/ai/decisions` | 是 | 查詢目前使用者的 AI 決策歷史，依時間倒序。支援 `limit` 與 `symbol` 篩選。 |
| GET | `/ai/decisions/{session_id}` | 是 | 查詢單筆 AI 決策（含完整 `agent_reports`）。 |

## 觸發流程

1. 使用者呼叫 `POST /ai/analyze` 並提供 `symbols` 列表。
2. API 為每個 symbol 產出一個唯一的 `session_id` (UUID)。
3. API 透過 `arq_pool.enqueue_job("task_run_ai_on_demand", ...)` 將任務推入 Redis 隊列。
4. API 立即回傳 `session_id` 列表與 `status: "running"` 給使用者。
5. ARQ Worker 執行 `task_run_ai_on_demand`，呼叫 LangGraph Agent 進行分析。
6. Agent 分析完成後，將結果持久化至 `trading.ai_decisions` 表。

## 依賴

- `app.database.get_db`：資料庫 session。
- `app.models.portfolio.AiDecision`：決策模型。
- `app.schemas.ai`：Pydantic schemas (AnalyzeRequest, AnalyzeResponse, AiDecisionRead)。
- `app.users.current_active_user`：取得當前登入用戶。
- `request.app.state.arq`：ARQ 任務隊列池。
