# Prisma Factsheet Backend — Overview

## What this is

A backend system that powers the daily factsheet for **Global Growth Prisma**, a mutual fund product managed by Spring Street Capital.

The live product it mirrors: `springstreet.in/products/prisma/global-growth-prisma`

Every day after US market close, the pipeline fetches prices, computes NAV, calculates portfolio exposures and risk metrics, and makes all of it available through a REST API. The frontend reads from this API to render the factsheet page.

---

## Stack

| Layer | Technology | Why |
|---|---|---|
| Language | Python 3.11 | Fast iteration; rich financial libraries |
| API framework | FastAPI + Uvicorn | Auto OpenAPI docs; async-ready; type-safe |
| ORM | SQLAlchemy 2.0 | Declarative models; transaction control |
| Migrations | Alembic | Version-controlled schema changes with rollback |
| Scheduler | APScheduler | In-process cron; logs failures to DB; no extra infra |
| Market data | yfinance | Free; covers equities, ETFs, FX rates |
| Cache | Redis | Sub-millisecond factsheet reads after pipeline runs |
| Database | PostgreSQL 16 | Relational data; transactions; GROUP BY for exposures |
| Containers | Docker Compose | One-command local setup |

---

## Architecture — Three Layers

```
┌──────────────────────────────────────────────────────┐
│                  INGESTION LAYER                     │
│                                                      │
│  APScheduler  ──►  ingest_prices                    │
│  (weekdays,         ingest_fx                        │
│   10 PM ET)         ingest_classification            │
│                     derive                           │
│                     cache_warm                       │
│                                                      │
│  Source: yfinance (prices, FX, sector/cap/ratios)   │
└─────────────────────────┬────────────────────────────┘
                          │  single atomic DB commit
┌─────────────────────────▼────────────────────────────┐
│                  STORAGE LAYER                       │
│                                                      │
│   PostgreSQL (durable)      Redis (fast-serve)       │
│   ├─ Fund details           ├─ Factsheet JSON        │
│   ├─ Market data                (24 h TTL)           │
│   ├─ Holdings (SCD2)                                 │
│   ├─ Derived snapshots                               │
│   └─ Pipeline runs / audit                          │
└─────────────────────────┬────────────────────────────┘
                          │
┌─────────────────────────▼────────────────────────────┐
│                  SERVE LAYER                         │
│                                                      │
│  FastAPI                                             │
│  Public:  GET /products  /factsheet  /nav            │
│           /holdings  /exposures  /performance        │
│           /growth                                    │
│  Admin:   POST/PUT/DELETE /admin/holdings            │
│           POST /admin/pipeline/trigger               │
└──────────────────────────────────────────────────────┘
```

---

## Repository Structure

```
Spring-Street-Backend-Assignment/
│
├── app/
│   ├── config.py            Settings (loaded from .env)
│   ├── database.py          SQLAlchemy engine + session factory
│   ├── redis_client.py      Shared Redis client
│   ├── main.py              FastAPI app + scheduler wiring
│   │
│   ├── models/              SQLAlchemy ORM models (15 tables)
│   │   ├── reference.py     Region, Sector (static seed data)
│   │   ├── core.py          AMC, FundManager, Security, Product, Plan, PlanFee
│   │   ├── market.py        Price, FXRate
│   │   ├── holdings.py      Holding, ConstituentHolding
│   │   ├── derived.py       Classification, NAV, Exposure, Performance
│   │   └── operational.py   PipelineRun, AuditLog
│   │
│   ├── schemas/             Pydantic response models (one file per domain)
│   │   ├── product.py       ProductSummary, ProductDetail, PlanOut, FeeOut
│   │   ├── nav.py           NAVPoint, NAVSeries
│   │   ├── holdings.py      HoldingOut
│   │   ├── exposures.py     ExposureOut
│   │   ├── performance.py   PerformanceOut
│   │   └── growth.py        GrowthPoint, GrowthSeries
│   │
│   ├── pipeline/            Daily data pipeline stages
│   │   ├── runner.py        Orchestrator — runs all stages, single commit
│   │   ├── ingest_prices.py Stage 1 — OHLCV via yfinance batch download
│   │   ├── ingest_fx.py     Stage 2 — FX rates (USDINR=X etc.)
│   │   ├── ingest_classification.py  Stage 3 — sector/cap/ratios, SCD2
│   │   ├── derive.py        Stage 4 — NAV, weights, exposures, performance
│   │   └── cache_warm.py    Stage 5 — serialize factsheet → Redis
│   │
│   ├── api/
│   │   ├── deps.py          Shared dependencies (get_db, get_product, require_admin)
│   │   ├── public/          Read-only endpoints (no auth)
│   │   └── admin/           Write endpoints (X-Admin-Token required)
│   │
│   └── seed/
│       ├── bootstrap.py     One-time DB seeder (AMC, product, securities, holdings)
│       ├── regions.json     47 countries with region + MSCI classification
│       └── sectors.json     11 GICS sectors
│
├── alembic/                 Database migrations
│   └── versions/001_initial_schema.py
│
├── docs/                    ← You are here
├── docker-compose.yml       Postgres + Redis + app containers
├── Dockerfile
├── .env.example             Environment variable reference
├── requirements.txt
└── README.md
```
