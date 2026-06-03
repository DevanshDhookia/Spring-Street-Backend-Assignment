"""
Pydantic response models for product and fund detail endpoints.

These models define exactly what the API sends back to the client.
Pydantic validates types at runtime and auto-generates the OpenAPI docs.
"""
from datetime import date

from pydantic import BaseModel


class ManagerOut(BaseModel):
    """One fund manager associated with a product."""
    name: str
    experience_years: int | None
    managing_since: date  # date they started managing this specific fund


class FeeOut(BaseModel):
    """Expense and exit load structure for a plan."""
    ter: float | None            # Total Expense Ratio (e.g. 0.005 = 0.50%)
    exit_load_pct: float | None  # Fee charged on redemption (e.g. 0.01 = 1%)
    exit_load_days: int | None   # Holding period below which exit load applies


class PlanOut(BaseModel):
    """One plan variant (Direct-Growth, Regular-IDCW, etc.)."""
    plan_type: str        # "direct" or "regular"
    option_type: str      # "growth" or "idcw"
    isin: str | None      # SEBI-assigned security identifier
    min_initial: float | None
    min_sip: float | None
    min_additional: float | None
    fees: FeeOut | None


class ProductSummary(BaseModel):
    """Compact card shown on the products list page."""
    code: str
    name: str
    scheme_category: str | None
    risk_level: str | None
    inception_date: date
    is_active: bool
    latest_nav: float | None       # Direct-Growth NAV, most recent date
    latest_nav_date: date | None
    aum: float | None              # Assets Under Management in base currency


class ProductDetail(BaseModel):
    """Full fund detail card — powers the factsheet header section."""
    code: str
    name: str
    objective: str | None
    inception_date: date
    scheme_type: str | None          # "open_ended" / "close_ended"
    scheme_category: str | None      # SEBI category: "equity", "debt", etc.
    scheme_sub_category: str | None
    risk_level: str | None           # Fund's own riskometer level
    benchmark_risk_level: str | None # Benchmark's riskometer level (for comparison)
    base_currency: str               # Currency in which the portfolio is managed (USD)
    reporting_currency: str          # Currency shown to Indian investors (INR)
    is_fund_of_funds: bool
    amc: str           # Asset Management Company name
    amc_cin: str | None  # Corporate Identification Number (SEBI registration)
    primary_benchmark: str | None    # e.g. "iShares MSCI World ETF"
    additional_benchmark: str | None # Secondary comparison index
    managers: list[ManagerOut]
    plans: list[PlanOut]
    trustee_name: str | None
    custodian_name: str | None
    rta_name: str | None  # Registrar and Transfer Agent
