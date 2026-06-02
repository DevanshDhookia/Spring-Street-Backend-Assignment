import uuid

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, Numeric, Text, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func

from .base import Base


class NAV(Base):
    __tablename__ = "nav"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plan_id = Column(UUID(as_uuid=True), ForeignKey("plans.id"), nullable=False)
    nav_date = Column(Date, nullable=False)
    nav = Column(Numeric(20, 6), nullable=False)
    nav_inr = Column(Numeric(20, 6))
    aum = Column(Numeric(20, 2))
    units_outstanding = Column(Numeric(20, 6))
    run_id = Column(UUID(as_uuid=True), ForeignKey("pipeline_runs.id"))
    computed_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("plan_id", "nav_date", name="uq_nav_plan_date"),
        Index("ix_nav_plan_date_desc", "plan_id", "nav_date"),
    )


class Exposure(Base):
    __tablename__ = "exposures"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    dimension = Column(Text, nullable=False)
    bucket = Column(Text, nullable=False)
    weight = Column(Numeric(10, 8), nullable=False)
    as_of_date = Column(Date, nullable=False)
    run_id = Column(UUID(as_uuid=True), ForeignKey("pipeline_runs.id"))

    __table_args__ = (
        UniqueConstraint("product_id", "dimension", "bucket", "as_of_date", name="uq_exposures"),
        Index("ix_exposures_product_dim_date", "product_id", "dimension", "as_of_date"),
    )


class Performance(Base):
    __tablename__ = "performance"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plan_id = Column(UUID(as_uuid=True), ForeignKey("plans.id"), nullable=False)
    as_of_date = Column(Date, nullable=False)
    trailing_returns = Column(JSONB, nullable=False)
    calendar_year_returns = Column(JSONB)
    primary_benchmark_returns = Column(JSONB)
    additional_benchmark_returns = Column(JSONB)
    growth_of_10k = Column(JSONB)
    lookback = Column(Text, nullable=False, default="3Y")
    std_dev = Column(Numeric(10, 6))
    sharpe = Column(Numeric(10, 6))
    sortino = Column(Numeric(10, 6))
    treynor = Column(Numeric(10, 6))
    beta = Column(Numeric(10, 6))
    alpha = Column(Numeric(10, 6))
    r_squared = Column(Numeric(10, 6))
    tracking_error = Column(Numeric(10, 6))
    information_ratio = Column(Numeric(10, 6))
    max_drawdown = Column(Numeric(10, 6))
    upside_capture = Column(Numeric(10, 6))
    downside_capture = Column(Numeric(10, 6))
    portfolio_pe = Column(Numeric(10, 4))
    portfolio_pb = Column(Numeric(10, 4))
    portfolio_dividend_yield = Column(Numeric(10, 6))
    holdings_count = Column(Integer)
    run_id = Column(UUID(as_uuid=True), ForeignKey("pipeline_runs.id"))
    computed_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("plan_id", "as_of_date", "lookback", name="uq_performance_plan_date_lookback"),
    )
