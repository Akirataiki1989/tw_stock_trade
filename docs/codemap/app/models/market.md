# app/models/market.py

**用途**：`market` schema 全部 ORM model。

## Classes

| Class | Table | 說明 |
|-------|-------|------|
| `Instrument` | `market.instruments` | 股票基本資料，`symbol` PK |
| `MarketQuote` | `market.market_quotes` | 即時報價快取，`symbol` PK + FK → `instruments` |
| `IntradayCandle` | `market.intraday_candles` | 盤中K線，`id` BIGSERIAL PK |
| `HistoricalCandle` | `market.historical_candles` | 歷史K線，`id` BIGSERIAL PK |

> FK / UNIQUE / INDEX / 欄位規格 → [`schema/orm.md`](../../../schema/orm.md)

## 依賴

- `app.models.base.Base`
