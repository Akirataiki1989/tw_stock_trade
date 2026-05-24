from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.market import CandleItem, CandleResponse, InstrumentRead, QuoteRead
from app.services import market as market_service
from app.users import current_active_user

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/quote/{symbol}", response_model=QuoteRead)
async def get_quote(
    symbol: str,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db),
):
    data = await market_service.get_quote(db, symbol)
    if not data:
        raise HTTPException(status_code=404, detail=f"Quote for {symbol} not found.")
    quote = QuoteRead.model_validate(data["quote"])
    return quote.model_copy(update={"name": data["name"]})


@router.get("/candles/{symbol}", response_model=CandleResponse)
async def get_candles(
    symbol: str,
    timeframe: str = Query("D", description="D/W/M 歷史K線；1/5/15/30/60 盤中K線"),
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to"),
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db),
):
    candles = await market_service.get_candles(db, symbol, timeframe, from_date, to_date)
    return CandleResponse(
        symbol=symbol,
        timeframe=timeframe,
        data=[CandleItem.model_validate(c) for c in candles],
    )


@router.get("/search", response_model=list[InstrumentRead])
async def search_instruments(
    q: str = Query(..., min_length=1, description="搜尋股票代碼或名稱"),
    limit: int = Query(10, ge=1, le=50),
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db),
):
    return await market_service.search_instruments(db, q, limit=limit)
