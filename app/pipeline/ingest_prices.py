"""Stage 1 — fetch OHLCV prices for all securities in one batched yfinance call."""
import math
import uuid
from datetime import date, timedelta

import pandas as pd
import yfinance as yf
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models import Price, Security


def run(session: Session, target_date: date, run_id: uuid.UUID) -> int:
    securities = session.query(Security).all()
    if not securities:
        return 0

    sec_by_ticker = {s.ticker: s for s in securities}

    # One batch call for all tickers — far fewer network round-trips than per-ticker calls
    raw = yf.download(
        list(sec_by_ticker),
        start=target_date.isoformat(),
        end=(target_date + timedelta(days=1)).isoformat(),  # end is exclusive
        auto_adjust=False,  # keep both Close and Adj Close
        progress=False,
        threads=True,
    )
    if raw.empty:
        return 0

    # Multi-ticker downloads return a MultiIndex; single-ticker returns flat columns
    is_multi = isinstance(raw.columns, pd.MultiIndex)
    rows = []

    for ticker, sec in sec_by_ticker.items():
        try:
            t_df = raw.xs(ticker, axis=1, level=1) if is_multi else raw
            if t_df.empty or _nan(t_df["Close"].iloc[0]):
                continue
            r = t_df.iloc[0]
            rows.append({
                "id": uuid.uuid4(),
                "security_id": sec.id,
                "trade_date": target_date,
                "open": _f(r.get("Open")),
                "high": _f(r.get("High")),
                "low": _f(r.get("Low")),
                "close": _f(r["Close"]),
                "adj_close": _f(r.get("Adj Close")),
                "volume": int(r["Volume"]) if not _nan(r.get("Volume")) else None,
                "source": "yfinance",
            })
        except (KeyError, IndexError):
            continue

    if rows:
        # ON CONFLICT DO NOTHING makes re-running the pipeline for the same date safe
        session.execute(
            pg_insert(Price.__table__)
            .values(rows)
            .on_conflict_do_nothing(index_elements=["security_id", "trade_date"])
        )
    return len(rows)


def _f(v) -> float | None:
    if v is None:
        return None
    try:
        f = float(v)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


def _nan(v) -> bool:
    if v is None:
        return True
    try:
        return math.isnan(float(v))
    except (TypeError, ValueError):
        return True
