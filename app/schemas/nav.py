"""Pydantic models for NAV history endpoint."""
from datetime import date

from pydantic import BaseModel


class NAVPoint(BaseModel):
    """A single NAV observation for one trading day."""
    date: date
    nav: float          # NAV in base currency (USD)
    nav_inr: float | None  # NAV converted to INR using that day's FX rate
    aum: float | None   # Total AUM at this date


class NAVSeries(BaseModel):
    """Ordered time series of NAV for a specific plan."""
    plan_type: str    # "direct" or "regular"
    option_type: str  # "growth" or "idcw"
    series: list[NAVPoint]  # Sorted ascending by date
