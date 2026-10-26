"""Module-level endpoints for the dashboards. Each value returned links back to a (series, geo, dim, period)
so the UI can open the investigation workspace for it."""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..analytics import transforms as T
from ..connectors.http import HttpClient, SourceError
from ..connectors.land_registry import PPD_PAGE, LandRegistryConnector
from ..db import get_db
from ..ingestion.cache import DbCacheStore
from ..models import Alert, Series
from ..registry.catalogue import CATALOGUE, SIC_SECTIONS
from ..registry.sources import SOURCES
from .. import services as svc
from .util import clean

router = APIRouter(prefix="/api", tags=["dashboards"])

KPIS = ["gdp_qoq", "cpi_yoy", "unemployment_rate", "awe_regular_growth", "bank_rate", "gilt_10y", "fx_gbp_usd",
        "psnd_ex_gdp", "hfce", "productivity_oph", "retail_sales_volume", "hpi_yoy"]
MARKETS = ["bank_rate", "sonia", "gilt_5y", "gilt_10y", "gilt_20y", "fx_gbp_usd", "fx_gbp_eur", "fx_gbp_jpy",
           "mortgage_2y_75", "mortgage_5y_75"]
TIMELINE = ["cpi_yoy", "bank_rate", "unemployment_rate", "gdp_yoy", "awe_regular_growth"]


@router.get("/overview")
def overview(db: Session = Depends(get_db)):
    alerts = db.scalars(select(Alert).where(Alert.active.is_(True)).order_by(Alert.updated_at.desc()).limit(12)).all()
    sources = svc.source_rows(db)
    return clean({
        "kpis": [svc.series_summary(db, CATALOGUE[k]) for k in KPIS],
        "markets": [svc.series_summary(db, CATALOGUE[k]) for k in MARKETS],
        "timeline_series": TIMELINE,
        "alerts": [alert_dict(a) for a in alerts],
        "sources": [{"id": s["id"], "name": s["name"], "publisher": s["publisher"], "status": s["status"],
                     "last_success_at": s["last_success_at"], "latency_class": s["latency_class"]} for s in sources],
    })


def alert_dict(a: Alert) -> dict:
    return {"id": a.id, "kind": a.kind, "severity": a.severity, "series_id": a.series_id, "source_id": a.source_id,
            "geo": a.geo, "dim": a.dim, "period": a.period, "title": a.title, "detail": a.detail,
            "created_at": a.created_at, "updated_at": a.updated_at, "active": a.active, "payload": a.payload}


def _three_month(s: pd.Series) -> pd.Series:
    r = s.rolling(3, min_periods=3).mean()
    return (r / r.shift(3) - 1) * 100


@router.get("/industry/heatmap")
def industry_heatmap(measure: str = Query("yoy", pattern="^(yoy|mom|3m3m)$"), months: int = Query(12, ge=3, le=36),
                     db: Session = Depends(get_db)):
    rows, periods, demo_any = [], set(), False
    for sd in [d for d in CATALOGUE.values() if d.group == "gva_sections"]:
        obs, demo = svc.obs_rows(db, sd.id)
        demo_any |= demo
        s = T.to_series(obs)
        if s.empty:
            rows.append({"series_id": sd.id, "section": sd.industry, "name": SIC_SECTIONS[sd.industry], "cells": []})
            continue
        m = {"yoy": T.year_on_year(s, sd), "mom": T.period_on_period(s, sd), "3m3m": _three_month(s)}[measure]
        m = m.dropna().iloc[-months:]
        cells = [{"period": f"{t.year:04d}-{t.month:02d}", "value": float(v), "level": float(s[t])} for t, v in m.items()]
        periods |= {c["period"] for c in cells}
        rows.append({"series_id": sd.id, "section": sd.industry, "name": SIC_SECTIONS[sd.industry], "cells": cells})
    wfj = {r["dim"]: r for r in _latest_by_dim(db, "workforce_jobs")}
    bc = {r["dim"]: r for r in _latest_by_dim(db, "business_counts")}
    for r in rows:
        r["workforce_jobs"] = wfj.get(r["section"])
        r["enterprises"] = bc.get(r["section"])
    return clean({"measure": measure, "unit": "%", "periods": sorted(periods), "rows": rows,
                  "data_status": "demo" if demo_any else "real",
                  "method": {"yoy": "% change on same month a year earlier",
                             "mom": "% change on previous month (volatile - ONS advises 3m/3m)",
                             "3m3m": "% change of the latest 3-month average on the previous 3-month average"}[measure],
                  "source": "ONS monthly GDP (MGDP) section indices, CVM SA"})


def _latest_by_dim(db: Session, series_id: str, geo: str | None = None) -> list[dict]:
    sd = CATALOGUE[series_id]
    demo = svc.use_demo(db, series_id)
    out = []
    for d in svc.dims_for(db, series_id, demo):
        rows, _ = svc.obs_rows(db, series_id, geo, d, demo=demo)
        v = [r for r in rows if r["value"] is not None]
        if len(v):
            prev = v[-2]["value"] if len(v) > 1 else None
            out.append({"series_id": series_id, "dim": d, "period": v[-1]["period"], "value": v[-1]["value"],
                        "previous_period": v[-2]["period"] if len(v) > 1 else None,
                        "change_pct": (v[-1]["value"] / prev - 1) * 100 if prev else None,
                        "data_status": svc.data_status(demo), "unit": sd.unit})
    return out


@router.get("/industry/{section}")
def industry_profile(section: str, geo: str | None = None, db: Session = Depends(get_db)):
    section = section.upper()
    if section not in SIC_SECTIONS:
        raise HTTPException(404, "Unknown SIC 2007 section")
    metrics = []
    for sd in CATALOGUE.values():
        if sd.industry == section:
            metrics.append({"kind": "series", **svc.series_summary(db, sd)})
    for sid in ("workforce_jobs", "business_counts"):
        g = geo if geo and CATALOGUE[sid].geography != "uk" else None
        r = next((x for x in _latest_by_dim(db, sid, g) if x["dim"] == section), None)
        if r:
            metrics.append({"kind": "dim", "id": sid, "title": CATALOGUE[sid].title, "dim": section, **r})
    return clean({"section": section, "name": SIC_SECTIONS[section], "classification": "SIC 2007", "metrics": metrics,
                  "note": "Only metrics published for this SIC section are shown; no breakdown is inferred."})


@router.get("/regions/profile/{geo}")
def region_profile(geo: str, db: Session = Depends(get_db)):
    out = []
    for sd in CATALOGUE.values():
        if sd.geography == "uk" or sd.geography == "gb":
            continue
        demo = svc.use_demo(db, sd.id)
        dim = "_" if not sd.dim_kind else None
        if dim is None:
            continue
        rows, _ = svc.obs_rows(db, sd.id, geo, dim, demo=demo)
        v = [r for r in rows if r["value"] is not None]
        if not v:
            continue
        uk, _ = svc.obs_rows(db, sd.id, "K02000001", dim, demo=demo)
        ukv = next((r["value"] for r in reversed(uk) if r["period"] == v[-1]["period"]), None)
        out.append({"series_id": sd.id, "title": sd.title, "unit": sd.unit, "decimals": sd.decimals, "period": v[-1]["period"],
                    "value": v[-1]["value"], "flags": v[-1]["flags"], "uk_value": ukv,
                    "data_status": svc.data_status(demo), "spark": [r["value"] for r in v[-24:]]})
    # Industrial concentration: location quotient of enterprise counts vs UK.
    lq = []
    bc_geo = {r["dim"]: r["value"] for r in _latest_by_dim(db, "business_counts", geo)}
    bc_uk = {r["dim"]: r["value"] for r in _latest_by_dim(db, "business_counts", "K02000001")}
    tg, tu = sum(v for v in bc_geo.values() if v), sum(v for v in bc_uk.values() if v)
    if tg and tu:
        for d, v in bc_geo.items():
            if d in bc_uk and bc_uk[d] and v is not None:
                lq.append({"section": d, "name": SIC_SECTIONS.get(d, d), "enterprises": v,
                           "share_pct": v / tg * 100, "uk_share_pct": bc_uk[d] / tu * 100,
                           "location_quotient": (v / tg) / (bc_uk[d] / tu)})
    from ..models import GeoArea

    g = db.get(GeoArea, geo)
    children = [{"code": c.code, "name": c.name} for c in db.scalars(select(GeoArea).where(GeoArea.parent_code == geo))]
    return clean({"geo": geo, "name": svc.geo_name(db, geo), "level": g.level if g else None,
                  "parent": g.parent_code if g else None, "children": sorted(children, key=lambda c: c["name"]),
                  "metrics": out, "industry_concentration": sorted(lq, key=lambda x: -x["location_quotient"]),
                  "lq_method": "Location quotient = section share of the area's enterprises / section share of UK "
                               "enterprises (UK Business Counts). >1 means relatively concentrated."})


@router.get("/trade/partners")
def trade_partners(flow: str = Query("exports", pattern="^(exports|imports)$"), months: int = Query(12, ge=1, le=12),
                   by: str = Query("partner", pattern="^(partner|sitc)$"), db: Session = Depends(get_db)):
    sid = f"hmrc_{flow}_{'partner' if by == 'partner' else 'sitc'}"
    sd = CATALOGUE[sid]
    ser = db.get(Series, sid)
    demo = svc.use_demo(db, sid)
    from ..models import Observation

    obs = db.scalars(select(Observation).where(Observation.series_id == sid, Observation.is_demo.is_(demo))).all()
    periods = sorted({o.period for o in obs})
    if not periods:
        return clean({"series_id": sid, "rows": [], "data_status": svc.data_status(demo)})
    cur_p = periods[-months:]
    prev_p = periods[-2 * months:-months] if len(periods) >= 2 * months else []
    agg, agg_prev = {}, {}
    for o in obs:
        if o.value is None:
            continue
        if o.period in cur_p:
            agg[o.dim] = agg.get(o.dim, 0) + o.value
        elif o.period in prev_p:
            agg_prev[o.dim] = agg_prev.get(o.dim, 0) + o.value
    total = sum(agg.values())
    rows = [{"dim": d, "label": svc.dim_label(sd, ser, d), "value": v, "share_pct": v / total * 100 if total else None,
             "change_pct": ((v / agg_prev[d] - 1) * 100) if agg_prev.get(d) else None}
            for d, v in sorted(agg.items(), key=lambda kv: -kv[1])]
    monthly = {}
    for o in obs:
        if o.value is not None:
            monthly[o.period] = monthly.get(o.period, 0) + o.value
    return clean({"series_id": sid, "flow": flow, "by": by, "window": [cur_p[0], cur_p[-1]],
                  "previous_window": [prev_p[0], prev_p[-1]] if prev_p else None, "total": total, "rows": rows,
                  "monthly_total": [{"period": p, "value": monthly[p]} for p in periods],
                  "unit": "£", "data_status": svc.data_status(demo),
                  "note": "HMRC OTS goods trade, current prices, not seasonally adjusted. Sum over the window; "
                          "change compares with the preceding window of equal length when available."})


@router.get("/housing/transactions")
def housing_transactions(district: str, months: int = Query(6, ge=1, le=24), limit: int = Query(200, ge=1, le=500)):
    """Individual Price Paid transactions for a local authority district (on demand, cached 6 h)."""
    http = HttpClient("land_registry", cache=DbCacheStore())
    try:
        since = date.today() - timedelta(days=31 * months)
        query, rows = LandRegistryConnector(http).price_paid(district, since, limit)
    except SourceError as e:
        raise HTTPException(502 if e.kind != "validation" else 422, f"Land Registry: {e}") from e
    finally:
        http.close()
    prices = sorted(r["price"] for r in rows if r["price"])
    med = prices[len(prices) // 2] if prices else None
    return clean({"district": district.upper(), "since": since, "count": len(rows), "median_price": med,
                  "rows": rows, "sparql_endpoint": "https://landregistry.data.gov.uk/landregistry/query",
                  "query": query, "source_page_url": PPD_PAGE, "licence": SOURCES["land_registry"].licence,
                  "attribution": SOURCES["land_registry"].attribution,
                  "note": "Standard and additional price paid entries as registered; latest weeks are incomplete. "
                          "Median of returned rows only (subject to the row limit)."})


@router.get("/score")
def economic_score(weights: str | None = Query(None, description="e.g. growth:1,labour:1,prices:1,financial:1"),
                   history_from: str = "2008-01", db: Session = Depends(get_db)):
    """Economic Conditions Score: transparent composite constructed by this platform (not an official statistic).
    Recomputed from the latest retrieved real observations on every request; demo data is never used."""
    from datetime import datetime, timezone

    from ..analytics import score as SC

    w = None
    if weights:
        try:
            w = {k.strip(): float(v) for k, v in (p.split(":") for p in weights.split(",") if p)}
        except ValueError as e:
            raise HTTPException(422, "weights must look like growth:1,labour:1,prices:1,financial:1") from e
    needed = sorted({i for c in SC.COMPONENTS for i in c.inputs})
    inputs, releases = {}, {}
    for sid in needed:
        rows, demo = svc.obs_rows(db, sid, demo=False)  # real observations only, regardless of demo mode
        if rows:
            inputs[sid] = T.to_series(rows)
            ser = db.get(Series, sid)
            releases[sid] = {"title": CATALOGUE[sid].title, "last_period": rows[-1]["period"],
                             "release_date": ser.release_date if ser else None,
                             "next_release": ser.next_release if ser else None,
                             "retrieved_at": ser.last_retrieved_at if ser else None,
                             "publisher": SOURCES[CATALOGUE[sid].source_id].publisher}
    try:
        out = SC.compute(inputs, w, history_from=f"{history_from}-01" if len(history_from) == 7 else history_from)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    rel = [r["release_date"] for r in releases.values() if r["release_date"]]
    return clean({**out, "computed_at": datetime.now(timezone.utc), "inputs": releases,
                  "latest_input_release": max(rel) if rel else None, "data_status": "real",
                  "label": "Economic Conditions Score - constructed by this platform from official data; "
                           "not an official statistic"})


@router.get("/gilts/instruments")
def gilts(db: Session = Depends(get_db)):
    ser = db.get(Series, "gilts_in_issue")
    inst = (ser.source_meta or {}).get("instruments", []) if ser else []
    return clean({"instruments": inst, "as_of": ser.last_period if ser else None,
                  "request_url": ser.last_request_url if ser else None, "data_status": "real" if inst else None})
