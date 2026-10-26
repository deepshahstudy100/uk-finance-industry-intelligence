"""ECB euro foreign exchange reference rates, plus transparently derived sterling crosses."""
from __future__ import annotations

import csv
import io
from datetime import date

from ..periods import day_key
from ..registry.catalogue import CATALOGUE, series_for_source
from .base import Connector, FetchResult, ObsIn, SeriesBatch, SourceError, to_float

API = "https://data-api.ecb.europa.eu/service/data/EXR/{key}"
PAGE = "https://data.ecb.europa.eu/data/datasets/EXR/EXR.{key}"


def parse_ecb_csv(text: str) -> dict[str, list[tuple[date, float]]]:
    reader = csv.DictReader(io.StringIO(text))
    need = {"KEY", "TIME_PERIOD", "OBS_VALUE"}
    if not reader.fieldnames or not need.issubset(reader.fieldnames):
        raise SourceError(f"Unexpected ECB CSV header {reader.fieldnames}", kind="validation")
    out: dict[str, list] = {}
    for row in reader:
        v = to_float(row["OBS_VALUE"])
        if v is None:
            continue
        key = row["KEY"].removeprefix("EXR.")
        out.setdefault(key, []).append((date.fromisoformat(row["TIME_PERIOD"]), v))
    return out


def derive(sd_id: str, base: dict[str, dict[str, float]]) -> list[ObsIn]:
    """Apply the catalogue formula. Only dates present in every input are emitted (no interpolation)."""
    if sd_id == "fx_gbp_eur":
        g = base["ecb_gbp_per_eur"]
        return [_o(p, 1.0 / v, sd_id) for p, v in sorted(g.items()) if v]
    num_id = {"fx_gbp_usd": "ecb_usd_per_eur", "fx_gbp_jpy": "ecb_jpy_per_eur"}[sd_id]
    num, den = base[num_id], base["ecb_gbp_per_eur"]
    return [_o(p, num[p] / den[p], sd_id) for p in sorted(set(num) & set(den)) if den[p]]


def _o(p: str, v: float, sd_id: str) -> ObsIn:
    d = date.fromisoformat(p)
    key, st, en = day_key(d)
    return ObsIn(period=key, period_start=st, period_end=en, value=v,
                 flags={"derived": True, "formula": CATALOGUE[sd_id].formula})


class EcbConnector(Connector):
    source_id = "ecb"

    def fetch(self, series_ids: list[str] | None = None) -> FetchResult:
        res = FetchResult()
        published = [s for s in series_for_source("ecb") if s.source_key != "derived"]
        currencies = "+".join(s.source_key.split(".")[1] for s in published)
        key = f"D.{currencies}.EUR.SP00.A"
        try:
            r = self.http.get(API.format(key=key), params={"startPeriod": "2000-01-01", "format": "csvdata"})
            data = parse_ecb_csv(r.text())
        except SourceError as e:
            for s in series_for_source("ecb"):
                res.errors.append({"series_id": s.id, **e.to_dict()})
            return res
        base: dict[str, dict[str, float]] = {}
        for s in published:
            rows = data.get(s.source_key, [])
            if not rows:
                res.errors.append({"series_id": s.id, "kind": "validation", "message": "No rows for key"})
                continue
            base[s.id] = {d.isoformat(): v for d, v in rows}
            obs = [ObsIn(*day_key(d), value=v) for d, v in rows]
            res.batches.append(SeriesBatch(s.id, obs, request_url=r.url,
                                           source_meta={"page_url": PAGE.format(key=s.source_key)}))
        for s in series_for_source("ecb"):
            if s.source_key != "derived":
                continue
            if not all(d in base for d in s.derived_from):
                res.errors.append({"series_id": s.id, "kind": "validation", "message": "Inputs unavailable"})
                continue
            res.batches.append(SeriesBatch(s.id, derive(s.id, base), request_url=r.url, source_meta={
                "derived_from": list(s.derived_from), "formula": s.formula,
                "page_url": PAGE.format(key=CATALOGUE[s.derived_from[0]].source_key),
                "modification_notice": "Derived by this platform from ECB reference rates (ECB reuse terms "
                                       "require modifications to be stated).",
            }))
        if series_ids:
            res.batches = [b for b in res.batches if b.series_id in series_ids]
        return res
