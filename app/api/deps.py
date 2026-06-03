from fastapi import Depends, HTTPException
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import PipelineRun, Product

# auto_error=False lets our own require_admin() return a cleaner 401 message
_admin_key = APIKeyHeader(name="X-Admin-Token", auto_error=False)


def get_product(code: str, db: Session = Depends(get_db)) -> Product:
    p = db.query(Product).filter_by(code=code, is_active=True).first()
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")
    return p


def pipeline_running(db: Session = Depends(get_db)) -> bool:
    """Check the DB (not Redis) — pipeline_runs is the authoritative state source."""
    run = db.query(PipelineRun).order_by(PipelineRun.started_at.desc()).first()
    return run is not None and run.status == "running"


def require_admin(token: str = Depends(_admin_key)) -> None:
    if not token or token != settings.admin_token:
        raise HTTPException(status_code=401, detail="Invalid or missing X-Admin-Token")
