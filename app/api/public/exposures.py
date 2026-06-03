from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_product
from app.models import Exposure, Product
from app.schemas import ExposureOut

router = APIRouter(prefix="/products", tags=["exposures"])

VALID_DIMENSIONS = {"sector", "country", "region", "cap", "asset_class"}


@router.get("/{code}/exposures")
def get_exposures(
    product: Product = Depends(get_product),
    db: Session = Depends(get_db),
    dimension: str | None = Query(None, description="sector | country | region | cap | asset_class"),
    as_of: date | None = Query(None),
):
    if not as_of:
        latest = db.query(Exposure.as_of_date).filter_by(product_id=product.id).order_by(Exposure.as_of_date.desc()).first()
        as_of = latest[0] if latest else None

    if not as_of:
        return {}

    q = db.query(Exposure).filter_by(product_id=product.id, as_of_date=as_of)
    if dimension and dimension in VALID_DIMENSIONS:
        q = q.filter_by(dimension=dimension)

    rows = q.order_by(Exposure.weight.desc()).all()

    if dimension:
        return [ExposureOut(bucket=r.bucket, weight=float(r.weight)) for r in rows]

    result: dict = {}
    for r in rows:
        result.setdefault(r.dimension, []).append(ExposureOut(bucket=r.bucket, weight=float(r.weight)))
    return result
