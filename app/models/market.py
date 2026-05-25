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
    last_synced: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


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


class UsMarketDaily(Base):
    """美股主要指數昨收數據（每日一筆）。"""

    __tablename__ = "us_market_daily"
    __table_args__ = {"schema": "market"}

    date: Mapped[date] = mapped_column(Date, primary_key=True)
    # S&P 500
    sp500_close: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    sp500_change: Mapped[Optional[float]] = mapped_column(Numeric(8, 4))   # % e.g. 1.23
    # NASDAQ
    nasdaq_close: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    nasdaq_change: Mapped[Optional[float]] = mapped_column(Numeric(8, 4))
    # TSM ADR
    tsm_adr_close: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    tsm_adr_change: Mapped[Optional[float]] = mapped_column(Numeric(8, 4))
    # 費城半導體 SOX
    sox_close: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    sox_change: Mapped[Optional[float]] = mapped_column(Numeric(8, 4))
    # 美元指數 DXY（絕對值重要，>100 強勢美元）
    dxy_close: Mapped[Optional[float]] = mapped_column(Numeric(8, 4))
    dxy_change: Mapped[Optional[float]] = mapped_column(Numeric(8, 4))
    # 10 年期公債殖利率（^TNX，Yahoo Finance 回傳單位：%，e.g. 4.5 = 4.5%）
    us10y_yield: Mapped[Optional[float]] = mapped_column(Numeric(6, 3))
    us10y_change_bps: Mapped[Optional[float]] = mapped_column(Numeric(6, 1))  # basis points
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class InstitutionalFlow(Base):
    """TWSE 三大法人買賣超（每日全市場，每支股票一筆）。"""

    __tablename__ = "institutional_flows"
    __table_args__ = (
        UniqueConstraint("date", "symbol"),
        {"schema": "market"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    symbol: Mapped[str] = mapped_column(String(10), nullable=False)
    # 外陸資（不含外資自營商）
    foreign_net: Mapped[Optional[int]] = mapped_column(BigInteger)   # 買賣超股數
    # 投信
    trust_buy: Mapped[Optional[int]] = mapped_column(BigInteger)
    trust_sell: Mapped[Optional[int]] = mapped_column(BigInteger)
    trust_net: Mapped[Optional[int]] = mapped_column(BigInteger)
    # 自營商（合計）
    dealer_net: Mapped[Optional[int]] = mapped_column(BigInteger)
    # 三大法人合計
    total_net: Mapped[Optional[int]] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class MarginTrading(Base):
    """TWSE 融資融券餘額（每日全市場，每支股票一筆）。"""

    __tablename__ = "margin_trading"
    __table_args__ = (
        UniqueConstraint("date", "symbol"),
        {"schema": "market"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    symbol: Mapped[str] = mapped_column(String(10), nullable=False)
    # 融資
    margin_buy: Mapped[Optional[int]] = mapped_column(BigInteger)
    margin_sell: Mapped[Optional[int]] = mapped_column(BigInteger)
    margin_balance_prev: Mapped[Optional[int]] = mapped_column(BigInteger)
    margin_balance: Mapped[Optional[int]] = mapped_column(BigInteger)  # 今日餘額 ⭐
    # 融券
    short_buy: Mapped[Optional[int]] = mapped_column(BigInteger)
    short_sell: Mapped[Optional[int]] = mapped_column(BigInteger)
    short_balance_prev: Mapped[Optional[int]] = mapped_column(BigInteger)
    short_balance: Mapped[Optional[int]] = mapped_column(BigInteger)   # 今日餘額 ⭐
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

