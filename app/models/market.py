import uuid

from sqlalchemy import BigInteger, Column, Date, DateTime, ForeignKey, Index, Numeric, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import CHAR, UUID
from sqlalchemy.sql import func

from .base import Base


class Price(Base):
    __tablename__ = "prices"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    security_id = Column(UUID(as_uuid=True), ForeignKey("securities.id"), nullable=False)
    trade_date = Column(Date, nullable=False)
    open = Column(Numeric(20, 6))
    high = Column(Numeric(20, 6))
    low = Column(Numeric(20, 6))
    close = Column(Numeric(20, 6), nullable=False)
    adj_close = Column(Numeric(20, 6))
    volume = Column(BigInteger)
    source = Column(Text, nullable=False, default="yfinance")
    ingested_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("security_id", "trade_date", name="uq_prices_security_date"),
        Index("ix_prices_security_date_desc", "security_id", "trade_date"),
    )


class FXRate(Base):
    __tablename__ = "fx_rates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    base = Column(CHAR(3), nullable=False)
    quote = Column(CHAR(3), nullable=False)
    rate_date = Column(Date, nullable=False)
    rate = Column(Numeric(20, 8), nullable=False)
    source = Column(Text, nullable=False, default="yfinance")

    __table_args__ = (
        UniqueConstraint("base", "quote", "rate_date", name="uq_fx_rates_pair_date"),
    )
