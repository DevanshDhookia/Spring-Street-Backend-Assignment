"""
Bootstrap script — run once after `alembic upgrade head`.

Loads static seed data (regions, sectors) and creates a sample AMC,
fund manager, securities, product (Global Growth Prisma), plans, fees,
and initial holdings so the pipeline has real data to process.

Usage:
    python -m app.seed.bootstrap
"""
import json
import uuid
from datetime import date
from pathlib import Path

from sqlalchemy.dialects.postgresql import insert

from app.database import SessionLocal
from app.models import (
    AMC, Classification, FundManager, Holding, Plan, PlanFee,
    Product, ProductManager, Region, Sector, Security,
)

SEED_DIR = Path(__file__).parent


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def upsert(session, model, rows: list[dict], conflict_cols: list[str]) -> int:
    if not rows:
        return 0
    stmt = (
        insert(model.__table__)
        .values(rows)
        .on_conflict_do_nothing(index_elements=conflict_cols)
    )
    result = session.execute(stmt)
    return result.rowcount


# ---------------------------------------------------------------------------
# reference data
# ---------------------------------------------------------------------------

def load_regions(session) -> None:
    rows = json.loads((SEED_DIR / "regions.json").read_text())
    n = upsert(session, Region, rows, ["country_code"])
    print(f"  regions: {n} inserted")


def load_sectors(session) -> None:
    rows = json.loads((SEED_DIR / "sectors.json").read_text())
    n = upsert(session, Sector, rows, ["code"])
    print(f"  sectors: {n} inserted")


# ---------------------------------------------------------------------------
# core identity
# ---------------------------------------------------------------------------

def create_amc(session) -> AMC:
    existing = session.query(AMC).filter_by(code="SPRING_STREET").first()
    if existing:
        return existing

    amc = AMC(
        id=uuid.uuid4(),
        code="SPRING_STREET",
        name="Spring Street Capital",
        cin="U65999MH2020PLC000001",
    )
    session.add(amc)
    session.flush()
    print(f"  AMC: {amc.name}")
    return amc


def create_fund_manager(session, amc: AMC) -> FundManager:
    existing = session.query(FundManager).filter_by(amc_id=amc.id, name="Arjun Mehta").first()
    if existing:
        return existing

    mgr = FundManager(
        id=uuid.uuid4(),
        amc_id=amc.id,
        name="Arjun Mehta",
        experience_years=18,
        bio=(
            "Arjun has 18 years of experience in global equity markets, "
            "previously at Goldman Sachs Asset Management and Fidelity International. "
            "He specialises in technology and consumer sectors across developed markets."
        ),
        is_active=True,
    )
    session.add(mgr)
    session.flush()
    print(f"  Fund manager: {mgr.name}")
    return mgr


# ---------------------------------------------------------------------------
# securities
# ---------------------------------------------------------------------------

# Tickers the pipeline will fetch from yfinance.
# domicile is ISO-3166 alpha-2; currency is the native trading currency.
HOLDING_SECURITIES = [
    {"ticker": "AAPL",  "exchange": "NASDAQ", "name": "Apple Inc.",                "asset_class": "equity", "domicile": "US", "currency": "USD"},
    {"ticker": "MSFT",  "exchange": "NASDAQ", "name": "Microsoft Corp.",            "asset_class": "equity", "domicile": "US", "currency": "USD"},
    {"ticker": "NVDA",  "exchange": "NASDAQ", "name": "NVIDIA Corp.",               "asset_class": "equity", "domicile": "US", "currency": "USD"},
    {"ticker": "GOOGL", "exchange": "NASDAQ", "name": "Alphabet Inc.",              "asset_class": "equity", "domicile": "US", "currency": "USD"},
    {"ticker": "AMZN",  "exchange": "NASDAQ", "name": "Amazon.com Inc.",            "asset_class": "equity", "domicile": "US", "currency": "USD"},
    {"ticker": "META",  "exchange": "NASDAQ", "name": "Meta Platforms Inc.",        "asset_class": "equity", "domicile": "US", "currency": "USD"},
    {"ticker": "TSLA",  "exchange": "NASDAQ", "name": "Tesla Inc.",                 "asset_class": "equity", "domicile": "US", "currency": "USD"},
    {"ticker": "JPM",   "exchange": "NYSE",   "name": "JPMorgan Chase & Co.",       "asset_class": "equity", "domicile": "US", "currency": "USD"},
    {"ticker": "JNJ",   "exchange": "NYSE",   "name": "Johnson & Johnson",          "asset_class": "equity", "domicile": "US", "currency": "USD"},
    {"ticker": "ASML",  "exchange": "NASDAQ", "name": "ASML Holding N.V.",          "asset_class": "equity", "domicile": "NL", "currency": "USD"},
    {"ticker": "TSM",   "exchange": "NYSE",   "name": "Taiwan Semiconductor (ADR)", "asset_class": "equity", "domicile": "TW", "currency": "USD"},
    {"ticker": "BABA",  "exchange": "NYSE",   "name": "Alibaba Group Holding (ADR)","asset_class": "equity", "domicile": "CN", "currency": "USD"},
]

BENCHMARK_SECURITIES = [
    {"ticker": "URTH", "exchange": "NYSE", "name": "iShares MSCI World ETF",  "asset_class": "etf", "domicile": "US", "currency": "USD", "is_fund": True},
    {"ticker": "ACWI", "exchange": "NASDAQ","name": "iShares MSCI ACWI ETF",  "asset_class": "etf", "domicile": "US", "currency": "USD", "is_fund": True},
]


def create_securities(session) -> dict[str, Security]:
    result = {}
    all_specs = HOLDING_SECURITIES + BENCHMARK_SECURITIES

    for spec in all_specs:
        sec = (
            session.query(Security)
            .filter_by(ticker=spec["ticker"], exchange=spec["exchange"])
            .first()
        )
        if not sec:
            sec = Security(id=uuid.uuid4(), **spec)
            session.add(sec)
            session.flush()

        result[spec["ticker"]] = sec

    print(f"  securities: {len(all_specs)} ensured")
    return result


# ---------------------------------------------------------------------------
# product
# ---------------------------------------------------------------------------

def create_product(session, amc: AMC, securities: dict[str, Security]) -> Product:
    existing = session.query(Product).filter_by(code="GLOBAL_GROWTH_PRISMA").first()
    if existing:
        return existing

    product = Product(
        id=uuid.uuid4(),
        code="GLOBAL_GROWTH_PRISMA",
        name="Global Growth Prisma",
        amc_id=amc.id,
        inception_date=date(2022, 1, 3),
        base_currency="USD",
        reporting_currency="INR",
        scheme_type="open_ended",
        scheme_category="equity",
        scheme_sub_category="global",
        is_fund_of_funds=False,
        primary_benchmark_id=securities["URTH"].id,
        additional_benchmark_id=securities["ACWI"].id,
        risk_level="moderately_high",
        benchmark_risk_level="moderately_high",
        trustee_name="Spring Street Trustees Pvt. Ltd.",
        custodian_name="Deutsche Bank AG",
        rta_name="KFintech Private Limited",
        objective=(
            "The fund seeks long-term capital appreciation by investing in a diversified "
            "portfolio of equity and equity-related instruments of companies across global "
            "markets. The fund follows a high-conviction, growth-oriented approach with a "
            "focus on technology, consumer, and financials sectors in developed markets."
        ),
        is_active=True,
    )
    session.add(product)
    session.flush()
    print(f"  product: {product.name}")
    return product


def create_product_manager(session, product: Product, manager: FundManager) -> None:
    existing = (
        session.query(ProductManager)
        .filter_by(product_id=product.id, manager_id=manager.id)
        .first()
    )
    if existing:
        return

    pm = ProductManager(
        id=uuid.uuid4(),
        product_id=product.id,
        manager_id=manager.id,
        role="primary",
        managing_since=product.inception_date,
    )
    session.add(pm)


# ---------------------------------------------------------------------------
# plans + fees
# ---------------------------------------------------------------------------

PLANS = [
    {"plan_type": "direct",  "option_type": "growth", "min_initial": 500,  "min_additional": 100, "min_sip": 100,  "min_redemption": 100},
    {"plan_type": "direct",  "option_type": "idcw",   "min_initial": 500,  "min_additional": 100, "min_sip": 100,  "min_redemption": 100},
    {"plan_type": "regular", "option_type": "growth", "min_initial": 500,  "min_additional": 100, "min_sip": 100,  "min_redemption": 100},
    {"plan_type": "regular", "option_type": "idcw",   "min_initial": 500,  "min_additional": 100, "min_sip": 100,  "min_redemption": 100},
]

# TER in decimal: direct ~0.50%, regular ~1.50%
# Exit load: 1% if redeemed within 365 days
FEES = {
    "direct":  {"ter": 0.0050, "exit_load_pct": 0.0100, "exit_load_days": 365},
    "regular": {"ter": 0.0150, "exit_load_pct": 0.0100, "exit_load_days": 365},
}


def create_plans(session, product: Product) -> list[Plan]:
    plans = []
    for spec in PLANS:
        plan = (
            session.query(Plan)
            .filter_by(product_id=product.id, plan_type=spec["plan_type"], option_type=spec["option_type"])
            .first()
        )
        if not plan:
            plan = Plan(id=uuid.uuid4(), product_id=product.id, **spec)
            session.add(plan)
            session.flush()

            fee_spec = FEES[spec["plan_type"]]
            fee = PlanFee(
                id=uuid.uuid4(),
                plan_id=plan.id,
                ter=fee_spec["ter"],
                exit_load_pct=fee_spec["exit_load_pct"],
                exit_load_days=fee_spec["exit_load_days"],
                effective_from=product.inception_date,
            )
            session.add(fee)

        plans.append(plan)

    print(f"  plans: {len(PLANS)} ensured")
    return plans


# ---------------------------------------------------------------------------
# holdings
# ---------------------------------------------------------------------------

# Quantities set so AUM ≈ $30–40M at approximate current prices.
# The pipeline recomputes weights and market_value daily.
INITIAL_HOLDINGS = [
    {"ticker": "AAPL",  "quantity": 15000},
    {"ticker": "MSFT",  "quantity": 8000},
    {"ticker": "NVDA",  "quantity": 5000},
    {"ticker": "GOOGL", "quantity": 10000},
    {"ticker": "AMZN",  "quantity": 10000},
    {"ticker": "META",  "quantity": 5000},
    {"ticker": "TSLA",  "quantity": 10000},
    {"ticker": "JPM",   "quantity": 12000},
    {"ticker": "JNJ",   "quantity": 10000},
    {"ticker": "ASML",  "quantity": 2000},
    {"ticker": "TSM",   "quantity": 15000},
    {"ticker": "BABA",  "quantity": 20000},
]


def create_holdings(session, product: Product, securities: dict[str, Security]) -> None:
    today = date.today()
    count = 0
    for spec in INITIAL_HOLDINGS:
        sec = securities[spec["ticker"]]
        existing = (
            session.query(Holding)
            .filter_by(product_id=product.id, security_id=sec.id, effective_to=None)
            .first()
        )
        if not existing:
            session.add(Holding(
                id=uuid.uuid4(),
                product_id=product.id,
                security_id=sec.id,
                quantity=spec["quantity"],
                effective_from=today,
                source="seed",
            ))
            count += 1

    print(f"  holdings: {count} created")


# ---------------------------------------------------------------------------
# entrypoint
# ---------------------------------------------------------------------------

def run() -> None:
    print("Bootstrapping database...")
    session = SessionLocal()
    try:
        print("\n[1/5] Reference data")
        load_regions(session)
        load_sectors(session)

        print("\n[2/5] AMC & fund manager")
        amc = create_amc(session)
        manager = create_fund_manager(session, amc)

        print("\n[3/5] Securities")
        securities = create_securities(session)

        print("\n[4/5] Product, plans & fees")
        product = create_product(session, amc, securities)
        create_product_manager(session, product, manager)
        create_plans(session, product)

        print("\n[5/5] Holdings")
        create_holdings(session, product, securities)

        session.commit()
        print("\nDone. Run the pipeline next:\n  python -m app.pipeline.runner\n")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    run()
