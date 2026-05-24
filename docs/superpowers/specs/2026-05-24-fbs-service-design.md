# FBS Service Design Spec

> 建立日期：2026-05-24  
> 狀態：已核准，待實作

---

## 背景

`app/services/fbs.py` 是 FBS Fubon Neo SDK 的封裝層，負責：
1. 管理 SDK 連線生命週期（singleton）
2. 為 ARQ Worker 提供背景同步方法（存入 DB）
3. 為 FastAPI endpoint 提供 on-demand 查詢方法（不存 DB）

FBS SDK（`fubon_neo`）為**同步 API**，所有呼叫一律透過 `asyncio.to_thread()` 包裝後在 async context 使用。

---

## 範圍

本次實作包含：
1. `trading.watchlist` 資料表（新 migration `0002_add_watchlist.py`）
2. `Watchlist` ORM class（加入 `app/models/portfolio.py`）
3. `app/services/fbs.py`（`FbsClient` class + singleton）

---

## 一、新增 DB 表：`trading.watchlist`

### 欄位規格

| 欄位 | 型別 | 說明 |
|------|------|------|
| `id` | `BIGINT PK autoincrement` | 主鍵 |
| `user_id` | `UUID FK → public.users.id ON DELETE CASCADE` | 所有者 |
| `symbol` | `VARCHAR(10) FK → market.instruments.symbol` | 關注股票代號 |
| `added_at` | `TIMESTAMPTZ server_default=now()` | 加入時間 |
| UNIQUE | `(user_id, symbol)` | 同用戶不重複 |

### 設計決策
- `holdings` 與 `watchlist` **允許持有相同 symbol**（語意不同：持有 vs. 追蹤）
- 重複請求問題在 ARQ Worker 查詢層以 SQL `UNION`（非 `UNION ALL`）去重解決

---

## 二、`FbsClient` 架構

### 檔案位置
`app/services/fbs.py`

### Class 設計

```python
class FbsClient:
    _sdk: FubonSDK | None
    _rest: Any | None  # build_rest_client 回傳型別

    # 連線管理（同步，供 ARQ on_startup/on_shutdown 呼叫）
    def connect(self) -> None
    def disconnect(self) -> None
    def is_connected(self) -> bool

    # 背景同步（async，存 DB，供 ARQ Worker 呼叫）
    async def sync_instruments(self, db: AsyncSession) -> int
    async def sync_quote(self, db: AsyncSession, symbol: str) -> bool
    async def sync_intraday_candles(self, db: AsyncSession, symbol: str, timeframe: str) -> int
    async def sync_historical_candles(
        self, db: AsyncSession, symbol: str, timeframe: str,
        from_date: date, to_date: date
    ) -> int

    # On-demand 查詢（async，不存 DB，供 FastAPI endpoint 呼叫）
    async def fetch_quote(self, symbol: str) -> dict | None
    async def fetch_candles(
        self, symbol: str, timeframe: str,
        from_date: date | None, to_date: date | None
    ) -> list[dict]

fbs_client = FbsClient()  # 模組層級 singleton
```

---

## 三、各方法資料流

### `connect()`
```
sdk = FubonSDK()
accounts = sdk.login(account, password, cert_path)
→ accounts.is_success 為 False 時拋 RuntimeError
token = sdk.exchange_realtime_token()
self._rest = build_rest_client(token)
```

### `sync_instruments(db)`
```
data = await to_thread(rest.stock.intraday.tickers, type="EQUITY")
→ 批次 INSERT INTO market.instruments ON CONFLICT (symbol) DO UPDATE
→ 回傳寫入筆數
```
**觸發時機**：每日開盤前（ARQ 排程）

### `sync_quote(db, symbol)`
```
data = await to_thread(rest.stock.intraday.quote, symbol=symbol)
→ INSERT INTO market.market_quotes ON CONFLICT (symbol) DO UPDATE SET ...fetched_at=now()
→ 成功回傳 True；429 或資料無效回傳 False（記 warning log，不拋例外）
```
**觸發時機**：盤中每分鐘，對 holdings ∪ watchlist 依序呼叫

### `sync_intraday_candles(db, symbol, timeframe)`
```
data = await to_thread(rest.stock.intraday.candles, symbol=symbol, timeframe=timeframe)
→ INSERT INTO market.intraday_candles ON CONFLICT (symbol, timeframe, ts) DO NOTHING
  （API 回傳今日全部 K 棒，已存在的不覆蓋，新增的才寫入）
→ 回傳寫入筆數
```

### `sync_historical_candles(db, symbol, timeframe, from_date, to_date)`
```
data = await to_thread(
    rest.stock.historical.candles,
    symbol=symbol, from=from_date, to=to_date,
    timeframe=timeframe, fields="open,high,low,close,volume,turnover,change"
)
→ INSERT INTO market.historical_candles ON CONFLICT (symbol, timeframe, date) DO UPDATE
  （補資料時覆蓋，確保正確性）
→ 回傳寫入筆數
```
**觸發時機**：每日盤後（ARQ 排程）

### `fetch_quote(symbol)` / `fetch_candles(...)`
```
直接呼叫 SDK → 回傳 dict / list，不寫 DB
供 FastAPI /market/search 預覽、/market/quote/{symbol} DB miss 時使用
```

---

## 四、錯誤處理

| 情況 | 處理方式 |
|------|---------|
| 登入失敗 | `connect()` 拋 `RuntimeError`，ARQ on_startup 失敗，Worker 不啟動 |
| HTTP 429 | `logger.warning` 記錄 symbol，`sync_quote` 回傳 `False`，其他 `sync_*` 靜默跳過 |
| 其他 SDK 例外 | 往上拋，讓 ARQ task 的重試機制處理 |
| Token 過期 | 官方文件未提及有效期限制，目前不實作定時刷新；若未來出現問題再加 |

---

## 五、ARQ Worker 整合點

| 呼叫方 | 方法 | 時機 |
|--------|------|------|
| ARQ `on_startup` | `fbs_client.connect()` | Worker 程序啟動 |
| ARQ `on_shutdown` | `fbs_client.disconnect()` | Worker 程序結束 |
| ARQ task `sync_all_instruments` | `sync_instruments()` | 每日 08:00 |
| ARQ task `sync_all_quotes` | `sync_quote()` × holdings∪watchlist | 盤中每分鐘 |
| ARQ task `sync_all_historical` | `sync_historical_candles()` × holdings∪watchlist | 每日 15:30 後 |
| FastAPI `/market/quote/{symbol}` | 優先查 DB，miss 時 `fetch_quote()` | 即時 |
| FastAPI `/market/search` 預覽 | `fetch_quote()` + `fetch_candles()` | 即時 |

---

## 六、速率限制分析

| API 類型 | 限制 | 預估使用量（70 支） | 使用率 |
|----------|------|------------------|--------|
| 日內行情 | 300 次/分鐘 | ~70 次/分鐘 | 23% |
| 歷史行情 | 60 次/分鐘 | ~70 次/日（盤後批次） | 極低 |

**結論**：正常規模（70 支以內）不會觸發 429；防禦性 try/except 僅作保險。

---

## 七、不在本次範圍

- ARQ Worker 任務定義（`app/worker.py`）→ Step 5
- WebSocket 即時推送 → Step 7
- ETF type 支援：實作時直接測試 `intraday.ticker("00940")`；若 SDK 支援則 `tickers()` 可加 `type="ETF"` 參數一併同步
