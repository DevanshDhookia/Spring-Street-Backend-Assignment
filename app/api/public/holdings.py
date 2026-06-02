from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_product
from app.models import Holding, Product, Security
from app.schemas import HoldingOut

router = APIRouter(prefix="/products", tags=["holdings"])


@router.get("/{code}/holdings", response_model=list[HoldingOut])
def get_holdings(
    product: Product = Depends(get_product),
    db: Session = Depends(get_db),
    as_of: date | None = Query(None, description="Defaults to latest active holdings"),
):
    q = (
        db.query(Holding, Security)
        .join(Security, Holding.security_id == Security.id)
        .filter(Holding.product_id == product.id)
    )

    if as_of:
        q = q.filter(Holding.effective_from <= as_of).filter(
            (Holding.effective_to.is_(None)) | (Holding.effective_to >= as_of)
        )
    else:
        q = q.filter(Holding.effective_to.is_(None))

    rows = q.order_by(Holding.weight.desc().nullslast()).all()

    return [
        HoldingOut(
            ticker=sec.ticker,
            name=sec.name,
            asset_class=sec.asset_class,
            domicile=sec.domicile,
            weight=float(h.weight) if h.weight else None,
            market_value=float(h.market_value) if h.market_value else None,
            quantity=float(h.quantity),
        )
        for h, sec in rows
    ]
