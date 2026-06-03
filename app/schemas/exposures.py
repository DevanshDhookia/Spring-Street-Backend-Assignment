"""Pydantic models for the exposure (allocation) endpoint."""
from pydantic import BaseModel


class ExposureOut(BaseModel):
    """
    One row in an exposure breakdown.

    Example (sector dimension):
        {"bucket": "Technology", "weight": 0.42}
    """
    bucket: str    # The label for this allocation slice (sector name, country code, etc.)
    weight: float  # Decimal weight of this bucket in the portfolio (0.42 = 42%)
