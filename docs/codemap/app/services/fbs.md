# app/services/fbs.py

**用途**：FBS Fubon Neo SDK（fubon_neo 2.2.8）封裝層。提供連線管理、背景同步方法與 on-demand 查詢方法。

## 模組層級 Singleton

```python
fbs_client = FbsClient()  # ARQ Worker 與 FastAPI endpoint import 此物件
```

## Class：FbsClient

### 連線管理（同步方法，供 ARQ on_startup/on_shutdown）

| 方法 | 說明 |
|------|------|
| `connect()` | `FubonSDK.login()` + `exchange_realtime_token()` + `build_rest_client()`；失敗拋 `RuntimeError` |
| `disconnect()` | 清空 `_sdk` / `_rest`（SDK 無明確 logout） |
| `is_connected() -> bool` | 檢查 `_sdk` 與 `_rest` 是否非 None |

### 背景同步（async，存 DB，供 ARQ Worker 呼叫）

| 方法 | 說明 | Upsert 策略 |
|------|------|------------|
| `sync_instruments(db) -> int` | 全量同步 `market.instruments`（FBS `tickers(type="EQUITY")`，~1568 筆） | ON CONFLICT DO UPDATE |
| `sync_quote(db, symbol) -> bool` | 單支 quote → `market.market_quotes`；429 回傳 False | ON CONFLICT DO UPDATE |
| `sync_intraday_candles(db, symbol, timeframe) -> int` | 今日全部 K 棒 → `market.intraday_candles` | ON CONFLICT DO NOTHING |
| `sync_historical_candles(db, symbol, timeframe, from_date, to_date) -> int` | 歷史 K 棒 → `market.historical_candles` | ON CONFLICT DO UPDATE |

### On-demand 查詢（async，不存 DB，供 FastAPI endpoint）

| 方法 | 說明 |
|------|------|
| `fetch_quote(symbol) -> dict \| None` | 即時拉取單支報價；例外時回傳 None |
| `fetch_candles(symbol, timeframe, from_date, to_date) -> list[dict]` | 即時拉取 K 棒；timeframe D/W/M 走 historical，其餘走 intraday；例外時回傳 `[]` |

## 技術備註

- FBS SDK 為同步 API，所有 SDK 呼叫透過 `asyncio.to_thread()` 包裝
- 盤中 K 棒 timestamp 欄位名稱為 `"date"`（格式：`"2026-05-22T09:00:00.000+08:00"`）
- 進程退出時 SDK C extension 可能出現 Segmentation fault（已知問題，ARQ Worker 長跑環境不受影響）
- 429 防禦：exception message 含 `"429"` 或 `"rate limit"` 時靜默跳過，不拋例外

## 依賴

- `fubon_neo.sdk.FubonSDK`、`fubon_neo.adapter.build_rest_client`
- `app.core.config.settings`（讀取 `fbs_account`、`fbs_password`、`fbs_cert_path`）
- `app.models.market`（Instrument、MarketQuote、IntradayCandle、HistoricalCandle）
- `sqlalchemy.dialects.postgresql.insert`（pg_insert，用於 ON CONFLICT upsert）
