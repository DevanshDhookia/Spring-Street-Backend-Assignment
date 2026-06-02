"""
Compute NAV, holding weights, exposures, and performance from ingested data.
All writes happen inside the caller's session — the runner commits atomically.
"""
import math
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import numpy as np
import pandas as pd
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.config import settings
from app.models import (
    Classification, Exposure, FXRate, Holding, NAV,
    Performance, Plan, Price, Product, Region, Security,
)


def run(session: Session, target_date: date, run_id: uuid.UUID) -> int:
    regions = {r.country_code: r.region for r in session.query(Region).all()}
    active_clf = {
        c.security_id: c
        for c in session.query(Classification).filter(Classification.effective_to.is_(None)).all()
    }
    products = session.query(Product).filter_by(is_active=True).all()

    total = 0
    for product in products:
        total += _process_product(session, product, target_date, run_id, regions, active_clf)
    return total


# ---------------------------------------------------------------------------

def _process_product(session, product, target_date, run_id, regions, active_clf) -> int:
    holdings = (
        session.query(Holding, Security)
        .join(Security, Holding.security_id == Security.id)
        .filter(Holding.product_id == product.id, Holding.effective_to.is_(None))
        .all()
    )
    if not holdings:
        return 0

    security_ids = [h.security_id for h, _ in holdings]
    price_map = {
        p.security_id: float(p.adj_close or p.close)
        for p in session.query(Price).filter(
            Price.security_id.in_(security_ids),
            Price.trade_date == target_date,
        ).all()
    }
    if not price_map:
        return 0

    aum = sum(
        float(h.quantity) * price_map[h.security_id]
        for h, _ in holdings
        if h.security_id in price_map
    )
    if aum == 0:
        return 0

    fx = _get_fx(session, product.base_currency, product.reporting_currency, target_date)

    # Update weights on active holdings
    for holding, _ in holdings:
        if holding.security_id in price_map:
            mv = float(holding.quantity) * price_map[holding.security_id]
            holding.weight = mv / aum
            holding.market_value = mv
            holding.run_id = run_id

    plans = session.query(Plan).filter_by(product_id=product.id, is_active=True).all()
    for plan in plans:
        units = _last_units(session, plan) or 1_000_000
        nav_val = aum / units
        _upsert_nav(session, plan.id, target_date, nav_val, nav_val * fx if fx else None, aum, units, run_id)

    _write_exposures(session, product, holdings, price_map, aum, target_date, run_id, regions, active_clf)
    _write_performance(session, product, plans, target_date, run_id)

    return len(plans)


# ---------------------------------------------------------------------------
# helpers

def _get_fx(session, base: str, quote: str, target_date: date) -> Optional[float]:
    if base == quote:
        return 1.0
    row = (
        session.query(FXRate)
        .filter_by(base=base, quote=quote)
        .filter(FXRate.rate_date <= target_date)
        .order_by(FXRate.rate_date.desc())
        .first()
    )
    return float(row.rate) if row else None


def _last_units(session, plan: Plan) -> Optional[float]:
    row = (
        session.query(NAV.units_outstanding)
        .filter_by(plan_id=plan.id)
        .order_by(NAV.nav_date.desc())
        .first()
    )
    return float(row[0]) if row and row[0] else None


def _upsert_nav(session, plan_id, nav_date, nav, nav_inr, aum, units, run_id):
    row = {
        "id": uuid.uuid4(),
        "plan_id": plan_id,
        "nav_date": nav_date,
        "nav": nav,
        "nav_inr": nav_inr,
        "aum": aum,
        "units_outstanding": units,
        "run_id": run_id,
        "computed_at": datetime.now(timezone.utc),
    }
    update_cols = ("nav", "nav_inr", "aum", "run_id", "computed_at")
    session.execute(
        pg_insert(NAV.__table__)
        .values(row)
        .on_conflict_do_update(
            index_elements=["plan_id", "nav_date"],
            set_={k: row[k] for k in update_cols},
        )
    )


# ---------------------------------------------------------------------------
# exposures

def _write_exposures(session, product, holdings, price_map, aum, target_date, run_id, regions, active_clf):
    weights = {
        h.security_id: {
            "w": float(h.quantity) * price_map[h.security_id] / aum,
            "sec": sec,
            "clf": active_clf.get(h.security_id),
        }
        for h, sec in holdings
        if h.security_id in price_map
    }

    dimensions = {
        "sector":      lambda d: (d["clf"].sector_code if d["clf"] and d["clf"].sector_code else "Unknown"),
        "country":     lambda d: (d["sec"].domicile or "Unknown"),
        "region":      lambda d: (regions.get(d["sec"].domicile, "Unknown") if d["sec"].domicile else "Unknown"),
        "cap":         lambda d: (d["clf"].cap_bucket if d["clf"] and d["clf"].cap_bucket else "Unknown"),
        "asset_class": lambda d: d["sec"].asset_class,
    }

    # Delete stale exposures for this date so re-runs are idempotent
    session.query(Exposure).filter_by(product_id=product.id, as_of_date=target_date).delete()

    rows = []
    for dim, fn in dimensions.items():
        agg: dict[str, float] = {}
        for data in weights.values():
            key = fn(data)
            agg[key] = agg.get(key, 0.0) + data["w"]
        for bucket, weight in agg.items():
            rows.append(Exposure(
                id=uuid.uuid4(),
                product_id=product.id,
                dimension=dim,
                bucket=bucket,
                weight=weight,
                as_of_date=target_date,
                run_id=run_id,
            ))

    session.add_all(rows)


# ---------------------------------------------------------------------------
# performance

def _write_performance(session, product, plans, target_date, run_id):
    bench_series = _bench_series(session, product, target_date)

    for plan in plans:
        for lookback, days in [("1Y", 252), ("3Y", 756), ("5Y", 1260)]:
            _write_plan_perf(session, plan, product, target_date, run_id, days, lookback, bench_series)


def _bench_series(session, product, target_date) -> Optional[pd.Series]:
    if not product.primary_benchmark_id:
        return None
    rows = (
        session.query(Price.trade_date, Price.adj_close, Price.close)
        .filter(
            Price.security_id == product.primary_benchmark_id,
            Price.trade_date <= target_date,
        )
        .order_by(Price.trade_date)
        .all()
    )
    if not rows:
        return None
    return pd.Series(
        [float(r.adj_close or r.close) for r in rows],
        index=[r.trade_date for r in rows],
    )


def _write_plan_perf(session, plan, product, target_date, run_id, days, lookback, bench_series):
    start = target_date - timedelta(days=days)
    nav_rows = (
        session.query(NAV.nav_date, NAV.nav)
        .filter(NAV.plan_id == plan.id, NAV.nav_date >= start, NAV.nav_date <= target_date)
        .order_by(NAV.nav_date)
        .all()
    )
    if len(nav_rows) < 2:
        return

    navs = pd.Series([float(r.nav) for r in nav_rows], index=[r.nav_date for r in nav_rows])
    fund_returns = navs.pct_change().dropna()

    bench_trailing = {}
    if bench_series is not None:
        bench_window = bench_series[bench_series.index >= start]
        if len(bench_window) >= 2:
            bench_trailing = _trailing_returns(bench_window)

    risk: dict = {}
    if bench_series is not None and len(fund_returns) >= 20:
        bench_ret = bench_series.pct_change().dropna()
        risk = _risk_metrics(fund_returns, bench_ret)

    # Growth of 10k since inception (not just the lookback window)
    inception_nav = session.query(NAV.nav).filter_by(plan_id=plan.id).order_by(NAV.nav_date).first()
    growth_of_10k = None
    if inception_nav:
        growth_of_10k = {
            "value": round(10000 * float(navs.iloc[-1]) / float(inception_nav[0]), 2),
            "as_of": target_date.isoformat(),
        }

    # Weighted portfolio ratios
    holdings = session.query(Holding).filter_by(product_id=product.id, effective_to=None).all()
    clf_map = {
        c.security_id: c
        for c in session.query(Classification).filter(Classification.effective_to.is_(None)).all()
    }
    port_pe, port_pb, port_dy = _weighted_ratios(holdings, clf_map)

    row = {
        "id": uuid.uuid4(),
        "plan_id": plan.id,
        "as_of_date": target_date,
        "trailing_returns": _trailing_returns(navs),
        "calendar_year_returns": _calendar_returns(navs),
        "primary_benchmark_returns": bench_trailing or None,
        "additional_benchmark_returns": None,
        "growth_of_10k": growth_of_10k,
        "lookback": lookback,
        "portfolio_pe": port_pe,
        "portfolio_pb": port_pb,
        "portfolio_dividend_yield": port_dy,
        "holdings_count": len([h for h in holdings if h.effective_to is None]),
        "run_id": run_id,
        "computed_at": datetime.now(timezone.utc),
        **risk,
    }

    update_cols = {k for k in row if k not in ("id", "plan_id", "as_of_date", "lookback")}
    session.execute(
        pg_insert(Performance.__table__)
        .values(row)
        .on_conflict_do_update(
            index_elements=["plan_id", "as_of_date", "lookback"],
            set_={k: row[k] for k in update_cols},
        )
    )


# ---------------------------------------------------------------------------
# maths

def _trailing_returns(navs: pd.Series) -> dict:
    result = {}
    n = len(navs)
    for label, td, annualize in [
        ("1M", 21, False), ("3M", 63, False), ("6M", 126, False),
        ("1Y", 252, False), ("3Y", 756, True), ("5Y", 1260, True),
    ]:
        if n > td:
            ratio = float(navs.iloc[-1] / navs.iloc[-td])
            r = (ratio ** (252 / td) - 1) if annualize else (ratio - 1)
            result[label] = _r(r)
    if n >= 2:
        days = (navs.index[-1] - navs.index[0]).days or 1
        years = days / 365.25
        si = (float(navs.iloc[-1] / navs.iloc[0]) ** (1 / years) - 1) if years >= 1 else float(navs.iloc[-1] / navs.iloc[0]) - 1
        result["SI"] = _r(si)
    return result


def _calendar_returns(navs: pd.Series) -> dict:
    result = {}
    for yr in sorted({d.year for d in navs.index}):
        yr_navs = navs[[d for d in navs.index if d.year == yr]]
        if len(yr_navs) >= 2:
            result[str(yr)] = _r(float(yr_navs.iloc[-1] / yr_navs.iloc[0]) - 1)
    return result


def _risk_metrics(fund: pd.Series, bench: pd.Series) -> dict:
    aligned = pd.concat([fund, bench], axis=1, join="inner").dropna()
    if len(aligned) < 20:
        return {}
    aligned.columns = ["f", "b"]
    f, b = aligned["f"], aligned["b"]
    rf = settings.risk_free_rate / 252

    std_dev = float(f.std() * np.sqrt(252))
    sharpe = _safe(float((f.mean() - rf) / f.std() * np.sqrt(252)) if f.std() > 0 else None)

    downside = f[f < rf] - rf
    sortino = _safe(float((f.mean() - rf) / downside.std() * np.sqrt(252)) if len(downside) > 1 and downside.std() > 0 else None)

    cov = np.cov(f.values, b.values)
    beta = _safe(float(cov[0, 1] / cov[1, 1]) if cov[1, 1] > 0 else None)

    fund_ann = float(f.mean() * 252)
    bench_ann = float(b.mean() * 252)
    alpha = _safe(fund_ann - (settings.risk_free_rate + (beta or 0) * (bench_ann - settings.risk_free_rate)))
    treynor = _safe((fund_ann - settings.risk_free_rate) / beta if beta and beta != 0 else None)

    corr = float(np.corrcoef(f.values, b.values)[0, 1])
    r_squared = _safe(corr ** 2)

    tracking = f - b
    tracking_error = _safe(float(tracking.std() * np.sqrt(252)))
    information_ratio = _safe(float(tracking.mean() / tracking.std() * np.sqrt(252)) if tracking.std() > 0 else None)

    cum = (1 + f).cumprod()
    max_drawdown = _safe(float((cum / cum.cummax() - 1).min()))

    up, down = b > 0, b < 0
    upside_capture = _safe(float(f[up].mean() / b[up].mean()) if up.sum() > 0 and b[up].mean() != 0 else None)
    downside_capture = _safe(float(f[down].mean() / b[down].mean()) if down.sum() > 0 and b[down].mean() != 0 else None)

    return dict(
        std_dev=std_dev, sharpe=sharpe, sortino=sortino, treynor=treynor,
        beta=beta, alpha=alpha, r_squared=r_squared,
        tracking_error=tracking_error, information_ratio=information_ratio,
        max_drawdown=max_drawdown, upside_capture=upside_capture, downside_capture=downside_capture,
    )


def _weighted_ratios(holdings, clf_map):
    total_w = sum(float(h.weight) for h in holdings if h.weight) or 1
    pe = pb = dy = 0.0
    for h in holdings:
        clf = clf_map.get(h.security_id)
        if not clf or not h.weight:
            continue
        w = float(h.weight) / total_w
        if clf.pe_ratio:      pe += float(clf.pe_ratio) * w
        if clf.pb_ratio:      pb += float(clf.pb_ratio) * w
        if clf.dividend_yield: dy += float(clf.dividend_yield) * w
    return (pe or None, pb or None, dy or None)


def _r(v) -> float:
    return round(v, 6)


def _safe(v) -> Optional[float]:
    if v is None:
        return None
    try:
        return None if math.isnan(float(v)) or math.isinf(float(v)) else v
    except (TypeError, ValueError):
        return None
