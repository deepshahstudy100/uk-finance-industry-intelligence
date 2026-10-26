"""Command line: python -m app.cli <command>

  init-db                 create tables (SQLite) / sync registry; seeds demo data if demo mode is on
  ingest <source> [...]   run ingestion for one or more sources (or 'all')
  sweep                   run the stale/delayed health sweep
  verify [--write]        live-check every catalogue identifier WITHOUT writing observations; prints a report
                          and with --write saves docs/verification-report.md
  catalogue               regenerate docs/source-catalogue.md from the registry
  openapi                 write docs/openapi.json
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from .connectors import CONNECTORS
from .connectors.http import HttpClient
from .db import session_scope
from .ingestion.runner import run_all, run_source
from .ingestion.sweep import health_sweep
from .main import init_db
from .registry.catalogue import CATALOGUE
from .registry.sources import SOURCES


def verify(write: bool = False) -> int:
    rows, failures = [], 0
    for sid, sd in SOURCES.items():
        if sd.latency_class == "on_demand":
            rows.append((sid, "-", "skipped", "on-demand source (needs free key)", ""))
            continue
        http = HttpClient(sid)
        t0 = time.monotonic()
        try:
            res = CONNECTORS[sid](http).fetch()
        except Exception as e:  # noqa: BLE001
            rows.append((sid, "*", "FAIL", f"{type(e).__name__}: {e}", ""))
            failures += 1
            continue
        finally:
            http.close()
        for b in res.batches:
            vals = [o for o in b.observations if o.value is not None]
            latest = max(vals, key=lambda o: (o.period_start, o.period)).period if vals else "-"
            rows.append((sid, b.series_id, "ok", f"{len(b.observations)} obs; latest {latest}", b.request_url or ""))
        for e in res.errors:
            rows.append((sid, e.get("series_id"), "FAIL", f"{e.get('kind')}: {e.get('message')}", e.get("url") or ""))
            failures += 1
        if sid == "ons_geography":
            for lvl, b in res.extra.get("boundaries", {}).items():
                rows.append((sid, f"boundaries:{lvl}", "ok", f"{len(b['geojson']['features'])} features", b["url"]))
            if "lad_lookup" in res.extra:
                rows.append((sid, "lookup:lad_itl1", "ok", f"{len(res.extra['lad_lookup']['rows'])} rows",
                             res.extra["lad_lookup"]["url"]))
        print(f"[{sid}] {time.monotonic() - t0:.1f}s", file=sys.stderr)
    covered = {r[1] for r in rows if r[2] == "ok"}
    disabled = [s.id for s in CATALOGUE.values() if not s.enabled]
    missing = [s for s in CATALOGUE if s not in covered and s not in disabled]
    for r in rows:
        print(f"{r[2]:7} {r[0]:14} {str(r[1]):26} {r[3]}")
    if missing:
        print("Not verified:", ", ".join(missing))
    if write:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        lines = [f"# Live verification report\n\nGenerated {ts} by `python -m app.cli verify --write`. Each row is a "
                 "real request to the official endpoint; no data was written.\n",
                 "| Result | Source | Series | Detail | Request URL |", "|---|---|---|---|---|"]
        for r in rows:
            url = r[4].replace("|", "%7C")
            lines.append(f"| {r[2]} | {r[0]} | `{r[1]}` | {r[3]} | {('[link](' + url[:300] + ')') if url else ''} |")
        if disabled:
            lines.append(f"\nDisabled by configuration (not verified): {', '.join(disabled)}")
        if missing:
            lines.append(f"\nNot verified in this run: {', '.join(missing)}")
        out = Path(__file__).resolve().parents[2] / "docs" / "verification-report.md"
        out.write_text("\n".join(lines) + "\n")
        print(f"Wrote {out}")
    return 1 if failures else 0


def write_catalogue() -> Path:
    from .registry.sources import NOT_INTEGRATED

    L = ["# Source catalogue", "", "Generated from `backend/app/registry/` by `python -m app.cli catalogue`. Do not edit by hand.", "",
         "## Sources", ""]
    for s in SOURCES.values():
        rl = s.rate_limit
        L += [f"### {s.publisher} — {s.name} (`{s.id}`)", "",
              f"- **Endpoint:** `{s.api_base}`", f"- **Documentation:** {s.docs_url}",
              f"- **Licence:** [{s.licence}]({s.licence_url})", f"- **Attribution:** {s.attribution}",
              f"- **Authentication:** {s.auth}",
              f"- **Rate limit:** {rl.note} ({'documented by source' if rl.documented else 'self-imposed'})",
              f"- **Update frequency:** {s.update_frequency}", f"- **Latency class:** {s.latency_class}",
              f"- **Polling:** every {s.refresh_minutes} min; stale after {s.stale_after_hours} h" if s.refresh_minutes
              else "- **Polling:** on demand only",
              f"- **Verification:** {s.verification}"]
        L += [f"- **Caveat:** {c}" for c in s.caveats]
        L.append("")
    L += ["## Series", "", "| ID | Title | Source | Identifier | Unit | Measure | Freq | SA | Geography | Breakdown |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for d in CATALOGUE.values():
        geo = d.geography + ("" if d.enabled else " (disabled)")
        L.append(f"| `{d.id}` | {d.title} | {d.source_id} | `{d.source_key}` | {d.unit} | {d.measure_type} | {d.frequency} | "
                 f"{d.seasonal_adjustment} | {geo} | {d.dim_kind or d.industry or ''} |")
    L += ["", "## Considered but not integrated", ""] + [f"- **{n['name']}** — {n['reason']}" for n in NOT_INTEGRATED]
    out = Path(__file__).resolve().parents[2] / "docs" / "source-catalogue.md"
    out.write_text("\n".join(L) + "\n")
    return out


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    cmd, args = argv[0], argv[1:]
    if cmd == "init-db":
        init_db()
        print("Database initialised")
        return 0
    if cmd == "ingest":
        init_db()
        if not args or args == ["all"]:
            print(json.dumps(run_all(), default=str, indent=1))
            return 0
        for sid in args:
            print(sid, json.dumps(run_source(sid, job="cli"), default=str)[:2000])
        return 0
    if cmd == "sweep":
        init_db()
        with session_scope() as s:
            print(health_sweep(s))
        return 0
    if cmd == "verify":
        return verify(write="--write" in args)
    if cmd == "catalogue":
        print(f"Wrote {write_catalogue()}")
        return 0
    if cmd == "openapi":
        from .main import app

        out = Path(__file__).resolve().parents[2] / "docs" / "openapi.json"
        out.write_text(json.dumps(app.openapi(), indent=1))
        print(f"Wrote {out}")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
