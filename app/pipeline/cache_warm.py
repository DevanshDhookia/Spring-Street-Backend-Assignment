"""Stage 5 — serialize the latest factsheet into Redis after each successful pipeline commit."""
import json
from datetime import date

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Exposure, NAV, Performance, Plan, Product
from app.redis_client import client


def run(session: Session, target_date: date) -> None:
    for product in session.query(Product).filter_by(is_active=True).all():
        _warm(session, product, target_date)


def _warm(session, product, target_date: date) -> None:
    plans = session.query(Plan).filter_by(product_id=product.id, is_active=True).all()

    navs = []
    for plan in plans:
        nav = session.query(NAV).filter_by(plan_id=plan.id, nav_date=target_date).first()
        if nav:
            navs.append({
                "plan_type": plan.plan_type,
                "option_type": plan.option_type,
                "nav": float(nav.nav),
                "nav_inr": float(nav.nav_inr) if nav.nav_inr else None,
                "aum": float(nav.aum) if nav.aum else None,
            })

    exposure_rows = (
        session.query(Exposure)
        .filter_by(product_id=product.id, as_of_date=target_date)
        .all()
    )
    exposures: dict[str, list] = {}
    for e in exposure_rows:
        exposures.setdefault(e.dimension, []).append({"bucket": e.bucket, "weight": float(e.weight)})
    for dim in exposures:
        exposures[dim].sort(key=lambda x: x["weight"], reverse=True)

    # Direct-Growth is the canonical plan shown on factsheet headlines
    direct = next((p for p in plans if p.plan_type == "direct" and p.option_type == "growth"), None)
    perf_summary = None
    if direct:
        perf = (
            session.query(Performance)
            .filter_by(plan_id=direct.id, as_of_date=target_date, lookback="1Y")
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

    payload = json.dumps({"as_of": target_date.isoformat(), "navs": navs, "exposures": exposures, "performance": perf_summary})
    client.setex(f"factsheet:{product.code}", settings.cache_ttl, payload)
