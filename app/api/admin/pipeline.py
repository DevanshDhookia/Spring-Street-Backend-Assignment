"""
Admin API — pipeline management.
Trigger runs manually and inspect run history + timings.
/admin/pipeline/status is intentionally public (no token required) so dashboards
can display data-freshness without exposing admin credentials.
"""
import threading

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_admin
from app.models import PipelineRun
from app.pipeline.runner import run_pipeline

router = APIRouter(prefix="/admin/pipeline", tags=["admin"])


@router.post("/trigger", dependencies=[Depends(require_admin)])
def trigger_pipeline():
    t = threading.Thread(target=run_pipeline, kwargs={"triggered_by": "manual"}, daemon=True)
    t.start()
    return {"status": "triggered"}


@router.get("/runs", dependencies=[Depends(require_admin)])
def list_runs(db: Session = Depends(get_db), limit: int = Query(20, le=100)):
    runs = db.query(PipelineRun).order_by(PipelineRun.started_at.desc()).limit(limit).all()
    return [_run_dict(r) for r in runs]


@router.get("/status")
def pipeline_status(db: Session = Depends(get_db)):
    """Last pipeline run status — public, no token required."""
    run = db.query(PipelineRun).order_by(PipelineRun.started_at.desc()).first()
    if not run:
        return {"status": "never_run", "last_run_date": None, "started_at": None, "finished_at": None}
    return {
        "status": run.status,
        "last_run_date": run.target_date.isoformat() if run.target_date else None,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "error": run.error if run.status == "failed" else None,
    }


def _run_dict(r: PipelineRun) -> dict:
    return {
        "id": str(r.id),
        "target_date": r.target_date.isoformat() if r.target_date else None,
        "triggered_by": r.triggered_by,
        "status": r.status,
        "started_at": r.started_at.isoformat() if r.started_at else None,
        "finished_at": r.finished_at.isoformat() if r.finished_at else None,
        "rows_processed": r.rows_processed,
        "timings": r.timings,
        "error": r.error,
    }
