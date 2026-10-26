# Deployment guide

## Option A — Docker Compose (recommended; local or any VM)

```bash
cp .env.example .env     # set POSTGRES_PASSWORD and UKINTEL_ADMIN_TOKEN; optionally UKINTEL_COMPANIES_HOUSE_API_KEY
docker compose up --build -d
```

Services:

| Service | Image | Role |
|---|---|---|
| `db` | postgres:16-alpine | Storage (named volume `pgdata`) |
| `api` | `backend/Dockerfile` | FastAPI on :8000; runs `alembic upgrade head` on start (`RUN_MIGRATIONS=1`) |
| `worker` | same image | `python -m app.worker`: scheduled ingestion + health sweep |
| `web` | `frontend/Dockerfile` | Next.js standalone server on :3000; proxies `/api/*` to `api:8000` |

Only `web` needs to be public. If you expose `api`, set `UKINTEL_ADMIN_TOKEN` so the manual refresh endpoint
(`POST /api/sources/{id}/refresh`) is protected; all other endpoints are read-only.

Notes:
- The frontend image build downloads the Geist font through `next/font/google` (free Google Fonts) and the
  npm packages; it needs network access at build time only.
- Logs: `docker compose logs -f worker` shows each ingestion run; the same runs (with every HTTP request) are
  visible on the **Sources & health** page.
- Backups: `docker compose exec db pg_dump -U ukintel ukintel > backup.sql`.
- Upgrades: `git pull && docker compose up --build -d` (migrations run automatically).

## Option B — Without containers

Run PostgreSQL (or SQLite for a single user), then as separate long-running processes (systemd, supervisord):

```
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
python -m app.worker            # exactly ONE worker process, or sources would be polled twice
cd frontend && API_INTERNAL_URL=http://127.0.0.1:8000 npm run build && npm start
```

## Option C — Free hosting tiers (no guarantees)

The stack needs: one always-on Python process for the worker, one web process for the API, a PostgreSQL
database (measured on 2026-10-26: ~80 MB for all sources incl. HTTP cache and demo rows; grows slowly) and a Node host for the UI. Free tiers can do this, with caveats:

- **Free tiers change, sleep, and impose limits.** A sleeping worker means no scheduled ingestion; the UI will
  then correctly show data as *stale*. Verify each provider's current terms (including commercial-use rules)
  before relying on it.
- Typical pattern: a managed free PostgreSQL tier, a free container/web-service tier for the API (the worker can
  be replaced by a free scheduled job/cron runner calling `python -m app.cli ingest all` a few times a day),
  and a free static/Node tier for the frontend with `API_INTERNAL_URL` pointing at the API.
- Self-hosting on a small existing machine (home server, a spare VM) with Docker Compose is the most reliable
  zero-cost option.

This project makes **no promise of unlimited free hosting or 24/7 uptime**. Data freshness is always shown
relative to each source's schedule, so degraded hosting is visible rather than silent.

## Operational checklist

- Set a real `UKINTEL_USER_AGENT` with your project URL or organisational contact (ONS asks bots to identify
  themselves; do not put personal data in it).
- Keep `UKINTEL_ENABLE_BOE_FX=false` unless you have confirmed your use of BoE spot FX is permitted.
- Run `python -m app.cli verify --write` after upgrades or when a source changes, and review
  `docs/verification-report.md`.
- Choose `UKINTEL_DEMO_MODE=off` for public deployments if you never want sample data shown.
