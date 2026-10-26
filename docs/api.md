# API documentation

Base URL: `http://localhost:8000` (the web UI reaches it same-origin via `/api/*`). Interactive docs:
`/docs` (Swagger UI), `/redoc`; machine-readable spec: [`openapi.json`](openapi.json) (regenerate with
`python -m app.cli openapi`).

Conventions:
- All endpoints are read-only `GET` except saved views and the manual refresh trigger.
- Every response containing observations carries `data_status`: `"real"` or `"demo"`. Real and demo data are
  never mixed in one response.
- Timestamps are UTC ISO 8601 with `Z`. Periods use canonical keys: `2026`, `2026-Q3`, `2026-09`,
  `2026-10-23` (daily/weekly start), `2026-10-26T12:30Z` (half-hourly).
- Date filters `start`/`end` accept `YYYY`, `YYYY-MM` or `YYYY-MM-DD`.
- Geography codes are GSS (`K02000001` UK, `E12000007` London, `E06000001` Hartlepool…). Dimension codes are SIC
  2007 sections (`C`), ISO country codes (`DE`), SITC sections (`7`), fuels (`wind`), DMO brackets.

## Series & analysis

| Endpoint | Description |
|---|---|
| `GET /api/series?category=&q=&source=` | Catalogue with latest value, change vs previous, status, sparkline |
| `GET /api/series/{id}` | Identity (definition, unit, frequency, SA, measure type, geography, SIC), provenance (publisher, dataset id, request URL, source page, licence, attribution, release / next release / retrieved), status with reasons, transformation rules, available geographies & breakdowns, related series, ONS version history |
| `GET /api/series/{id}/observations?geo=&dim=&start=&end=` | Raw observations: value, status, source flags (CI/CV/forecast/derived), release date, retrieved time, ingestion run id |
| `GET /api/series/{id}/analysis?geo=&dim=&start=&end=&window=` | Points with period-on-period, year-on-year, rolling and indexed values (each only where allowed), historical context, volatility, missing data, outliers, decomposition, relationships, uncertainty, comparable regions/industries, typed findings |
| `GET /api/series/{id}/slice?by=geo|dim&period=&level=itl1|lad&dim=&geo=` | Cross-section at one period (map / heatmap / ranking) with change vs previous period and shares |
| `GET /api/series/{id}/revisions?geo=&dim=` | Revisions detected between retrievals + publisher version list |
| `GET /api/series/{id}/vintages?n=4&periods=12` | ONS only: earlier published versions vs current (fetched on demand, cached) |
| `GET /api/series/{id}/scenario?mode=flat|trend|custom&periods=&value=` | Transparent what-if projection with formula |
| `GET /api/compare?ids=a,b&mode=level|indexed|yoy|pop&geo=&start=&end=` | Aligned series; `note` explains refusals (e.g. indexing a rate) |
| `GET /api/correlate?a=&b=&basis=changes|levels&max_lag=&start=` | Pearson/Spearman with CI, lag profile, warnings; 409 if real and demo would be mixed |
| `GET /api/export?series_id=&geo=&dim=&start=&end=&format=csv|json&include_analysis=` | Download with per-row provenance columns (publisher, dataset id, request URL, source page, licence, attribution, retrieved time, run id, data_status) |

## Dashboards

| Endpoint | Description |
|---|---|
| `GET /api/overview` | KPI tiles, market monitor, alerts, source health |
| `GET /api/industry/heatmap?measure=yoy|mom|3m3m&months=` | MGDP sections × months, with latest workforce jobs and enterprise counts |
| `GET /api/industry/{section}?geo=` | Every published metric for a SIC section (no inferred breakdowns) |
| `GET /api/regions/profile/{geo}` | Regional series vs UK, child local authorities, location quotients |
| `GET /api/trade/partners?flow=exports|imports&by=partner|sitc&months=12` | HMRC goods trade by partner/SITC, shares, change vs prior window |
| `GET /api/housing/transactions?district=&months=&limit=` | Price Paid transactions (live SPARQL, cached 6 h) with the exact query |
| `GET /api/gilts/instruments` | DMO gilts in issue (when retrievable) |

## Platform

| Endpoint | Description |
|---|---|
| `GET /api/meta` | Demo mode, optional integrations, not-integrated sources, paid dependencies (`[]`) |
| `GET /api/sources` | Registry + live health per source |
| `GET /api/sources/{id}/runs` · `GET /api/runs/{id}` | Ingestion log with every HTTP request (URL, status, attempt, latency, bytes, cache) |
| `POST /api/sources/{id}/refresh` | Queue an ingestion run (requires `X-Admin-Token` if `UKINTEL_ADMIN_TOKEN` is set) |
| `GET /api/alerts?active=&kind=&series_id=` | Outlier, revision, stale, delayed, source_failure, validation alerts |
| `GET /api/search?q=` | Metrics, places, industries |
| `GET/POST/DELETE /api/views` | Saved views (page path + filters) |
| `GET /api/geo/boundaries/{itl1|lad}` · `GET /api/geo/areas?level=&parent=` | ONS boundaries (GeoJSON) and area hierarchy |
| `GET /api/companies/search?q=` · `GET /api/companies/{number}` | Companies House (503 with explanation when no key) |
| `GET /api/catalogue` | Full registry and catalogue as JSON |

## Examples

```bash
curl -s "localhost:8000/api/series/cpi_yoy/analysis?start=2020" | jq '.findings'
```

```bash
curl -s -OJ "localhost:8000/api/export?series_id=claimant_rate&geo=E08000003&format=csv&include_analysis=true"
```

```bash
curl -s "localhost:8000/api/correlate?a=cpi_services_yoy&b=awe_regular_growth&max_lag=12" | jq '.contemporaneous, .best_lag, .warnings'
```
