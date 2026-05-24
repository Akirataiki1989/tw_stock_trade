from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.portfolio import (
    HoldingRead,
    PerformanceRead,
    PortfolioInit,
    PortfolioRead,
    PortfolioStats,
    TradeRead,
)
from app.services import portfolio as portfolio_service
from app.users import current_active_user

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.get("", response_model=PortfolioRead)
async def get_portfolio(
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db),
):
    portfolio = await portfolio_service.get_portfolio(db, user.id)
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found. Please initialize first.")
    return portfolio


@router.post("/init", response_model=PortfolioRead)
async def init_portfolio(
    body: PortfolioInit,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db),
):
    existing = await portfolio_service.get_portfolio(db, user.id)
    if existing:
        raise HTTPException(status_code=400, detail="Portfolio already initialized.")
    return await portfolio_service.init_portfolio(db, user.id, body.initial_capital)


@router.get("/holdings", response_model=list[HoldingRead])
async def get_holdings(
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db),
):
    holdings = await portfolio_service.get_holdings(db, user.id)
    result = []
    for h in holdings:
        cost_basis = h.avg_cost * h.shares
        pct = round(float(h.unrealized_pnl) / cost_basis * 100, 2) if cost_basis else 0.0
        item = HoldingRead.model_validate(h)
        result.append(item.model_copy(update={"unrealized_pnl_pct": pct}))
    return result


@router.get("/trades", response_model=list[TradeRead])
async def get_trades(
    limit: int = 50,
    offset: int = 0,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db),
):
    return await portfolio_service.get_trades(db, user.id, limit=limit, offset=offset)


@router.get("/performance", response_model=list[PerformanceRead])
async def get_performance(
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db),
):
    return await portfolio_service.get_performance(db, user.id)


@router.get("/stats", response_model=PortfolioStats)
async def get_stats(
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db),
):
    return await portfolio_service.get_stats(db, user.id)
