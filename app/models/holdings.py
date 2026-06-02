import uuid

from sqlalchemy import Column, Date, ForeignKey, Index, Numeric, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from .base import Base


class Holding(Base):
    __tablename__ = "holdings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    security_id = Column(UUID(as_uuid=True), ForeignKey("securities.id"), nullable=False)
    quantity = Column(Numeric(20, 6), nullable=False)
    weight = Column(Numeric(10, 8))
    market_value = Column(Numeric(20, 2))
    effective_from = Column(Date, nullable=False)
    effective_to = Column(Date)
    source = Column(Text, nullable=False, default="admin")
    run_id = Column(UUID(as_uuid=True), ForeignKey("pipeline_runs.id"))

    __table_args__ = (
        UniqueConstraint("product_id", "security_id", "effective_from", name="uq_holdings_product_security_from"),
        Index("ix_holdings_product_from", "product_id", "effective_from"),
    )


class ConstituentHolding(Base):
    __tablename__ = "constituent_holdings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    parent_security_id = Column(UUID(as_uuid=True), ForeignKey("securities.id"), nullable=False)
    child_security_id = Column(UUID(as_uuid=True), ForeignKey("securities.id"), nullable=False)
    weight = Column(Numeric(10, 8), nullable=False)
    effective_from = Column(Date, nullable=False)
    effective_to = Column(Date)
    source = Column(Text, nullable=False)

    __table_args__ = (
        UniqueConstraint("parent_security_id", "child_security_id", "effective_from", name="uq_constituent_holdings"),
        Index("ix_constituent_holdings_parent_from", "parent_security_id", "effective_from"),
    )


class Classification(Base):
    __tablename__ = "classifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    security_id = Column(UUID(as_uuid=True), ForeignKey("securities.id"), nullable=False)
    sector_code = Column(Text, ForeignKey("sectors.code"))
    market_cap_usd = Column(Numeric(20, 2))
    cap_bucket = Column(Text)
    pe_ratio = Column(Numeric(10, 4))
    pb_ratio = Column(Numeric(10, 4))
    dividend_yield = Column(Numeric(10, 6))
    effective_from = Column(Date, nullable=False)
    effective_to = Column(Date)
    source = Column(Text, nullable=False, default="yfinance")

    __table_args__ = (
        UniqueConstraint("security_id", "effective_from", name="uq_classifications_security_from"),
    )
