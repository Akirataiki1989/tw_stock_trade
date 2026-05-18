import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Portfolio(Base):
    __tablename__ = "portfolios"
    __table_args__ = (UniqueConstraint("user_id"), {"schema": "trading"})

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("public.users.id", ondelete="CASCADE"), nullable=False
    )
    initial_capital: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    cash: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    total_value: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Holding(Base):
    __tablename__ = "holdings"
    __table_args__ = (UniqueConstraint("user_id", "symbol"), {"schema": "trading"})

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("public.users.id", ondelete="CASCADE"), nullable=False
    )
    symbol: Mapped[str] = mapped_column(String(10), nullable=False)
    company_name: Mapped[Optional[str]] = mapped_column(String(100))
    shares: Mapped[int] = mapped_column(Integer, CheckConstraint("shares > 0"), nullable=False)
    avg_cost: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    current_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, server_default="0")
    # GENERATED ALWAYS AS ... STORED — 由 Alembic DDL 直接建立
    market_value: Mapped[float] = mapped_column(Numeric(15, 2), nullable=True)
    unrealized_pnl: Mapped[float] = mapped_column(Numeric(15, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Trade(Base):
    __tablename__ = "trades"
    __table_args__ = {"schema": "trading"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("public.users.id", ondelete="CASCADE"), nullable=False
    )
    symbol: Mapped[str] = mapped_column(String(10), nullable=False)
    company_name: Mapped[Optional[str]] = mapped_column(String(100))
    action: Mapped[str] = mapped_column(
        String(4), CheckConstraint("action IN ('BUY', 'SELL')"), nullable=False
    )
    shares: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    total_amount: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    fee: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, server_default="0")
    tax: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, server_default="0")
    net_amount: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    decision_reason: Mapped[Optional[str]] = mapped_column(Text)
    realized_pnl: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False, server_default="0")
    realized_pnl_pct: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AiDecision(Base):
    __tablename__ = "ai_decisions"
    __table_args__ = {"schema": "trading"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("public.users.id", ondelete="CASCADE"), nullable=False
    )
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    analysis: Mapped[Optional[str]] = mapped_column(Text)
    decisions: Mapped[Optional[dict]] = mapped_column(JSONB)
    market_summary: Mapped[Optional[str]] = mapped_column(Text)
    model_used: Mapped[Optional[str]] = mapped_column(String(100))
    tokens_used: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    execution_ms: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    agent_reports: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DailyPerformance(Base):
    __tablename__ = "daily_performance"
    __table_args__ = (UniqueConstraint("user_id", "date"), {"schema": "trading"})

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("public.users.id", ondelete="CASCADE"), nullable=False
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    total_value: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    cash: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    holdings_value: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    daily_return_pct: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False, server_default="0")
    cumulative_return_pct: Mapped[float] = mapped_column(
        Numeric(8, 4), nullable=False, server_default="0"
    )
    total_trades: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    winning_trades: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
