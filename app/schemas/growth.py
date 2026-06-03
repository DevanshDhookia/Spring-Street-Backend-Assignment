"""Pydantic models for the growth-of-10k series endpoint."""
from datetime import date

from pydantic import BaseModel


class GrowthPoint(BaseModel):
    """Value of ₹10,000 invested at inception, measured on one date."""
    date: date
    value: float  # e.g. 13450.75 means ₹10,000 grew to ₹13,450.75


class GrowthSeries(BaseModel):
    """Time series showing how ₹10,000 would have grown over the fund's life."""
    plan_type: str
    option_type: str
    initial: float        # Always 10000.0 — the hypothetical starting investment
    series: list[GrowthPoint]  # Monthly (default) or daily data points
