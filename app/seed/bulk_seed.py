"""
Fast historical seeder — run once after bootstrap.

Fetches ALL prices and FX rates for the full date range in a single yfinance
call each, bulk-inserts them, then loops derive.run() per day (pure SQL math,
no network). Result: 3 years of data in ~15 min instead of 12 hours.

Does NOT touch the pipeline — safe to run alongside it.

Usage:
    python -m app.seed.bulk_seed                # 3 years
    python -m app.seed.bulk_seed --years 1      # 1 year
    python -m app.seed.bulk_seed --years 5      # 5 years
"""
import argparse
import math
import time
import uuid
from datetime import date, timedelta

import pandas as pd
import yfinance as yf
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.database import SessionLocal
from app.models import FXRate, Price, Security
from app.pipeline import derive, ingest_classification
from app.pipeline.runner import _register_run, _update_run


# ── helpers ──────────────────────────────────────────────────────────────────

def _f(v):
    if v is None:
        return None
    try:
        f = float(v)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


def _trading_days(start: date, end: date) -> list[date]:
    days = []
    d = start
    while d <= end:
        if d.weekday() < 5:
            days.append(d)
        d += timedelta(days=1)
    return days


# ── stage 1: bulk price fetch ─────────────────────────────────────────────

def bulk_ingest_prices(session, start: date, end: date) -> int:
    securities = session.query(Security).all()
    if not securities:
        return 0

    sec_by_ticker = {s.ticker: s for s in securities}
    tickers = list(sec_by_ticker)

    print(f"  Fetching prices for {len(tickers)} tickers from {start} to {end}…", flush=True)
    raw = yf.download(
        tickers,
        start=start.isoformat(),
        end=(end + timedelta(days=1)).isoformat(),
        auto_adjust=False,
        progress=False,
        threads=True,
    )
    if raw.empty:
        print("  No price data returned from yfinance.")
        return 0

    is_multi = isinstance(raw.columns, pd.MultiIndex)
    rows = []

    for ticker, sec in sec_by_ticker.items():
        try:
            t_df = raw.xs(ticker, axis=1, level=1) if is_multi else raw
            t_df = t_df.dropna(subset=["Close"])
            for idx, row in t_df.iterrows():
                trade_date = idx.date() if hasattr(idx, "date") else idx
                rows.append({
                    "id": uuid.uuid4(),
                    "security_id": sec.id,
                    "trade_date": trade_date,
                    "open":      _f(row.get("Open")),
                    "high":      _f(row.get("High")),
                    "low":       _f(row.get("Low")),
                    "close":     _f(row["Close"]),
                    "adj_close": _f(row.get("Adj Close")),
                    "volume":    int(row["Volume"]) if not math.isnan(float(row.get("Volume") or float("nan"))) else None,
                    "source":    "yfinance_bulk",
                })
        except (KeyError, IndexError):
            continue

    # Insert in chunks to avoid huge parameter lists
    chunk = 500
    inserted = 0
    for i in range(0, len(rows), chunk):
        result = session.execute(
            pg_insert(Price.__table__)
            .values(rows[i:i + chunk])
            .on_conflict_do_nothing(index_elements=["security_id", "trade_date"])
        )
        inserted += result.rowcount

    session.flush()
    print(f"  Prices: {inserted} new rows inserted ({len(rows)} fetched)")
    return inserted


# ── stage 2: bulk FX fetch ────────────────────────────────────────────────

def bulk_ingest_fx(session, start: date, end: date) -> int:
    from app.models import Product
    products = session.query(Product).filter_by(is_active=True).all()
    pairs = {
        (p.base_currency, p.reporting_currency)
        for p in products
        if p.base_currency != p.reporting_currency
    }
    if not pairs:
        return 0

    rows = []
    for base, quote in pairs:
        ticker_sym = f"{base}{quote}=X"
        print(f"  Fetching FX {ticker_sym} from {start} to {end}…", flush=True)
        try:
            raw = yf.download(
                ticker_sym,
                start=start.isoformat(),
                end=(end + timedelta(days=1)).isoformat(),
                progress=False,
            )
            if raw.empty:
                continue

            close_col = (
                raw[("Close", ticker_sym)]
                if ("Close", ticker_sym) in raw.columns
                else raw["Close"].iloc[:, 0] if isinstance(raw.columns, pd.MultiIndex) else raw["Close"]
            )
            close_col = close_col.dropna()

            for idx, rate in close_col.items():
                rate_date = idx.date() if hasattr(idx, "date") else idx
                rows.append({
                    "id": uuid.uuid4(),
                    "base": base,
                    "quote": quote,
                    "rate_date": rate_date,
                    "rate": float(rate),
                    "source": "yfinance_bulk",
                })
        except Exception as e:
            print(f"  FX fetch failed for {ticker_sym}: {e}")
            continue

    if not rows:
        return 0

    result = session.execute(
        pg_insert(FXRate.__table__)
        .values(rows)
        .on_conflict_do_nothing(index_elements=["base", "quote", "rate_date"])
    )
    session.flush()
    inserted = result.rowcount
    print(f"  FX rates: {inserted} new rows inserted ({len(rows)} fetched)")
    return inserted


# ── stage 3: classification (one-time, current snapshot) ─────────────────

def run_classification(session) -> None:
    run_id = uuid.uuid4()
    today = date.today()
    print("  Fetching classifications from yfinance (one per ticker)…", flush=True)
    n = ingest_classification.run(session, today, run_id)
    session.flush()
    print(f"  Classifications: {n} updated")


# ── stage 4: derive per day ────────────────────────────────────────────────

def _register_pipeline_run(run_id: uuid.UUID, target_date: date) -> None:
    from app.models import PipelineRun
    from datetime import datetime, timezone
    s = SessionLocal()
    try:
        s.add(PipelineRun(
            id=run_id,
            job_name="bulk_seed",
            triggered_by="bulk_seed",
            status="success",
            target_date=target_date,
            finished_at=datetime.now(timezone.utc),
            rows_processed=0,
        ))
        s.commit()
    finally:
        s.close()


def run_derive_all(session, trading_days: list[date]) -> None:
    total = len(trading_days)
    print(f"\n  Running derive for {total} trading days…")
    t_total = time.perf_counter()

    for i, target_date in enumerate(trading_days, 1):
        run_id = uuid.uuid4()
        _register_pipeline_run(run_id, target_date)
        try:
            rows = derive.run(session, target_date, run_id)
            if rows:
                session.flush()
            if i % 5 == 0 or i == total:
                session.commit()
                elapsed = round(time.perf_counter() - t_total)
                print(f"    [{i:03d}/{total}] {target_date}  committed  ({elapsed}s elapsed)", flush=True)
        except Exception as e:
            print(f"    [{i:03d}/{total}] {target_date}  ✗ {e}")
            session.rollback()
            session = SessionLocal()
            continue

    print(f"  Derive done  ({round(time.perf_counter() - t_total)}s total)")


# ── entrypoint ────────────────────────────────────────────────────────────

def run(years: int = 3) -> None:
    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=int(years * 365.25))
    trading_days = _trading_days(start, end)

    print(f"\nBulk seeding {years} year(s) of data")
    print(f"  {start}  →  {end}  ({len(trading_days)} trading days)\n")

    t0 = time.perf_counter()

    # ── Phase 1: bulk price + FX ingestion (network, fast) ──
    print("[1/3] Ingesting prices & FX rates (single yfinance call each)")
    session = SessionLocal()
    try:
        bulk_ingest_prices(session, start, end)
        bulk_ingest_fx(session, start, end)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    # ── Phase 2: derive per day (SQL math, no network) ──
    print("\n[2/3] Running derive per day (SQL only, no network calls)")
    session = SessionLocal()
    try:
        run_derive_all(session, trading_days)
    finally:
        session.close()

    elapsed = round(time.perf_counter() - t0)
    print(f"\n[3/3] Done in {elapsed}s ({elapsed//60}m {elapsed%60}s)")
    print("  Open frontend/index.html — all tabs should now have data.\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fast bulk historical seeder")
    parser.add_argument("--years", type=int, default=3, help="Years of history to seed (default: 3)")
    args = parser.parse_args()
    run(years=args.years)
