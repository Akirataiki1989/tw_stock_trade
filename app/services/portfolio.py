import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.portfolio import DailyPerformance, Holding, Portfolio, Trade
from app.schemas.portfolio import PortfolioStats


async def get_portfolio(db: AsyncSession, user_id: uuid.UUID) -> Portfolio | None:
    result = await db.execute(select(Portfolio).where(Portfolio.user_id == user_id))
    return result.scalar_one_or_none()


async def init_portfolio(
    db: AsyncSession, user_id: uuid.UUID, initial_capital: float
) -> Portfolio:
    portfolio = Portfolio(
        user_id=user_id,
        initial_capital=initial_capital,
        cash=initial_capital,
        total_value=initial_capital,
    )
    db.add(portfolio)
    await db.commit()
    await db.refresh(portfolio)
    return portfolio


async def get_holdings(db: AsyncSession, user_id: uuid.UUID) -> list[Holding]:
    result = await db.execute(select(Holding).where(Holding.user_id == user_id))
    return list(result.scalars().all())


async def get_trades(
    db: AsyncSession, user_id: uuid.UUID, limit: int = 50, offset: int = 0
) -> list[Trade]:
    result = await db.execute(
        select(Trade)
        .where(Trade.user_id == user_id)
        .order_by(Trade.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def get_performance(db: AsyncSession, user_id: uuid.UUID) -> list[DailyPerformance]:
    result = await db.execute(
        select(DailyPerformance)
        .where(DailyPerformance.user_id == user_id)
        .order_by(DailyPerformance.date.desc())
    )
    return list(result.scalars().all())


async def get_stats(db: AsyncSession, user_id: uuid.UUID) -> PortfolioStats:
    agg = await db.execute(
        select(
            func.count().label("total"),
            func.sum(Trade.realized_pnl).label("total_pnl"),
        ).where(Trade.user_id == user_id)
    )
    row = agg.one()
    total_trades = row.total or 0
    total_pnl = float(row.total_pnl or 0)

    win_agg = await db.execute(
        select(func.count()).where(Trade.user_id == user_id, Trade.realized_pnl > 0)
    )
    winning_trades = win_agg.scalar() or 0

    portfolio = await get_portfolio(db, user_id)
    initial_capital = float(portfolio.initial_capital) if portfolio else 1.0
    win_rate = round(winning_trades / total_trades * 100, 2) if total_trades else 0.0
    total_return_pct = round(total_pnl / initial_capital * 100, 4) if initial_capital else 0.0

    return PortfolioStats(
        total_trades=total_trades,
        winning_trades=winning_trades,
        win_rate=win_rate,
        total_pnl=round(total_pnl, 2),
        total_return_pct=total_return_pct,
    )
