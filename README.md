# Prisma Factsheet Backend

Backend system powering the daily factsheet for **Global Growth Prisma**, a global equity fund by Spring Street Capital.

**Stack:** Python · FastAPI · PostgreSQL · Redis · APScheduler · yfinance · Docker Compose

---

## For Evaluators — Getting Everything Running

### Step 1 — Start the services

```bash
cp .env.example .env
docker compose up --build
```

Starts PostgreSQL, Redis, and the FastAPI server. Wait until you see `Uvicorn running on http://0.0.0.0:8000`.

### Step 2 — Migrate + seed (in a second terminal)

```bash
docker compose exec app alembic upgrade head
docker compose exec app python -m app.seed.bootstrap
```

Creates all 15 tables and seeds one fund product with 12 holdings, 4 plans, and fees.

### Step 3 — Backfill historical data

Run this from your **host terminal** (not inside Docker) — yfinance fetches data using your machine's IP:

```bash
python backfill.py
```

> **Why not `docker compose exec`?** Yahoo Finance rate-limits Docker container IPs. Running from your host machine avoids this.
>
> **Prerequisites for running locally:** Python 3.11+ and `pip install -r requirements.txt` in a virtualenv.

This fetches the last 10 trading days of live prices from yfinance, computes NAV, exposures, and all performance metrics, and caches results in Redis.

> Takes ~60 seconds per day. Use `--days 30` for fuller chart history or `--days 1` for a quick smoke test.

The `.env.example` is pre-configured to point at Docker's postgres on port **5433** (to avoid conflict with any local postgres on 5432).

### Step 4 — Open the frontend

```
Open  frontend/index.html  in any browser
```

No extra server needed. The file connects directly to `http://localhost:8000`.

---

## Frontend — Dev Console

`frontend/index.html` is a single-file browser dashboard over the full API.

| Tab | What it shows |
|---|---|
| **Factsheet** | Fund details, managers, plans & fees, NAV table, benchmark names, investment objective |
| **NAV** | Interactive line chart with date range and plan filters; period return summary |
| **Holdings** | Portfolio positions with weights and market values; historical `?as_of=` date lookup |
| **Exposures** | Doughnut charts for sector / country / region / cap / asset class allocations |
| **Performance** | Trailing returns vs both benchmarks, calendar year returns, all 12 risk metrics, portfolio P/E·P/B·yield |
| **Admin** | Trigger the pipeline manually, view run history with per-stage timings, add/update/close holdings (SCD2) |

The sidebar shows the pipeline status in real time (running / success / failed) and the latest NAV per product.

---

## Running the pipeline

The pipeline runs automatically at 10 PM ET every weekday (configurable in `.env`).

```bash
# Backfill last 10 trading days — run from host, not inside Docker (yfinance + Docker IPs conflict)
python backfill.py

# Backfill last 30 days (fuller chart history)
python backfill.py --days 30

# Specific past date (from host)
python -m app.pipeline.runner --date 2024-06-01

# Via admin API (triggers pipeline inside Docker, runs in background)
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
| GET | `/products/{code}/factsheet` | Headline factsheet (served from Redis, DB fallback) |
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
| [docs/01_overview.md](docs/01_overview.md) | Architecture diagram, stack rationale, full repo structure |
| [docs/02_setup.md](docs/02_setup.md) | Docker and manual setup, every environment variable explained |
| [docs/03_schema.md](docs/03_schema.md) | All 15 database tables with column-by-column explanation and precision rationale |
| [docs/04_pipeline.md](docs/04_pipeline.md) | All 5 pipeline stages, atomicity model, scheduler wiring, risk metric formulas, failure modes |
| [docs/05_api.md](docs/05_api.md) | Every endpoint with curl examples and full response shapes |
| [docs/06_design_decisions.md](docs/06_design_decisions.md) | D01–D15 architectural decisions with rationale and trade-offs |

---

## Environment variables

Configured in `.env` (copy from `.env.example`):

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql://postgres:postgres@localhost:5432/prisma_factsheet` | PostgreSQL connection |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection |
| `PIPELINE_CRON` | `0 22 * * 1-5` | Cron schedule (10 PM ET weekdays) |
| `PIPELINE_TIMEZONE` | `America/New_York` | Timezone for the cron |
| `RISK_FREE_RATE` | `0.05` | Annual risk-free rate for Sharpe/Sortino/Treynor |
| `CACHE_TTL` | `86400` | Redis cache TTL in seconds |
| `ADMIN_TOKEN` | `changeme` | Token for `X-Admin-Token` header on admin routes |
