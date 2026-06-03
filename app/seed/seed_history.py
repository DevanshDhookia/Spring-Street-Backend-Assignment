"""
Backfill historical pipeline data for the last N trading days.

Run this once after bootstrap so the frontend has NAV history,
performance metrics, and exposure charts to display.

Usage:
    python -m app.seed.seed_history          # last 30 trading days
    python -m app.seed.seed_history --days 60
"""
import argparse
import sys
import time
from datetime import date, timedelta

from app.pipeline.runner import run_pipeline


def last_n_trading_days(n: int) -> list[date]:
    """Return the last N weekdays before today, most recent first."""
    days = []
    d = date.today() - timedelta(days=1)  # start from yesterday (today's market may still be open)
    while len(days) < n:
        if d.weekday() < 5:   # 0=Mon … 4=Fri
            days.append(d)
        d -= timedelta(days=1)
    return days


def run(n: int = 30) -> None:
    trading_days = last_n_trading_days(n)

    print(f"\nBackfilling {len(trading_days)} trading days")
    print(f"  From : {trading_days[-1]}  →  To: {trading_days[0]}")
    print(f"  This fetches live prices from yfinance — takes ~60s per day\n")

    success = 0
    failed  = 0

    # Process oldest → newest so NAV series builds up in order
    for i, target_date in enumerate(reversed(trading_days), 1):
        print(f"[{i:02d}/{len(trading_days)}] {target_date} ", end="", flush=True)
        t0 = time.perf_counter()
        try:
            run_pipeline(target_date=target_date, triggered_by="seed_history")
            elapsed = round(time.perf_counter() - t0)
            print(f"✓  ({elapsed}s)")
            success += 1
        except Exception as e:
            print(f"✗  {e}")
            failed += 1
            # Don't stop — skip bad days (holidays, yfinance gaps) and continue
            continue

    print(f"\nDone. {success} succeeded, {failed} failed.")
    if success == 0:
        print("No data was written. Check your database connection and yfinance availability.")
        sys.exit(1)
    else:
        print("\nNext steps:")
        print("  Open frontend/index.html in your browser")
        print("  Click on 'Global Growth Prisma' in the sidebar")
        print("  All tabs (NAV chart, Holdings, Exposures, Performance) should now have data\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill historical pipeline data")
    parser.add_argument("--days", type=int, default=30, help="Number of trading days to backfill (default: 30)")
    args = parser.parse_args()
    run(n=args.days)
