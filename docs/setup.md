# Setup guide (local development)

## Requirements

- Python 3.11–3.13 (3.12 recommended; [uv](https://docs.astral.sh/uv/) makes this easy)
- Node.js 22 and npm
- Optional: Docker (for PostgreSQL / the full stack)

No API keys are required. Optional free keys: Companies House (company search) and a NOMIS uid.

## 1. Backend

```bash
cd backend
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e ".[dev]"
cp ../.env.example .env        # defaults: SQLite, demo_mode=fallback
```

Fetch real data (about 2–3 minutes; respects each source's rate limit):

```bash
.venv/bin/python -m app.cli ingest all
```

Or a single source: `.venv/bin/python -m app.cli ingest ons` (sources: `ons boe ecb nomis land_registry
hmrc_ots neso_carbon desnz_fuel dmo ons_geography`). Re-running is safe: unchanged values are not rewritten
and changed values are recorded as revisions.

Run the API:

```bash
.venv/bin/uvicorn app.main:app --port 8000
```

Run the scheduler (polls each source at its registry interval and runs the stale/delayed sweep):

```bash
.venv/bin/python -m app.worker
```

Other commands:

| Command | Purpose |
|---|---|
| `python -m app.cli verify --write` | Live-check every catalogue identifier against the official endpoints (writes nothing to the DB) and regenerate `docs/verification-report.md` |
| `python -m app.cli catalogue` | Regenerate `docs/source-catalogue.md` from the registry |
| `python -m app.cli openapi` | Write `docs/openapi.json` |
| `python -m app.cli sweep` | Raise/resolve stale and delayed alerts now |

### Using PostgreSQL locally

```bash
docker run -d --name ukintel-pg -e POSTGRES_USER=ukintel -e POSTGRES_PASSWORD=ukintel -e POSTGRES_DB=ukintel -p 5432:5432 postgres:16-alpine
```

Set `UKINTEL_DATABASE_URL=postgresql+psycopg://ukintel:ukintel@localhost:5432/ukintel` and apply migrations:

```bash
.venv/bin/alembic upgrade head
```

(With SQLite, tables are created automatically on startup; with PostgreSQL, Alembic owns the schema.)

## 2. Frontend

```bash
cd frontend
npm install              # postinstall copies the MapLibre worker into public/
npm run dev              # http://localhost:3000 (proxies /api/* to http://localhost:8000)
```

Point the proxy elsewhere with `API_INTERNAL_URL=http://host:port` (read at build/start time).
Production build: `npm run build && npm start`. Development mode compiles each route on first visit, which can
take several seconds; production builds don't have this delay.

## 3. Tests

```bash
cd backend && .venv/bin/python -m pytest      # 56 tests: parsers (real captured payloads), analytics, HTTP, ingestion, API
cd frontend && npm test && npm run typecheck && npm run lint
```

Parser tests use small, trimmed real responses captured from each source on 2026-10-26 (`backend/tests/fixtures`).
The DMO fixture is hand-written in the observed schema (with illustrative values) because DMO blocks
programmatic access.

## Demo mode

`UKINTEL_DEMO_MODE`:

- `fallback` (default): series with **no** real observations show synthetic sample data, labelled everywhere.
  As soon as a real retrieval succeeds, real data is served and the demo rows are ignored.
- `off`: no sample data; panels show "No observations retrieved yet".
- `only`: everything is synthetic (offline UI work). Always labelled.
