"""
Admin API — holdings management.
All writes are SCD2: closing an existing row and opening a new one preserves history.
Every mutation is written to audit_log.
"""
import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_admin
from app.models import AuditLog, Holding, Product, Security

router = APIRouter(prefix="/admin/holdings", tags=["admin"])


class HoldingCreate(BaseModel):
    product_code: str
    ticker: str
    quantity: float
    effective_from: date | None = None


class HoldingUpdate(BaseModel):
    quantity: float


@router.post("", status_code=201, dependencies=[Depends(require_admin)])
def add_holding(body: HoldingCreate, db: Session = Depends(get_db)):
    product = db.query(Product).filter_by(code=body.product_code, is_active=True).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    security = db.query(Security).filter_by(ticker=body.ticker).first()
    if not security:
        raise HTTPException(status_code=404, detail="Security not found")

    eff_from = body.effective_from or date.today()

    # Close any existing active holding for this (product, security) pair
    existing = db.query(Holding).filter_by(
        product_id=product.id, security_id=security.id, effective_to=None
    ).first()
    if existing:
        existing.effective_to = eff_from - timedelta(days=1)

    holding = Holding(
        id=uuid.uuid4(),
        product_id=product.id,
        security_id=security.id,
        quantity=body.quantity,
        effective_from=eff_from,
    )
    db.add(holding)
    db.add(AuditLog(
        actor="admin",
        action="create",
        entity="holdings",
        entity_id=holding.id,
        after={"product_code": body.product_code, "ticker": body.ticker, "quantity": float(body.quantity)},
    ))
    db.commit()
    return {"id": str(holding.id)}


@router.put("/{holding_id}", dependencies=[Depends(require_admin)])
def update_holding(holding_id: uuid.UUID, body: HoldingUpdate, db: Session = Depends(get_db)):
    holding = db.query(Holding).filter_by(id=holding_id, effective_to=None).first()
    if not holding:
        raise HTTPException(status_code=404, detail="Holding not found or already closed")

    today = date.today()
    before = {"quantity": float(holding.quantity)}

    # SCD2: close old row, open new row with updated quantity
    holding.effective_to = today
    new_holding = Holding(
        id=uuid.uuid4(),
        product_id=holding.product_id,
        security_id=holding.security_id,
        quantity=body.quantity,
        effective_from=today,
    )
    db.add(new_holding)
    db.add(AuditLog(
        actor="admin",
        action="update",
        entity="holdings",
        entity_id=new_holding.id,
        before=before,
        after={"quantity": float(body.quantity)},
    ))
    db.commit()
    return {"id": str(new_holding.id)}


@router.delete("/{holding_id}", status_code=204, dependencies=[Depends(require_admin)])
def close_holding(holding_id: uuid.UUID, db: Session = Depends(get_db)):
    holding = db.query(Holding).filter_by(id=holding_id, effective_to=None).first()
    if not holding:
        raise HTTPException(status_code=404, detail="Holding not found or already closed")

    holding.effective_to = date.today()
    db.add(AuditLog(
        actor="admin",
        action="delete",
        entity="holdings",
        entity_id=holding.id,
        before={"quantity": float(holding.quantity)},
    ))
    db.commit()
