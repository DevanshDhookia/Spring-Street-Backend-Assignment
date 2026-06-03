"""Pydantic models for the holdings endpoint."""
from pydantic import BaseModel


class HoldingOut(BaseModel):
    """One position in the portfolio, as of a given date."""
    ticker: str
    name: str
    asset_class: str      # "equity", "etf", "debt", etc.
    domicile: str | None  # ISO-3166 alpha-2 country code (e.g. "US", "NL")
    weight: float | None  # Portfolio weight as a decimal (0.15 = 15%)
    market_value: float | None  # In base currency (USD)
    quantity: float       # Number of shares/units held
