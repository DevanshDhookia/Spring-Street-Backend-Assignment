from datetime import date
from typing import Any

from pydantic import BaseModel


class ProductSummary(BaseModel):
    code: str
    name: str
    scheme_category: str | None
    risk_level: str | None
    inception_date: date
    is_active: bool


class ManagerOut(BaseModel):
    name: str
    experience_years: int | None
    managing_since: date


class PlanOut(BaseModel):
    plan_type: str
    option_type: str
    isin: str | None
    min_initial: float | None
    min_sip: float | None


class ProductDetail(BaseModel):
    code: str
    name: str
    objective: str | None
    inception_date: date
    scheme_type: str | None
    scheme_category: str | None
    scheme_sub_category: str | None
    risk_level: str | None
    base_currency: str
    reporting_currency: str
    is_fund_of_funds: bool
    amc: str
    managers: list[ManagerOut]
    plans: list[PlanOut]
    trustee_name: str | None
    custodian_name: str | None
    rta_name: str | None


class NAVPoint(BaseModel):
    date: date
    nav: float
    nav_inr: float | None
    aum: float | None


class NAVSeries(BaseModel):
    plan_type: str
    option_type: str
    series: list[NAVPoint]


class HoldingOut(BaseModel):
    ticker: str
    name: str
    asset_class: str
    domicile: str | None
    weight: float | None
    market_value: float | None
    quantity: float


class ExposureOut(BaseModel):
    bucket: str
    weight: float


class PerformanceOut(BaseModel):
    plan_type: str
    option_type: str
    as_of_date: date
    lookback: str
    trailing_returns: dict[str, Any]
    calendar_year_returns: dict[str, Any] | None
    primary_benchmark_returns: dict[str, Any] | None
    growth_of_10k: dict[str, Any] | None
    risk_metrics: dict[str, Any]
    portfolio: dict[str, Any]
