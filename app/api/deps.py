from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import PipelineRun, Product


def get_product(code: str, db: Session = Depends(get_db)) -> Product:
    p = db.query(Product).filter_by(code=code, is_active=True).first()
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")
    return p


def pipeline_running(db: Session = Depends(get_db)) -> bool:
    run = db.query(PipelineRun).order_by(PipelineRun.started_at.desc()).first()
    return run is not None and run.status == "running"
