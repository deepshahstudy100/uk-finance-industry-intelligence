"""Ingestion: fetch -> validate (in connectors) -> upsert with revision detection -> log -> alerts.

Guarantees:
  * Real and demo observations are stored separately (is_demo) and never overwrite each other.
  * A failed fetch never writes any value; previously retrieved real data is kept and marked stale/delayed.
  * Every run is logged with each HTTP request (URL, status, attempts, latency, cache use).
"""
from __future__ import annotations

import logging
import math
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..analytics.stats import outliers
from ..analytics.transforms import to_series
from ..config import get_settings
from ..connectors import CONNECTORS
from ..connectors.base import SeriesBatch
from ..connectors.geography import dumps
from ..connectors.http import HttpClient, SourceError
from ..db import session_scope
from ..models import Alert, GeoArea, GeoBoundary, IngestionRun, Observation, ObservationRevision, Series, Source
from ..registry.catalogue import CATALOGUE
from ..registry.geography import AREAS, ITL_TO_GSS
from ..registry.sources import SOURCES
from .cache import DbCacheStore

log = logging.getLogger("ukintel.ingest")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def sync_registry(s: Session) -> None:
    """Mirror the code registry into the database (idempotent)."""
    settings = get_settings()
    for sd in SOURCES.values():
        row = s.get(Source, sd.id) or Source(id=sd.id, consecutive_failures=0)
        row.name, row.publisher, row.meta = sd.name, sd.publisher, sd.to_dict()
        row.enabled = sd.enabled_by_default
        row.disabled_reason = None
        if sd.id == "companies_house" and not settings.companies_house_api_key:
            row.disabled_reason = "No API key configured (free registration). Company search is unavailable."
        s.merge(row)
    s.flush()
    for d in CATALOGUE.values():
        row = s.get(Series, d.id) or Series(id=d.id, source_meta={})
        row.source_id, row.source_key, row.title, row.definition = d.source_id, d.source_key, d.title, d.to_dict()
        s.merge(row)
    for code, name, level, parent, itl, slug in AREAS:
        g = s.get(GeoArea, code) or GeoArea(code=code)
        g.name, g.level, g.parent_code = name, level, parent
        g.alt_codes = {**(g.alt_codes or {}), "itl": itl, "lr_slug": slug}
        s.merge(g)
    s.commit()


def _same(a: float | None, b: float | None) -> bool:
    if a is None or b is None:
        return a is b
    return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12)


def upsert_batch(s: Session, run: IngestionRun, b: SeriesBatch, *, is_demo: bool = False) -> dict:
    retrieved = now_utc()
    existing = {
        (o.geo, o.dim, o.period): o
        for o in s.scalars(select(Observation).where(Observation.series_id == b.series_id,
                                                     Observation.is_demo == is_demo))
    }
    counts = {"inserted": 0, "updated": 0, "revised": 0, "unchanged": 0}
    seen: set = set()
    new_rows = []
    for o in b.observations:
        k = (o.geo, o.dim, o.period)
        if k in seen:
            continue  # duplicate key in one payload: keep first occurrence
        seen.add(k)
        rel = o.release_date or b.release_date
        cur = existing.get(k)
        if cur is None:
            new_rows.append(Observation(
                series_id=b.series_id, geo=o.geo, dim=o.dim, period=o.period, period_start=o.period_start,
                period_end=o.period_end, value=o.value, status=o.status, flags=o.flags, release_date=rel,
                retrieved_at=retrieved, run_id=run.id, is_demo=is_demo))
            counts["inserted"] += 1
            continue
        if not _same(cur.value, o.value):
            if not is_demo:
                s.add(ObservationRevision(series_id=b.series_id, geo=o.geo, dim=o.dim, period=o.period,
                                          old_value=cur.value, new_value=o.value, old_release_date=cur.release_date,
                                          new_release_date=rel, detected_at=retrieved, run_id=run.id))
            cur.value = o.value
            counts["revised"] += 1
        elif cur.status != o.status or (cur.flags or {}) != (o.flags or {}):
            counts["updated"] += 1
        else:
            counts["unchanged"] += 1
            cur.retrieved_at = retrieved
            continue
        cur.status, cur.flags, cur.release_date, cur.retrieved_at, cur.run_id = o.status, o.flags, rel, retrieved, run.id
    s.add_all(new_rows)
    ser = s.get(Series, b.series_id)
    if ser is not None and not is_demo:
        ser.last_retrieved_at = retrieved
        ser.last_request_url = b.request_url
        if b.source_title:
            ser.source_title = b.source_title
        if b.release_date:
            ser.release_date = b.release_date
        ser.next_release = b.next_release
        ser.source_meta = {**(ser.source_meta or {}), **b.source_meta}
        latest = max((o for o in b.observations if o.value is not None), key=lambda o: (o.period_start, o.period), default=None)
        if latest:
            ser.last_period = latest.period
    return counts


def _alert(s: Session, fingerprint: str, **kw) -> None:
    a = s.scalar(select(Alert).where(Alert.fingerprint == fingerprint))
    t = now_utc()
    if a is None:
        s.add(Alert(fingerprint=fingerprint, created_at=t, updated_at=t, active=True, **kw))
    else:
        for k, v in kw.items():
            setattr(a, k, v)
        a.updated_at, a.active = t, True


def resolve_alerts(s: Session, prefix: str) -> None:
    for a in s.scalars(select(Alert).where(Alert.fingerprint.like(prefix + "%"), Alert.active.is_(True))):
        a.active = False
        a.updated_at = now_utc()


def detect_outliers(s: Session, series_id: str) -> None:
    sd = CATALOGUE[series_id]
    if sd.frequency == "HH":
        return
    combos = s.execute(select(Observation.geo, Observation.dim).where(
        Observation.series_id == series_id, Observation.is_demo.is_(False)).distinct()).all()
    for geo, dim in combos[:60]:
        rows = [{"period_start": o.period_start, "value": o.value} for o in s.scalars(
            select(Observation).where(Observation.series_id == series_id, Observation.geo == geo,
                                      Observation.dim == dim, Observation.is_demo.is_(False))
            .order_by(Observation.period_start))]
        ser = to_series(rows)
        found = outliers(sd, ser, lookback=3)
        for o in found:
            _alert(s, f"outlier:{series_id}:{geo}:{dim}:{o['period']}", kind="outlier", severity="info",
                   series_id=series_id, source_id=sd.source_id, geo=geo, dim=dim, period=o["period"],
                   title=f"Unusual change: {sd.title}",
                   detail=f"{o['change']:+.2f}{o['change_unit']} in {o['period']} (robust z {o['robust_z']}). "
                          "Statistical flag only - check releases for an explanation.", payload=o)


def _store_geography(s: Session, run: IngestionRun, extra: dict) -> int:
    n = 0
    for level, b in (extra.get("boundaries") or {}).items():
        gb = s.get(GeoBoundary, level) or GeoBoundary(level=level)
        gb.geojson, gb.source_url, gb.retrieved_at = dumps(b["geojson"]), b["url"], now_utc()
        gb.feature_count = len(b["geojson"]["features"])
        s.merge(gb)
        n += gb.feature_count
    lk = extra.get("lad_lookup")
    if lk:
        for row in lk["rows"]:
            code = row.get("LAD25CD")
            if not code:
                continue
            g = s.get(GeoArea, code) or GeoArea(code=code)
            g.name, g.level = row.get("LAD25NM") or code, "lad"
            g.parent_code = ITL_TO_GSS.get(row.get("ITL125CD"))
            g.alt_codes = {"itl1": row.get("ITL125CD"), "lookup_url": lk["url"]}
            s.merge(g)
            n += 1
    return n


def run_source(source_id: str, series_ids: list[str] | None = None, *, job: str = "scheduled") -> dict:
    if source_id not in CONNECTORS:
        raise ValueError(f"Unknown source {source_id}")
    with session_scope() as s:
        sync_registry(s)
        src = s.get(Source, source_id)
        run = IngestionRun(source_id=source_id, job=job, started_at=now_utc(), status="running", errors=[],
                           requests=[])
        s.add(run)
        s.flush()
        run_id = run.id
        if not src.enabled or SOURCES[source_id].latency_class == "on_demand":
            run.status, run.finished_at, run.message = "skipped", now_utc(), "Source disabled or on-demand"
            return {"run_id": run_id, "status": "skipped"}
    http = HttpClient(source_id, cache=DbCacheStore())
    connector = CONNECTORS[source_id](http)
    fatal: str | None = None
    try:
        result = connector.fetch(series_ids)
    except SourceError as e:
        result, fatal = None, str(e)
        errors = [{"series_id": None, **e.to_dict()}]
    except Exception as e:  # noqa: BLE001 - recorded, never swallowed silently
        log.exception("Connector crashed")
        result, fatal = None, f"{type(e).__name__}: {e}"
        errors = [{"series_id": None, "kind": "crash", "message": fatal}]
    finally:
        http.close()

    with session_scope() as s:
        run = s.get(IngestionRun, run_id)
        src = s.get(Source, source_id)
        run.requests = http.request_log[-500:]
        totals = {"inserted": 0, "updated": 0, "revised": 0, "unchanged": 0}
        if result is not None:
            errors = result.errors
            for b in result.batches:
                c = upsert_batch(s, run, b)
                for k in totals:
                    totals[k] += c[k]
                run.fetched += len(b.observations)
                if c["revised"]:
                    _alert(s, f"revision:{b.series_id}:{run_id}", kind="revision", severity="info",
                           series_id=b.series_id, source_id=source_id,
                           title=f"Revisions detected: {CATALOGUE[b.series_id].title}",
                           detail=f"{c['revised']} previously retrieved value(s) changed in this retrieval.",
                           payload={"run_id": run_id, "count": c["revised"]})
            if source_id == "ons_geography":
                run.fetched += _store_geography(s, run, result.extra)
        run.inserted, run.updated, run.revised, run.unchanged = (totals["inserted"], totals["updated"],
                                                                 totals["revised"], totals["unchanged"])
        run.errors = errors
        ok = result is not None and (result.batches or result.extra.get("boundaries"))
        run.status = "failed" if not ok else ("partial" if errors else "success")
        run.finished_at = now_utc()
        run.message = fatal or (f"{len(errors)} series failed" if errors else "OK")
        src.last_attempt_at = run.finished_at
        if ok:
            src.last_success_at = run.finished_at
            src.consecutive_failures = 0 if not errors else src.consecutive_failures
            src.last_error = None if not errors else "; ".join(e.get("message", "")[:120] for e in errors[:3])
        else:
            src.consecutive_failures = (src.consecutive_failures or 0) + 1
            src.last_error = run.message
        # Alerts
        if errors:
            for e in errors:
                sid = e.get("series_id")
                kind = "validation" if e.get("kind") == "validation" else "source_failure"
                _alert(s, f"{kind}:{source_id}:{sid}", kind=kind, severity="warning" if ok else "critical",
                       series_id=sid if sid in CATALOGUE else None, source_id=source_id,
                       title=f"{SOURCES[source_id].publisher}: {'validation failed' if kind == 'validation' else 'retrieval failed'}"
                             + (f" ({sid})" if sid else ""),
                       detail=f"{e.get('kind')}: {e.get('message')}. Previously retrieved data (if any) is retained "
                              "and labelled stale; nothing was substituted.", payload=e)
        if ok:
            failed_ids = {e.get("series_id") for e in errors}
            for b in result.batches:
                if b.series_id not in failed_ids:
                    resolve_alerts(s, f"source_failure:{source_id}:{b.series_id}")
                    resolve_alerts(s, f"validation:{source_id}:{b.series_id}")
            if not errors:
                resolve_alerts(s, f"source_failure:{source_id}:None")
    if result is not None:
        with session_scope() as s:
            for b in result.batches:
                try:
                    detect_outliers(s, b.series_id)
                except Exception:  # noqa: BLE001
                    log.exception("Outlier detection failed for %s", b.series_id)
    with session_scope() as s:
        run = s.get(IngestionRun, run_id)
        return {"run_id": run_id, "status": run.status, "fetched": run.fetched, "inserted": run.inserted,
                "revised": run.revised, "errors": run.errors}


def run_all(job: str = "manual") -> list[dict]:
    out = []
    for sid, sd in SOURCES.items():
        if sd.latency_class == "on_demand":
            continue
        try:
            out.append({"source": sid, **run_source(sid, job=job)})
        except Exception as e:  # noqa: BLE001
            log.exception("run_source failed")
            out.append({"source": sid, "status": "failed", "error": str(e)})
    return out
