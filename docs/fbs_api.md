# FBS Fubon Neo API 規格

文件來源：https://www.fbs.com.tw/TradeAPI/docs/market-data/http-api/getting-started

## 認證
- 使用 `fubon_neo` SDK 登入，需要帳號、密碼、數位憑證（.pfx）
- 憑證路徑掛載於 Docker volume（只讀），不進 git
- API Key 透過 Fernet 加密存 DB

## Intraday Endpoints

### GET /intraday/tickers
查詢股票列表。

Request params:
- `type` *: `EQUITY` / `INDEX` / `WARRANT` / `ODDLOT`
- `exchange`: `TWSE` / `TPEx`
- `market`: `TSE` / `OTC` / `ESB` / `TIB` / `PSB`
- `industry`: 產業別代碼
- `isNormal` / `isAttention` / `isDisposition` / `isHalted`: boolean 篩選

Response `data[]`:
- `symbol`: 股票代碼
- `name`: 股票簡稱

### GET /intraday/ticker/{symbol}
取得單一股票基本資料。

Response 主要欄位：
- `symbol`, `name`, `nameEn`, `industry`, `securityType`
- `referencePrice`, `limitUpPrice`, `limitDownPrice`
- `canDayTrade`, `canBuyDayTrade`
- `boardLot`, `tradingCurrency`
- `isAttention`, `isDisposition`
- `previousClose`

### GET /intraday/quote/{symbol}
取得即時報價。

Response 主要欄位：
- `referencePrice`, `previousClose`
- `openPrice`, `openTime`, `highPrice`, `highTime`, `lowPrice`, `lowTime`
- `closePrice`, `closeTime`, `lastPrice`, `lastSize`, `avgPrice`
- `change`, `changePercent`, `amplitude`
- `bids[]`, `asks[]`（委買委賣五檔）
- `total`（成交統計物件）
- `isLimitUpPrice`, `isLimitDownPrice`, `isTrial`, `isOpen`, `isClose`
- `lastUpdated`

### GET /intraday/candles/{symbol}
取得盤中 K 線。

Request params:
- `type`: `oddlot`（零股）
- `timeframe`: `1` / `5` / `10` / `15` / `30` / `60`（分鐘）
- `sort`: `asc`（預設）/ `desc`

Response `data[]`:
- `open`, `high`, `low`, `close`
- `volume`（整股：張；零股：股）
- `average`（均價）

### GET /intraday/trades/{symbol}
取得成交明細。

### GET /intraday/volumes/{symbol}
取得分價量表。

## Snapshot Endpoints

### GET /snapshot/quotes/{market}
全市場即時報價快照。

### GET /snapshot/movers/{market}
漲跌幅排行。

### GET /snapshot/actives/{market}
成交量/額排行。

## Historical Endpoints

### GET /historical/candles/{symbol}
取得歷史 K 線（最多 1 年）。

Request params:
- `from`, `to`: `yyyy-MM-dd`
- `timeframe`: `1`/`5`/`10`/`15`/`30`/`60`/`D`/`W`/`M`
- `adjusted`: `true`/`false`（還原股價）
- `fields`: `open,high,low,close,volume,turnover,change`
- `sort`: `desc`（預設）/ `asc`

Response `data[]`:
- `date`
- `open`, `high`, `low`, `close`
- `volume`（張）
- `turnover`（成交額）
- `change`（漲跌）

### GET /historical/stats/{symbol}
取得近 52 週股價數據。

## 注意事項
- volume 單位：整股為「張」，盤中零股為「股」，指數為「成交金額」
- 歷史 K 線最多查 1 年，超過需分批查詢
- WebSocket 即時推送另有獨立文件（待補）
