# Database Schema

15 tables across 5 groups. All primary keys are UUIDs.  
All monetary values use `NUMERIC` (never `FLOAT`) to avoid floating-point rounding errors.

---

## Group 1 — Reference / Seed (static, loaded once)

### `regions`
Maps every country to a geographic region and MSCI market classification.  
Used by `derive.py` to group holdings into region exposures.

| Column | Type | Notes |
|---|---|---|
| `country_code` | CHAR(2) PK | ISO 3166 alpha-2 (e.g. "US", "IN") |
| `country_name` | TEXT | Full name |
| `region` | TEXT | "North America", "Europe", "Asia Pacific", etc. |
| `msci_class` | TEXT | "Developed", "Emerging", "Frontier" |

47 rows loaded by `bootstrap.py`.

---

### `sectors`
Lookup table for GICS sector codes.  
yfinance returns free-text sector names; `ingest_classification.py` maps them to these codes.

| Column | Type | Notes |
|---|---|---|
| `code` | TEXT PK | "TECH", "FIN", "HLTH", etc. |
| `name` | TEXT | Human-readable name |

11 rows (one per GICS sector).

---

## Group 2 — Core Identity

### `amcs`
Asset Management Companies. One row per fund house.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `code` | TEXT UNIQUE | Internal code e.g. "SPRING_STREET" |
| `name` | TEXT | Display name |
| `cin` | TEXT | SEBI Corporate Identification Number |

---

### `fund_managers`
Individual portfolio managers. Linked to an AMC.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `amc_id` | UUID FK → amcs | |
| `name` | TEXT | |
| `experience_years` | INT | Total years in the industry |
| `bio` | TEXT | Short paragraph for the factsheet |
| `is_active` | BOOL | |

---

### `securities`
Every tradable asset: stocks, ETFs, benchmark indices, FX pairs.  
Both portfolio holdings and benchmarks live here.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `ticker` | TEXT | yfinance ticker symbol (e.g. "AAPL", "URTH") |
| `exchange` | TEXT | "NASDAQ", "NYSE", etc. |
| `name` | TEXT | Display name |
| `isin` | TEXT | Optional ISIN |
| `asset_class` | TEXT | "equity", "etf", "debt", "cash" |
| `domicile` | CHAR(2) FK → regions | Country of incorporation |
| `currency` | CHAR(3) | Native trading currency |
| `is_fund` | BOOL | True for ETFs/benchmarks — skip sector classification |

Unique constraint on `(ticker, exchange)`.

---

### `products`
Mutual fund products. One product = one fund (e.g. Global Growth Prisma).

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `code` | TEXT UNIQUE | URL-safe identifier ("GLOBAL_GROWTH_PRISMA") |
| `name` | TEXT | |
| `amc_id` | UUID FK → amcs | |
| `inception_date` | DATE | |
| `base_currency` | CHAR(3) | Portfolio managed in this currency (USD) |
| `reporting_currency` | CHAR(3) | NAV reported in this currency (INR) |
| `scheme_type` | TEXT | "open_ended" / "close_ended" |
| `scheme_category` | TEXT | SEBI category: "equity", "debt", etc. |
| `scheme_sub_category` | TEXT | "global", "large_cap", etc. |
| `is_fund_of_funds` | BOOL | |
| `primary_benchmark_id` | UUID FK → securities | e.g. iShares MSCI World ETF |
| `additional_benchmark_id` | UUID FK → securities | Secondary benchmark |
| `risk_level` | TEXT | Fund riskometer level |
| `benchmark_risk_level` | TEXT | |
| `trustee_name` | TEXT | |
| `custodian_name` | TEXT | |
| `rta_name` | TEXT | Registrar and Transfer Agent |
| `objective` | TEXT | Investment objective paragraph |
| `is_active` | BOOL | |

---

### `product_managers`
Many-to-many join between products and fund managers.  
Tracks managing_since / managing_until so historical manager assignments are preserved.

| Column | Type | Notes |
|---|---|---|
| `product_id` | UUID FK → products | |
| `manager_id` | UUID FK → fund_managers | |
| `role` | TEXT | "primary", "co-manager" |
| `managing_since` | DATE | |
| `managing_until` | DATE | NULL = currently active |

---

### `plans`
Each product has multiple plan variants: Direct/Regular × Growth/IDCW.  
Minimum investment amounts and ISIN differ per plan.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `product_id` | UUID FK → products | |
| `plan_type` | TEXT | "direct" or "regular" |
| `option_type` | TEXT | "growth" or "idcw" |
| `isin` | TEXT | SEBI ISIN for this plan |
| `amfi_code` | TEXT | AMFI registration code |
| `min_initial` | NUMERIC(15,2) | Minimum first investment (INR) |
| `min_additional` | NUMERIC(15,2) | Minimum top-up |
| `min_sip` | NUMERIC(15,2) | Minimum SIP amount |
| `min_redemption` | NUMERIC(15,2) | |

Unique constraint on `(product_id, plan_type, option_type)`.

---

### `plan_fees`
TER (Total Expense Ratio) and exit load per plan.  
SCD2: when TER changes, close the old row and open a new one.

| Column | Type | Notes |
|---|---|---|
| `plan_id` | UUID FK → plans | |
| `ter` | NUMERIC(6,4) | e.g. 0.0050 = 0.50% |
| `exit_load_pct` | NUMERIC(6,4) | e.g. 0.0100 = 1% |
| `exit_load_days` | INT | Holding period below which exit load applies |
| `effective_from` | DATE | |
| `effective_to` | DATE | NULL = currently active |

---

## Group 3 — Market Data (written by pipeline stages 1 & 2)

### `prices`
Daily OHLCV for every security. Written by `ingest_prices.py`.

| Column | Type | Notes |
|---|---|---|
| `security_id` | UUID FK → securities | |
| `trade_date` | DATE | |
| `open/high/low/close` | NUMERIC(20,6) | Raw prices |
| `adj_close` | NUMERIC(20,6) | Adjusted for splits and dividends — used in performance calcs |
| `volume` | BIGINT | |
| `source` | TEXT | "yfinance" |

Unique on `(security_id, trade_date)`. Index on `(security_id, trade_date DESC)` for fast latest-price lookups.

---

### `fx_rates`
Daily FX rate per currency pair. Written by `ingest_fx.py`.  
Used by `derive.py` to convert AUM and NAV from USD to INR.

| Column | Type | Notes |
|---|---|---|
| `base` | CHAR(3) | "USD" |
| `quote` | CHAR(3) | "INR" |
| `rate_date` | DATE | |
| `rate` | NUMERIC(20,8) | How many quote units per 1 base unit |

---

## Group 4 — Holdings & Classification (SCD2)

### `holdings`
Which securities the fund owns and in what quantity.  
Admin-managed (no external data source — see Decision D03).  
Weights and market values are recomputed daily by the pipeline.

| Column | Type | Notes |
|---|---|---|
| `product_id` | UUID FK → products | |
| `security_id` | UUID FK → securities | |
| `quantity` | NUMERIC(20,6) | Shares/units held |
| `weight` | NUMERIC(10,8) | Updated by pipeline (% of AUM) |
| `market_value` | NUMERIC(20,2) | Updated by pipeline (in base currency) |
| `effective_from` | DATE | Date this holding row became active |
| `effective_to` | DATE | NULL = currently active; set when quantity changes |
| `source` | TEXT | "admin" or "seed" |

SCD2: when an admin changes quantity, the old row gets `effective_to = today` and a new row is inserted with `effective_from = today`.

---

### `constituent_holdings`
Look-through for fund-of-funds: maps a parent ETF to its underlying securities.  
Populated manually if the product holds other funds. Not used by the sample product.

---

### `classifications`
Sector, market-cap bucket, and valuation ratios per security.  
Updated daily by `ingest_classification.py`. SCD2 on sector + cap changes.

| Column | Type | Notes |
|---|---|---|
| `security_id` | UUID FK → securities | |
| `sector_code` | TEXT FK → sectors | "TECH", "FIN", etc. |
| `market_cap_usd` | NUMERIC(20,2) | Raw market cap in USD |
| `cap_bucket` | TEXT | "large" / "mid" / "small" / "micro" |
| `pe_ratio` | NUMERIC(10,4) | Trailing P/E |
| `pb_ratio` | NUMERIC(10,4) | Price-to-book |
| `dividend_yield` | NUMERIC(10,6) | Annual yield as decimal |
| `effective_from` | DATE | |
| `effective_to` | DATE | NULL = currently active |

---

## Group 5 — Derived Snapshots (written by pipeline stages 4 & 5)

### `nav`
Daily NAV per plan, computed from AUM and units outstanding.

| Column | Type | Notes |
|---|---|---|
| `plan_id` | UUID FK → plans | |
| `nav_date` | DATE | |
| `nav` | NUMERIC(20,6) | In base currency (USD) |
| `nav_inr` | NUMERIC(20,6) | In reporting currency (INR), using that day's FX rate |
| `aum` | NUMERIC(20,2) | Total AUM = Σ(quantity × price) |
| `units_outstanding` | NUMERIC(20,6) | Carried forward from previous day (admin-managed) |

Unique on `(plan_id, nav_date)`. Pipeline uses `INSERT … ON CONFLICT DO UPDATE` so re-runs are safe.

---

### `exposures`
Portfolio allocation by dimension. One row per (product, dimension, bucket, date).

| Column | Type | Notes |
|---|---|---|
| `product_id` | UUID FK → products | |
| `dimension` | TEXT | "sector", "country", "region", "cap", "asset_class" |
| `bucket` | TEXT | e.g. "Technology", "US", "North America", "large", "equity" |
| `weight` | NUMERIC(10,8) | Decimal weight (0.42 = 42%) |
| `as_of_date` | DATE | |

The pipeline deletes and rewrites all exposures for `(product, date)` so re-runs are idempotent.

---

### `performance`
All performance metrics per plan per lookback window per date.  
One row per (plan, date, lookback). Three lookbacks: 1Y, 3Y, 5Y.

Key columns:
- `trailing_returns` JSONB — `{"1M": 0.02, "3M": 0.06, "6M": 0.11, "1Y": 0.24, "SI": 0.18}`
- `calendar_year_returns` JSONB — `{"2022": -0.15, "2023": 0.28}`
- `primary_benchmark_returns` JSONB — same shape as trailing_returns
- `additional_benchmark_returns` JSONB
- `growth_of_10k` JSONB — `{"value": 13450.0, "as_of": "2024-06-01"}`
- `std_dev`, `sharpe`, `sortino`, `treynor`, `beta`, `alpha` — NUMERIC(10,6) each
- `r_squared`, `tracking_error`, `information_ratio`, `max_drawdown` — NUMERIC(10,6) each
- `upside_capture`, `downside_capture` — NUMERIC(10,6) each
- `portfolio_pe`, `portfolio_pb`, `portfolio_dividend_yield` — weighted-average ratios
- `holdings_count` — number of active holdings on that date

---

## Group 6 — Operational

### `pipeline_runs`
One row per pipeline execution. Written before the run starts (status="running"), updated when it finishes.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `job_name` | TEXT | "full_pipeline" |
| `triggered_by` | TEXT | "scheduler", "manual", or admin email |
| `started_at` | TIMESTAMPTZ | |
| `finished_at` | TIMESTAMPTZ | NULL while running |
| `status` | TEXT | "running" → "success" or "failed" |
| `target_date` | DATE | The trading date processed |
| `rows_processed` | INT | Count returned by derive.run() |
| `timings` | JSONB | `{"ingest_prices_ms": 4200, "derive_ms": 820, ...}` |
| `error` | TEXT | Exception message on failure; NULL on success |

---

### `audit_log`
Immutable record of every admin write (holdings add/update/delete).

| Column | Type | Notes |
|---|---|---|
| `actor` | TEXT | "admin" (future: user email) |
| `action` | TEXT | "create", "update", "delete" |
| `entity` | TEXT | "holdings" |
| `entity_id` | UUID | The affected row's ID |
| `before` | JSONB | Previous state (NULL for creates) |
| `after` | JSONB | New state (NULL for deletes) |
| `occurred_at` | TIMESTAMPTZ | |

---

## Numeric Precision Reference

| Data type | Column type | Why |
|---|---|---|
| Prices (USD) | NUMERIC(20,6) | 6 decimal places covers FX rates like USDINR |
| Weights | NUMERIC(10,8) | 8 decimal places for precise portfolio weights |
| AUM / money | NUMERIC(20,2) | 2 decimal places, 20 total digits covers $100B+ |
| Ratios (PE, PB) | NUMERIC(10,4) | 4 decimal places for financial ratios |
