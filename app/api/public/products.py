from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_product
from app.models import AMC, FundManager, Plan, Product, ProductManager
from app.schemas import ManagerOut, PlanOut, ProductDetail, ProductSummary

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=list[ProductSummary])
def list_products(db: Session = Depends(get_db)):
    return [
        ProductSummary(
            code=p.code,
            name=p.name,
            scheme_category=p.scheme_category,
            risk_level=p.risk_level,
            inception_date=p.inception_date,
            is_active=p.is_active,
        )
        for p in db.query(Product).filter_by(is_active=True).all()
    ]


@router.get("/{code}", response_model=ProductDetail)
def get_product_detail(product: Product = Depends(get_product), db: Session = Depends(get_db)):
    amc = db.query(AMC).filter_by(id=product.amc_id).first()

    manager_rows = (
        db.query(FundManager, ProductManager)
        .join(ProductManager, FundManager.id == ProductManager.manager_id)
        .filter(ProductManager.product_id == product.id, ProductManager.managing_until.is_(None))
        .all()
    )
    managers = [
        ManagerOut(
            name=fm.name,
            experience_years=fm.experience_years,
            managing_since=pm.managing_since,
        )
        for fm, pm in manager_rows
    ]

    plans = [
        PlanOut(
            plan_type=pl.plan_type,
            option_type=pl.option_type,
            isin=pl.isin,
            min_initial=float(pl.min_initial) if pl.min_initial else None,
            min_sip=float(pl.min_sip) if pl.min_sip else None,
        )
        for pl in db.query(Plan).filter_by(product_id=product.id, is_active=True).all()
    ]

    return ProductDetail(
        code=product.code,
        name=product.name,
        objective=product.objective,
        inception_date=product.inception_date,
        scheme_type=product.scheme_type,
        scheme_category=product.scheme_category,
        scheme_sub_category=product.scheme_sub_category,
        risk_level=product.risk_level,
        base_currency=product.base_currency,
        reporting_currency=product.reporting_currency,
        is_fund_of_funds=product.is_fund_of_funds,
        amc=amc.name if amc else "",
        managers=managers,
        plans=plans,
        trustee_name=product.trustee_name,
        custodian_name=product.custodian_name,
        rta_name=product.rta_name,
    )
