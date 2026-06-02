"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-06-02
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- seed / reference ------------------------------------------------
    op.create_table(
        "regions",
        sa.Column("country_code", sa.CHAR(2), primary_key=True),
        sa.Column("country_name", sa.Text, nullable=False),
        sa.Column("region", sa.Text, nullable=False),
        sa.Column("msci_class", sa.Text),
    )

    op.create_table(
        "sectors",
        sa.Column("code", sa.Text, primary_key=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.UniqueConstraint("name", name="uq_sectors_name"),
    )

    # --- operational (created early — other tables reference pipeline_runs) --
    op.create_table(
        "pipeline_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_name", sa.Text, nullable=False),
        sa.Column("triggered_by", sa.Text, nullable=False, server_default="scheduler"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.Text, nullable=False, server_default="running"),
        sa.Column("target_date", sa.Date),
        sa.Column("rows_processed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error", sa.Text),
        sa.Column("timings", postgresql.JSONB),
    )
    op.create_index("ix_pipeline_runs_job_started", "pipeline_runs", ["job_name", "started_at"])
    op.create_index("ix_pipeline_runs_status", "pipeline_runs", ["status"])

    op.create_table(
        "audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("actor", sa.Text, nullable=False),
        sa.Column("action", sa.Text, nullable=False),
        sa.Column("entity", sa.Text, nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True)),
        sa.Column("before", postgresql.JSONB),
        sa.Column("after", postgresql.JSONB),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_audit_log_entity_id_occurred", "audit_log", ["entity", "entity_id", "occurred_at"])

    # --- core identity ---------------------------------------------------
    op.create_table(
        "amcs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.Text, nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("cin", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("code", name="uq_amcs_code"),
    )

    op.create_table(
        "fund_managers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("amc_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("amcs.id"), nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("experience_years", sa.Integer),
        sa.Column("bio", sa.Text),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
    )

    op.create_table(
        "securities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("ticker", sa.Text, nullable=False),
        sa.Column("exchange", sa.Text),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("isin", sa.Text),
        sa.Column("asset_class", sa.Text, nullable=False),
        sa.Column("domicile", sa.CHAR(2), sa.ForeignKey("regions.country_code")),
        sa.Column("currency", sa.CHAR(3), nullable=False),
        sa.Column("is_fund", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("ticker", "exchange", name="uq_securities_ticker_exchange"),
    )
    op.create_index("ix_securities_isin", "securities", ["isin"])

    op.create_table(
        "products",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.Text, nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("amc_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("amcs.id"), nullable=False),
        sa.Column("inception_date", sa.Date, nullable=False),
        sa.Column("base_currency", sa.CHAR(3), nullable=False),
        sa.Column("reporting_currency", sa.CHAR(3), nullable=False),
        sa.Column("scheme_type", sa.Text),
        sa.Column("scheme_category", sa.Text),
        sa.Column("scheme_sub_category", sa.Text),
        sa.Column("is_fund_of_funds", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("primary_benchmark_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("securities.id")),
        sa.Column("additional_benchmark_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("securities.id")),
        sa.Column("risk_level", sa.Text),
        sa.Column("benchmark_risk_level", sa.Text),
        sa.Column("trustee_name", sa.Text),
        sa.Column("custodian_name", sa.Text),
        sa.Column("rta_name", sa.Text),
        sa.Column("objective", sa.Text),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("code", name="uq_products_code"),
    )

    op.create_table(
        "product_managers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("manager_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("fund_managers.id"), nullable=False),
        sa.Column("role", sa.Text, nullable=False),
        sa.Column("managing_since", sa.Date, nullable=False),
        sa.Column("managing_until", sa.Date),
        sa.UniqueConstraint("product_id", "manager_id", "managing_since", name="uq_product_managers"),
    )

    op.create_table(
        "plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("plan_type", sa.Text, nullable=False),
        sa.Column("option_type", sa.Text, nullable=False),
        sa.Column("isin", sa.Text),
        sa.Column("amfi_code", sa.Text),
        sa.Column("min_initial", sa.Numeric(15, 2)),
        sa.Column("min_additional", sa.Numeric(15, 2)),
        sa.Column("min_sip", sa.Numeric(15, 2)),
        sa.Column("min_redemption", sa.Numeric(15, 2)),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.UniqueConstraint("product_id", "plan_type", "option_type", name="uq_plans_product_type_option"),
    )
    op.create_index("ix_plans_isin", "plans", ["isin"])
    op.create_index("ix_plans_amfi_code", "plans", ["amfi_code"])

    op.create_table(
        "plan_fees",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("plans.id"), nullable=False),
        sa.Column("ter", sa.Numeric(6, 4), nullable=False),
        sa.Column("exit_load_pct", sa.Numeric(6, 4)),
        sa.Column("exit_load_days", sa.Integer),
        sa.Column("effective_from", sa.Date, nullable=False),
        sa.Column("effective_to", sa.Date),
        sa.UniqueConstraint("plan_id", "effective_from", name="uq_plan_fees_plan_from"),
    )

    # --- market data -----------------------------------------------------
    op.create_table(
        "prices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("security_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("securities.id"), nullable=False),
        sa.Column("trade_date", sa.Date, nullable=False),
        sa.Column("open", sa.Numeric(20, 6)),
        sa.Column("high", sa.Numeric(20, 6)),
        sa.Column("low", sa.Numeric(20, 6)),
        sa.Column("close", sa.Numeric(20, 6), nullable=False),
        sa.Column("adj_close", sa.Numeric(20, 6)),
        sa.Column("volume", sa.BigInteger),
        sa.Column("source", sa.Text, nullable=False, server_default="yfinance"),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("security_id", "trade_date", name="uq_prices_security_date"),
    )
    op.create_index("ix_prices_security_date_desc", "prices", ["security_id", "trade_date"])

    op.create_table(
        "fx_rates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("base", sa.CHAR(3), nullable=False),
        sa.Column("quote", sa.CHAR(3), nullable=False),
        sa.Column("rate_date", sa.Date, nullable=False),
        sa.Column("rate", sa.Numeric(20, 8), nullable=False),
        sa.Column("source", sa.Text, nullable=False, server_default="yfinance"),
        sa.UniqueConstraint("base", "quote", "rate_date", name="uq_fx_rates_pair_date"),
    )

    # --- holdings + classifications (SCD2) --------------------------------
    op.create_table(
        "holdings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("security_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("securities.id"), nullable=False),
        sa.Column("quantity", sa.Numeric(20, 6), nullable=False),
        sa.Column("weight", sa.Numeric(10, 8)),
        sa.Column("market_value", sa.Numeric(20, 2)),
        sa.Column("effective_from", sa.Date, nullable=False),
        sa.Column("effective_to", sa.Date),
        sa.Column("source", sa.Text, nullable=False, server_default="admin"),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pipeline_runs.id")),
        sa.UniqueConstraint("product_id", "security_id", "effective_from", name="uq_holdings_product_security_from"),
    )
    op.create_index("ix_holdings_product_from", "holdings", ["product_id", "effective_from"])

    op.create_table(
        "constituent_holdings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("parent_security_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("securities.id"), nullable=False),
        sa.Column("child_security_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("securities.id"), nullable=False),
        sa.Column("weight", sa.Numeric(10, 8), nullable=False),
        sa.Column("effective_from", sa.Date, nullable=False),
        sa.Column("effective_to", sa.Date),
        sa.Column("source", sa.Text, nullable=False),
        sa.UniqueConstraint("parent_security_id", "child_security_id", "effective_from", name="uq_constituent_holdings"),
    )
    op.create_index("ix_constituent_holdings_parent_from", "constituent_holdings", ["parent_security_id", "effective_from"])

    op.create_table(
        "classifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("security_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("securities.id"), nullable=False),
        sa.Column("sector_code", sa.Text, sa.ForeignKey("sectors.code")),
        sa.Column("market_cap_usd", sa.Numeric(20, 2)),
        sa.Column("cap_bucket", sa.Text),
        sa.Column("pe_ratio", sa.Numeric(10, 4)),
        sa.Column("pb_ratio", sa.Numeric(10, 4)),
        sa.Column("dividend_yield", sa.Numeric(10, 6)),
        sa.Column("effective_from", sa.Date, nullable=False),
        sa.Column("effective_to", sa.Date),
        sa.Column("source", sa.Text, nullable=False, server_default="yfinance"),
        sa.UniqueConstraint("security_id", "effective_from", name="uq_classifications_security_from"),
    )

    # --- derived snapshots -----------------------------------------------
    op.create_table(
        "nav",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("plans.id"), nullable=False),
        sa.Column("nav_date", sa.Date, nullable=False),
        sa.Column("nav", sa.Numeric(20, 6), nullable=False),
        sa.Column("nav_inr", sa.Numeric(20, 6)),
        sa.Column("aum", sa.Numeric(20, 2)),
        sa.Column("units_outstanding", sa.Numeric(20, 6)),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pipeline_runs.id")),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("plan_id", "nav_date", name="uq_nav_plan_date"),
    )
    op.create_index("ix_nav_plan_date_desc", "nav", ["plan_id", "nav_date"])

    op.create_table(
        "exposures",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("dimension", sa.Text, nullable=False),
        sa.Column("bucket", sa.Text, nullable=False),
        sa.Column("weight", sa.Numeric(10, 8), nullable=False),
        sa.Column("as_of_date", sa.Date, nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pipeline_runs.id")),
        sa.UniqueConstraint("product_id", "dimension", "bucket", "as_of_date", name="uq_exposures"),
    )
    op.create_index("ix_exposures_product_dim_date", "exposures", ["product_id", "dimension", "as_of_date"])

    op.create_table(
        "performance",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("plans.id"), nullable=False),
        sa.Column("as_of_date", sa.Date, nullable=False),
        sa.Column("trailing_returns", postgresql.JSONB, nullable=False),
        sa.Column("calendar_year_returns", postgresql.JSONB),
        sa.Column("primary_benchmark_returns", postgresql.JSONB),
        sa.Column("additional_benchmark_returns", postgresql.JSONB),
        sa.Column("growth_of_10k", postgresql.JSONB),
        sa.Column("lookback", sa.Text, nullable=False, server_default="3Y"),
        sa.Column("std_dev", sa.Numeric(10, 6)),
        sa.Column("sharpe", sa.Numeric(10, 6)),
        sa.Column("sortino", sa.Numeric(10, 6)),
        sa.Column("treynor", sa.Numeric(10, 6)),
        sa.Column("beta", sa.Numeric(10, 6)),
        sa.Column("alpha", sa.Numeric(10, 6)),
        sa.Column("r_squared", sa.Numeric(10, 6)),
        sa.Column("tracking_error", sa.Numeric(10, 6)),
        sa.Column("information_ratio", sa.Numeric(10, 6)),
        sa.Column("max_drawdown", sa.Numeric(10, 6)),
        sa.Column("upside_capture", sa.Numeric(10, 6)),
        sa.Column("downside_capture", sa.Numeric(10, 6)),
        sa.Column("portfolio_pe", sa.Numeric(10, 4)),
        sa.Column("portfolio_pb", sa.Numeric(10, 4)),
        sa.Column("portfolio_dividend_yield", sa.Numeric(10, 6)),
        sa.Column("holdings_count", sa.Integer),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pipeline_runs.id")),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("plan_id", "as_of_date", "lookback", name="uq_performance_plan_date_lookback"),
    )


def downgrade() -> None:
    op.drop_table("performance")
    op.drop_table("exposures")
    op.drop_table("nav")
    op.drop_table("classifications")
    op.drop_table("constituent_holdings")
    op.drop_table("holdings")
    op.drop_table("fx_rates")
    op.drop_table("prices")
    op.drop_table("plan_fees")
    op.drop_table("plans")
    op.drop_table("product_managers")
    op.drop_table("products")
    op.drop_table("securities")
    op.drop_table("fund_managers")
    op.drop_table("amcs")
    op.drop_table("audit_log")
    op.drop_table("pipeline_runs")
    op.drop_table("sectors")
    op.drop_table("regions")
