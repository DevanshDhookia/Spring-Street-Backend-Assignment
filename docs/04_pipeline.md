# The Data Pipeline

The pipeline runs every weekday after US market close and populates all derived data (NAV, exposures, performance) from raw prices and holdings.

---

## Flow Diagram

```
APScheduler (10 PM ET weekdays)
  OR  POST /admin/pipeline/trigger
  OR  python -m app.pipeline.runner
         │
         ▼
   runner.run_pipeline(target_date)
         │
         ├─ Stage 1: ingest_prices          ← yfinance batch OHLCV download
         │
         ├─ Stage 2: ingest_fx              ← yfinance FX rates (USDINR=X)
         │
         ├─ Stage 3: ingest_classification  ← yfinance .info (sector, cap, ratios)
         │
         ├─ Stage 4: derive                 ← NAV, weights, exposures, performance
         │
         │   ←——— session.commit() ———————  ONE atomic write (all 4 stages)
         │
         └─ Stage 5: cache_warm             ← serialize factsheet → Redis
```

Stages 1–4 share one SQLAlchemy session. **Nothing is committed until all four succeed.**  
Stage 5 runs after the commit — Redis always reflects persisted state.

---

## Stage 1 — `ingest_prices`

**File:** `app/pipeline/ingest_prices.py`

Fetches OHLCV prices for every row in the `securities` table.

**Key design choice — batch download:**
```python
yf.download(all_tickers, start=target_date, end=target_date + 1d)
```
One HTTP call for all 14 tickers instead of 14 calls. This is Design Decision D12.

**yfinance MultiIndex quirk:**  
When you download multiple tickers, yfinance returns a `DataFrame` with a two-level column index: `(price_type, ticker)`. For example: `("Close", "AAPL")`. When there's only one ticker, the columns are flat. The code detects which format it got:
```python
is_multi = isinstance(raw.columns, pd.MultiIndex)
t_df = raw.xs(ticker, axis=1, level=1) if is_multi else raw
```

**Idempotency:**  
Uses `INSERT … ON CONFLICT DO NOTHING` on `(security_id, trade_date)`. Safe to re-run.

**What gets stored:**
- `close` — raw closing price
- `adj_close` — adjusted for stock splits and dividends (used in performance calculations)

---

## Stage 2 — `ingest_fx`

**File:** `app/pipeline/ingest_fx.py`

Fetches FX rates for all currency pairs needed across active products.

The sample product is managed in USD but reports in INR. So we fetch `USDINR=X`.

**Why not batch?**  
yfinance FX tickers (`USDINR=X`) cannot be combined in a single `yf.download()` call reliably. Each pair is fetched individually.

**MultiIndex handling (same yfinance quirk):**  
Even single-ticker downloads return MultiIndex columns in yfinance ≥0.2:
```python
close_col = raw[("Close", ticker_sym)] if ("Close", ticker_sym) in raw.columns else raw["Close"].iloc[:, 0]
```

---

## Stage 3 — `ingest_classification`

**File:** `app/pipeline/ingest_classification.py`

Fetches sector, market-cap, PE, PB, and dividend yield for every non-fund security.

**yfinance call:**
```python
info = yf.Ticker(sec.ticker).info  # dict with ~100 fields
```

**SCD2 logic:**

```
IF sector_code AND cap_bucket are UNCHANGED:
    → update PE, PB, yield on the existing row (daily noise, no history needed)

ELSE (sector or cap changed):
    → existing.effective_to = target_date - 1   (close old row)
    → INSERT new row with effective_from = target_date
```

Both changes happen in the same uncommitted session. The single commit in the runner writes them atomically.

**Sector mapping:**  
yfinance returns strings like "Financial Services". We map them to stable codes like "FIN" so our API is consistent regardless of yfinance string changes.

**ETFs skipped:**  
`is_fund=True` securities (benchmarks like URTH/ACWI) don't have sector data. Skipped.

---

## Stage 4 — `derive`

**File:** `app/pipeline/derive.py`

The compute-heavy stage. For each active product:

### Step 1 — Compute AUM
```
AUM = Σ (quantity × price) for all active holdings with a price today
```

### Step 2 — Update holding weights
```
weight = (quantity × price) / AUM
market_value = quantity × price
```
These are written back onto the `Holding` rows already in the session.

### Step 3 — Compute NAV
```
NAV = AUM / units_outstanding
NAV_INR = NAV × USDINR_rate (from Stage 2)
```
Upserted into the `nav` table using `INSERT … ON CONFLICT DO UPDATE` on `(plan_id, nav_date)`.

### Step 4 — Write exposures
For each of 5 dimensions (`sector`, `country`, `region`, `cap`, `asset_class`):
```
Group holdings by their classification value for that dimension
Sum the weights within each group
Write one Exposure row per group
```
The pipeline **deletes** all existing exposure rows for `(product, date)` before writing, making re-runs idempotent.

### Step 5 — Write performance
For each plan × each lookback (1Y / 3Y / 5Y):

**Trailing returns:**
| Period | Formula |
|---|---|
| 1M, 3M, 6M | `(nav_today / nav_N_days_ago) - 1` |
| 1Y, 3Y, 5Y | `(nav_today / nav_N_days_ago) ^ (252/N) - 1` (annualised CAGR) |
| SI (Since Inception) | `(nav_today / nav_inception) ^ (1/years) - 1` |

**Risk metrics** (computed over the lookback window of daily returns):

| Metric | Formula |
|---|---|
| Std Dev | `std(daily_returns) × √252` |
| Sharpe | `(mean_return_ann − Rf) / std_dev` |
| Sortino | Same but uses only downside deviations |
| Beta | `cov(fund, bench) / var(bench)` |
| Alpha | `fund_ann − (Rf + β × (bench_ann − Rf))` |
| R² | `corr(fund, bench)²` |
| Tracking Error | `std(fund − bench) × √252` |
| Information Ratio | `mean(fund − bench) / std(fund − bench) × √252` |
| Max Drawdown | `min((cumulative_return / peak) − 1)` |
| Upside Capture | `fund_mean_up / bench_mean_up` |
| Downside Capture | `fund_mean_down / bench_mean_down` |

Risk-free rate `Rf` comes from `RISK_FREE_RATE` in `.env` (default 5%).

**Growth of ₹10,000:**
```
value = 10000 × (nav_today / nav_inception)
```

**Portfolio-level ratios:**
```
portfolio_pe = Σ (holding.weight × security.pe_ratio)
```
Same for P/B and dividend yield.

---

## Stage 5 — `cache_warm`

**File:** `app/pipeline/cache_warm.py`

Runs **after** the DB commit. Serialises the factsheet to JSON and pushes to Redis:

```python
client.setex(f"factsheet:{product.code}", cache_ttl, json_string)
```

`setex` = SET with EXpiry. The key disappears automatically after `CACHE_TTL` seconds (default 24h). The API falls back to the DB if the key is missing — expiry never causes a 404.

**What's cached:**
- Latest NAV for all plans
- All exposure dimensions
- Direct-Growth 1Y headline performance (trailing returns, Sharpe, max drawdown, growth of 10k)

**What's NOT cached:**
- Full NAV history (queried with from/to filters)
- Historical holdings (queried with as_of filter)
- Multi-lookback performance (3Y, 5Y)

---

## Atomicity (Decision D11)

```python
session = SessionLocal()
try:
    stage("ingest_prices", ...)
    stage("ingest_fx", ...)
    stage("ingest_classification", ...)
    rows = stage("derive", ...)

    session.commit()       # ALL four stages commit here — or not at all

    cache_warm.run(...)    # Only runs if commit succeeded

except Exception:
    session.rollback()     # Undo everything from all four stages
    raise
finally:
    session.close()
```

The user never sees a half-updated factsheet. Either the full day's data arrives, or yesterday's data stays live.

---

## Scheduler Wiring

APScheduler starts in `app/main.py` as a FastAPI lifespan event:

```python
scheduler = BackgroundScheduler(timezone=settings.pipeline_timezone)
scheduler.add_job(
    run_pipeline,
    CronTrigger.from_crontab(settings.pipeline_cron),  # from .env
    misfire_grace_time=3600,  # if the server was down, run up to 1h late
)
scheduler.start()
```

`BackgroundScheduler` runs in a daemon thread, separate from the async HTTP event loop. The pipeline is CPU+IO bound; running it in a thread keeps the API responsive.

---

## Manual Trigger Options

**CLI (backfill or one-off):**
```bash
python -m app.pipeline.runner
python -m app.pipeline.runner --date 2024-01-15
```

**Admin API:**
```bash
curl -X POST http://localhost:8000/admin/pipeline/trigger \
  -H "X-Admin-Token: changeme"
# Returns immediately with {"status": "triggered"}
# Poll /admin/pipeline/status to check progress
```

---

## Failure Modes

| What fails | Effect | Recovery |
|---|---|---|
| yfinance returns no data for a ticker | That ticker skipped; pipeline continues | Re-run next day or backfill |
| yfinance timeout | Stage raises → rollback → yesterday's data stays live | Retry manually |
| Derive error (bad data, division by zero) | Full rollback | Fix data, re-trigger |
| Redis unavailable during cache_warm | DB stays consistent; API falls back to DB | No action needed |
| Redis unavailable at read time | API builds from DB directly | No action needed |

---

## Pipeline Run Record

Every run creates a `pipeline_runs` row you can inspect:

```bash
# Check status of last run
curl http://localhost:8000/admin/pipeline/status

# Full run history with per-stage timings
curl http://localhost:8000/admin/pipeline/runs \
  -H "X-Admin-Token: changeme"
```

Example timings JSONB:
```json
{
  "ingest_prices_ms": 4200,
  "ingest_fx_ms": 380,
  "ingest_classification_ms": 18400,
  "derive_ms": 820,
  "cache_warm_ms": 45
}
```

`ingest_classification` is the slowest stage because it makes one `yf.Ticker.info` call per security (no batch API available).
