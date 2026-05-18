from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Instrument(Base):
    __tablename__ = "instruments"
    __table_args__ = {"schema": "market"}

    symbol: Mapped[str] = mapped_column(String(10), primary_key=True)
    name: Mapped[Optional[str]] = mapped_column(String(100))
    name_en: Mapped[Optional[str]] = mapped_column(String(100))
    exchange: Mapped[Optional[str]] = mapped_column(String(10))
    market: Mapped[Optional[str]] = mapped_column(String(10))
    industry: Mapped[Optional[str]] = mapped_column(String(50))
    security_type: Mapped[Optional[str]] = mapped_column(String(20))
    board_lot: Mapped[Optional[int]] = mapped_column(Integer)
    trading_currency: Mapped[Optional[str]] = mapped_column(String(10))
    can_day_trade: Mapped[Optional[bool]] = mapped_column(Boolean)
    can_buy_day_trade: Mapped[Optional[bool]] = mapped_column(Boolean)
    limit_up_price: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    limit_down_price: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    reference_price: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    is_attention: Mapped[bool] = mapped_column(Boolean, server_default="false")
    is_disposition: Mapped[bool] = mapped_column(Boolean, server_default="false")
    last_synced: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MarketQuote(Base):
    __tablename__ = "market_quotes"
    __table_args__ = {"schema": "market"}

    symbol: Mapped[str] = mapped_column(
        String(10), ForeignKey("market.instruments.symbol"), primary_key=True
    )
    reference_price: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    prev_close: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    open_price: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    high_price: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    low_price: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    close_price: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    last_price: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    last_size: Mapped[Optional[int]] = mapped_column(Integer)
    avg_price: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    change: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    change_pct: Mapped[Optional[float]] = mapped_column(Numeric(8, 4))
    amplitude: Mapped[Optional[float]] = mapped_column(Numeric(8, 4))
    bids: Mapped[Optional[dict]] = mapped_column(JSONB)
    asks: Mapped[Optional[dict]] = mapped_column(JSONB)
    total: Mapped[Optional[dict]] = mapped_column(JSONB)
    is_limit_up: Mapped[bool] = mapped_column(Boolean, server_default="false")
    is_limit_down: Mapped[bool] = mapped_column(Boolean, server_default="false")
    is_trial: Mapped[bool] = mapped_column(Boolean, server_default="false")
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class IntradayCandle(Base):
    __tablename__ = "intraday_candles"
    __table_args__ = (UniqueConstraint("symbol", "timeframe", "ts"), {"schema": "market"})

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(10), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(5), nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    open: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    high: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    low: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    close: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    volume: Mapped[Optional[int]] = mapped_column(BigInteger)
    average: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))


class HistoricalCandle(Base):
    __tablename__ = "historical_candles"
    __table_args__ = (UniqueConstraint("symbol", "timeframe", "date"), {"schema": "market"})

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(10), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(5), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    open: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    high: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    low: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    close: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    volume: Mapped[Optional[int]] = mapped_column(BigInteger)
    turnover: Mapped[Optional[float]] = mapped_column(Numeric(20, 2))
    change: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
