"""Periodic health sweep: raises stale/delayed alerts and resolves them when the condition clears."""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..models import Series, Source
from ..registry.catalogue import CATALOGUE
from .. import services as svc
from .runner import _alert, resolve_alerts


def health_sweep(s: Session) -> dict:
    counts = {"stale": 0, "delayed": 0}
    for sd in CATALOGUE.values():
        if not sd.enabled:
            continue
        st = svc.status_for(s, sd, s.get(Series, sd.id), s.get(Source, sd.source_id))
        for kind in ("stale", "delayed"):
            fp = f"{kind}:{sd.id}"
            if st["status"] == kind:
                counts[kind] += 1
                _alert(s, fp, kind=kind, severity="warning", series_id=sd.id, source_id=sd.source_id,
                       title=f"{'Stale' if kind == 'stale' else 'Delayed'}: {sd.title}",
                       detail=" ".join(st["reasons"]), payload=st)
            else:
                resolve_alerts(s, fp)
    return counts
