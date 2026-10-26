"""ONS time series via the website JSON (`{uri}/data`), with CDID -> URI resolution through the
ONS search API (api.beta.ons.gov.uk/v1/search). Also exposes published vintages (`versions[]`)."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, ValidationError

from ..periods import parse_ons_date
from ..registry.catalogue import CATALOGUE, series_for_source
from .base import Connector, FetchResult, ObsIn, SeriesBatch, SourceError, to_float

WEB = "https://www.ons.gov.uk"
SEARCH = "https://api.beta.ons.gov.uk/v1/search"


class OnsObs(BaseModel):
    model_config = ConfigDict(extra="ignore")
    date: str
    value: str
    updateDate: str | None = None


class OnsDescription(BaseModel):
    model_config = ConfigDict(extra="ignore")
    title: str
    cdid: str
    datasetId: str | None = None
    unit: str | None = ""
    preUnit: str | None = ""
    releaseDate: str | None = None
    nextRelease: str | None = None
    datasetUri: str | None = None
    keyNote: str | None = None


class OnsTimeseries(BaseModel):
    model_config = ConfigDict(extra="ignore")
    description: OnsDescription
    months: list[OnsObs] = []
    quarters: list[OnsObs] = []
    years: list[OnsObs] = []
    versions: list[dict] = []
    relatedDocuments: list[dict] = []
    uri: str
    type: str


FREQ_FIELD = {"M": "months", "Q": "quarters", "A": "years"}


def _dt(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def parse_timeseries(payload: dict, frequency: str) -> tuple[OnsTimeseries, list[ObsIn]]:
    try:
        ts = OnsTimeseries.model_validate(payload)
    except ValidationError as e:
        raise SourceError(f"ONS payload failed schema validation: {e.errors()[:3]}", kind="validation") from e
    if ts.type != "timeseries":
        raise SourceError(f"Unexpected ONS content type {ts.type!r}", kind="validation")
    rows = getattr(ts, FREQ_FIELD[frequency])
    if not rows:
        raise SourceError(f"ONS series {ts.description.cdid} has no {FREQ_FIELD[frequency]} observations",
                          kind="validation")
    out: list[ObsIn] = []
    for r in rows:
        key, start, end, f = parse_ons_date(r.date)
        if f != frequency:
            raise SourceError(f"ONS date {r.date!r} does not match frequency {frequency}", kind="validation")
        v = to_float(r.value)
        out.append(ObsIn(period=key, period_start=start, period_end=end, value=v,
                         status="normal" if v is not None else "missing", release_date=_dt(r.updateDate)))
    return ts, out


class OnsConnector(Connector):
    source_id = "ons"

    def resolve_uri(self, cdid: str, dataset: str, hint: str | None) -> str:
        """Resolve a CDID+dataset to its website URI through the official search API."""
        r = self.http.get(SEARCH, params={"q": cdid, "content_type": "timeseries", "limit": 20}, cache_ttl_s=86400 * 7)
        items = [i for i in r.json().get("items", []) if i.get("cdid", "").upper() == cdid.upper()]
        exact = [i for i in items if i.get("dataset_id", "").upper() == dataset.upper()]
        if exact:
            return exact[0]["uri"]
        if hint:
            return hint
        if items:
            return items[0]["uri"]
        raise SourceError(f"CDID {cdid} not found via ONS search", kind="not_found")

    def fetch_one(self, series_id: str) -> SeriesBatch:
        sd = CATALOGUE[series_id]
        p = sd.params
        uri = p.get("uri")
        try:
            r = self.http.get(f"{WEB}{uri}/data")
        except SourceError as e:
            if e.kind != "not_found":
                raise
            uri = self.resolve_uri(p["cdid"], p["dataset"], None)
            r = self.http.get(f"{WEB}{uri}/data")
        try:
            payload = r.json()
        except ValueError as e:
            raise SourceError("ONS returned non-JSON content", kind="validation", url=r.url) from e
        ts, obs = parse_timeseries(payload, sd.frequency)
        if ts.description.cdid.upper() != p["cdid"].upper():
            raise SourceError(f"Asked for {p['cdid']} but ONS returned {ts.description.cdid}", kind="validation")
        unit = ((ts.description.preUnit or "") + (ts.description.unit or "")).strip()
        return SeriesBatch(
            series_id=series_id,
            observations=obs,
            request_url=r.url,
            source_title=ts.description.title,
            release_date=_dt(ts.description.releaseDate),
            next_release=ts.description.nextRelease,
            source_meta={
                "uri": ts.uri,
                "page_url": f"{WEB}{ts.uri}",
                "dataset_id": ts.description.datasetId,
                "dataset_url": f"{WEB}{ts.description.datasetUri}" if ts.description.datasetUri else None,
                "source_unit": unit,
                "key_note": (ts.description.keyNote or "").strip() or None,
                "bulletins": [f"{WEB}{d['uri']}" for d in ts.relatedDocuments if d.get("uri")][:3],
                "versions": [
                    {"label": v.get("label"), "updateDate": v.get("updateDate"),
                     "correctionNotice": v.get("correctionNotice") or None, "uri": v.get("uri")}
                    for v in ts.versions[-24:]
                ],
                "version_count": len(ts.versions),
            },
        )

    def fetch(self, series_ids: list[str] | None = None) -> FetchResult:
        res = FetchResult()
        ids = series_ids or [s.id for s in series_for_source("ons") if s.enabled]
        for sid in ids:
            try:
                res.batches.append(self.fetch_one(sid))
            except SourceError as e:
                res.errors.append({"series_id": sid, **e.to_dict()})
        return res

    def fetch_vintage(self, version_uri: str, frequency: str) -> tuple[OnsTimeseries, list[ObsIn]]:
        """A previously published version (e.g. .../previous/v130). Cached for 30 days: vintages are immutable."""
        r = self.http.get(f"{WEB}{version_uri}/data", cache_ttl_s=86400 * 30)
        return parse_timeseries(r.json(), frequency)
