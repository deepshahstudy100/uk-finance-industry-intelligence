"""Synthetic SAMPLE data for demo mode.

These values are generated from a seeded random walk. They are NOT real statistics, are stored with
is_demo=True, are never mixed with real observations, and every API response that contains them carries
`data_status: "demo"` so the UI can label them. They exist only so the interface can be explored when
sources are unreachable (e.g. offline development).
"""
from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta, timezone

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..connectors.base import ObsIn, SeriesBatch
from ..models import IngestionRun, Observation, Source
from ..periods import day_key, halfhour_key, month_key, quarter_key, week_key, year_key
from ..registry.catalogue import CATALOGUE, SIC_SECTIONS, SeriesDef
from ..registry.geography import ITL1_GSS, UK_CODE

DEMO_DIMS = {
    "sic_section": list(SIC_SECTIONS)[:19],
    "fuel": ["gas", "wind", "nuclear", "solar", "biomass", "imports", "hydro", "coal", "other"],
    "partner_country": ["US", "DE", "NL", "FR", "IE", "CN", "BE", "ES", "IT", "CH"],
    "sitc1": [str(i) for i in range(10)],
    "maturity_bracket": ["Conventional|Short", "Conventional|Medium", "Conventional|Long", "Index-linked|Long",
                         "All|All"],
}
BASE = {"rate": 4.0, "growth_rate": 2.0, "share": 30.0, "index": 100.0, "price": 250.0, "level": 10000.0}


def _rng(key: str) -> np.random.Generator:
    return np.random.default_rng(int(hashlib.sha256(key.encode()).hexdigest()[:8], 16))


def _periods(sd: SeriesDef, n: int):
    today = date.today()
    out = []
    if sd.frequency == "M":
        y, m = today.year, today.month
        for _ in range(n):
            m -= 1
            if m == 0:
                y, m = y - 1, 12
            out.append(month_key(y, m))
    elif sd.frequency == "Q":
        y, q = today.year, (today.month - 1) // 3 + 1
        for _ in range(n):
            q -= 1
            if q == 0:
                y, q = y - 1, 4
            out.append(quarter_key(y, q))
    elif sd.frequency == "A":
        out = [year_key(today.year - i) for i in range(1, n + 1)]
    elif sd.frequency == "W":
        monday = today - timedelta(days=today.weekday())
        out = [week_key(monday - timedelta(weeks=i)) for i in range(1, n + 1)]
    elif sd.frequency == "D":
        d, k = today, 0
        while k < n:
            d -= timedelta(days=1)
            if d.weekday() < 5:
                out.append(day_key(d))
                k += 1
    else:
        t = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        out = [halfhour_key(t - timedelta(minutes=30 * i)) for i in range(1, n + 1)]
    return list(reversed(out))


def demo_batch(sd: SeriesDef) -> SeriesBatch:
    n = {"M": 120, "Q": 48, "A": 10, "W": 104, "D": 500, "HH": 336}[sd.frequency]
    periods = _periods(sd, n)
    geos = [UK_CODE] + (ITL1_GSS if "itl1" in sd.geography else [])
    dims = DEMO_DIMS.get(sd.dim_kind or "", ["_"])
    obs = []
    base = BASE.get(sd.measure_type, 100.0)
    for g in geos:
        for d in dims:
            r = _rng(f"{sd.id}:{g}:{d}")
            scale = base * (0.6 + 0.8 * r.random())
            vol = 0.02 if sd.measure_type in ("index", "price", "level") else 0.08
            x = scale
            for key, st, en in periods:
                x = max(0.0, x * (1 + r.normal(0.001, vol))) if sd.measure_type in ("index", "price", "level") \
                    else max(0.0, x + r.normal(0, vol * base))
                obs.append(ObsIn(period=key, period_start=st, period_end=en, value=round(float(x), 3), geo=g, dim=d,
                                 flags={"demo": True}))
    return SeriesBatch(sd.id, obs, request_url=None, source_meta={})


def ensure_demo(s: Session) -> int:
    """Create demo observations once. Never touches real (is_demo=False) rows."""
    have = s.scalar(select(func.count()).select_from(Observation).where(Observation.is_demo.is_(True)))
    if have:
        return 0
    from ..ingestion.runner import now_utc, upsert_batch

    if s.get(Source, "demo") is None:
        s.add(Source(id="demo", name="Demo sample data generator", publisher="This platform (synthetic data)",
                     meta={"synthetic": True, "note": "Seeded random walk; not real statistics."}, enabled=True,
                     consecutive_failures=0))
        s.flush()
    run = IngestionRun(source_id="demo", job="demo-seed", started_at=now_utc(), status="success", errors=[],
                       requests=[], message="Synthetic SAMPLE data for demo mode (not real statistics)")
    s.add(run)
    s.flush()
    total = 0
    for sd in CATALOGUE.values():
        b = demo_batch(sd)
        upsert_batch(s, run, b, is_demo=True)
        total += len(b.observations)
    run.inserted, run.finished_at = total, now_utc()
    return total
