"""Query helpers shared by the API. The demo policy is enforced here, in one place."""
from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .analytics.transforms import rules
from .config import get_settings
from .ingestion.health import series_status, source_status
from .models import IngestionRun, Observation, ObservationRevision, Series, Source
from .registry.catalogue import CATALOGUE, SIC_SECTIONS, SeriesDef
from .registry.geography import NAMES, UK_CODE
from .registry.sources import SOURCES

GB_SERIES_DEFAULT = "K03000001"


def sdef(series_id: str) -> SeriesDef:
    sd = CATALOGUE.get(series_id)
    if not sd:
        raise HTTPException(404, f"Unknown series {series_id!r}")
    return sd


def default_geo(sd: SeriesDef) -> str:
    return GB_SERIES_DEFAULT if sd.geography == "gb" else UK_CODE


def has_real(s: Session, series_id: str) -> bool:
    return s.scalar(select(Observation.id).where(Observation.series_id == series_id,
                                                 Observation.is_demo.is_(False)).limit(1)) is not None


def has_demo(s: Session, series_id: str) -> bool:
    return s.scalar(select(Observation.id).where(Observation.series_id == series_id,
                                                 Observation.is_demo.is_(True)).limit(1)) is not None


def use_demo(s: Session, series_id: str) -> bool:
    """Demo rows are used only if demo_mode=only, or demo_mode=fallback AND the series has no real data at all.
    Real and demo data are never combined in one response."""
    mode = get_settings().demo_mode
    if mode == "only":
        return True
    if mode == "off":
        return False
    return not has_real(s, series_id)


def data_status(demo: bool) -> str:
    return "demo" if demo else "real"


def obs_rows(s: Session, series_id: str, geo: str | None = None, dim: str | None = None,
             start: date | None = None, end: date | None = None, *, demo: bool | None = None) -> tuple[list[dict], bool]:
    sd = sdef(series_id)
    demo = use_demo(s, series_id) if demo is None else demo
    q = select(Observation).where(Observation.series_id == series_id, Observation.is_demo.is_(demo),
                                  Observation.geo == (geo or default_geo(sd)), Observation.dim == (dim or "_"))
    if start:
        q = q.where(Observation.period_end >= start)
    if end:
        q = q.where(Observation.period_start <= end)
    q = q.order_by(Observation.period_start)
    rows = [obs_dict(o) for o in s.scalars(q)]
    return rows, demo


def obs_dict(o: Observation) -> dict:
    return {"period": o.period, "period_start": o.period_start, "period_end": o.period_end, "value": o.value,
            "status": o.status, "flags": o.flags or {}, "geo": o.geo, "dim": o.dim,
            "release_date": o.release_date, "retrieved_at": o.retrieved_at, "run_id": o.run_id,
            "is_demo": o.is_demo}


def dims_for(s: Session, series_id: str, demo: bool) -> list[str]:
    return [d for (d,) in s.execute(select(Observation.dim).where(
        Observation.series_id == series_id, Observation.is_demo.is_(demo)).distinct())]


def geos_for(s: Session, series_id: str, demo: bool) -> list[str]:
    return [g for (g,) in s.execute(select(Observation.geo).where(
        Observation.series_id == series_id, Observation.is_demo.is_(demo)).distinct())]


def dim_label(sd: SeriesDef, ser: Series | None, dim: str) -> str:
    if dim == "_":
        return "Total"
    if sd.dim_kind == "sic_section":
        return f"{dim}: {SIC_SECTIONS.get(dim, dim)}"
    labels = (ser.source_meta or {}).get("dim_labels", {}) if ser else {}
    return labels.get(dim, dim)


def geo_name(s: Session, code: str, ser: Series | None = None) -> str:
    if code in NAMES:
        return NAMES[code]
    names = (ser.source_meta or {}).get("geo_names", {}) if ser else {}
    if code in names:
        return names[code]
    from .models import GeoArea

    g = s.get(GeoArea, code)
    return g.name if g else code


def status_for(s: Session, sd: SeriesDef, ser: Series | None, src_row: Source | None) -> dict:
    last = s.scalars(select(Observation).where(Observation.series_id == sd.id, Observation.is_demo.is_(False),
                                               Observation.geo == default_geo(sd), Observation.value.is_not(None))
                     .order_by(Observation.period_start.desc()).limit(1)).first()
    if last is None:  # geography-only or dim-only series: any combination
        last = s.scalars(select(Observation).where(Observation.series_id == sd.id, Observation.is_demo.is_(False))
                         .order_by(Observation.period_start.desc()).limit(1)).first()
    real = last is not None
    return series_status(
        sd, SOURCES[sd.source_id],
        last_success_at=src_row.last_success_at if src_row else None,
        release_date=ser.release_date if ser else None, next_release=ser.next_release if ser else None,
        last_period_end=last.period_end if last else None, last_status=last.status if last else None,
        has_real=real, has_demo=has_demo(s, sd.id) if not real else False,
        source_enabled=(src_row.enabled if src_row else True) and (
            sd.enabled or (sd.source_key.startswith("XUDL") and get_settings().enable_boe_fx)),
    )


def provenance(s: Session, sd: SeriesDef, ser: Series | None, geo: str | None = None) -> dict:
    src = SOURCES[sd.source_id]
    meta = dict((ser.source_meta or {}) if ser else {})
    if sd.source_id == "land_registry" and geo:
        from .connectors.land_registry import HPI_PAGE
        from .registry.geography import LR_SLUG_TO_GSS

        slug = {v: k for k, v in LR_SLUG_TO_GSS.items()}.get(geo)
        if slug:
            meta["page_url"] = HPI_PAGE.format(slug=slug)
    last_run = s.scalars(select(IngestionRun).where(IngestionRun.source_id == sd.source_id,
                                                    IngestionRun.status.in_(["success", "partial"]))
                         .order_by(IngestionRun.id.desc()).limit(1)).first()
    return {
        "source_id": src.id, "source_name": src.name, "publisher": src.publisher,
        "dataset_identifier": sd.source_key, "source_title": ser.source_title if ser else None,
        "request_url": ser.last_request_url if ser else None,
        "source_page_url": meta.get("page_url") or src.homepage,
        "dataset_url": meta.get("dataset_url") or meta.get("definition_url"),
        "bulletins": meta.get("bulletins", []), "docs_url": src.docs_url,
        "licence": src.licence, "licence_url": src.licence_url, "attribution": src.attribution,
        "release_date": ser.release_date if ser else None, "next_release": ser.next_release if ser else None,
        "last_retrieved_at": ser.last_retrieved_at if ser else None,
        "last_run_id": last_run.id if last_run else None,
        "latency_class": src.latency_class, "update_frequency": src.update_frequency,
        "derived_from": list(sd.derived_from), "formula": sd.formula,
        "modification_notice": meta.get("modification_notice"),
        "source_unit": meta.get("source_unit"), "key_note": meta.get("key_note"),
        "caveats": src.caveats,
    }


def series_summary(s: Session, sd: SeriesDef, *, with_latest: bool = True) -> dict:
    ser = s.get(Series, sd.id)
    src_row = s.get(Source, sd.source_id)
    st = status_for(s, sd, ser, src_row)
    out = {"id": sd.id, "title": sd.title, "category": sd.category, "unit": sd.unit, "frequency": sd.frequency,
           "measure_type": sd.measure_type, "source_id": sd.source_id, "geography": sd.geography,
           "dim_kind": sd.dim_kind, "industry": sd.industry, "group": sd.group, "status": st["status"],
           "status_reasons": st["reasons"], "decimals": sd.decimals, "enabled": sd.enabled}
    if with_latest and st["status"] != "disabled":
        rows, demo = obs_rows(s, sd.id)
        vals = [r for r in rows if r["value"] is not None]
        if not vals and sd.dim_kind:
            # Use the total/All dimension where one exists
            for d in ("All|All", "_"):
                rows, demo = obs_rows(s, sd.id, dim=d)
                vals = [r for r in rows if r["value"] is not None]
                if vals:
                    break
        out["data_status"] = data_status(demo) if vals else None
        if vals:
            last = vals[-1]
            prev = vals[-2] if len(vals) > 1 else None
            out["latest"] = {"period": last["period"], "value": last["value"], "status": last["status"],
                             "release_date": last["release_date"], "retrieved_at": last["retrieved_at"]}
            if prev:
                pp = sd.measure_type in ("rate", "growth_rate", "share")
                out["change"] = {"vs_period": prev["period"], "unit": "pp" if pp else "%",
                                 "value": (last["value"] - prev["value"]) if pp else (
                                     (last["value"] / prev["value"] - 1) * 100 if prev["value"] else None)}
            out["spark"] = [r["value"] for r in vals[-40:]]
    return out


def series_detail(s: Session, series_id: str) -> dict:
    sd = sdef(series_id)
    ser = s.get(Series, sd.id)
    src_row = s.get(Source, sd.source_id)
    demo = use_demo(s, sd.id)
    st = status_for(s, sd, ser, src_row)
    nrev = s.scalar(select(func.count()).select_from(ObservationRevision).where(
        ObservationRevision.series_id == sd.id)) or 0
    geos = geos_for(s, sd.id, demo)
    dims = dims_for(s, sd.id, demo)
    return {
        "identity": {**sd.to_dict(), "industry_name": SIC_SECTIONS.get(sd.industry or "", None),
                     "industry_classification": "SIC 2007" if (sd.industry or sd.dim_kind == "sic_section") else None},
        "provenance": provenance(s, sd, ser),
        "status": st,
        "data_status": data_status(demo),
        "rules": {k: vars(v) for k, v in rules(sd).items()},
        "geographies": [{"code": g, "name": geo_name(s, g, ser)} for g in sorted(geos)],
        "dims": [{"code": d, "label": dim_label(sd, ser, d)} for d in sorted(dims)],
        "default_geo": default_geo(sd),
        "default_dim": "All|All" if "All|All" in dims else ("_" if "_" in dims or not dims else sorted(dims)[0]),
        "revision_count": nrev,
        "related": [series_summary(s, CATALOGUE[r], with_latest=True) for r in sd.related if r in CATALOGUE],
        "versions": ((ser.source_meta or {}).get("versions", []) if ser else [])[-12:],
        "version_count": (ser.source_meta or {}).get("version_count") if ser else None,
    }


def source_rows(s: Session) -> list[dict]:
    out = []
    for sd in SOURCES.values():
        row = s.get(Source, sd.id)
        st = source_status(sd, enabled=row.enabled if row else sd.enabled_by_default,
                           last_success_at=row.last_success_at if row else None,
                           last_attempt_at=row.last_attempt_at if row else None,
                           consecutive_failures=row.consecutive_failures if row else 0)
        if sd.id == "companies_house":
            st = {"status": "on_demand" if get_settings().companies_house_api_key else "not_configured",
                  "reasons": [row.disabled_reason] if row and row.disabled_reason else ["Queried on demand."]}
        last_run = s.scalars(select(IngestionRun).where(IngestionRun.source_id == sd.id)
                             .order_by(IngestionRun.id.desc()).limit(1)).first()
        n_obs = s.scalar(select(func.count()).select_from(Observation).join(Series, Series.id == Observation.series_id)
                         .where(Series.source_id == sd.id, Observation.is_demo.is_(False))) or 0
        out.append({**sd.to_dict(), "status": st["status"], "status_reasons": st["reasons"],
                    "last_success_at": row.last_success_at if row else None,
                    "last_attempt_at": row.last_attempt_at if row else None,
                    "last_error": row.last_error if row else None,
                    "consecutive_failures": row.consecutive_failures if row else 0,
                    "observations": n_obs, "series": [x.id for x in CATALOGUE.values() if x.source_id == sd.id],
                    "last_run": run_dict(last_run, brief=True) if last_run else None})
    return out


def run_dict(r: IngestionRun, brief: bool = False) -> dict:
    d = {"id": r.id, "source_id": r.source_id, "job": r.job, "started_at": r.started_at, "finished_at": r.finished_at,
         "status": r.status, "fetched": r.fetched, "inserted": r.inserted, "updated": r.updated,
         "revised": r.revised, "unchanged": r.unchanged, "message": r.message, "errors": r.errors,
         "request_count": len(r.requests or [])}
    if not brief:
        d["requests"] = r.requests
    return d


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
