# Design Decisions

Every meaningful architectural choice made during the build, with the reasoning behind it.

---

## D01 — Storage: PostgreSQL + Redis

**Decision:** Use PostgreSQL as the primary data store and Redis as a read-cache for the factsheet API.

**Why PostgreSQL:**
- Holdings, NAV, exposures, and performance are all relational. GROUP BY for aggregating exposure weights, JOINs to resolve holding → security → classification. These are natural SQL operations.
- ACID transactions make the atomic pipeline commit (D11) straightforward.
- NUMERIC types eliminate the floating-point rounding errors you get with FLOAT.

**Why Redis:**
- The factsheet endpoint is the most-hit route. Building it from the DB requires 3–4 JOINs across large tables (~20–50ms). Serving from Redis takes ~0.5ms.
- Redis is populated after every successful pipeline commit. TTL = 24h. The API falls back to the DB if the key is missing.

**Trade-off accepted:** Redis adds operational complexity. Acceptable for this read-heavy pattern.

---

## D03 — Holdings source: admin API only

**Decision:** Holdings are managed exclusively through the admin API. No external source.

**Why:** No external data source provides the exact fund's holdings (this is proprietary data). An admin manages the portfolio; the pipeline computes weights from quantities and prices.

**Implication:** Holdings are "true" at the quantity level (from admin). Weights and market values are derived daily by the pipeline.

---

## D04 — Market data: yfinance only

**Decision:** Use yfinance as the sole market data source.

**Why:** Free, covers all the needed asset classes (US equities, ETFs, FX rates), and meets the assignment requirement.

**Trade-off:** yfinance is unofficial and can break without notice. A production system would use Bloomberg, Refinitiv, or a paid API with SLAs.

---

## D05 — Classifications: yfinance → DB daily

**Decision:** Pull sector, cap, PE, PB, and dividend yield from yfinance every day and store in the DB.

**Why:** Sector and market-cap classifications can change (a company grows from mid-cap to large-cap; a company moves from Consumer Cyclical to Technology). Fetching daily and applying SCD2 captures these changes with full history.

**Why not just call yfinance at query time?** The API would be slow and dependent on yfinance being available at read time. Storing in the DB decouples the API from yfinance.

---

## D06 — NAV: computed daily, full history kept

**Decision:** Compute and store NAV for every day the pipeline runs. Never overwrite historical NAVs.

**Why:**
- Trailing return calculations require past NAVs.
- The growth-of-10k series and calendar year returns need the full history.
- Point-in-time queries for historical holdings need historical NAVs to match.

---

## D07 — Pipeline schedule: configurable via .env

**Decision:** The pipeline cron expression and timezone live in `.env`, not in code.

**Why:** US markets close at 4 PM ET; Indian markets close at 3:30 PM IST. A fund that holds Indian securities needs to run at a different time than one holding US securities. Changing the schedule requires no code change — just edit `PIPELINE_CRON` and `PIPELINE_TIMEZONE`.

---

## D08 — Database: PostgreSQL

See D01. Additionally: the `exposures` table uses a long format (one row per bucket) which makes GROUP BY aggregations natural. A wide format (one column per sector) would require schema changes every time a new sector appeared.

---

## D09 — Decimal precision: NUMERIC, never FLOAT

**Decision:** All financial values stored as PostgreSQL `NUMERIC` with explicit precision.

| Type | Precision | Rationale |
|---|---|---|
| Prices | NUMERIC(20,6) | 6 decimal places covers FX rates (USDINR ≈ 83.45) |
| Weights | NUMERIC(10,8) | 8 decimal places for precise portfolio weights |
| AUM / money | NUMERIC(20,2) | 2 decimal places, 20 digits covers $100B+ funds |
| Ratios | NUMERIC(10,4) | P/E, P/B — 4 decimal places sufficient |

`FLOAT` (IEEE 754) would introduce rounding errors like `0.1 + 0.2 = 0.30000000000000004`. Unacceptable for financial data.

---

## D10 — Scheduler: APScheduler

**Decision:** Use APScheduler running in-process, rather than cron, Celery, or Airflow.

| Option | Why rejected |
|---|---|
| System cron | No failure logging; no retry; no API trigger; restarts break the schedule |
| Celery | Requires a broker (RabbitMQ/Redis queue); massive operational overhead for one scheduled job |
| Airflow | A full DAG orchestration platform for a 5-stage linear job — enormous overkill |
| APScheduler | In-process; writes failure records to DB; supports manual trigger via API; zero extra infra |

---

## D11 — Atomic pipeline transaction

**Decision:** Stages 1–4 share one SQLAlchemy session. A single `session.commit()` makes all four stages' writes permanent atomically.

**Why:** Without this, a failure in Stage 4 (derive) after Stage 1 (prices) already committed would leave stale price data in the DB with no matching NAV or exposures. Users would get an inconsistent factsheet.

**How:** The session is passed from the runner into each stage function. No stage calls `commit()`. The runner commits once:
```python
stage("ingest_prices", ...)
stage("ingest_fx", ...)
stage("ingest_classification", ...)
stage("derive", ...)
session.commit()  # <-- only here
```

If anything fails, `session.rollback()` undoes all four stages. Yesterday's data remains live.

---

## D12 — Batch yfinance calls

**Decision:** Download all security prices in a single `yf.download(all_tickers, ...)` call.

**Why:** yfinance's `download()` function fetches all tickers in one HTTP request to Yahoo Finance's bulk endpoint. Fetching 14 tickers individually would take 14× as long due to network latency.

**Also:** Stage timings are captured per stage and stored in `pipeline_runs.timings` JSONB. This makes it easy to identify which stage is the bottleneck.

---

## D13 — Separate URL per data type

**Decision:** `/nav`, `/holdings`, `/exposures`, `/performance`, `/growth` are separate endpoints rather than one giant `/factsheet` blob.

**Why:** A client rendering the factsheet page doesn't need all data at once. The holdings table, the NAV chart, and the performance section can load independently. Separate endpoints also allow different cache strategies and `?as_of=` parameters per data type.

The `/factsheet` endpoint exists as a headline summary (Redis-cached), not as a replacement for the granular endpoints.

---

## D14 — Serving strategy: DB during pipeline, Redis after

**Decision:**
```
Request arrives
  → Is a pipeline currently running?
      YES → Build from DB (safe: only committed data is visible)
       NO → Check Redis cache
              HIT  → return cached JSON (~0.5ms)
              MISS → build from DB
```

**Why avoid Redis while pipeline runs:** The pipeline commits atomically at the end of Stage 4. While stages 1–3 are running, the DB has new prices but no updated NAV or exposures yet. Serving from Redis during this window is safe because Redis still has the previous day's data (which is correct). We only skip Redis when a run is actively "running" to prevent a race where the pipeline commits mid-request and a caller sees the old Redis payload while the DB is already updated.

**How `pipeline_running` is checked:** The `pipeline_runs` table — not Redis — is authoritative. A `SELECT` on the most recent row's `status` column.

---

## D15 — Market hours: configurable in .env

**Decision:** The pipeline timezone is set in `.env` via `PIPELINE_TIMEZONE`.

**Why:** The same codebase can serve:
- A US equity fund: `PIPELINE_CRON=0 22 * * 1-5`, `PIPELINE_TIMEZONE=America/New_York` → runs at 10 PM ET (6 hours after US close)
- An Indian equity fund: `PIPELINE_CRON=30 16 * * 1-5`, `PIPELINE_TIMEZONE=Asia/Kolkata` → runs at 4:30 PM IST (1 hour after NSE close)

No code change required.

---

## Authentication: Simple shared token

**Decision:** Admin routes use a single `X-Admin-Token` header checked against `ADMIN_TOKEN` in `.env`.

**Why acceptable for a prototype:** There's one admin (the fund manager / ops team). JWT/OAuth2 adds significant complexity (user table, token expiry, refresh flow) with no benefit when there's a single consumer.

**What a production upgrade looks like:** Replace `require_admin()` in `deps.py` with a JWT validator. The rest of the code is unchanged.

---

## SCD2 on Holdings and Classifications

**SCD2 = Slowly Changing Dimension, Type 2** — a pattern for tracking history in a relational table.

Instead of overwriting a row when data changes, you:
1. Set `effective_to = change_date - 1` on the old row
2. Insert a new row with `effective_from = change_date`

**Result:** The full history is preserved. You can query the state of the portfolio on any past date:
```python
.filter(Holding.effective_from <= as_of)
.filter((Holding.effective_to.is_(None)) | (Holding.effective_to >= as_of))
```

Used on:
- `holdings` — when admin changes quantity
- `classifications` — when a stock's sector or cap bucket changes
- `plan_fees` — when TER is revised
