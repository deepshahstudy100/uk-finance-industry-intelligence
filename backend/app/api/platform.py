"""Sources, ingestion runs, alerts, search, saved views, geography and Companies House."""
from __future__ import annotations

import threading

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..connectors.companies_house import CompaniesHouseConnector
from ..connectors.http import HttpClient, SourceError
from ..db import get_db
from ..ingestion.cache import DbCacheStore
from ..ingestion.runner import run_source
from ..models import Alert, GeoArea, GeoBoundary, IngestionRun, SavedView
from ..registry.catalogue import CATALOGUE, SIC_SECTIONS
from ..registry.sources import NOT_INTEGRATED, SOURCES
from .. import services as svc
from .dashboards import alert_dict
from .util import clean, require_admin

router = APIRouter(prefix="/api", tags=["platform"])
_running: set[str] = set()
_lock = threading.Lock()


@router.get("/health")
def health():
    return {"ok": True}


@router.get("/meta")
def meta():
    st = get_settings()
    return {"demo_mode": st.demo_mode, "companies_house_enabled": bool(st.companies_house_api_key),
            "boe_fx_enabled": st.enable_boe_fx, "not_integrated": NOT_INTEGRATED, "series_count": len(CATALOGUE),
            "source_count": len(SOURCES), "paid_dependencies": [],
            "statement": "No paid API, premium data source, paid LLM or subscription is required."}


@router.get("/sources")
def sources(db: Session = Depends(get_db)):
    return clean(svc.source_rows(db))


@router.get("/sources/{source_id}/runs")
def runs(source_id: str, limit: int = Query(20, le=100), db: Session = Depends(get_db)):
    if source_id not in SOURCES and source_id != "demo":
        raise HTTPException(404, "Unknown source")
    rs = db.scalars(select(IngestionRun).where(IngestionRun.source_id == source_id)
                    .order_by(IngestionRun.id.desc()).limit(limit)).all()
    return clean([svc.run_dict(r) for r in rs])


@router.get("/runs/{run_id}")
def run(run_id: int, db: Session = Depends(get_db)):
    r = db.get(IngestionRun, run_id)
    if not r:
        raise HTTPException(404, "Unknown run")
    return clean(svc.run_dict(r))


def _run_bg(source_id: str):
    try:
        run_source(source_id, job="manual")
    finally:
        with _lock:
            _running.discard(source_id)


@router.post("/sources/{source_id}/refresh", dependencies=[Depends(require_admin)])
def refresh(source_id: str, bg: BackgroundTasks):
    if source_id not in SOURCES:
        raise HTTPException(404, "Unknown source")
    with _lock:
        if source_id in _running:
            return {"queued": False, "reason": "Already running"}
        _running.add(source_id)
    bg.add_task(_run_bg, source_id)
    return {"queued": True}


@router.get("/alerts")
def alerts(active: bool = True, kind: str | None = None, series_id: str | None = None, limit: int = 100,
           db: Session = Depends(get_db)):
    q = select(Alert)
    if active:
        q = q.where(Alert.active.is_(True))
    if kind:
        q = q.where(Alert.kind == kind)
    if series_id:
        q = q.where(Alert.series_id == series_id)
    return clean([alert_dict(a) for a in db.scalars(q.order_by(Alert.updated_at.desc()).limit(limit))])


@router.get("/search")
def search(q: str = Query(..., min_length=1, max_length=100), db: Session = Depends(get_db)):
    ql = q.lower().strip()
    series = []
    for sd in CATALOGUE.values():
        hay = f"{sd.id} {sd.title} {sd.definition} {sd.source_key} {' '.join(sd.tags)} {sd.category}".lower()
        if all(tok in hay for tok in ql.split()):
            series.append({"type": "series", "id": sd.id, "title": sd.title, "subtitle":
                           f"{SOURCES[sd.source_id].publisher} · {sd.unit} · {sd.frequency}", "category": sd.category})
    areas = db.scalars(select(GeoArea).where(or_(GeoArea.name.ilike(f"%{q}%"), GeoArea.code.ilike(f"{q}%")))
                       .limit(15)).all()
    inds = [{"type": "industry", "id": k, "title": f"{k}: {v}", "subtitle": "SIC 2007 section"}
            for k, v in SIC_SECTIONS.items() if ql in v.lower() or ql == k.lower()]
    return clean({"query": q, "results": series[:25] + [
        {"type": "geography", "id": a.code, "title": a.name, "subtitle": f"{a.level.upper()} · {a.code}"} for a in areas
    ] + inds, "companies_available": bool(get_settings().companies_house_api_key)})


class ViewIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    path: str = Field(min_length=1, max_length=400)
    state: dict = {}


@router.get("/views")
def list_views(db: Session = Depends(get_db)):
    return clean([{"id": v.id, "name": v.name, "path": v.path, "state": v.state, "created_at": v.created_at}
                  for v in db.scalars(select(SavedView).order_by(SavedView.id.desc()))])


@router.post("/views")
def create_view(v: ViewIn, db: Session = Depends(get_db)):
    row = SavedView(name=v.name, path=v.path, state=v.state, created_at=svc.utcnow())
    db.add(row)
    db.commit()
    return {"id": row.id}


@router.delete("/views/{view_id}")
def delete_view(view_id: int, db: Session = Depends(get_db)):
    row = db.get(SavedView, view_id)
    if row:
        db.delete(row)
        db.commit()
    return {"deleted": bool(row)}


@router.get("/geo/boundaries/{level}")
def boundaries(level: str, db: Session = Depends(get_db)):
    b = db.get(GeoBoundary, level)
    if not b:
        raise HTTPException(404, "Boundaries not retrieved yet - run the ons_geography source")
    return Response(b.geojson, media_type="application/geo+json",
                    headers={"Cache-Control": "public, max-age=86400", "X-Source-URL": b.source_url[:500],
                             "X-Retrieved-At": b.retrieved_at.isoformat()})


@router.get("/geo/areas")
def areas(level: str | None = None, parent: str | None = None, db: Session = Depends(get_db)):
    q = select(GeoArea)
    if level:
        q = q.where(GeoArea.level == level)
    if parent:
        q = q.where(GeoArea.parent_code == parent)
    return clean([{"code": a.code, "name": a.name, "level": a.level, "parent": a.parent_code, "alt": a.alt_codes}
                  for a in db.scalars(q.order_by(GeoArea.name))])


def _ch():
    return HttpClient("companies_house", cache=DbCacheStore())


@router.get("/companies/search")
def companies_search(q: str = Query(..., min_length=2, max_length=100)):
    http = _ch()
    try:
        return CompaniesHouseConnector(http).search(q)
    except SourceError as e:
        code = {"disabled": 503, "validation": 422, "auth": 502, "rate_limited": 429}.get(e.kind, 502)
        raise HTTPException(code, str(e)) from e
    finally:
        http.close()


@router.get("/companies/{number}")
def company(number: str):
    http = _ch()
    try:
        out = CompaniesHouseConnector(http).profile(number)
    except SourceError as e:
        code = {"disabled": 503, "validation": 422, "not_found": 404, "rate_limited": 429}.get(e.kind, 502)
        raise HTTPException(code, str(e)) from e
    finally:
        http.close()
    sics = out["profile"].get("sic_codes") or []
    out["sic_sections"] = [{"sic": c, "section": sic_to_section(c)} for c in sics]
    out["attribution"] = SOURCES["companies_house"].attribution
    return out


# SIC 2007 division ranges -> section (published SIC 2007 structure).
_SECTION_RANGES = [("A", 1, 3), ("B", 5, 9), ("C", 10, 33), ("D", 35, 35), ("E", 36, 39), ("F", 41, 43),
                   ("G", 45, 47), ("H", 49, 53), ("I", 55, 56), ("J", 58, 63), ("K", 64, 66), ("L", 68, 68),
                   ("M", 69, 75), ("N", 77, 82), ("O", 84, 84), ("P", 85, 85), ("Q", 86, 88), ("R", 90, 93),
                   ("S", 94, 96), ("T", 97, 98), ("U", 99, 99)]


def sic_to_section(code: str) -> str | None:
    try:
        div = int(str(code)[:2])
    except ValueError:
        return None
    return next((s for s, lo, hi in _SECTION_RANGES if lo <= div <= hi), None)


@router.get("/catalogue")
def catalogue():
    return clean({"sources": [s.to_dict() for s in SOURCES.values()],
                  "series": [s.to_dict() for s in CATALOGUE.values()], "not_integrated": NOT_INTEGRATED})
