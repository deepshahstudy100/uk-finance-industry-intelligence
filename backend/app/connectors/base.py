from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

from .http import HttpClient, SourceError


@dataclass
class ObsIn:
    period: str
    period_start: date
    period_end: date
    value: float | None
    geo: str = "K02000001"
    dim: str = "_"
    status: str = "normal"  # normal | provisional | estimate | forecast | suppressed | missing
    flags: dict = field(default_factory=dict)
    release_date: datetime | None = None


@dataclass
class SeriesBatch:
    series_id: str
    observations: list[ObsIn]
    request_url: str | None = None
    source_title: str | None = None
    release_date: datetime | None = None
    next_release: str | None = None
    source_meta: dict = field(default_factory=dict)
    # If True, observations for (series, geo, dim) combinations in this batch fully replace stored ones
    # only for the periods returned; we never delete history that the source stopped returning.


@dataclass
class FetchResult:
    batches: list[SeriesBatch] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)  # per-series failures (partial success)
    extra: dict = field(default_factory=dict)  # e.g. lookups, boundaries


class Connector:
    source_id: str = ""

    def __init__(self, http: HttpClient):
        self.http = http

    def fetch(self, series_ids: list[str] | None = None) -> FetchResult:  # pragma: no cover - interface
        raise NotImplementedError


def to_float(v) -> float | None:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(",", "")
    if s in ("", "..", ":", "-", "x", "*", "c", "NA", "N/A", "null"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


__all__ = ["ObsIn", "SeriesBatch", "FetchResult", "Connector", "SourceError", "to_float"]
