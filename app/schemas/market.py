from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class InstrumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    symbol: str
    name: Optional[str] = None
    name_en: Optional[str] = None
    exchange: Optional[str] = None
    market: Optional[str] = None
    industry: Optional[str] = None
    security_type: Optional[str] = None
    board_lot: Optional[int] = None
    trading_currency: Optional[str] = None
    can_day_trade: Optional[bool] = None
    can_buy_day_trade: Optional[bool] = None
    limit_up_price: Optional[float] = None
    limit_down_price: Optional[float] = None
    reference_price: Optional[float] = None
    is_attention: bool
    is_disposition: bool
    last_synced: datetime


class QuoteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    symbol: str
    name: Optional[str] = None
    reference_price: Optional[float] = None
    prev_close: Optional[float] = None
    open_price: Optional[float] = None
    high_price: Optional[float] = None
    low_price: Optional[float] = None
    close_price: Optional[float] = None
    last_price: Optional[float] = None
    last_size: Optional[int] = None
    avg_price: Optional[float] = None
    change: Optional[float] = None
    change_pct: Optional[float] = None
    amplitude: Optional[float] = None
    bids: Optional[Any] = None
    asks: Optional[Any] = None
    total: Optional[Any] = None
    is_limit_up: bool
    is_limit_down: bool
    is_trial: bool
    fetched_at: datetime


class CandleItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    # intraday
    ts: Optional[datetime] = None
    average: Optional[float] = None
    # historical
    date: Optional[date] = None
    turnover: Optional[float] = None
    change: Optional[float] = None
    # 共用
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    volume: Optional[int] = None


class CandleResponse(BaseModel):
    symbol: str
    timeframe: str
    data: list[CandleItem]
