"""Fetch FX rates for all (base, reporting) currency pairs used by active products."""
import uuid
from datetime import date, timedelta

import yfinance as yf
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models import FXRate, Product


def run(session: Session, target_date: date, run_id: uuid.UUID) -> int:
    products = session.query(Product).filter_by(is_active=True).all()
    pairs = {
        (p.base_currency, p.reporting_currency)
        for p in products
        if p.base_currency != p.reporting_currency
    }
    if not pairs:
        return 0

    end = (target_date + timedelta(days=1)).isoformat()
    rows = []

    for base, quote in pairs:
        try:
            raw = yf.download(
                f"{base}{quote}=X",
                start=target_date.isoformat(),
                end=end,
                progress=False,
            )
            if raw.empty or raw["Close"].isna().all():
                continue
            rows.append({
                "id": uuid.uuid4(),
                "base": base,
                "quote": quote,
                "rate_date": target_date,
                "rate": float(raw["Close"].iloc[0]),
                "source": "yfinance",
            })
        except Exception:
            continue

    if rows:
        session.execute(
            pg_insert(FXRate.__table__)
            .values(rows)
            .on_conflict_do_nothing(index_elements=["base", "quote", "rate_date"])
        )
    return len(rows)
