# app/agent/state.py

## 用途

定義 LangGraph Agent 的狀態結構，包含分析師報告、辯論過程及最終決策。

## TypedDicts

| 名稱 | 欄位 | 說明 |
|------|------|------|
| `AnalystReport` | `analyst_id`, `analysis`, `signal`, `confidence` | 單一分析師的輸出內容 |
| `DebateState` | `bull_argument`, `bear_argument`, `current_round`, `winner` | 辯論過程的狀態 |
| `FinalDecision` | `symbol`, `action`, `quantity`, `reason`, `confidence` | 最終交易決策 |
| `GraphState` | `symbol`, `context`, `analyst_reports`, `debate`, `decision`, `metadata` | **主狀態**。`analyst_reports` 使用 `operator.add` reducer，支援平行節點結果彙整。 |

## Reducer 說明

- `analyst_reports: Annotated[list[AnalystReport], operator.add]`：當技術、情緒、風險分析師平行執行時，其結果會被自動累加到列表，而不會互相覆蓋。
