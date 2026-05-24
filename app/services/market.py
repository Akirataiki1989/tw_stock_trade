from datetime import date

from sqlalchemy import Date as SADate
from sqlalchemy import cast, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.market import HistoricalCandle, Instrument, IntradayCandle, MarketQuote

HISTORICAL_TIMEFRAMES = {"D", "W", "M"}


async def get_quote(
    db: AsyncSession, symbol: str
) -> dict | None:
    result = await db.execute(select(MarketQuote).where(MarketQuote.symbol == symbol))
    quote = result.scalar_one_or_none()
    if not quote:
        return None
    inst = await db.execute(select(Instrument.name).where(Instrument.symbol == symbol))
    name = inst.scalar_one_or_none()
    return {"quote": quote, "name": name}


async def get_candles(
    db: AsyncSession,
    symbol: str,
    timeframe: str,
    from_date: date | None = None,
    to_date: date | None = None,
) -> list:
    if timeframe in HISTORICAL_TIMEFRAMES:
        stmt = (
            select(HistoricalCandle)
            .where(HistoricalCandle.symbol == symbol, HistoricalCandle.timeframe == timeframe)
            .order_by(HistoricalCandle.date.asc())
        )
        if from_date:
            stmt = stmt.where(HistoricalCandle.date >= from_date)
        if to_date:
            stmt = stmt.where(HistoricalCandle.date <= to_date)
    else:
        stmt = (
            select(IntradayCandle)
            .where(IntradayCandle.symbol == symbol, IntradayCandle.timeframe == timeframe)
            .order_by(IntradayCandle.ts.asc())
        )
        if from_date:
            stmt = stmt.where(cast(IntradayCandle.ts, SADate) >= from_date)
        if to_date:
            stmt = stmt.where(cast(IntradayCandle.ts, SADate) <= to_date)

    result = await db.execute(stmt)
    return list(result.scalars().all())


async def search_instruments(
    db: AsyncSession, q: str, limit: int = 10
) -> list[Instrument]:
    result = await db.execute(
        select(Instrument)
        .where(or_(Instrument.symbol.ilike(f"%{q}%"), Instrument.name.ilike(f"%{q}%")))
        .limit(limit)
    )
    return list(result.scalars().all())
