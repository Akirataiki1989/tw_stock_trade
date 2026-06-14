# app/agent/nodes.py

## 用途

定義 LangGraph 中的節點執行邏輯，包含資料拉取、AI 分析、辯論與結果存檔。

## Node Factories

| 工廠函式 | 產生節點 | 說明 |
|------|------|------|
| `make_fetch_context` | `fetch_context` | 從 DB 拉取即時行情與外部數據供後續分析。 |
| `make_technical_analyst` | `technical_analyst` | 執行技術面分析。 |
| `make_sentiment_analyst` | `sentiment_analyst` | 執行籌碼面分析。 |
| `make_risk_analyst` | `risk_analyst` | 執行風險評估。 |
| `make_bull_researcher` | `bull_researcher` | 辯論節點：強化看多論點。 |
| `make_bear_researcher` | `bear_researcher` | 辯論節點：強化看空論點。 |
| `make_research_manager` | `research_manager` | 綜合評估並產出最終決策。 |
| `make_persist_result` | `persist_result` | 將決策與快照寫入 `trading.ai_decisions`。 |

## Standalone Nodes

| 節點名 | 說明 |
|------|------|
| `debate_init` | 初始化辯論狀態，並執行**熔斷機制**。 |
| `execute_or_preview` | (Stub) 未來整合下單 API 或僅預覽。 |

## 熔斷機制說明

在 `debate_init` 節點中：
- 若 **風險分析師** 給出的建議為 `HOLD` (觀望)。
- 且 **信心度 (confidence) >= 0.8**。
- **邏輯**：系統判斷目前風險過高，無須進行後續 Bull/Bear 辯論，直接跳轉至決策階段以節省 Token 與時間。
