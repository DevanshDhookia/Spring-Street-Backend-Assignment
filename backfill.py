"""
Run the data pipeline for the last N trading days.

Use this right after setup so the frontend has real data to display —
NAV charts, performance metrics, exposure breakdowns, and holdings.

Usage:
    python backfill.py           # last 10 trading days  (fast, ~10 min)
    python backfill.py --days 30 # last 30 days          (full charts, ~30 min)
    python backfill.py --days 1  # yesterday only        (quick smoke test)
"""
import argparse
import sys
import time
from datetime import date, timedelta


def last_n_trading_days(n: int) -> list[date]:
    days, d = [], date.today() - timedelta(days=1)
    while len(days) < n:
        if d.weekday() < 5:   # Mon–Fri only
            days.append(d)
        d -= timedelta(days=1)
    return days  # most recent first


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill pipeline data for the last N trading days")
    parser.add_argument("--days", type=int, default=10, help="Number of trading days (default: 10)")
    args = parser.parse_args()

    from app.pipeline.runner import run_pipeline

    trading_days = last_n_trading_days(args.days)
    print(f"\nBackfilling {len(trading_days)} trading days")
    print(f"  {trading_days[-1]}  →  {trading_days[0]}")
    print(f"  (yfinance fetches live data — ~60s per day)\n")

    ok, fail = 0, 0
    for i, d in enumerate(reversed(trading_days), 1):  # oldest → newest
        print(f"  [{i:02d}/{len(trading_days)}] {d} ", end="", flush=True)
        t0 = time.perf_counter()
        try:
            run_pipeline(target_date=d, triggered_by="backfill")
            print(f"✓  ({round(time.perf_counter()-t0)}s)")
            ok += 1
        except Exception as e:
            print(f"✗  {e}")
            fail += 1   # skip bad days (holidays, yfinance gaps) and keep going

    print(f"\n{'─'*40}")
    print(f"  {ok} days succeeded  ·  {fail} skipped")

    if ok == 0:
        print("\n  No data written. Check your DB connection and yfinance availability.")
        sys.exit(1)

    print("""
  ✓ Done! Open the frontend to see everything live:

      open frontend/index.html          (Mac)
      start frontend/index.html         (Windows)

  Click "Global Growth Prisma" in the sidebar.
  All tabs — NAV chart, Holdings, Exposures, Performance — should now have data.
""")


if __name__ == "__main__":
    main()
