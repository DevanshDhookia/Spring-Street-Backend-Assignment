from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_product
from app.models import NAV, Plan, Product
from app.schemas import NAVPoint, NAVSeries

router = APIRouter(prefix="/products", tags=["nav"])


@router.get("/{code}/nav", response_model=NAVSeries)
def get_nav(
    product: Product = Depends(get_product),
    db: Session = Depends(get_db),
    plan_type: str = Query("direct"),
    option_type: str = Query("growth"),
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    limit: int = Query(365, le=1825),
):
    plan = db.query(Plan).filter_by(product_id=product.id, plan_type=plan_type, option_type=option_type).first()

    series = []
    if plan:
        q = db.query(NAV).filter(NAV.plan_id == plan.id)
        if from_date:
            q = q.filter(NAV.nav_date >= from_date)
        if to_date:
            q = q.filter(NAV.nav_date <= to_date)
        rows = q.order_by(NAV.nav_date.desc()).limit(limit).all()
        series = [
            NAVPoint(date=r.nav_date, nav=float(r.nav), nav_inr=float(r.nav_inr) if r.nav_inr else None, aum=float(r.aum) if r.aum else None)
            for r in reversed(rows)
        ]

    return NAVSeries(plan_type=plan_type, option_type=option_type, series=series)
