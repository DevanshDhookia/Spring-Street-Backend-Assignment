from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_product
from app.models import NAV, Plan, Product
from app.schemas import GrowthPoint, GrowthSeries

router = APIRouter(prefix="/products", tags=["growth"])

INITIAL = 10_000.0


@router.get("/{code}/growth", response_model=GrowthSeries)
def get_growth_series(
    product: Product = Depends(get_product),
    db: Session = Depends(get_db),
    plan_type: str = Query("direct"),
    option_type: str = Query("growth"),
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    frequency: str = Query("monthly", pattern="^(daily|monthly)$"),
):
    """Growth of ₹10,000 from inception, sampled monthly (default) or daily."""
    plan = db.query(Plan).filter_by(product_id=product.id, plan_type=plan_type, option_type=option_type).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    q = db.query(NAV).filter(NAV.plan_id == plan.id)
    if from_date:
        q = q.filter(NAV.nav_date >= from_date)
    if to_date:
        q = q.filter(NAV.nav_date <= to_date)
    rows = q.order_by(NAV.nav_date).all()

    if not rows:
        raise HTTPException(status_code=404, detail="No NAV data available")

    base_nav = float(rows[0].nav)
    if base_nav == 0:
        raise HTTPException(status_code=500, detail="Base NAV is zero")

    if frequency == "monthly":
        # Keep only the last trading day of each month
        seen: dict[tuple[int, int], NAV] = {}
        for r in rows:
            seen[(r.nav_date.year, r.nav_date.month)] = r
        sampled = sorted(seen.values(), key=lambda r: r.nav_date)
    else:
        sampled = rows

    series = [GrowthPoint(date=r.nav_date, value=round(INITIAL * float(r.nav) / base_nav, 2)) for r in sampled]

    return GrowthSeries(plan_type=plan_type, option_type=option_type, initial=INITIAL, series=series)
