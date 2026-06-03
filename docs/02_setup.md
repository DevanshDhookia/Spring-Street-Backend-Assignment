# Setup Guide

Two paths: Docker (fast) or Manual (more control).

---

## Prerequisites

| Tool | Minimum version |
|---|---|
| Python | 3.11 |
| Docker + Docker Compose | any recent version |
| Git | any |

---

## Option A — Docker Compose (recommended)

Everything (Postgres, Redis, app) runs in containers. One command.

```bash
# 1. Clone the repo
git clone <repo-url>
cd Spring-Street-Backend-Assignment

# 2. Copy and edit environment variables
cp .env.example .env
# Edit .env if needed (see Environment Variables section below)

# 3. Build and start all services
docker compose up --build

# 4. In a second terminal — run migrations
docker compose exec app alembic upgrade head

# 5. Seed the database (creates the sample product + holdings)
docker compose exec app python -m app.seed.bootstrap

# 6. Backfill 30 days of historical data (needed for charts and performance metrics)
docker compose exec app python -m app.seed.seed_history
# Takes ~15-30 min (one yfinance call per security per day). Use --days 5 for a quick demo.

# 7. Open the frontend
open frontend/index.html      # click "Global Growth Prisma" in the sidebar
```

API is now live at: **http://localhost:8000**
Interactive docs: **http://localhost:8000/docs**
Frontend console: open **frontend/index.html** in any browser

---

## Option B — Manual Setup

Use this if you want to run the API directly without Docker.

### 1. Create virtualenv and install dependencies

```bash
python3.11 -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Start Postgres and Redis locally

```bash
# Postgres (if using Homebrew on Mac)
brew services start postgresql@16

# Redis
brew services start redis

# Or use Docker just for the databases:
docker compose up db redis -d
```

### 3. Create the database

```bash
# If using local Postgres (not Docker):
createdb prisma_factsheet
```

### 4. Configure environment variables

```bash
cp .env.example .env
# Edit DATABASE_URL if your Postgres user/password differs from the default
```

### 5. Run migrations

```bash
alembic upgrade head
```

This creates all 15 tables. Safe to re-run — Alembic tracks which migrations have been applied.

### 6. Seed the database

```bash
python -m app.seed.bootstrap
```

This creates:
- Spring Street Capital (AMC)
- Arjun Mehta (fund manager)
- 14 securities (12 holdings + 2 benchmarks)
- Global Growth Prisma (product) with 4 plans and fees
- Initial 12 holdings

### 7. Backfill historical data

```bash
# Run the pipeline for the last 30 trading days so charts have data to display
python -m app.seed.seed_history

# Fewer days for a quick demo:
python -m app.seed.seed_history --days 5

# Or a specific date:
python -m app.pipeline.runner --date 2024-01-15
```

This fetches live prices from yfinance. Expect ~30–60 seconds per day.

### 8. Start the API server

```bash
uvicorn app.main:app --reload
```

API: **http://localhost:8000**
Docs: **http://localhost:8000/docs**

---

## Environment Variables

All variables live in `.env`. The app reads them via Pydantic-settings.

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql://postgres:postgres@localhost:5432/prisma_factsheet` | PostgreSQL connection string |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection string |
| `PIPELINE_CRON` | `0 22 * * 1-5` | Cron expression for daily pipeline (default: 10 PM ET weekdays) |
| `PIPELINE_TIMEZONE` | `America/New_York` | Timezone for the cron schedule. Use `Asia/Kolkata` for Indian market hours |
| `RISK_FREE_RATE` | `0.05` | Annual risk-free rate for Sharpe/Sortino/Treynor (5% = US 10Y Treasury) |
| `CACHE_TTL` | `86400` | Redis cache TTL in seconds (86400 = 24 hours) |
| `ADMIN_TOKEN` | `changeme` | Secret for `X-Admin-Token` header on admin routes |

---

## Verifying the setup

```bash
# Health check
curl http://localhost:8000/health

# Pipeline status
curl http://localhost:8000/admin/pipeline/status

# List products (should return Global Growth Prisma)
curl http://localhost:8000/products

# Product detail
curl http://localhost:8000/products/GLOBAL_GROWTH_PRISMA
```

See `docs/05_api.md` for the full list of endpoints with examples.

---

## Rolling back the database

```bash
# Undo all migrations (drops all tables)
alembic downgrade base

# Re-apply
alembic upgrade head
```

---

## Docker Compose services

| Service | Port | Notes |
|---|---|---|
| `db` | 5432 | Postgres 16 with health check |
| `redis` | 6379 | Redis 7 with health check |
| `app` | 8000 | FastAPI + Uvicorn; waits for both dependencies to be healthy |

Data persists across restarts in a named Docker volume (`pgdata`).
