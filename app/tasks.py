"""app/tasks.py — ARQ cron task 函式與共用 helper。

所有 cron task 接收 ARQ 提供的 ctx: dict，從中取得 db_factory（async_sessionmaker）。
"""
import logging
import time as _time
import traceback as tb
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.market import HistoricalCandle
from app.services.fbs import fbs_client

# ── 自訂 TRACE 層級（level=5，低於 DEBUG=10）────────────────────────────────

TRACE = 5
logging.addLevelName(TRACE, "TRACE")


def _trace(self, msg, *args, **kwargs):  # type: ignore[override]
    if self.isEnabledFor(TRACE):
        self._log(TRACE, msg, args, **kwargs)


logging.Logger.trace = _trace  # type: ignore[attr-defined]

# ── logger ────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── helper 函式 ────────────────────────────────────────────────────────────────

_TZ = ZoneInfo("Asia/Taipei")


def is_trading_hours() -> bool:
    """台股交易時間：週一至週五 09:00–13:30（台北時間）。"""
    now = datetime.now(_TZ)
    if now.weekday() >= 5:  # 5=Sat, 6=Sun
        return False
    return time(9, 0) <= now.time() <= time(13, 30)


async def get_watch_symbols(db: AsyncSession) -> list[str]:
    """查詢 holdings ∪ watchlist 的 symbol 清單（SQL UNION 自動去重）。"""
    result = await db.execute(
        text("""
            SELECT symbol FROM trading.holdings
            UNION
            SELECT symbol FROM trading.watchlist
        """)
    )
    return [row[0] for row in result.fetchall()]


# ── cron tasks ────────────────────────────────────────────────────────────────


async def task_sync_instruments(ctx: dict) -> None:
    """每日 08:30：全量同步 market.instruments。"""
    t0 = _time.monotonic()
    logger.info("task_sync_instruments: started")
    async with ctx["db_factory"]() as db:
        try:
            n = await fbs_client.sync_instruments(db)
            elapsed = _time.monotonic() - t0
            logger.info("task_sync_instruments: done in %.1fs, wrote=%d instruments", elapsed, n)
        except Exception as e:
            logger.error("task_sync_instruments: unexpected error=%s", e)
            logger.trace(  # type: ignore[attr-defined]
                "task_sync_instruments detail: fbs_connected=%s\n%s",
                fbs_client.is_connected(), tb.format_exc(),
            )
            raise


async def task_sync_quotes(ctx: dict) -> None:
    """每分鐘：同步 holdings∪watchlist 的即時報價（盤中限定）。"""
    if not is_trading_hours():
        logger.info("task_sync_quotes: outside trading hours, skipped")
        return

    # isClose probe：颱風假、國定假日等非交易日判斷
    probe = await fbs_client.fetch_quote("2330")
    if probe and probe.get("isClose"):
        logger.info("task_sync_quotes: market closed (isClose=True), skipped")
        return

    t0 = _time.monotonic()
    async with ctx["db_factory"]() as db:
        symbols = await get_watch_symbols(db)
        logger.info("task_sync_quotes: started, symbols=%d", len(symbols))
        ok = fail = 0
        for symbol in symbols:
            try:
                logger.trace(  # type: ignore[attr-defined]
                    "task_sync_quotes: FBS request symbol=%s method=intraday.quote", symbol
                )
                result = await fbs_client.sync_quote(db, symbol)
                if result:
                    logger.debug("task_sync_quotes: symbol=%s ok", symbol)
                    ok += 1
                else:
                    logger.warning("task_sync_quotes: symbol=%s failed (429 or empty)", symbol)
                    fail += 1
            except Exception as e:
                logger.error("task_sync_quotes: symbol=%s unexpected error=%s", symbol, e)
                logger.trace(  # type: ignore[attr-defined]
                    "task_sync_quotes detail: symbol=%s fbs_connected=%s\n%s",
                    symbol, fbs_client.is_connected(), tb.format_exc(),
                )
                fail += 1

    elapsed = _time.monotonic() - t0
    logger.info(
        "task_sync_quotes: done in %.1fs, success=%d, failed=%d", elapsed, ok, fail
    )


async def task_sync_intraday_candles(ctx: dict) -> None:
    """每 5 分鐘：同步 holdings∪watchlist 的今日盤中 5 分 K（盤中限定）。"""
    if not is_trading_hours():
        logger.info("task_sync_intraday_candles: outside trading hours, skipped")
        return

    t0 = _time.monotonic()
    async with ctx["db_factory"]() as db:
        symbols = await get_watch_symbols(db)
        logger.info(
            "task_sync_intraday_candles: started, symbols=%d, timeframe=5", len(symbols)
        )
        for symbol in symbols:
            try:
                logger.trace(  # type: ignore[attr-defined]
                    "task_sync_intraday_candles: FBS request symbol=%s tf=5", symbol
                )
                count = await fbs_client.sync_intraday_candles(db, symbol, "5")
                logger.debug(
                    "task_sync_intraday_candles: symbol=%s wrote=%d", symbol, count
                )
            except Exception as e:
                logger.error(
                    "task_sync_intraday_candles: symbol=%s unexpected error=%s", symbol, e
                )
                logger.trace(  # type: ignore[attr-defined]
                    "task_sync_intraday_candles detail: symbol=%s fbs_connected=%s\n%s",
                    symbol, fbs_client.is_connected(), tb.format_exc(),
                )

    elapsed = _time.monotonic() - t0
    logger.info("task_sync_intraday_candles: done in %.1fs, symbols=%d", elapsed, len(symbols))


async def task_sync_historical_candles(ctx: dict) -> None:
    """每日 14:00：增量同步日 K（新 symbol 補 2 年）。"""
    t0 = _time.monotonic()
    async with ctx["db_factory"]() as db:
        symbols = await get_watch_symbols(db)
        logger.info("task_sync_historical_candles: started, symbols=%d", len(symbols))

        for symbol in symbols:
            try:
                last_date: date | None = await db.scalar(
                    select(func.max(HistoricalCandle.date)).where(
                        HistoricalCandle.symbol == symbol,
                        HistoricalCandle.timeframe == "D",
                    )
                )

                to_date = date.today()

                if last_date is None:
                    # 首次載入：補抓 2 年
                    from_date = to_date - timedelta(days=730)
                    logger.info(
                        "task_sync_historical_candles: %s initial load from=%s",
                        symbol, from_date,
                    )
                else:
                    from_date = last_date + timedelta(days=1)
                    if from_date > to_date:
                        logger.debug(
                            "task_sync_historical_candles: %s already up-to-date", symbol
                        )
                        continue

                # FBS 限制單次最多 1 年，超過時拆兩次查詢
                if (to_date - from_date).days > 365:
                    mid = from_date + timedelta(days=365)
                    count1 = await fbs_client.sync_historical_candles(
                        db, symbol, "D", from_date, mid
                    )
                    count2 = await fbs_client.sync_historical_candles(
                        db, symbol, "D", mid + timedelta(days=1), to_date
                    )
                    count = count1 + count2
                else:
                    count = await fbs_client.sync_historical_candles(
                        db, symbol, "D", from_date, to_date
                    )

                logger.info(
                    "task_sync_historical_candles: %s from=%s to=%s wrote=%d",
                    symbol, from_date, to_date, count,
                )

            except Exception as e:
                logger.error(
                    "task_sync_historical_candles: symbol=%s unexpected error=%s", symbol, e
                )
                logger.trace(  # type: ignore[attr-defined]
                    "task_sync_historical_candles detail: symbol=%s fbs_connected=%s\n%s",
                    symbol, fbs_client.is_connected(), tb.format_exc(),
                )

    elapsed = _time.monotonic() - t0
    logger.info("task_sync_historical_candles: done in %.1fs", elapsed)


async def task_clear_intraday_candles(ctx: dict) -> None:
    """每日 14:30：清空全表 market.intraday_candles（每日重建設計）。"""
    async with ctx["db_factory"]() as db:
        await db.execute(text("DELETE FROM market.intraday_candles"))
        await db.commit()
    logger.info("task_clear_intraday_candles: table cleared")





