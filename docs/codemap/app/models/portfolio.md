# app/models/portfolio.py

**用途**：`trading` schema 全部 ORM model。

## Classes

| Class | Table | 說明 |
|-------|-------|------|
| `Portfolio` | `trading.portfolios` | 每用戶一筆，現金與總資產 |
| `Holding` | `trading.holdings` | 持倉，含 GENERATED 市值 / 損益欄位 |
| `Trade` | `trading.trades` | 每筆買賣紀錄 |
| `AiDecision` | `trading.ai_decisions` | LangGraph 決策快照 |
| `DailyPerformance` | `trading.daily_performance` | 每日績效紀錄 |

> FK / UNIQUE / INDEX / GENERATED 欄位規格 → [`schema/orm.md`](../../../schema/orm.md)

## 依賴

- `app.models.base.Base`
