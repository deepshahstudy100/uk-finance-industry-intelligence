"""Series, observations, analysis, revisions, comparisons, correlation, scenario and export."""
from __future__ import annotations

import csv
import io
import json

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..analytics import findings as F
from ..analytics import stats as S
from ..analytics import transforms as T
from ..connectors.http import HttpClient, SourceError
from ..connectors.ons import OnsConnector
from ..db import get_db
from ..ingestion.cache import DbCacheStore
from ..models import ObservationRevision, Series
from ..registry.catalogue import CATALOGUE
from ..registry.geography import ITL1_GSS, UK_CODE
from .. import services as svc
from .util import clean, parse_date

router = APIRouter(prefix="/api", tags=["series"])


@router.get("/series")
def list_series(category: str | None = None, q: str | None = None, source: str | None = None,
                db: Session = Depends(get_db)):
    out = []
    for sd in CATALOGUE.values():
        if category and sd.category != category:
            continue
        if source and sd.source_id != source:
            continue
        if q and q.lower() not in (sd.title + " " + sd.definition + " " + " ".join(sd.tags)).lower():
            continue
        out.append(svc.series_summary(db, sd))
    return clean(out)


@router.get("/series/{series_id}")
def get_series(series_id: str, db: Session = Depends(get_db)):
    return clean(svc.series_detail(db, series_id))


@router.get("/series/{series_id}/observations")
def observations(series_id: str, geo: str | None = None, dim: str | None = None, start: str | None = None,
                 end: str | None = None, db: Session = Depends(get_db)):
    sd = svc.sdef(series_id)
    rows, demo = svc.obs_rows(db, series_id, geo, dim, parse_date(start), parse_date(end))
    ser = db.get(Series, series_id)
    return clean({"series_id": series_id, "title": sd.title, "decimals": sd.decimals,
                  "geo": geo or svc.default_geo(sd), "dim": dim or "_",
                  "geo_name": svc.geo_name(db, geo or svc.default_geo(sd), ser),
                  "dim_label": svc.dim_label(sd, ser, dim or "_"), "unit": sd.unit, "frequency": sd.frequency,
                  "data_status": svc.data_status(demo), "observations": rows,
                  "provenance": svc.provenance(db, sd, ser, geo)})


def _frame(db, series_id, geo, dim):
    sd = svc.sdef(series_id)
    rows, demo = svc.obs_rows(db, series_id, geo, dim)
    return sd, rows, demo, T.to_series(rows)


@router.get("/series/{series_id}/analysis")
def analysis(series_id: str, geo: str | None = None, dim: str | None = None, start: str | None = None,
             end: str | None = None, window: int | None = None, related: bool = True, db: Session = Depends(get_db)):
    sd, rows, demo, s = _frame(db, series_id, geo, dim)
    ser = db.get(Series, series_id)
    rl = T.rules(sd)
    w = window or T.default_window(sd.frequency)
    pop = T.period_on_period(s, sd) if rl["period_on_period"].allowed else pd.Series(index=s.index, dtype=float)
    yoy = T.year_on_year(s, sd) if rl["year_on_year"].allowed else pd.Series(index=s.index, dtype=float)
    roll = T.rolling_mean(s, w)
    sd_, ed_ = parse_date(start), parse_date(end)
    mask = pd.Series(True, index=s.index)
    if sd_:
        mask &= s.index >= pd.Timestamp(sd_)
    if ed_:
        mask &= s.index <= pd.Timestamp(ed_)
    in_range = s[mask]
    idx = T.rebase(in_range) if rl["index"].allowed else pd.Series(index=in_range.index, dtype=float)
    by_ts = {pd.Timestamp(r["period_start"]): r for r in rows}
    points = []
    for ts in in_range.index:
        r = by_ts.get(ts, {})
        points.append({"period": r.get("period"), "period_start": ts.date().isoformat(), "value": s.get(ts),
                       "pop": pop.get(ts), "yoy": yoy.get(ts), "rolling": roll.get(ts), "indexed": idx.get(ts),
                       "status": r.get("status"), "flags": r.get("flags")})
    ctx = S.historical_context(s)
    outl = S.outliers(sd, s)
    nrev = len(db.scalars(select(ObservationRevision.id).where(ObservationRevision.series_id == series_id)).all())
    rel_out = []
    if related and not demo:
        for rid in sd.related[:6]:
            if rid not in CATALOGUE:
                continue
            rdef = CATALOGUE[rid]
            rgeo = geo if (geo and rdef.geography != "uk" and geo != svc.default_geo(sd)) else None
            rrows, rdemo = svc.obs_rows(db, rid, rgeo)
            if rdemo or len(rrows) < 10:
                continue
            res = S.correlate(sd, s, rdef, T.to_series(rrows), max_lag=6 if sd.frequency in ("M", "Q") else 3)
            c = res["contemporaneous"]
            rel_out.append({"series_id": rid, "title": rdef.title, "pearson": c["pearson"], "n": c["n"],
                            "p_value": c["p_value"], "best_lag": res["best_lag"], "frequency": res["frequency"],
                            "basis": res["basis_description"]})
    uncertainty_vals = [{"period": r["period"], **{k: r["flags"][k] for k in ("ci95_pp", "cv_pct", "reliability")
                                                   if k in (r["flags"] or {})}}
                        for r in rows[-24:] if any(k in (r["flags"] or {}) for k in ("ci95_pp", "cv_pct"))]
    comparables = _comparables(db, sd, geo, dim)
    decomposition = S.decompose(sd, s) if rl["decomposition"].allowed else {"available": False,
                                                                             "reason": rl["decomposition"].reason}
    return clean({
        "series_id": series_id, "data_status": svc.data_status(demo), "unit": sd.unit,
        "change_unit": T.change_unit(sd), "window": w, "rules": {k: vars(v) for k, v in rl.items()},
        "method": {
            "pop": "Period-on-period " + ("difference (pp)" if T.change_unit(sd) == "pp" else "% change"),
            "yoy": "Same period one year earlier; " + ("difference (pp)" if T.change_unit(sd) == "pp" else "% change"),
            "rolling": f"Trailing mean over {w} observations (min {w // 2 + 1})",
            "indexed": "Rebased to 100 at the first observation in the selected range",
        },
        "points": points, "context": ctx, "volatility": S.volatility(sd, s),
        "missing": S.missing_report(sd, rows), "outliers": outl, "decomposition": decomposition,
        "relationships": sorted(rel_out, key=lambda x: -abs(x["pearson"] or 0)),
        "relationship_note": S.ASSOCIATION_NOTE,
        "uncertainty": {"text": sd.uncertainty, "values": uncertainty_vals},
        "comparables": comparables,
        "findings": F.build(sd, s, revisions=nrev, outliers=outl, context=ctx, correlations=rel_out),
        "notes": list(sd.notes),
        "geo_name": svc.geo_name(db, geo or svc.default_geo(sd), ser),
        "dim_label": svc.dim_label(sd, ser, dim or "_"),
    })


def _comparables(db: Session, sd, geo, dim) -> dict:
    """Latest values for comparable regions (same series) or comparable industries (same group / dims)."""
    out: dict = {}
    ser = db.get(Series, sd.id)
    demo = svc.use_demo(db, sd.id)
    if sd.geography != "uk":
        cur_geos = set(svc.geos_for(db, sd.id, demo))
        regs = []
        for g in [UK_CODE] + ITL1_GSS:
            if g not in cur_geos:
                continue
            rows, _ = svc.obs_rows(db, sd.id, g, dim, demo=demo)
            v = [r for r in rows if r["value"] is not None]
            if v:
                regs.append({"geo": g, "name": svc.geo_name(db, g, ser), "period": v[-1]["period"],
                             "value": v[-1]["value"], "flags": v[-1]["flags"]})
        out["regions"] = regs
    if sd.group == "gva_sections" or sd.dim_kind == "sic_section":
        inds = []
        if sd.group == "gva_sections":
            for other in CATALOGUE.values():
                if other.group == "gva_sections":
                    rows, _ = svc.obs_rows(db, other.id)
                    s = T.to_series(rows)
                    yy = T.year_on_year(s, other).dropna()
                    if len(yy):
                        inds.append({"series_id": other.id, "industry": other.industry, "title": other.title,
                                     "period": rows[-1]["period"], "value": rows[-1]["value"],
                                     "yoy": float(yy.iloc[-1])})
        else:
            for d in svc.dims_for(db, sd.id, demo):
                rows, _ = svc.obs_rows(db, sd.id, geo, d, demo=demo)
                v = [r for r in rows if r["value"] is not None]
                if v:
                    inds.append({"dim": d, "industry": d, "title": svc.dim_label(sd, ser, d),
                                 "period": v[-1]["period"], "value": v[-1]["value"]})
        out["industries"] = inds
    return out


@router.get("/series/{series_id}/revisions")
def revisions(series_id: str, geo: str | None = None, dim: str | None = None, db: Session = Depends(get_db)):
    sd = svc.sdef(series_id)
    q = select(ObservationRevision).where(ObservationRevision.series_id == series_id)
    if geo:
        q = q.where(ObservationRevision.geo == geo)
    if dim:
        q = q.where(ObservationRevision.dim == dim)
    rows = db.scalars(q.order_by(ObservationRevision.detected_at.desc()).limit(500)).all()
    ser = db.get(Series, series_id)
    return clean({
        "series_id": series_id,
        "detected": [{"period": r.period, "geo": r.geo, "dim": r.dim, "old_value": r.old_value,
                      "new_value": r.new_value, "revision": (r.new_value - r.old_value)
                      if r.new_value is not None and r.old_value is not None else None,
                      "old_release_date": r.old_release_date, "new_release_date": r.new_release_date,
                      "detected_at": r.detected_at, "run_id": r.run_id} for r in rows],
        "published_versions": ((ser.source_meta or {}).get("versions", []) if ser else []),
        "version_count": (ser.source_meta or {}).get("version_count") if ser else None,
        "supports_vintages": sd.source_id == "ons",
        "note": "'detected' lists changes observed between this platform's own retrievals. "
                "'published_versions' is the publisher's version history (ONS only).",
    })


@router.get("/series/{series_id}/vintages")
def vintages(series_id: str, n: int = Query(4, ge=1, le=8), periods: int = Query(12, ge=1, le=40),
             db: Session = Depends(get_db)):
    sd = svc.sdef(series_id)
    if sd.source_id != "ons":
        raise HTTPException(400, "Published vintages are available for ONS series only")
    ser = db.get(Series, series_id)
    versions = ((ser.source_meta or {}).get("versions", []) if ser else [])[-n:]
    if not versions:
        raise HTTPException(404, "No version history retrieved yet for this series")
    current, demo = svc.obs_rows(db, series_id)
    if demo:
        raise HTTPException(409, "Series has no real data; vintages unavailable")
    keep = [r["period"] for r in current if r["value"] is not None][-periods:]
    http = HttpClient("ons", cache=DbCacheStore())
    con = OnsConnector(http)
    cols, errors = [], []
    try:
        for v in versions:
            try:
                _, obs = con.fetch_vintage(v["uri"], sd.frequency)
                vals = {o.period: o.value for o in obs}
                cols.append({"label": v["label"], "updateDate": v["updateDate"],
                             "correctionNotice": v.get("correctionNotice"),
                             "url": f"https://www.ons.gov.uk{v['uri']}/data",
                             "values": {p: vals.get(p) for p in keep}})
            except SourceError as e:
                errors.append({"label": v["label"], **e.to_dict()})
    finally:
        http.close()
    cur = {r["period"]: r["value"] for r in current}
    return clean({"series_id": series_id, "periods": keep, "current": {p: cur.get(p) for p in keep},
                  "vintages": cols, "errors": errors,
                  "note": "Each column is a previously published ONS version of this series (immutable; cached)."})


@router.get("/series/{series_id}/slice")
def slice_(series_id: str, by: str = Query("geo", pattern="^(geo|dim)$"), period: str | None = None,
           geo: str | None = None, dim: str | None = None, level: str | None = None, db: Session = Depends(get_db)):
    """Cross-section at one period: across geographies (map) or across dimensions (industry/partner)."""
    from ..models import GeoArea, Observation

    sd = svc.sdef(series_id)
    demo = svc.use_demo(db, series_id)
    ser = db.get(Series, series_id)
    q = select(Observation).where(Observation.series_id == series_id, Observation.is_demo.is_(demo))
    if by == "geo":
        q = q.where(Observation.dim == (dim or "_"))
        if level == "itl1":
            q = q.where(Observation.geo.in_(ITL1_GSS))
        elif level == "lad":
            lads = [c for (c,) in db.execute(select(GeoArea.code).where(GeoArea.level == "lad"))]
            non_lad = ITL1_GSS + [UK_CODE, "E92000001", "K03000001"]
            q = q.where(Observation.geo.in_(lads) if lads else Observation.geo.notin_(non_lad))
    else:
        q = q.where(Observation.geo == (geo or svc.default_geo(sd)))
    obs = db.scalars(q).all()
    periods = sorted({o.period for o in obs if o.value is not None}, key=lambda p: p)
    if not periods:
        return clean({"series_id": series_id, "period": None, "periods": [], "rows": [],
                      "data_status": svc.data_status(demo)})
    target = period if period in periods else periods[-1]
    prev = periods[periods.index(target) - 1] if periods.index(target) > 0 else None
    cur = [o for o in obs if o.period == target]
    prev_map = {(o.geo, o.dim): o.value for o in obs if o.period == prev}
    vals = [o.value for o in cur if o.value is not None]
    total = sum(vals) if sd.measure_type == "level" else None
    rows = []
    for o in sorted(cur, key=lambda o: -(o.value or float("-inf"))):
        pv = prev_map.get((o.geo, o.dim))
        pp = sd.measure_type in T.PP_TYPES
        ch = None
        if o.value is not None and pv is not None:
            ch = (o.value - pv) if pp else ((o.value / pv - 1) * 100 if pv else None)
        rows.append({"geo": o.geo, "geo_name": svc.geo_name(db, o.geo, ser), "dim": o.dim,
                     "dim_label": svc.dim_label(sd, ser, o.dim), "value": o.value, "status": o.status,
                     "flags": o.flags, "change": ch, "share": (o.value / total * 100) if total and o.value else None})
    return clean({"series_id": series_id, "by": by, "period": target, "previous_period": prev,
                  "periods": periods[-60:], "rows": rows, "change_unit": T.change_unit(sd), "unit": sd.unit,
                  "data_status": svc.data_status(demo),
                  "share_note": "Share of the listed rows' total (only for additive level series)." if total else None})


@router.get("/series/{series_id}/scenario")
def scenario(series_id: str, mode: str = Query("trend", pattern="^(flat|trend|custom)$"), periods: int = 12,
             value: float | None = None, lookback: int = 12, geo: str | None = None, dim: str | None = None,
             db: Session = Depends(get_db)):
    sd, rows, demo, s = _frame(db, series_id, geo, dim)
    out = S.scenario(sd, s, mode=mode, periods=periods, value=value, lookback=lookback)
    return clean({**out, "data_status": svc.data_status(demo)})


@router.get("/compare")
def compare(ids: str, geo: str | None = None, start: str | None = None, end: str | None = None,
            mode: str = Query("level", pattern="^(level|indexed|yoy|pop)$"), db: Session = Depends(get_db)):
    out = []
    for sid in [i for i in ids.split(",") if i][:8]:
        sd = svc.sdef(sid)
        g = geo if (geo and sd.geography != "uk") else None
        rows, demo = svc.obs_rows(db, sid, g)
        s = T.to_series(rows)
        rl = T.rules(sd)
        note = None
        if mode == "indexed":
            if not rl["index"].allowed:
                note = rl["index"].reason
                s2 = s * float("nan")
            else:
                sub = s
                if start:
                    sub = s[s.index >= pd.Timestamp(parse_date(start))]
                s2 = T.rebase(sub)
        elif mode == "yoy":
            s2 = T.year_on_year(s, sd) if rl["year_on_year"].allowed else s * float("nan")
            note = rl["year_on_year"].caveat or rl["year_on_year"].reason or None
        elif mode == "pop":
            s2 = T.period_on_period(s, sd)
        else:
            s2 = s
        if start:
            s2 = s2[s2.index >= pd.Timestamp(parse_date(start))]
        if end:
            s2 = s2[s2.index <= pd.Timestamp(parse_date(end))]
        unit = {"indexed": "index (start = 100)", "yoy": T.change_unit(sd) + " y/y",
                "pop": T.change_unit(sd)}.get(mode, sd.unit)
        out.append({"series_id": sid, "title": sd.title, "unit": unit, "frequency": sd.frequency,
                    "data_status": svc.data_status(demo), "note": note,
                    "points": [{"period_start": t.date().isoformat(), "value": v} for t, v in s2.items()]})
    return clean({"mode": mode, "series": out})


@router.get("/correlate")
def correlate(a: str, b: str, geo_a: str | None = None, geo_b: str | None = None, dim_a: str | None = None,
              dim_b: str | None = None, basis: str = Query("changes", pattern="^(changes|levels)$"),
              max_lag: int = Query(12, ge=0, le=36), start: str | None = None, db: Session = Depends(get_db)):
    ad, arows, ademo, as_ = _frame(db, a, geo_a, dim_a)
    bd, brows, bdemo, bs = _frame(db, b, geo_b, dim_b)
    if ademo != bdemo:
        raise HTTPException(409, "Cannot correlate real data with demo sample data")
    if start:
        ts = pd.Timestamp(parse_date(start))
        as_, bs = as_[as_.index >= ts], bs[bs.index >= ts]
    res = S.correlate(ad, as_, bd, bs, max_lag=max_lag, basis=basis)
    return clean({"a": {"id": a, "title": ad.title}, "b": {"id": b, "title": bd.title},
                  "data_status": svc.data_status(ademo), **res})


EXPORT_COLS = ["series_id", "title", "geo", "geo_name", "dim", "dim_label", "period", "period_start", "period_end",
               "value", "unit", "status", "flags", "release_date", "retrieved_at", "ingestion_run_id", "data_status",
               "publisher", "source", "dataset_identifier", "request_url", "source_page_url", "licence",
               "attribution"]


@router.get("/export")
def export(series_id: str, geo: str | None = None, dim: str | None = None, start: str | None = None,
           end: str | None = None, format: str = Query("csv", pattern="^(csv|json)$"),
           include_analysis: bool = False, db: Session = Depends(get_db)):
    sd = svc.sdef(series_id)
    ser = db.get(Series, series_id)
    rows, demo = svc.obs_rows(db, series_id, geo, dim, parse_date(start), parse_date(end))
    prov = svc.provenance(db, sd, ser, geo)
    g = geo or svc.default_geo(sd)
    extra = {}
    if include_analysis:
        full, _ = svc.obs_rows(db, series_id, geo, dim)
        s = T.to_series(full)
        rl = T.rules(sd)
        pop = T.period_on_period(s, sd)
        yoy = T.year_on_year(s, sd) if rl["year_on_year"].allowed else pd.Series(dtype=float)
        extra = {pd.Timestamp(r["period_start"]): {"pop": pop.get(pd.Timestamp(r["period_start"])),
                                                   "yoy": yoy.get(pd.Timestamp(r["period_start"]))} for r in rows}
    base = {"series_id": series_id, "title": sd.title, "geo": g, "geo_name": svc.geo_name(db, g, ser),
            "dim": dim or "_", "dim_label": svc.dim_label(sd, ser, dim or "_"), "unit": sd.unit,
            "data_status": svc.data_status(demo), "publisher": prov["publisher"], "source": prov["source_name"],
            "dataset_identifier": prov["dataset_identifier"], "request_url": prov["request_url"],
            "source_page_url": prov["source_page_url"], "licence": prov["licence"],
            "attribution": prov["attribution"]}
    records = []
    for r in rows:
        rec = {**base, "period": r["period"], "period_start": r["period_start"], "period_end": r["period_end"],
               "value": r["value"], "status": r["status"], "flags": r["flags"], "release_date": r["release_date"],
               "retrieved_at": r["retrieved_at"], "ingestion_run_id": r["run_id"]}
        if include_analysis:
            e = extra.get(pd.Timestamp(r["period_start"]), {})
            rec[f"pop_{T.change_unit(sd)}"] = e.get("pop")
            rec[f"yoy_{T.change_unit(sd)}"] = e.get("yoy")
        records.append(clean(rec))
    fname = f"{series_id}_{g}_{dim or 'total'}".replace("|", "-")
    if format == "json":
        payload = {"metadata": clean({**base, "definition": sd.definition, "frequency": sd.frequency,
                                      "measure_type": sd.measure_type, "seasonal_adjustment": sd.seasonal_adjustment,
                                      "notes": list(sd.notes), "provenance": prov,
                                      "analysis_methods": {"pop": "period-on-period " + T.change_unit(sd),
                                                           "yoy": "vs same period a year earlier " + T.change_unit(sd)}
                                      if include_analysis else None,
                                      "demo_warning": "SYNTHETIC SAMPLE DATA - NOT REAL STATISTICS" if demo else None}),
                   "observations": records}
        return Response(json.dumps(payload, indent=1), media_type="application/json",
                        headers={"Content-Disposition": f'attachment; filename="{fname}.json"'})
    buf = io.StringIO()
    cols = EXPORT_COLS + ([f"pop_{T.change_unit(sd)}", f"yoy_{T.change_unit(sd)}"] if include_analysis else [])
    w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
    w.writeheader()
    for rec in records:
        w.writerow({**rec, "flags": json.dumps(rec["flags"]) if rec["flags"] else ""})
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{fname}.csv"'})
