"""
Pipeline orchestrator.

Runs all stages in sequence. All stage writes share one session and are
committed atomically at the end — any failure rolls back the entire run,
leaving the previous day's data intact for users.

Usage:
    python -m app.pipeline.runner
    python -m app.pipeline.runner --date 2024-06-01
"""
import argparse
import time
import uuid
from datetime import date, datetime, timezone

from app.database import SessionLocal
from app.models import PipelineRun
from app.pipeline import cache_warm, derive, ingest_classification, ingest_fx, ingest_prices


def run_pipeline(target_date: date | None = None, triggered_by: str = "manual") -> None:
    if target_date is None:
        target_date = date.today()

    run_id = uuid.uuid4()
    timings: dict = {}

    # Commit the "running" record immediately so the API can reflect pipeline state
    _register_run(run_id, target_date, triggered_by)
    print(f"[pipeline] run_id={run_id}  date={target_date}")

    session = SessionLocal()
    try:
        def stage(name: str, fn) -> int:
            t0 = time.perf_counter()
            n = fn(session, target_date, run_id)
            ms = round((time.perf_counter() - t0) * 1000)
            timings[f"{name}_ms"] = ms
            print(f"  {name}: {n} rows  ({ms}ms)")
            return n

        stage("ingest_prices", ingest_prices.run)
        stage("ingest_fx", ingest_fx.run)
        stage("ingest_classification", ingest_classification.run)
        rows = stage("derive", derive.run)

        # Single atomic commit — rolls back everything if anything above failed
        session.commit()

        # Cache warm runs after commit so Redis always reflects persisted state
        t0 = time.perf_counter()
        cache_warm.run(session, target_date)
        timings["cache_warm_ms"] = round((time.perf_counter() - t0) * 1000)
        print(f"  cache_warm: done  ({timings['cache_warm_ms']}ms)")

        _update_run(run_id, "success", rows, timings, None)
        print(f"[pipeline] done  {timings}")

    except Exception as exc:
        session.rollback()
        _update_run(run_id, "failed", 0, timings, str(exc))
        print(f"[pipeline] FAILED — {exc}")
        raise
    finally:
        session.close()


def _register_run(run_id: uuid.UUID, target_date: date, triggered_by: str) -> None:
    s = SessionLocal()
    try:
        s.add(PipelineRun(
            id=run_id,
            job_name="full_pipeline",
            triggered_by=triggered_by,
            status="running",
            target_date=target_date,
        ))
        s.commit()
    finally:
        s.close()


def _update_run(run_id: uuid.UUID, status: str, rows: int, timings: dict, error) -> None:
    s = SessionLocal()
    try:
        s.query(PipelineRun).filter_by(id=run_id).update({
            "status": status,
            "finished_at": datetime.now(timezone.utc),
            "rows_processed": rows,
            "timings": timings,
            "error": error,
        })
        s.commit()
    finally:
        s.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Prisma data pipeline")
    parser.add_argument("--date", help="Target date (YYYY-MM-DD), defaults to today")
    args = parser.parse_args()
    run_pipeline(date.fromisoformat(args.date) if args.date else None)
