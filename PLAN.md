# Prisma Factsheet Backend — Implementation Plan

## Overview
Backend system powering the Spring Street Prisma factsheet product experience.  
Mirrors the live product at springstreet.in/products/prisma/global-growth-prisma.

## Stack
| Concern         | Choice                        |
|-----------------|-------------------------------|
| Language        | Python 3.12                   |
| API Framework   | FastAPI + Uvicorn              |
| ORM             | SQLAlchemy 2.0                |
| Migrations      | Alembic                       |
| Scheduler       | APScheduler                   |
| Market Data     | yfinance                      |
| Cache           | Redis                         |
| Database        | PostgreSQL 16                 |
| Containerization| Docker Compose                |

## Architecture

Three layers:

```
┌─────────────────────────────────────────┐
│         INGESTION & ORCHESTRATION        │
│  APScheduler (configurable via .env)    │
│  ingest_prices → ingest_fx →            │
│  ingest_classification → derive →       │
│  cache_warm                             │
│  Source: yfinance                       │
└──────────────────┬──────────────────────┘
                   │
┌──────────────────▼──────────────────────┐
│               STORAGE                    │
│  PostgreSQL              Redis           │
│  ├─ Fund details         ├─ Market data  │
│  ├─ Market data          ├─ FX rates     │
│  ├─ Holdings (SCD2)      └─ Computed     │
│  ├─ Derived snapshots                   │
│  └─ Pipeline runs / audit log           │
└──────────────────┬──────────────────────┘
                   │
┌──────────────────▼──────────────────────┐
│                  SERVE                   │
│  FastAPI                                │
│  Public: GET /products /factsheet       │
│          /nav /holdings /exposures      │
│          /performance                   │
│  Admin:  POST/PUT /admin/holdings       │
│          /admin/products                │
│          /admin/pipeline/trigger        │
└─────────────────────────────────────────┘
```

## Key Design Decisions

| # | Decision | Choice | Why |
|---|----------|--------|-----|
| D01 | Storage | PostgreSQL + Redis | DB for durability; Redis for serving fast during/after pipeline |
| D03 | Holdings source | Admin API (DB) | No external source provided |
| D04 | Market data | yfinance only | Assignment requirement |
| D05 | Classifications | yfinance → DB (daily) | Sector/cap can change; pull & store |
| D06 | NAV | Computed daily, full history kept | Needed for return charts and performance calc |
| D07 | Pipeline schedule | Configurable via .env | US + Indian market hours differ |
| D08 | Database | PostgreSQL | Relational data, transactions, GROUP BY for exposures |
| D09 | Decimal precision | NUMERIC(20,6) prices / (10,8) weights / (20,2) money | Financial accuracy |
| D10 | Scheduler | APScheduler | Celery = overkill; cron = no failure logs |
| D11 | Consistency | Atomic transaction per pipeline run | Never show a half-updated factsheet |
| D12 | API calls | Batch yfinance fetches; track stage timing | Minimise latency and failures |
| D13 | API shape | Separate URLs per data type | Only send what the client needs |
| D14 | Serving during pipeline | Serve from DB; switch to Redis after completion | Users never see stale/partial data |
| D15 | Market hours | Configurable in .env | Supports both US and Indian schedules |

## Database Schema (15 tables)

### Seed / Reference (static, loaded once)
- `regions` — country → region + MSCI class
- `sectors` — GICS sector codes mapped to yfinance names

### Core Identity
- `amcs` — Asset Management Companies
- `fund_managers` — managers with experience/bio
- `securities` — every tradable asset (stocks, ETFs, indices, FX)
- `products` — fund products with SEBI metadata
- `product_managers` — M2M: which manager runs which fund (with since/until dates)
- `plans` — Direct/Regular × Growth/IDCW variants per product
- `plan_fees` — TER + exit load (SCD2)

### Market Data
- `prices` — OHLCV per security per day (source: yfinance)
- `fx_rates` — base/quote/date rate (source: yfinance)

### Holdings & Classification (SCD2)
- `holdings` — qty per security per product (admin-managed); weights recomputed daily
- `constituent_holdings` — look-through for fund-of-funds (ETF → underlying stocks)
- `classifications` — sector, cap bucket, PE/PB/yield per security (source: yfinance)

### Derived Snapshots (pipeline output)
- `nav` — per-plan NAV + AUM per day
- `exposures` — long-format: one row per (product, dimension, bucket, date)
- `performance` — trailing/calendar returns + all risk metrics per plan per lookback

### Operational
- `pipeline_runs` — job status, timing JSON, error capture
- `audit_log` — every admin write (who, what, before/after)

## Pipeline Stages

```
ingest_prices       fetch all security prices for target_date via yfinance
ingest_fx           fetch all required currency pairs (USD→INR etc)
ingest_classification  sector, market_cap, PE, PB, dividend_yield from yfinance
derive              compute NAV / weights / exposures / performance → atomic DB write
cache_warm          serialize factsheets → push to Redis
```

`derive` is wrapped in a single DB transaction. Any failure rolls back and the previous
day's data remains live for users.

## API Endpoints

### Public
| Method | Path | Description |
|--------|------|-------------|
| GET | `/products` | List all active products |
| GET | `/products/{code}` | Product metadata + fund details |
| GET | `/products/{code}/factsheet` | Full factsheet (Redis → DB fallback) |
| GET | `/products/{code}/nav` | NAV history, accepts `?from=&to=` |
| GET | `/products/{code}/holdings` | Current holdings with weights |
| GET | `/products/{code}/exposures` | Accepts `?dimension=sector\|country\|region\|cap` |
| GET | `/products/{code}/performance` | Accepts `?lookback=1Y\|3Y\|5Y` |

### Admin (requires `X-Admin-Token` header)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/admin/holdings` | Add a holding to a product |
| PUT | `/admin/holdings/{id}` | Update quantity (SCD2: closes old, opens new) |
| DELETE | `/admin/holdings/{id}` | Close a holding |
| POST | `/admin/pipeline/trigger` | Manual pipeline run |
| GET | `/admin/pipeline/runs` | Pipeline run history + stage timings |

## Phase Breakdown

| Phase | What ships | Commit |
|-------|-----------|--------|
| 1 | Scaffold: pyproject, docker-compose, app skeleton, Alembic init | `chore: project scaffold` |
| 2 | SQLAlchemy models + Alembic migration 001 | `feat: database schema and initial migration` |
| 3 | Seed JSON + bootstrap script (sample AMC/product/holdings) | `feat: seed data and bootstrap script` |
| 4 | Full pipeline (ingest + derive + cache_warm + runner) | `feat: data ingestion and derivation pipeline` |
| 5 | Public read API | `feat: public read API` |
| 6 | Admin API | `feat: admin API` |
| 7 | APScheduler wiring + README | `docs: README and scheduler wiring` |

## Performance Metrics Computed

| Metric | Formula |
|--------|---------|
| Trailing returns | CAGR for ≥1Y periods; simple return for <1Y |
| Calendar year returns | Year-by-year simple returns from NAV history |
| Growth of 10k | `10000 × (nav_today / nav_inception)` |
| Std dev | `std(daily_returns) × √252` (annualised) |
| Sharpe | `(mean_return_annualised − Rf) / std_dev` |
| Sortino | Sharpe but penalises only downside deviation |
| Beta | `cov(fund, benchmark) / var(benchmark)` |
| Alpha | `fund_return − (Rf + β × (benchmark_return − Rf))` annualised |
| R² | `corr(fund, benchmark)²` |
| Tracking error | `std(fund_returns − benchmark_returns) × √252` |
| Information ratio | `mean(active_returns) / std(active_returns) × √252` |
| Max drawdown | Worst peak-to-trough in lookback window |
| Upside/downside capture | Fund return / benchmark return in up/down months |

## What's Intentionally Excluded
- JWT / OAuth (simple `X-Admin-Token` is sufficient for prototype)
- Multi-source fallback for yfinance
- Test suite (not in scope)
- CI/CD
