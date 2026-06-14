# Changelog 索引

各版本更新重點一覽。點擊版本號查看詳細說明。

| 版本 | 日期 | 重點摘要 |
|------|------|---------|
| [v0.6.0](v0.6.0.md) | 2026-06-14 | Step 6 完成：LangGraph Agent（多分析師+Bull/Bear辯論+AsyncPostgresSaver/pgvector記憶）、4 個 AI cron tasks |
| [v0.5.5](v0.5.5.md) | 2026-05-25 | Step 5.5 完成：外部數據同步（yfinance + TWSE T86/MI_MARGN API）、3 個新表（us_market_daily、institutional_flows、margin_trading）、3 個 cron tasks（08:30/16:00/16:05） |
| [v0.5.0](v0.5.0.md) | 2026-05-24 | Step 4 完成：FbsClient（FBS SDK 封裝）、trading.watchlist 表、Python 3.12 鎖定 |
| [v0.1.0](v0.1.0.md) | 2026-05-18 | 初始架構：DB schema（3 層 9 表）、SQLAlchemy models（GENERATED ALWAYS AS）、pydantic-settings config、Alembic async migration |

---

## 版本規則

- **patch**（0.1.x）：bug fix、文件更新、小型重構
- **minor**（0.x.0）：新增功能模組（每完成一個 roadmap Step）
- **major**（x.0.0）：重大架構變更

## 下一版預計（v0.7.0）

待 WebSocket 推送完成後發布。
