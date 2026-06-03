from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_product
from app.models import Performance, Plan, Product
from app.schemas import PerformanceOut

router = APIRouter(prefix="/products", tags=["performance"])

RISK_KEYS = (
    "std_dev", "sharpe", "sortino", "treynor", "beta", "alpha",
    "r_squared", "tracking_error", "information_ratio",
    "max_drawdown", "upside_capture", "downside_capture",
)


@router.get("/{code}/performance", response_model=PerformanceOut)
def get_performance(
    product: Product = Depends(get_product),
    db: Session = Depends(get_db),
    plan_type: str = Query("direct"),
    option_type: str = Query("growth"),
    lookback: str = Query("1Y", pattern="^(1Y|3Y|5Y)$"),
):
    plan = db.query(Plan).filter_by(product_id=product.id, plan_type=plan_type, option_type=option_type).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    row = db.query(Performance).filter_by(plan_id=plan.id, lookback=lookback).order_by(Performance.as_of_date.desc()).first()
    if not row:
        raise HTTPException(status_code=404, detail="No performance data available yet")

    return PerformanceOut(
        plan_type=plan_type,
        option_type=option_type,
        as_of_date=row.as_of_date,
        lookback=row.lookback,
        trailing_returns=row.trailing_returns or {},
        calendar_year_returns=row.calendar_year_returns,
        primary_benchmark_returns=row.primary_benchmark_returns,
        additional_benchmark_returns=row.additional_benchmark_returns,
        growth_of_10k=row.growth_of_10k,
        risk_metrics={k: float(getattr(row, k)) if getattr(row, k) is not None else None for k in RISK_KEYS},
        portfolio={
            "pe": float(row.portfolio_pe) if row.portfolio_pe else None,
            "pb": float(row.portfolio_pb) if row.portfolio_pb else None,
            "dividend_yield": float(row.portfolio_dividend_yield) if row.portfolio_dividend_yield else None,
            "holdings_count": row.holdings_count,
        },
    )
