from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class PortfolioRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    initial_capital: float
    cash: float
    total_value: float
    created_at: datetime
    updated_at: datetime


class HoldingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    symbol: str
    company_name: Optional[str] = None
    shares: int
    avg_cost: float
    current_price: float
    market_value: Optional[float] = None
    unrealized_pnl: Optional[float] = None
    unrealized_pnl_pct: Optional[float] = None
    created_at: datetime
    updated_at: datetime


class TradeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    symbol: str
    company_name: Optional[str] = None
    action: str
    shares: int
    price: float
    total_amount: float
    fee: float
    tax: float
    net_amount: float
    decision_reason: Optional[str] = None
    realized_pnl: float
    realized_pnl_pct: float
    created_at: datetime


class PerformanceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    date: date
    total_value: float
    cash: float
    holdings_value: float
    daily_return_pct: float
    cumulative_return_pct: float
    total_trades: int
    winning_trades: int
    created_at: datetime


class PortfolioStats(BaseModel):
    total_trades: int
    winning_trades: int
    win_rate: float
    total_pnl: float
    total_return_pct: float


class PortfolioInit(BaseModel):
    initial_capital: float
