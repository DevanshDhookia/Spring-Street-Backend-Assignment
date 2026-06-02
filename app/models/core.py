import uuid

from sqlalchemy import (
    Boolean, Column, Date, DateTime, ForeignKey,
    Index, Integer, Numeric, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import CHAR, UUID
from sqlalchemy.sql import func

from .base import Base


class AMC(Base):
    __tablename__ = "amcs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(Text, unique=True, nullable=False)
    name = Column(Text, nullable=False)
    cin = Column(Text)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class FundManager(Base):
    __tablename__ = "fund_managers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    amc_id = Column(UUID(as_uuid=True), ForeignKey("amcs.id"), nullable=False)
    name = Column(Text, nullable=False)
    experience_years = Column(Integer)
    bio = Column(Text)
    is_active = Column(Boolean, nullable=False, default=True)


class Security(Base):
    __tablename__ = "securities"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticker = Column(Text, nullable=False)
    exchange = Column(Text)
    name = Column(Text, nullable=False)
    isin = Column(Text)
    asset_class = Column(Text, nullable=False)
    domicile = Column(CHAR(2), ForeignKey("regions.country_code"))
    currency = Column(CHAR(3), nullable=False)
    is_fund = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("ticker", "exchange", name="uq_securities_ticker_exchange"),
        Index("ix_securities_isin", "isin"),
    )


class Product(Base):
    __tablename__ = "products"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(Text, unique=True, nullable=False)
    name = Column(Text, nullable=False)
    amc_id = Column(UUID(as_uuid=True), ForeignKey("amcs.id"), nullable=False)
    inception_date = Column(Date, nullable=False)
    base_currency = Column(CHAR(3), nullable=False)
    reporting_currency = Column(CHAR(3), nullable=False)
    scheme_type = Column(Text)
    scheme_category = Column(Text)
    scheme_sub_category = Column(Text)
    is_fund_of_funds = Column(Boolean, nullable=False, default=False)
    primary_benchmark_id = Column(UUID(as_uuid=True), ForeignKey("securities.id"))
    additional_benchmark_id = Column(UUID(as_uuid=True), ForeignKey("securities.id"))
    risk_level = Column(Text)
    benchmark_risk_level = Column(Text)
    trustee_name = Column(Text)
    custodian_name = Column(Text)
    rta_name = Column(Text)
    objective = Column(Text)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class ProductManager(Base):
    __tablename__ = "product_managers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    manager_id = Column(UUID(as_uuid=True), ForeignKey("fund_managers.id"), nullable=False)
    role = Column(Text, nullable=False)
    managing_since = Column(Date, nullable=False)
    managing_until = Column(Date)

    __table_args__ = (
        UniqueConstraint("product_id", "manager_id", "managing_since", name="uq_product_managers"),
    )


class Plan(Base):
    __tablename__ = "plans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    plan_type = Column(Text, nullable=False)
    option_type = Column(Text, nullable=False)
    isin = Column(Text)
    amfi_code = Column(Text)
    min_initial = Column(Numeric(15, 2))
    min_additional = Column(Numeric(15, 2))
    min_sip = Column(Numeric(15, 2))
    min_redemption = Column(Numeric(15, 2))
    is_active = Column(Boolean, nullable=False, default=True)

    __table_args__ = (
        UniqueConstraint("product_id", "plan_type", "option_type", name="uq_plans_product_type_option"),
        Index("ix_plans_isin", "isin"),
        Index("ix_plans_amfi_code", "amfi_code"),
    )


class PlanFee(Base):
    __tablename__ = "plan_fees"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plan_id = Column(UUID(as_uuid=True), ForeignKey("plans.id"), nullable=False)
    ter = Column(Numeric(6, 4), nullable=False)
    exit_load_pct = Column(Numeric(6, 4))
    exit_load_days = Column(Integer)
    effective_from = Column(Date, nullable=False)
    effective_to = Column(Date)

    __table_args__ = (
        UniqueConstraint("plan_id", "effective_from", name="uq_plan_fees_plan_from"),
    )
