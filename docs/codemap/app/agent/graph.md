# app/agent/graph.py

## 用途

負責 LangGraph 的建構、編排與 LLM (Gemini) 的初始化。

## 函式

| 函式 | 簽名 | 說明 |
|------|------|------|
| `build_graph` | `(*, db_factory, checkpointer, store, llm=None)` | 組裝所有節點與邊，返回編譯後的 `CompiledGraph`。 |
| `get_pg_url` | `()` | 取得適合 LangGraph Postgres Saver 使用的連線字串。 |
| `_make_llm` | `()` | 初始化 `ChatGoogleGenerativeAI`。 |

## 圖流程 (Flow)

```text
START
  │
  ▼
fetch_context
  │
  ├─▶ technical_analyst ──┐
  ├─▶ sentiment_analyst ──┼─▶ (Parallel)
  └─▶ risk_analyst ──────┘
  │
  ▼
debate_init ────┐ (Circuit Breaker: Risk HOLD + high confidence)
  │             │
  ▼             │
bull_researcher ◄─┘
  ▲     │
  │     ▼
  └── bear_researcher (Max N rounds)
  │
  ▼
research_manager
  │
  ▼
execute_or_preview
  │
  ▼
persist_result
  │
  ▼
END
```

## 條件路由邏輯

- **辯論輪數控制**：由 `bear_researcher` 判斷當前輪數是否達到 `settings.ai_max_debate_rounds`。
- **熔斷跳轉**：在 `debate_init` 判斷是否需要跳過辯論直接進入 `research_manager`。
