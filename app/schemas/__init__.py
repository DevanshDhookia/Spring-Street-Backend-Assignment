"""
Re-export all response schemas from one place.

Importing from `app.schemas` continues to work for all existing code.
Individual schema files can also be imported directly for clarity:
    from app.schemas.product import ProductDetail
    from app.schemas.performance import PerformanceOut
"""
from app.schemas.exposures import ExposureOut
from app.schemas.growth import GrowthPoint, GrowthSeries
from app.schemas.holdings import HoldingOut
from app.schemas.nav import NAVPoint, NAVSeries
from app.schemas.performance import PerformanceOut
from app.schemas.product import (
    FeeOut,
    ManagerOut,
    PlanOut,
    ProductDetail,
    ProductSummary,
)

__all__ = [
    "ExposureOut",
    "FeeOut",
    "GrowthPoint",
    "GrowthSeries",
    "HoldingOut",
    "ManagerOut",
    "NAVPoint",
    "NAVSeries",
    "PerformanceOut",
    "PlanOut",
    "ProductDetail",
    "ProductSummary",
]
