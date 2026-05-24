# FBS Fubon Neo SDK 使用指南

> 最後更新：2026-05-23  
> 文件來源：實際測試驗證（fubon_neo 2.2.8）

---

## 套件資訊

- whl 路徑：`/volume1/web/codeserver/fubon_neo-2.2.8-cp37-abi3-manylinux_2_17_x86_64.manylinux2014_x86_64.whl`
- 安裝方式：`uv add /volume1/web/codeserver/fubon_neo-2.2.8-....whl`
- 憑證路徑：`/volume1/web/cert/F128147584.pfx`

---

## 初始化與登入

```python
from fubon_neo.sdk import FubonSDK
from fubon_neo.adapter import build_rest_client

sdk = FubonSDK()

# 登入（cert 為 .pfx 憑證路徑）
accounts = sdk.login(account, password, cert_path)
# accounts.is_success: bool
# accounts.data[0]: Account { name, branch_no, account, account_type }

account_obj = accounts.data[0]

# 取得 market data token（不傳參數）
token = sdk.exchange_realtime_token()

# 建立 REST client
rest = build_rest_client(token)
# rest.stock      → 股票市場資料
# rest.futopt     → 期貨選擇權（本專案不使用）
# rest.options    → 選擇權
```

---

## SDK 模組結構

| 屬性 | 類型 | 用途 |
|------|------|------|
| `sdk.stock` | `Stock` | **股票交易**（place_order、cancel_order 等），非市場資料 |
| `sdk.accounting` | `Accounting` | 帳務查詢 |
| `sdk.futopt` | `Futopt` | 期貨交易 |
| `rest.stock` | `RestClientFactory.stock` | **股票市場資料**（本專案使用此處） |

> ⚠️ `sdk.stock` 是交易模組；市場資料要用 `rest.stock`（透過 `build_rest_client` 建立）

---

## 市場資料 API

### `rest.stock.intraday` — 盤中資料

#### 取得全部股票列表（用於同步 instruments）
```python
result = rest.stock.intraday.tickers(type="EQUITY")
# result: { 'data': [ {'symbol', 'name', 'industry'}, ... ] }
# 共 1568 筆（TWSE + TPEx）
```

#### 取得單一股票基本資料
```python
result = rest.stock.intraday.ticker(symbol="2330")
# {
#   'symbol': '2330', 'name': '台積電',
#   'industry': '24', 'securityType': '01',
#   'exchange': 'TWSE', 'market': 'TSE',
#   'referencePrice': 2230, 'limitUpPrice': 2450, 'limitDownPrice': 2010,
#   'canDayTrade': True, 'canBuyDayTrade': True,
#   'isAttention': False, 'isDisposition': False,
#   'boardLot': 1000, 'tradingCurrency': 'TWD',
#   'previousClose': 2230
# }
```

#### 取得即時報價
```python
result = rest.stock.intraday.quote(symbol="2330")
# {
#   'symbol': '2330', 'name': '台積電',
#   'referencePrice': 2230, 'previousClose': 2230,
#   'openPrice': 2245, 'highPrice': 2260, 'lowPrice': 2225,
#   'closePrice': 2255, 'lastPrice': 2255, 'lastSize': 3821, 'avgPrice': 2243.86,
#   'change': 25, 'changePercent': 1.12, 'amplitude': 1.57,
#   'bids': [{'price': 2255, 'size': 756}, ...],   # 五檔委買
#   'asks': [{'price': 2260, 'size': 397}, ...],   # 五檔委賣
#   'total': {'tradeValue': ..., 'tradeVolume': 24324, 'transaction': 6384, ...},
#   'isClose': True
# }
```

#### 取得盤中K線
```python
result = rest.stock.intraday.candles(symbol="2330", timeframe="1")
# timeframe: "1" / "5" / "10" / "15" / "30" / "60"
# result['data']: [
#   {
#     'date': '2026-05-22T09:00:00.000+08:00',  # ⚠️ 欄位名稱是 "date"，不是 "time"
#     'open': 100, 'high': 105, 'low': 99, 'close': 103,
#     'volume': 500, 'average': 102.0
#   }, ...
# ]
```

---

### `rest.stock.historical` — 歷史資料

#### 取得歷史K線
```python
result = rest.stock.historical.candles(**{
    "symbol": "2330",
    "from": "2026-01-01",
    "to": "2026-05-23",
    "timeframe": "D",          # D / W / M
    "fields": "open,high,low,close,volume,turnover,change",
})
# result['data']: [
#   {'date': '2026-05-22', 'open': 2245, 'high': 2260,
#    'low': 2225, 'close': 2255, 'volume': 26823133,
#    'turnover': 60188140377, 'change': 25},
#   ...
# ]
# sort 預設 'desc'（最新優先）
```

---

## 注意事項

- `sdk.exchange_realtime_token()` **不傳任何參數**
- REST client 為**同步 API**，設計供 ARQ Worker 呼叫；在 FastAPI async context 需用 `asyncio.to_thread()`
- Token 有效期未知，官方文件無說明，目前不主動刷新
- `volume` 單位：歷史K線為股（shares），盤中視 type 而定
- 歷史K線最多查 1 年，超過需分批查詢
- WebSocket 即時推送走 `fubon_neo.adapter.WebSocketStockClientWrapper`（Step 7 待實作）
- **`isClose: True`**：`intraday.quote` 回傳此旗標表示今日休市（國定假日、颱風假等）；Worker 以 `fetch_quote("2330")` 作為 isClose probe，比靜態假日行事曆更可靠
- **Segmentation fault on process exit**：SDK C extension 已知問題，僅在一次性腳本退出時出現，ARQ Worker 長跑環境不受影響，無需處理
