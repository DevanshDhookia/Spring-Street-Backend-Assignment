"""
GET /products/{code}/factsheet

Serving strategy (Decision 14):
  - Pipeline running   → serve from DB (safe, never partial)
  - Redis cache hit    → serve from Redis (fast path)
  - Cache miss         → build from DB and return
"""
import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_product, pipeline_running
from app.models import Exposure, NAV, Performance, Plan, Product
from app.redis_client import client

router = APIRouter(prefix="/products", tags=["factsheet"])


@router.get("/{code}/factsheet")
def get_factsheet(
    product: Product = Depends(get_product),
    db: Session = Depends(get_db),
    running: bool = Depends(pipeline_running),
):
    if not running:
        cached = client.get(f"factsheet:{product.code}")
        if cached:
            return json.loads(cached)

    return _build_from_db(db, product)


def _build_from_db(db: Session, product: Product) -> dict:
    plans = db.query(Plan).filter_by(product_id=product.id, is_active=True).all()

    navs = []
    latest_date = None
    for plan in plans:
        row = db.query(NAV).filter_by(plan_id=plan.id).order_by(NAV.nav_date.desc()).first()
        if row:
            if latest_date is None or row.nav_date > latest_date:
                latest_date = row.nav_date
            navs.append({
                "plan_type": plan.plan_type,
                "option_type": plan.option_type,
                "nav": float(row.nav),
                "nav_inr": float(row.nav_inr) if row.nav_inr else None,
                "aum": float(row.aum) if row.aum else None,
                "as_of": row.nav_date.isoformat(),
            })

    exposures: dict = {}
    if latest_date:
        rows = db.query(Exposure).filter_by(product_id=product.id, as_of_date=latest_date).all()
        for e in rows:
            exposures.setdefault(e.dimension, []).append(
                {"bucket": e.bucket, "weight": float(e.weight)}
            )
        for dim in exposures:
            exposures[dim].sort(key=lambda x: x["weight"], reverse=True)

    perf_summary = None
    direct = next((p for p in plans if p.plan_type == "direct" and p.option_type == "growth"), None)
    if direct and latest_date:
        perf = (
            db.query(Performance)
            .filter_by(plan_id=direct.id, as_of_date=latest_date, lookback="1Y")
            .first()
        )
        if perf:
            perf_summary = {
                "trailing_returns": perf.trailing_returns,
                "growth_of_10k": perf.growth_of_10k,
                "sharpe": float(perf.sharpe) if perf.sharpe else None,
                "max_drawdown": float(perf.max_drawdown) if perf.max_drawdown else None,
                "std_dev": float(perf.std_dev) if perf.std_dev else None,
                "holdings_count": perf.holdings_count,
            }

    return {
        "as_of": latest_date.isoformat() if latest_date else None,
        "navs": navs,
        "exposures": exposures,
        "performance": perf_summary,
    }
