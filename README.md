# UK National Finance & Industry Intelligence Platform

A dense, dark analytical workspace for official UK economic, financial and industry statistics — built
entirely on **free, openly licensed public sources**, with full provenance for every number.

- **No paid API, premium data feed, paid LLM or subscription** is needed for core operation.
- **Every displayed value is investigable**: click any KPI, chart point, heatmap cell, map area or table row to
  open the investigation workspace (definition, raw observations, provenance, revisions, statistics,
  relationships, scenario, findings, export).
- **Economic Conditions Score** (0–100, 50 = historical average): a transparent, live-recomputed composite of
  eight published indicators with every input, weight and contribution shown — constructed by this platform,
  not an official statistic ([method](docs/methodology.md#9-economic-conditions-score-platform-construction--not-an-official-statistic)).
- **Release-aware updates**: besides scheduled polling, the worker fetches ONS series within ~15 minutes of
  their announced publication time.
- **Mock data is never presented as live data.** Demo values are synthetic, stored separately, only used when a
  series has no real observations, and labelled everywhere (hatched purple `DEMO · sample data` badge,
  `data_status: "demo"` in every API response, a warning in every export).

The interface draws on the analytical design principles of tools such as Palantir Foundry/Gotham (dense
panels, linked views, a separate investigation workspace). It uses no Palantir logos, assets or code and is
not affiliated with Palantir.

## What's integrated (verified live on 2026-10-26)

| Source | What | Licence | Access |
|---|---|---|---|
| ONS (website time-series JSON + search API) | GDP, monthly GDP by SIC section, CPI/CPIH + 12 COICOP divisions, labour market, pay, productivity, retail, public finances, trade totals | OGL v3.0 | no key |
| Bank of England IADB | Bank Rate, SONIA, 5/10/20y gilt yields, mortgage rates, approvals | OGL v3.0 (selected FX excluded) | no key |
| ECB Data Portal | EUR reference rates → derived GBP/USD, GBP/EUR, GBP/JPY (stated as modifications) | ECB reuse terms | no key |
| NOMIS | APS unemployment/employment (with 95% CIs), claimant count, ASHE pay (with CVs), UK Business Counts, workforce jobs — regions & 361 local authorities | OGL v3.0 | optional free uid |
| HM Land Registry | UK HPI by region (SPARQL); individual Price Paid transactions on demand | OGL v3.0 | no key |
| HMRC OTS (uktradeinfo OData) | Goods trade by partner country and SITC section | OGL v3.0 | no key |
| NESO Carbon Intensity | GB generation mix & carbon intensity, half-hourly | CC BY 4.0 | no key |
| DESNZ (via GOV.UK Content API) | Weekly road fuel prices | OGL v3.0 | no key |
| UK DMO | Gilts in issue (D1A) — **usually unavailable**: blocked by bot protection; not circumvented | OGL v3.0 | no key |
| Companies House | Company search, profile, filing history (on demand) | public register data | **free key required** |
| ONS Open Geography | ITL1 + LAD 2025 boundaries, LAD→ITL1 lookup | OGL v3.0 | no key |

94 catalogued series. Full details: [docs/source-catalogue.md](docs/source-catalogue.md). Live endpoint check:
[docs/verification-report.md](docs/verification-report.md). Not integrated (and why): equity indices
(proprietary), BoE spot FX (third-party redistribution restrictions), ONS PPI (no current observations at
verification), DESNZ Energy Trends spreadsheets (not yet parsed).

## Quick start

**Docker (PostgreSQL, API, scheduled worker, web):**

```bash
cp .env.example .env
```

```bash
docker compose up --build
```

UI at http://localhost:3000, API docs at http://localhost:8000/docs. The worker begins ingesting all sources
within a minute (staggered); until a series has real data, it shows labelled demo data (set
`UKINTEL_DEMO_MODE=off` to show "unavailable" instead).

**Without Docker** (SQLite, Python ≥3.11 <3.14, Node 22): see [docs/setup.md](docs/setup.md).

## Repository layout

```
backend/   FastAPI + SQLAlchemy + Alembic; connectors, ingestion, analytics, API, tests
  app/registry/   source registry (licences, limits, schedules, verification) and series catalogue
  app/connectors/ one module per source: HTTP, schema validation, parsing
  app/ingestion/  runner (upsert + revision detection + run log), health, sweep, DB cache
  app/analytics/  transformations & appropriateness rules, statistics, deterministic findings
  app/api/        REST endpoints
  tests/          pytest (parsers on real captured payloads, analytics, HTTP resilience, ingestion, API)
frontend/  Next.js 16 + TypeScript + Tailwind v4 + shadcn/ui (Base UI) + ECharts + MapLibre GL
docs/      setup, deployment, API, schema, methodology, source catalogue, verification, cost & limitations
```

## Documentation

- [Setup guide](docs/setup.md) · [Deployment guide](docs/deployment.md) · [API documentation](docs/api.md)
  (+ [openapi.json](docs/openapi.json))
- [Database schema](docs/database-schema.md) · [Methodology & statistical rules](docs/methodology.md)
- [Source catalogue](docs/source-catalogue.md) · [Verification report](docs/verification-report.md)
- [Cost & limitations report](docs/cost-and-limitations.md) · [Acceptance tests](docs/acceptance.md)

## Tests

```bash
cd backend && .venv/bin/python -m pytest
```

```bash
cd frontend && npm test
```
