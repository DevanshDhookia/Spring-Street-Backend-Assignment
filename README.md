# Prisma Factsheet Backend

Backend system powering the daily factsheet for **Global Growth Prisma**, a global equity fund by Spring Street Capital.

**Stack:** Python · FastAPI · PostgreSQL · Redis · APScheduler · yfinance · Docker Compose

---

## Assignment Goals

> *Design and implement systems that can power the Prisma factsheet/product experience.*
> Reference: [springstreet.in/products/prisma/global-growth-prisma](https://springstreet.in/products/prisma/global-growth-prisma)

The assignment asked candidates to think through:

| Area | What was required |
|---|---|
| **Database schema design** | Model all data needed to power a SEBI-compliant factsheet |
| **Backend architecture** | Design a layered, maintainable system |
| **Data pipelines / ETL** | Fetch, transform, and store market data daily |
| **API design** | Clean REST endpoints for frontend consumption |
| **Data freshness** | Systems that update factsheet data daily without downtime |

---

## My Approach

### Step 1 — Domain Study
Before writing any code I studied the live Prisma factsheet and built a **data source matrix** — mapping every field on the factsheet to its source (yfinance, static config, or computed), storage format, and freshness requirement.

→ **[docs/Domain_Study.pdf](docs/Domain_Study.pdf)**

### Step 2 — System Architecture
Using the domain study, I designed a 3-layer architecture before writing any code:

```
INGESTION  →  STORAGE  →  SERVE
```

- **Ingestion:** APScheduler triggers a 5-stage pipeline (prices → FX → classification → derive → cache)
- **Storage:** PostgreSQL for durable relational data; Redis for sub-millisecond factsheet reads
- **Serve:** FastAPI with separate public and admin route groups

Key decisions made at this stage: atomic pipeline transaction (never show a partial factsheet), SCD2 for holdings and classification history, separate URL per data type, Redis populated only after DB commit.

→ **[docs/System_Architecture.pdf](docs/System_Architecture.pdf)**

### Step 3 — Implementation
Built the system phase by phase, committing each layer independently:

| Phase | What was built |
|---|---|
| 1 | Project scaffold — FastAPI, Docker Compose, Alembic, app skeleton |
| 2 | 15-table PostgreSQL schema with full Alembic migration and downgrade |
| 3 | Seed data — 47 regions, 11 sectors, sample AMC/product/holdings |
| 4 | 5-stage data pipeline with atomic commit and Redis cache warming |
| 5 | Public read API — 8 endpoints including growth-of-₹10k series |
| 6 | Admin API — holdings CRUD (SCD2), pipeline trigger, audit log |
| 7 | APScheduler wiring, Docker fixes, backfill script, frontend dev console |

### What I prioritised
- **Correctness over shortcuts** — atomic pipeline transaction means users never see stale/partial data
- **Financial precision** — `NUMERIC` types throughout, never `FLOAT`
- **History preservation** — SCD2 on holdings and classifications for point-in-time queries
- **Evaluator experience** — working frontend, one-command backfill, 6 documentation files

→ **[docs/06_design_decisions.md](docs/06_design_decisions.md)** — every architectural decision with rationale

---

## For Evaluators — Getting Everything Running

### Step 1 — Start the services

```bash
cp .env.example .env
docker compose up --build
```

Starts PostgreSQL (port 5433), Redis (port 6379), and the FastAPI server (port 8000).  
Wait until you see `Uvicorn running on http://0.0.0.0:8000`.

### Step 2 — Migrate + seed (in a second terminal)

```bash
docker compose exec app alembic upgrade head
docker compose exec app python -m app.seed.bootstrap
```

Creates all 15 tables and seeds one fund product with 12 holdings, 4 plans, and fees.

### Step 3 — Backfill historical data

Run from your **host terminal** (not inside Docker) — yfinance fetches data using your machine's IP:

```bash
pip install -r requirements.txt   # first time only
python backfill.py                 # last 10 trading days (~10 min)
```

> **Why not `docker compose exec`?** Yahoo Finance rate-limits Docker container IPs. Running from your host machine avoids this.

The `.env.example` points at Docker's postgres on port **5433** (avoids conflict with any local postgres on 5432).

### Step 4 — Open the frontend

```
Open  frontend/index.html  in any browser
```

No server needed. Connects directly to `http://localhost:8000`.

---

## Frontend — Dev Console

`frontend/index.html` is a single-file browser dashboard over the full API.

| Tab | What it shows |
|---|---|
| **Factsheet** | Fund details, managers, plans & fees, NAV table, benchmark names, investment objective |
| **NAV** | Interactive line chart with date range and plan filters; period return summary |
| **Holdings** | Portfolio positions with weights and market values; historical `?as_of=` date lookup |
| **Exposures** | Doughnut charts for sector / country / region / cap / asset class allocations |
| **Performance** | Trailing returns vs both benchmarks, calendar year returns, all 12 risk metrics, portfolio P/E · P/B · yield |
| **Admin** | Trigger pipeline manually, view run history with per-stage timings, add/update/close holdings (SCD2) |

---

## Running the pipeline

The pipeline runs automatically at 10 PM ET every weekday (configurable in `.env`).

```bash
# Backfill last 10 trading days — run from host (not inside Docker)
python backfill.py

# Backfill last 30 days (fuller chart history)
python backfill.py --days 30

# Specific past date
python -m app.pipeline.runner --date 2024-06-01

# Via admin API (triggers inside Docker in background)
curl -X POST http://localhost:8000/admin/pipeline/trigger \
  -H "X-Admin-Token: changeme"
```

---

## API

Base URL: `http://localhost:8000` · Interactive docs: `http://localhost:8000/docs`

| Method | Path | Description |
|---|---|---|
| GET | `/products` | List all products with latest NAV and AUM |
| GET | `/products/{code}` | Fund detail — managers, plans, fees, benchmarks, AMC CIN |
| GET | `/products/{code}/factsheet` | Headline factsheet (Redis → DB fallback) |
| GET | `/products/{code}/nav` | NAV history — `?plan_type=direct&from_date=&limit=365` |
| GET | `/products/{code}/holdings` | Portfolio positions — `?as_of=YYYY-MM-DD` for history |
| GET | `/products/{code}/exposures` | Allocation by `?dimension=sector\|country\|region\|cap\|asset_class` |
| GET | `/products/{code}/performance` | Returns + 12 risk metrics — `?lookback=1Y\|3Y\|5Y` |
| GET | `/products/{code}/growth` | Growth of ₹10,000 series — `?frequency=monthly\|daily` |
| GET | `/admin/pipeline/status` | Last pipeline run status (public) |
| POST | `/admin/pipeline/trigger` | Manual run — requires `X-Admin-Token` header |
| GET | `/admin/pipeline/runs` | Run history with per-stage timings |
| POST | `/admin/holdings` | Add a holding |
| PUT | `/admin/holdings/{id}` | Update quantity (SCD2 — preserves history) |
| DELETE | `/admin/holdings/{id}` | Close a holding (soft delete) |

---

## Documentation

| Document | Contents |
|---|---|
| [docs/Domain_Study.pdf](docs/Domain_Study.pdf) | Pre-implementation domain research — data source matrix, field-by-field freshness analysis |
| [docs/System_Architecture.pdf](docs/System_Architecture.pdf) | Architecture diagram drawn before coding — 3-layer design, data flow |
| [docs/01_overview.md](docs/01_overview.md) | Architecture diagram, stack rationale, full repo structure |
| [docs/02_setup.md](docs/02_setup.md) | Docker and manual setup, every environment variable explained |
| [docs/03_schema.md](docs/03_schema.md) | All 15 database tables with column-by-column explanation and precision rationale |
| [docs/04_pipeline.md](docs/04_pipeline.md) | All 5 pipeline stages, atomicity model, scheduler wiring, risk metric formulas, failure modes |
| [docs/05_api.md](docs/05_api.md) | Every endpoint with curl examples and full response shapes |
| [docs/06_design_decisions.md](docs/06_design_decisions.md) | D01–D15 architectural decisions with rationale and trade-offs |

---

## Environment Variables

Configured in `.env` (copy from `.env.example`):

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql://postgres:postgres@localhost:5433/prisma_factsheet` | PostgreSQL connection (port 5433 for Docker) |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection |
| `PIPELINE_CRON` | `0 22 * * 1-5` | Cron schedule (10 PM ET weekdays) |
| `PIPELINE_TIMEZONE` | `America/New_York` | Timezone for the cron |
| `RISK_FREE_RATE` | `0.05` | Annual risk-free rate for Sharpe/Sortino/Treynor |
| `CACHE_TTL` | `86400` | Redis cache TTL in seconds |
| `ADMIN_TOKEN` | `changeme` | Token for `X-Admin-Token` header on admin routes |
