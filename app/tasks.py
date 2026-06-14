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
from app.services.external_data import (
    fetch_twse_institutional,
    fetch_twse_margin,
    fetch_us_market_data,
    upsert_institutional_flows,
    upsert_margin_trading,
    upsert_us_market_daily,
)
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


async def task_sync_us_market(ctx: dict) -> None:
    """每日 08:30：同步美股主要指數昨收數據（開盤前備妥，LangGraph fetch_context 節點讀取）。"""
    t0 = _time.monotonic()
    logger.info("task_sync_us_market: started")
    try:
        data = await fetch_us_market_data()
        trade_date = datetime.now(_TZ).date()
        async with ctx["db_factory"]() as db:
            await upsert_us_market_daily(db, data, trade_date)
        elapsed = _time.monotonic() - t0
        logger.info(
            "task_sync_us_market: done in %.1fs, sp500=%.2f(%+.2f%%)",
            elapsed,
            data.get("sp500", {}).get("close") or 0,
            data.get("sp500", {}).get("change") or 0,
        )
    except Exception as e:
        logger.error("task_sync_us_market: unexpected error=%s", e)
        raise


async def task_sync_institutional_flows(ctx: dict) -> None:
    """每日 16:00：同步 TWSE 三大法人買賣超（全市場，~1000 支股票）。"""
    t0 = _time.monotonic()
    logger.info("task_sync_institutional_flows: started")
    try:
        trade_date, records = await fetch_twse_institutional()
        if not records:
            logger.info("task_sync_institutional_flows: 無資料（非交易日或 API 異常），skipped")
            return
        async with ctx["db_factory"]() as db:
            n = await upsert_institutional_flows(db, records, trade_date)
        elapsed = _time.monotonic() - t0
        logger.info(
            "task_sync_institutional_flows: done in %.1fs, date=%s, wrote=%d",
            elapsed, trade_date, n,
        )
    except Exception as e:
        logger.error("task_sync_institutional_flows: unexpected error=%s", e)
        raise


async def task_sync_margin_trading(ctx: dict) -> None:
    """每日 16:05：同步 TWSE 融資融券餘額（全市場，~700 支股票）。"""
    t0 = _time.monotonic()
    logger.info("task_sync_margin_trading: started")
    try:
        trade_date, records = await fetch_twse_margin()
        if not records:
            logger.info("task_sync_margin_trading: 無資料（非交易日或 API 異常），skipped")
            return
        async with ctx["db_factory"]() as db:
            n = await upsert_margin_trading(db, records, trade_date)
        elapsed = _time.monotonic() - t0
        logger.info(
            "task_sync_margin_trading: done in %.1fs, date=%s, wrote=%d",
            elapsed, trade_date, n,
        )
    except Exception as e:
        logger.error("task_sync_margin_trading: unexpected error=%s", e)
        raise


async def get_ai_interval(db: AsyncSession) -> int:
    """Read ai_interval_minutes from trading.settings. Default: 30."""
    val = await db.scalar(
        text("SELECT value FROM trading.settings WHERE key = 'ai_interval_minutes'")
    )
    return int(val) if val else 30


async def task_maybe_run_ai(ctx: dict) -> None:
    """每分鐘觸發：依 ai_interval_minutes 設定決定是否執行 AI 分析。"""
    import uuid as _uuid
    from app.agent.graph import build_graph
    from app.models.portfolio import Holding, Portfolio
    from sqlalchemy import select as _select

    now = datetime.now(_TZ)
    if not is_trading_hours():
        return

    async with ctx["db_factory"]() as db:
        interval = await get_ai_interval(db)

    if now.minute % interval != 0:
        return

    logger.info("task_maybe_run_ai: interval=%d min, starting at %s", interval, now.strftime("%H:%M"))
    t0 = _time.monotonic()

    graph = build_graph(
        db_factory=ctx["db_factory"],
        checkpointer=ctx["checkpointer"],
        store=ctx["store"],
    )

    async with ctx["db_factory"]() as db:
        portfolios = (await db.execute(_select(Portfolio))).scalars().all()

    ok = fail = 0
    for port in portfolios:
        async with ctx["db_factory"]() as db:
            holdings = (await db.execute(
                _select(Holding).where(Holding.user_id == port.user_id)
            )).scalars().all()

        for h in holdings:
            session_id = str(_uuid.uuid4())
            thread_id = f"ai_{port.user_id}_{h.symbol}_{now.strftime('%Y%m%d_%H%M')}"
            try:
                from app.agent.state import DebateState
                await graph.ainvoke(
                    {
                        "symbol": h.symbol,
                        "user_id": str(port.user_id),
                        "session_id": session_id,
                        "analyst_reports": [],
                        "debate_state": DebateState(bull_history="", bear_history="",
                                                    history="", current_response="", count=0),
                        "final_decision": None,
                        "executed": False,
                        "execution_note": "",
                    },
                    {"configurable": {"thread_id": thread_id}},
                )
                ok += 1
            except Exception as e:
                fail += 1
                logger.error("task_maybe_run_ai: user=%s symbol=%s error=%s",
                             str(port.user_id)[:8], h.symbol, e)

    logger.info("task_maybe_run_ai: done in %.1fs ok=%d fail=%d",
                _time.monotonic() - t0, ok, fail)


async def task_update_trade_outcomes(ctx: dict) -> None:
    """每日 17:00：將 7 天前的 AI 決策損益結果回填至 Store 記憶。"""
    from datetime import timedelta
    from app.agent.memory import NAMESPACE

    store = ctx["store"]
    target_date = datetime.now(_TZ).date() - timedelta(days=7)
    logger.info("task_update_trade_outcomes: backfilling outcomes for %s", target_date)

    async with ctx["db_factory"]() as db:
        rows = (await db.execute(text("""
            SELECT session_id, decisions, created_at
            FROM trading.ai_decisions
            WHERE DATE(created_at AT TIME ZONE 'Asia/Taipei') = :d
        """), {"d": target_date})).fetchall()

    updated = 0
    for row in rows:
        session_id = str(row[0])
        decisions = row[1] or {}
        for symbol, decision in decisions.items():
            entry_price = decision.get("target_price", 0)
            action = decision.get("action", "HOLD")
            if not entry_price or action == "HOLD":
                continue
            async with ctx["db_factory"]() as db:
                current = await db.scalar(text(
                    "SELECT last_price FROM market.market_quotes WHERE symbol=:s"
                ), {"s": symbol})
            if not current:
                continue
            raw_return = (float(current) - entry_price) / entry_price
            outcome = -raw_return if action == "SELL" else raw_return

            all_items = await store.asearch(NAMESPACE, filter={"symbol": symbol}, limit=500)
            for item in all_items:
                if session_id in item.key:
                    await store.aput(NAMESPACE, item.key, {**item.value, "outcome_score": round(outcome, 4)})
                    updated += 1
                    break

    logger.info("task_update_trade_outcomes: updated %d store entries", updated)


async def task_cleanup_checkpoints(ctx: dict) -> None:
    """每日 03:00：刪除 checkpoint_ttl_days 天前的 checkpoint 記錄。"""
    from app.core.config import settings
    ttl = settings.checkpoint_ttl_days
    async with ctx["db_factory"]() as db:
        r = await db.execute(text(
            f"DELETE FROM checkpoints WHERE thread_ts < NOW() - INTERVAL '{ttl} days'"
        ))
        deleted = r.rowcount
        await db.execute(text("""
            DELETE FROM checkpoint_blobs
            WHERE thread_id NOT IN (SELECT thread_id FROM checkpoints)
        """))
        await db.execute(text("""
            DELETE FROM checkpoint_writes
            WHERE thread_id NOT IN (SELECT thread_id FROM checkpoints)
        """))
        await db.commit()
    logger.info("task_cleanup_checkpoints: deleted %d rows older than %d days", deleted, ttl)


async def task_prune_store_memories(ctx: dict) -> None:
    """每週日 02:00：每個 symbol 只保留 top N 筆記憶（按 outcome_score 排序）。"""
    from app.core.config import settings
    from app.agent.memory import NAMESPACE

    store = ctx["store"]
    async with ctx["db_factory"]() as db:
        symbols = await get_watch_symbols(db)

    total_deleted = 0
    for symbol in symbols:
        try:
            items = await store.asearch(NAMESPACE, filter={"symbol": symbol}, limit=1000)
            scored = sorted(
                [i for i in items if i.value.get("outcome_score") is not None],
                key=lambda x: x.value["outcome_score"], reverse=True,
            )
            unscored = [i for i in items if i.value.get("outcome_score") is None]
            keep = settings.store_max_per_symbol
            to_delete = scored[keep:] + unscored[max(0, keep - len(scored)):]
            for item in to_delete:
                await store.adelete(NAMESPACE, item.key)
                total_deleted += 1
        except Exception as e:
            logger.error("task_prune_store_memories: symbol=%s error=%s", symbol, e)

    logger.info("task_prune_store_memories: deleted %d memory entries", total_deleted)


