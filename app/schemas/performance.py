"""Pydantic models for the performance endpoint."""
from datetime import date
from typing import Any

from pydantic import BaseModel


class PerformanceOut(BaseModel):
    """
    Full performance snapshot for one plan + lookback window combination.

    The `risk_metrics` dict contains all 12 quantitative risk indicators
    (Sharpe, Sortino, Beta, Alpha, R², Tracking Error, etc.).

    The `portfolio` dict contains weighted-average fundamental ratios
    (P/E, P/B, dividend yield, and total holdings count).
    """
    plan_type: str
    option_type: str
    as_of_date: date          # The date this snapshot was computed
    lookback: str             # "1Y", "3Y", or "5Y" — the window used for risk metrics

    trailing_returns: dict[str, Any]             # {"1M": 0.02, "3M": 0.06, ..., "SI": 0.18}
    calendar_year_returns: dict[str, Any] | None # {"2022": -0.15, "2023": 0.28, ...}
    primary_benchmark_returns: dict[str, Any] | None
    additional_benchmark_returns: dict[str, Any] | None

    growth_of_10k: dict[str, Any] | None  # {"value": 13500.0, "as_of": "2024-06-01"}

    risk_metrics: dict[str, Any]   # All 12 indicators (see ARCHITECTURE.md for formulas)
    portfolio: dict[str, Any]      # {"pe": 28.4, "pb": 5.1, "dividend_yield": 0.012, "holdings_count": 12}
