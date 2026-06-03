from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_product
from app.models import AMC, NAV, FundManager, Plan, PlanFee, Product, ProductManager, Security
from app.schemas import FeeOut, ManagerOut, PlanOut, ProductDetail, ProductSummary

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=list[ProductSummary])
def list_products(db: Session = Depends(get_db)):
    result = []
    for p in db.query(Product).filter_by(is_active=True).all():
        direct_plan = db.query(Plan).filter_by(product_id=p.id, plan_type="direct", option_type="growth", is_active=True).first()
        nav_row = (
            db.query(NAV).filter_by(plan_id=direct_plan.id).order_by(NAV.nav_date.desc()).first()
            if direct_plan else None
        )
        result.append(ProductSummary(
            code=p.code,
            name=p.name,
            scheme_category=p.scheme_category,
            risk_level=p.risk_level,
            inception_date=p.inception_date,
            is_active=p.is_active,
            latest_nav=float(nav_row.nav) if nav_row else None,
            latest_nav_date=nav_row.nav_date if nav_row else None,
            aum=float(nav_row.aum) if nav_row and nav_row.aum else None,
        ))
    return result


@router.get("/{code}", response_model=ProductDetail)
def get_product_detail(product: Product = Depends(get_product), db: Session = Depends(get_db)):
    amc = db.query(AMC).filter_by(id=product.amc_id).first()

    manager_rows = (
        db.query(FundManager, ProductManager)
        .join(ProductManager, FundManager.id == ProductManager.manager_id)
        .filter(ProductManager.product_id == product.id, ProductManager.managing_until.is_(None))
        .all()
    )

    plans = []
    for pl in db.query(Plan).filter_by(product_id=product.id, is_active=True).all():
        fee_row = db.query(PlanFee).filter_by(plan_id=pl.id, effective_to=None).order_by(PlanFee.effective_from.desc()).first()
        plans.append(PlanOut(
            plan_type=pl.plan_type,
            option_type=pl.option_type,
            isin=pl.isin,
            min_initial=float(pl.min_initial) if pl.min_initial else None,
            min_sip=float(pl.min_sip) if pl.min_sip else None,
            min_additional=float(pl.min_additional) if pl.min_additional else None,
            fees=FeeOut(
                ter=float(fee_row.ter) if fee_row else None,
                exit_load_pct=float(fee_row.exit_load_pct) if fee_row and fee_row.exit_load_pct else None,
                exit_load_days=fee_row.exit_load_days if fee_row else None,
            ),
        ))

    bench = db.query(Security).filter_by(id=product.primary_benchmark_id).first() if product.primary_benchmark_id else None
    add_bench = db.query(Security).filter_by(id=product.additional_benchmark_id).first() if product.additional_benchmark_id else None

    return ProductDetail(
        code=product.code,
        name=product.name,
        objective=product.objective,
        inception_date=product.inception_date,
        scheme_type=product.scheme_type,
        scheme_category=product.scheme_category,
        scheme_sub_category=product.scheme_sub_category,
        risk_level=product.risk_level,
        benchmark_risk_level=product.benchmark_risk_level,
        base_currency=product.base_currency,
        reporting_currency=product.reporting_currency,
        is_fund_of_funds=product.is_fund_of_funds,
        amc=amc.name if amc else "",
        amc_cin=amc.cin if amc else None,
        primary_benchmark=bench.name if bench else None,
        additional_benchmark=add_bench.name if add_bench else None,
        managers=[ManagerOut(name=fm.name, experience_years=fm.experience_years, managing_since=pm.managing_since) for fm, pm in manager_rows],
        plans=plans,
        trustee_name=product.trustee_name,
        custodian_name=product.custodian_name,
        rta_name=product.rta_name,
    )
