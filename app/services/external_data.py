"""app/services/external_data.py — 外部數據同步：美股指數 + TWSE 法人籌碼 + 融資融券。

所有 fetch 函式均為 async；yfinance 為同步 API，使用 asyncio.to_thread() 包裝。
TWSE API 以 aiohttp async client 呼叫。
upsert 函式使用 PostgreSQL INSERT ... ON CONFLICT DO UPDATE。
"""

import asyncio
import logging
from datetime import date
from zoneinfo import ZoneInfo

import aiohttp
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.market import InstitutionalFlow, MarginTrading, UsMarketDaily

logger = logging.getLogger(__name__)

_TZ = ZoneInfo("Asia/Taipei")

# ── US Market tickers ──────────────────────────────────────────────────────────

_US_TICKERS = {
    "sp500":   "^GSPC",
    "nasdaq":  "^IXIC",
    "tsm_adr": "TSM",
    "sox":     "^SOX",
    "dxy":     "DX-Y.NYB",
    "us10y":   "^TNX",
}

# ── Pure helpers (no I/O — easy to unit-test) ─────────────────────────────────


def clean_number(s: str) -> int | None:
    """將 TWSE 回傳的數字字串轉為 int。

    規則：
    - 去除逗號（千分位）
    - "－" / "-" / "" → None
    - 負數："-1,234" → -1234
    """
    s = s.strip()
    if s in ("－", "-", "", "---"):
        return None
    try:
        return int(s.replace(",", ""))
    except ValueError:
        logger.warning("clean_number: cannot parse %r", s)
        return None


def parse_institutional_row(fields: list[str], row: list[str]) -> dict | None:
    """將 T86 API 的一列資料（fields + row）解析為 dict。

    回傳 None 表示應跳過（例如「合計」列、非股票列）。

    Key mapping（欄位名 → DB column）：
        外陸資買賣超股數(不含外資自營商) → foreign_net
        投信買進股數                      → trust_buy
        投信賣出股數                      → trust_sell
        投信買賣超股數                    → trust_net
        自營商買賣超股數                  → dealer_net  （第一個符合，為合計）
        三大法人買賣超股數                → total_net
    """
    if len(fields) != len(row):
        return None

    rec = dict(zip(fields, row))

    symbol = rec.get("證券代號", "").strip()
    if not symbol or symbol == "合計":
        return None

    return {
        "symbol": symbol,
        "foreign_net": clean_number(rec.get("外陸資買賣超股數(不含外資自營商)", "-")),
        "trust_buy":   clean_number(rec.get("投信買進股數", "-")),
        "trust_sell":  clean_number(rec.get("投信賣出股數", "-")),
        "trust_net":   clean_number(rec.get("投信買賣超股數", "-")),
        "dealer_net":  clean_number(rec.get("自營商買賣超股數", "-")),
        "total_net":   clean_number(rec.get("三大法人買賣超股數", "-")),
    }


def parse_margin_row(fields: list[str], row: list[str]) -> dict | None:
    """將 MI_MARGN API 的一列資料解析為 dict。

    回傳 None 表示應跳過（合計列或無代號列）。

    Key mapping：
        代號         → symbol
        融資買進     → margin_buy
        融資賣出     → margin_sell
        融資前日餘額 → margin_balance_prev
        融資今日餘額 → margin_balance
        融券買進     → short_buy
        融券賣出     → short_sell
        融券前日餘額 → short_balance_prev
        融券今日餘額 → short_balance
    """
    if len(fields) != len(row):
        return None

    rec = dict(zip(fields, row))

    symbol = rec.get("代號", "").strip()
    if not symbol or symbol == "合計":
        return None

    return {
        "symbol":             symbol,
        "margin_buy":         clean_number(rec.get("買進", "-")),    # 融資買進
        "margin_sell":        clean_number(rec.get("賣出", "-")),    # 融資賣出（第一個）
        "margin_balance_prev": clean_number(rec.get("前日餘額", "-")),
        "margin_balance":     clean_number(rec.get("今日餘額", "-")),
        "short_buy":          None,   # 欄位名重複，見下方說明
        "short_sell":         None,
        "short_balance_prev": None,
        "short_balance":      None,
    }


def parse_margin_row_full(fields: list[str], row: list[str]) -> dict | None:
    """MI_MARGN 完整解析，處理融資/融券欄位名稱重複問題。

    TWSE 回傳的 fields 陣列中，融資與融券共用同名欄位（買進/賣出/前日餘額/今日餘額）。
    解決方式：改用 index 直接取值。

    MI_MARGN tables[1] fields index 對應（共 16 欄）：
        0: 代號, 1: 名稱
        融資: 2=買進, 3=賣出, 4=現金償還, 5=前日餘額, 6=今日餘額, 7=限額
        融券: 8=買進, 9=賣出, 10=現券償還, 11=前日餘額, 12=今日餘額, 13=限額
        14: 資券互抵, 15: 註記
    """
    if len(row) < 14:
        return None

    symbol = row[0].strip()
    if not symbol or symbol == "合計":
        return None

    return {
        "symbol":              symbol,
        "margin_buy":          clean_number(row[2]),
        "margin_sell":         clean_number(row[3]),
        "margin_balance_prev": clean_number(row[5]),
        "margin_balance":      clean_number(row[6]),
        "short_buy":           clean_number(row[8]),
        "short_sell":          clean_number(row[9]),
        "short_balance_prev":  clean_number(row[11]),
        "short_balance":       clean_number(row[12]),
    }


# ── Fetch functions ────────────────────────────────────────────────────────────


def _fetch_us_market_sync() -> dict:
    """同步版本的美股抓取（供 asyncio.to_thread 使用）。

    ⚠️  ^TNX：Yahoo Finance 回傳的是 yield * 10（例如 4.5% → 45.0）。
         us10y_yield 欄位儲存真實 % 值，故除以 10。
         若未來 Yahoo 修正格式，需調整此處。
    """
    import yfinance as yf

    result: dict = {}

    for key, ticker_sym in _US_TICKERS.items():
        try:
            hist = yf.Ticker(ticker_sym).history(period="5d").dropna(subset=["Close"])
            if len(hist) < 2:
                logger.warning("_fetch_us_market_sync: %s 資料不足 2 筆", ticker_sym)
                result[key] = {"close": None, "change": None}
                continue

            close = float(hist["Close"].iloc[-1])
            prev  = float(hist["Close"].iloc[-2])
            pct   = round((close - prev) / prev * 100, 4) if prev else None

            result[key] = {"close": round(close, 4), "change": pct}
        except Exception as e:
            logger.error("_fetch_us_market_sync: %s error=%s", ticker_sym, e)
            result[key] = {"close": None, "change": None}

    # 修正 ^TNX 單位（Yahoo 回傳 yield×10）
    if result.get("us10y", {}).get("close") is not None:
        raw_close = result["us10y"]["close"]
        if result["us10y"]["change"]:
            raw_prev  = raw_close / (1 + result["us10y"]["change"] / 100)
        else:
            raw_prev = raw_close
        actual_yield = round(raw_close / 10, 3)
        actual_prev  = round(raw_prev / 10, 3)
        change_bps   = round((actual_yield - actual_prev) * 100, 1)
        result["us10y"] = {"close": actual_yield, "change_bps": change_bps}

    return result


async def fetch_us_market_data() -> dict:
    """非同步包裝：在 thread pool 執行 yfinance 查詢。"""
    return await asyncio.to_thread(_fetch_us_market_sync)


async def fetch_twse_institutional() -> tuple[date | None, list[dict]]:
    """抓取 TWSE T86 三大法人買賣超（全市場）。

    回傳 (trade_date, records_list)。
    若 stat != "OK" 或非交易日，回傳 (None, [])。
    """
    url = "https://www.twse.com.tw/rwd/zh/fund/T86"
    params = {"response": "json", "selectType": "ALLBUT0999"}
    timeout = aiohttp.ClientTimeout(total=30)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url, params=params) as resp:
            resp.raise_for_status()
            data = await resp.json(content_type=None)

    if data.get("stat") != "OK":
        logger.warning("fetch_twse_institutional: stat=%s (非交易日或無資料)", data.get("stat"))
        return None, []

    raw_date = data.get("date", "")   # "20260525"
    if len(raw_date) != 8:
        return None, []
    trade_date = date(int(raw_date[:4]), int(raw_date[4:6]), int(raw_date[6:]))

    fields = data.get("fields", [])
    rows   = data.get("data", [])

    records = []
    for row in rows:
        parsed = parse_institutional_row(fields, row)
        if parsed:
            records.append(parsed)

    logger.info("fetch_twse_institutional: date=%s, records=%d", trade_date, len(records))
    return trade_date, records


async def fetch_twse_margin() -> tuple[date | None, list[dict]]:
    """抓取 TWSE MI_MARGN 融資融券餘額（全市場）。

    MI_MARGN 的 per-stock 資料在 tables[1]，欄位有重複名稱問題，
    故使用 parse_margin_row_full（index-based）解析。

    回傳 (trade_date, records_list)。
    """
    url = "https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN"
    params = {"response": "json", "selectType": "STOCK"}
    timeout = aiohttp.ClientTimeout(total=30)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url, params=params) as resp:
            resp.raise_for_status()
            data = await resp.json(content_type=None)

    if data.get("stat") != "OK":
        logger.warning("fetch_twse_margin: stat=%s (非交易日或無資料)", data.get("stat"))
        return None, []

    raw_date = data.get("date", "")
    if len(raw_date) != 8:
        return None, []
    trade_date = date(int(raw_date[:4]), int(raw_date[4:6]), int(raw_date[6:]))

    tables = data.get("tables", [])
    if len(tables) < 2:
        logger.warning("fetch_twse_margin: tables 結構異常，長度=%d", len(tables))
        return trade_date, []

    stock_table = tables[1]   # index 1 = 股票融資融券彙總
    fields = stock_table.get("fields", [])
    rows   = stock_table.get("data", [])

    records = []
    for row in rows:
        parsed = parse_margin_row_full(fields, row)
        if parsed:
            records.append(parsed)

    logger.info("fetch_twse_margin: date=%s, records=%d", trade_date, len(records))
    return trade_date, records


# ── DB upsert functions ────────────────────────────────────────────────────────


async def upsert_us_market_daily(db: AsyncSession, data: dict, trade_date: date) -> None:
    """將美股指數數據 upsert 到 market.us_market_daily。"""
    row = {
        "date":           trade_date,
        "sp500_close":    data.get("sp500", {}).get("close"),
        "sp500_change":   data.get("sp500", {}).get("change"),
        "nasdaq_close":   data.get("nasdaq", {}).get("close"),
        "nasdaq_change":  data.get("nasdaq", {}).get("change"),
        "tsm_adr_close":  data.get("tsm_adr", {}).get("close"),
        "tsm_adr_change": data.get("tsm_adr", {}).get("change"),
        "sox_close":      data.get("sox", {}).get("close"),
        "sox_change":     data.get("sox", {}).get("change"),
        "dxy_close":      data.get("dxy", {}).get("close"),
        "dxy_change":     data.get("dxy", {}).get("change"),
        "us10y_yield":    data.get("us10y", {}).get("close"),
        "us10y_change_bps": data.get("us10y", {}).get("change_bps"),
    }

    stmt = (
        insert(UsMarketDaily)
        .values(**row)
        .on_conflict_do_update(
            index_elements=["date"],
            set_={k: v for k, v in row.items() if k != "date"},
        )
    )
    await db.execute(stmt)
    await db.commit()


async def upsert_institutional_flows(
    db: AsyncSession, records: list[dict], trade_date: date
) -> int:
    """批次 upsert 三大法人數據。回傳寫入筆數。"""
    if not records:
        return 0

    rows = [{"date": trade_date, **r} for r in records]

    stmt = (
        insert(InstitutionalFlow)
        .values(rows)
        .on_conflict_do_update(
            index_elements=["date", "symbol"],
            set_={
                "foreign_net": insert(InstitutionalFlow).excluded.foreign_net,
                "trust_buy":   insert(InstitutionalFlow).excluded.trust_buy,
                "trust_sell":  insert(InstitutionalFlow).excluded.trust_sell,
                "trust_net":   insert(InstitutionalFlow).excluded.trust_net,
                "dealer_net":  insert(InstitutionalFlow).excluded.dealer_net,
                "total_net":   insert(InstitutionalFlow).excluded.total_net,
            },
        )
    )
    await db.execute(stmt)
    await db.commit()
    return len(rows)


async def upsert_margin_trading(
    db: AsyncSession, records: list[dict], trade_date: date
) -> int:
    """批次 upsert 融資融券數據。回傳寫入筆數。"""
    if not records:
        return 0

    rows = [{"date": trade_date, **r} for r in records]

    stmt = (
        insert(MarginTrading)
        .values(rows)
        .on_conflict_do_update(
            index_elements=["date", "symbol"],
            set_={
                "margin_buy":          insert(MarginTrading).excluded.margin_buy,
                "margin_sell":         insert(MarginTrading).excluded.margin_sell,
                "margin_balance_prev": insert(MarginTrading).excluded.margin_balance_prev,
                "margin_balance":      insert(MarginTrading).excluded.margin_balance,
                "short_buy":           insert(MarginTrading).excluded.short_buy,
                "short_sell":          insert(MarginTrading).excluded.short_sell,
                "short_balance_prev":  insert(MarginTrading).excluded.short_balance_prev,
                "short_balance":       insert(MarginTrading).excluded.short_balance,
            },
        )
    )
    await db.execute(stmt)
    await db.commit()
    return len(rows)
