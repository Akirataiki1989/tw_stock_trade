# app/agent/memory.py

## 用途

管理 LangGraph Agent 的長期記憶 (Vector Store) 與短期記憶 (Checkpointer)。實作基於 PostgreSQL 的持久化方案。

## 函式

| 函式 | 簽名 | 說明 |
|------|------|------|
| `save_pattern` | `(store, symbol, content)` | 將分析結果存入向量儲存，含 metadata。 |
| `search_patterns` | `(store, symbol, query)` | 搜尋特定標的的相似記憶。 |
| `format_memories` | `(items)` | 將搜尋結果格式化為提示詞友善的字串。 |
| `make_prod_store` | `(url, embed_fn)` | 建立生產環境用的 `AsyncPostgresStore` (pgvector)。 |
| `make_prod_checkpointer` | `(url)` | 建立生產環境用的 `AsyncPostgresSaver`。 |

## 重要實作細節

### Score=None 修正
在某些 `InMemoryStore` 實作中，搜尋結果的 `score` 可能為 `None`，導致排序錯誤。生產環境已透過 `AsyncPostgresStore` 與 pgvector 確保搜尋穩定，並在應用層過濾 `similarity_threshold`。

## 生產環境初始化 Pattern

必須在 `startup` 階段初始化，並管理非同步 Context Manager：

```python
# app/worker.py 範例
store = AsyncPostgresStore.from_conn_string(url, embed_fn)
await store._cm.__aenter__()  # 必須手動進入 CM
ctx["store"] = store
```
在 `shutdown` 階段：
```python
await ctx["store"]._cm.__aexit__(None, None, None)
```
