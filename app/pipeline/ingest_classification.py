"""
Stage 3 — fetch sector, market-cap, and valuation ratios via yfinance.

SCD2 rule:
  - Sector or cap changed  → close old row, open new row (history preserved)
  - Only ratios changed    → update existing row in place (daily noise, no new history)
"""
import uuid
from datetime import date, timedelta

import yfinance as yf
from sqlalchemy.orm import Session

from app.models import Classification, Security

# yfinance sector strings → our stable sector codes
SECTOR_MAP: dict[str, str] = {
    "Technology": "TECH",
    "Financial Services": "FIN",
    "Healthcare": "HLTH",
    "Consumer Cyclical": "CONS_CYC",
    "Industrials": "INDU",
    "Communication Services": "COMM",
    "Consumer Defensive": "CONS_DEF",
    "Energy": "ENGY",
    "Basic Materials": "MATR",
    "Real Estate": "REIT",
    "Utilities": "UTIL",
}


def run(session: Session, target_date: date, run_id: uuid.UUID) -> int:
    # ETFs and benchmark indices carry no sector data
    securities = session.query(Security).filter_by(is_fund=False).all()

    active_clf = {
        c.security_id: c
        for c in session.query(Classification).filter(Classification.effective_to.is_(None)).all()
    }

    count = 0
    for sec in securities:
        try:
            info = yf.Ticker(sec.ticker).info
        except Exception:
            continue

        sector_code = SECTOR_MAP.get(info.get("sector", ""))
        cap_bucket = _cap_bucket(info.get("marketCap"))
        ratios = {
            "market_cap_usd": info.get("marketCap"),
            "pe_ratio": info.get("trailingPE"),
            "pb_ratio": info.get("priceToBook"),
            "dividend_yield": info.get("dividendYield"),
        }

        existing = active_clf.get(sec.id)

        if existing and existing.sector_code == sector_code and existing.cap_bucket == cap_bucket:
            for k, v in ratios.items():
                setattr(existing, k, v)
        else:
            if existing:
                existing.effective_to = target_date - timedelta(days=1)
            session.add(Classification(
                id=uuid.uuid4(),
                security_id=sec.id,
                sector_code=sector_code,
                cap_bucket=cap_bucket,
                effective_from=target_date,
                source="yfinance",
                **ratios,
            ))

        count += 1

    return count


def _cap_bucket(market_cap_usd) -> str | None:
    """≥$10B = large, $2B–$10B = mid, $300M–$2B = small, <$300M = micro."""
    if not market_cap_usd:
        return None
    b = market_cap_usd / 1e9
    if b >= 10:  return "large"
    if b >= 2:   return "mid"
    if b >= 0.3: return "small"
    return "micro"
