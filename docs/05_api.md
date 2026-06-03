# API Reference

Base URL: `http://localhost:8000`  
Interactive docs: `http://localhost:8000/docs`

All responses are JSON. All dates are ISO 8601 strings (`"2024-06-01"`).  
Admin routes require the header: `X-Admin-Token: <ADMIN_TOKEN from .env>`

---

## Public Endpoints

### `GET /health`
Liveness check. Returns 200 as long as the process is up.
```bash
curl http://localhost:8000/health
# {"status": "ok"}
```

---

### `GET /products`
List all active products with latest NAV and AUM.

```bash
curl http://localhost:8000/products
```
```json
[
  {
    "code": "GLOBAL_GROWTH_PRISMA",
    "name": "Global Growth Prisma",
    "scheme_category": "equity",
    "risk_level": "moderately_high",
    "inception_date": "2022-01-03",
    "is_active": true,
    "latest_nav": 14.235600,
    "latest_nav_date": "2024-06-01",
    "aum": 35420000.00
  }
]
```

---

### `GET /products/{code}`
Full fund detail card: managers, plans, fees, benchmarks, AMC info.

```bash
curl http://localhost:8000/products/GLOBAL_GROWTH_PRISMA
```
```json
{
  "code": "GLOBAL_GROWTH_PRISMA",
  "name": "Global Growth Prisma",
  "objective": "The fund seeks long-term capital appreciation...",
  "inception_date": "2022-01-03",
  "scheme_type": "open_ended",
  "scheme_category": "equity",
  "risk_level": "moderately_high",
  "benchmark_risk_level": "moderately_high",
  "base_currency": "USD",
  "reporting_currency": "INR",
  "is_fund_of_funds": false,
  "amc": "Spring Street Capital",
  "amc_cin": "U65999MH2020PLC000001",
  "primary_benchmark": "iShares MSCI World ETF",
  "additional_benchmark": "iShares MSCI ACWI ETF",
  "managers": [
    {"name": "Arjun Mehta", "experience_years": 18, "managing_since": "2022-01-03"}
  ],
  "plans": [
    {
      "plan_type": "direct",
      "option_type": "growth",
      "isin": null,
      "min_initial": 500.0,
      "min_sip": 100.0,
      "min_additional": 100.0,
      "fees": {"ter": 0.005, "exit_load_pct": 0.01, "exit_load_days": 365}
    }
  ],
  "trustee_name": "Spring Street Trustees Pvt. Ltd.",
  "custodian_name": "Deutsche Bank AG",
  "rta_name": "KFintech Private Limited"
}
```

---

### `GET /products/{code}/factsheet`
Pre-built factsheet JSON. Served from Redis if available, DB otherwise.

```bash
curl http://localhost:8000/products/GLOBAL_GROWTH_PRISMA/factsheet
```
```json
{
  "as_of": "2024-06-01",
  "navs": [
    {"plan_type": "direct", "option_type": "growth", "nav": 14.2356, "nav_inr": 1187.45, "aum": 35420000}
  ],
  "exposures": {
    "sector": [
      {"bucket": "Technology", "weight": 0.42},
      {"bucket": "Financial Services", "weight": 0.18}
    ],
    "country": [{"bucket": "US", "weight": 0.78}, {"bucket": "NL", "weight": 0.09}],
    "region": [{"bucket": "North America", "weight": 0.78}],
    "cap": [{"bucket": "large", "weight": 0.91}],
    "asset_class": [{"bucket": "equity", "weight": 1.0}]
  },
  "performance": {
    "trailing_returns": {"1M": 0.024, "3M": 0.067, "1Y": 0.183, "SI": 0.142},
    "growth_of_10k": {"value": 14235.6, "as_of": "2024-06-01"},
    "sharpe": 1.24,
    "max_drawdown": -0.182,
    "std_dev": 0.148,
    "holdings_count": 12
  }
}
```

---

### `GET /products/{code}/nav`

NAV history for a specific plan. Defaults to Direct-Growth, last 365 days.

**Query params:**

| Param | Default | Options |
|---|---|---|
| `plan_type` | `direct` | `direct`, `regular` |
| `option_type` | `growth` | `growth`, `idcw` |
| `from_date` | — | `YYYY-MM-DD` |
| `to_date` | — | `YYYY-MM-DD` |
| `limit` | `365` | max 1825 (5 years) |

```bash
curl "http://localhost:8000/products/GLOBAL_GROWTH_PRISMA/nav?limit=5"
```
```json
{
  "plan_type": "direct",
  "option_type": "growth",
  "series": [
    {"date": "2024-05-28", "nav": 14.1102, "nav_inr": 1176.23, "aum": 35200000},
    {"date": "2024-05-29", "nav": 14.1850, "nav_inr": 1182.45, "aum": 35310000},
    {"date": "2024-05-30", "nav": 14.2100, "nav_inr": 1184.67, "aum": 35360000},
    {"date": "2024-05-31", "nav": 14.1990, "nav_inr": 1183.75, "aum": 35340000},
    {"date": "2024-06-01", "nav": 14.2356, "nav_inr": 1187.45, "aum": 35420000}
  ]
}
```

---

### `GET /products/{code}/holdings`

Current holdings sorted by weight (descending). Supports point-in-time lookup.

**Query params:**

| Param | Default | Description |
|---|---|---|
| `as_of` | — | `YYYY-MM-DD` — returns holdings active on that date (SCD2 query) |

```bash
curl http://localhost:8000/products/GLOBAL_GROWTH_PRISMA/holdings
```
```json
[
  {"ticker": "AAPL", "name": "Apple Inc.", "asset_class": "equity", "domicile": "US", "weight": 0.142, "market_value": 5032400, "quantity": 15000},
  {"ticker": "MSFT", "name": "Microsoft Corp.", "asset_class": "equity", "domicile": "US", "weight": 0.118, "market_value": 4179560, "quantity": 8000}
]
```

---

### `GET /products/{code}/exposures`

Portfolio allocation by dimension.

**Query params:**

| Param | Default | Description |
|---|---|---|
| `dimension` | — | `sector`, `country`, `region`, `cap`, `asset_class`. Omit for all. |
| `as_of` | — | Defaults to latest available date |

```bash
# Sector breakdown only
curl "http://localhost:8000/products/GLOBAL_GROWTH_PRISMA/exposures?dimension=sector"
```
```json
[
  {"bucket": "Technology", "weight": 0.42},
  {"bucket": "Financial Services", "weight": 0.18},
  {"bucket": "Healthcare", "weight": 0.12}
]
```

```bash
# All dimensions at once
curl http://localhost:8000/products/GLOBAL_GROWTH_PRISMA/exposures
```
```json
{
  "sector": [...],
  "country": [...],
  "region": [...],
  "cap": [...],
  "asset_class": [...]
}
```

---

### `GET /products/{code}/performance`

Full performance snapshot: trailing returns, calendar returns, benchmark comparison, risk metrics, and portfolio fundamentals.

**Query params:**

| Param | Default | Options |
|---|---|---|
| `plan_type` | `direct` | `direct`, `regular` |
| `option_type` | `growth` | `growth`, `idcw` |
| `lookback` | `1Y` | `1Y`, `3Y`, `5Y` |

```bash
curl "http://localhost:8000/products/GLOBAL_GROWTH_PRISMA/performance?lookback=1Y"
```
```json
{
  "plan_type": "direct",
  "option_type": "growth",
  "as_of_date": "2024-06-01",
  "lookback": "1Y",
  "trailing_returns": {"1M": 0.024, "3M": 0.067, "6M": 0.112, "1Y": 0.183, "SI": 0.142},
  "calendar_year_returns": {"2022": -0.152, "2023": 0.284, "2024": 0.108},
  "primary_benchmark_returns": {"1M": 0.018, "3M": 0.054, "1Y": 0.156},
  "additional_benchmark_returns": {"1M": 0.016, "3M": 0.049, "1Y": 0.148},
  "growth_of_10k": {"value": 14235.6, "as_of": "2024-06-01"},
  "risk_metrics": {
    "std_dev": 0.148,
    "sharpe": 1.24,
    "sortino": 1.68,
    "treynor": 0.182,
    "beta": 0.94,
    "alpha": 0.028,
    "r_squared": 0.912,
    "tracking_error": 0.048,
    "information_ratio": 0.56,
    "max_drawdown": -0.182,
    "upside_capture": 1.04,
    "downside_capture": 0.88
  },
  "portfolio": {
    "pe": 28.4,
    "pb": 5.1,
    "dividend_yield": 0.012,
    "holdings_count": 12
  }
}
```

---

### `GET /products/{code}/growth`

Growth of ₹10,000 invested at inception, as a time series.

**Query params:**

| Param | Default | Options |
|---|---|---|
| `plan_type` | `direct` | `direct`, `regular` |
| `option_type` | `growth` | `growth`, `idcw` |
| `frequency` | `monthly` | `monthly`, `daily` |
| `from_date` | — | Defaults to inception |
| `to_date` | — | Defaults to today |

```bash
curl "http://localhost:8000/products/GLOBAL_GROWTH_PRISMA/growth?frequency=monthly"
```
```json
{
  "plan_type": "direct",
  "option_type": "growth",
  "initial": 10000.0,
  "series": [
    {"date": "2022-01-31", "value": 9840.20},
    {"date": "2022-02-28", "value": 9612.80},
    {"date": "2022-03-31", "value": 9980.40},
    {"date": "2024-05-31", "value": 14180.60},
    {"date": "2024-06-01", "value": 14235.60}
  ]
}
```

---

## Admin Endpoints

All admin routes require the header: `X-Admin-Token: changeme` (change in `.env`).

---

### `POST /admin/holdings`
Add a new holding to a product.

```bash
curl -X POST http://localhost:8000/admin/holdings \
  -H "Content-Type: application/json" \
  -H "X-Admin-Token: changeme" \
  -d '{
    "product_code": "GLOBAL_GROWTH_PRISMA",
    "ticker": "AAPL",
    "quantity": 15000,
    "effective_from": "2024-06-01"
  }'
# {"id": "uuid-of-new-holding"}
```

If an active holding already exists for this (product, ticker) pair, it is **SCD2-closed** and replaced.

---

### `PUT /admin/holdings/{holding_id}`
Update the quantity of an existing holding.

SCD2: closes the old row (sets `effective_to = today`) and opens a new row with the updated quantity.

```bash
curl -X PUT http://localhost:8000/admin/holdings/<holding-uuid> \
  -H "Content-Type: application/json" \
  -H "X-Admin-Token: changeme" \
  -d '{"quantity": 18000}'
# {"id": "uuid-of-new-holding-row"}
```

---

### `DELETE /admin/holdings/{holding_id}`
Close a holding (set `effective_to = today`). Soft delete — history is preserved.

```bash
curl -X DELETE http://localhost:8000/admin/holdings/<holding-uuid> \
  -H "X-Admin-Token: changeme"
# 204 No Content
```

---

### `POST /admin/pipeline/trigger`
Trigger a manual pipeline run in a background thread. Returns immediately.

```bash
curl -X POST http://localhost:8000/admin/pipeline/trigger \
  -H "X-Admin-Token: changeme"
# {"status": "triggered"}
```

---

### `GET /admin/pipeline/status` *(no token required)*
Last pipeline run status. Safe to expose on a dashboard.

```bash
curl http://localhost:8000/admin/pipeline/status
```
```json
{
  "status": "success",
  "last_run_date": "2024-06-01",
  "started_at": "2024-06-01T22:00:03Z",
  "finished_at": "2024-06-01T22:01:18Z",
  "error": null
}
```

---

### `GET /admin/pipeline/runs`
Full run history with per-stage timings.

```bash
curl "http://localhost:8000/admin/pipeline/runs?limit=5" \
  -H "X-Admin-Token: changeme"
```
```json
[
  {
    "id": "uuid",
    "target_date": "2024-06-01",
    "triggered_by": "scheduler",
    "status": "success",
    "started_at": "2024-06-01T22:00:03Z",
    "finished_at": "2024-06-01T22:01:18Z",
    "rows_processed": 4,
    "timings": {
      "ingest_prices_ms": 4200,
      "ingest_fx_ms": 380,
      "ingest_classification_ms": 18400,
      "derive_ms": 820,
      "cache_warm_ms": 45
    },
    "error": null
  }
]
```
