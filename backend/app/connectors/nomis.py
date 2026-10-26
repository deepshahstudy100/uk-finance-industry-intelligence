"""NOMIS API (CSV). Each request is sized to stay under the 25,000-cell guest limit."""
from __future__ import annotations

import csv
import io
import re

from ..config import get_settings
from ..periods import month_key, parse_month_name, parse_rolling_window, year_key
from ..registry.catalogue import CATALOGUE, series_for_source
from ..registry.geography import NAMES
from .base import Connector, FetchResult, ObsIn, SeriesBatch, SourceError, to_float

API = "https://www.nomisweb.co.uk/api/v01/dataset/{ds}.data.csv"
DEF = "https://www.nomisweb.co.uk/api/v01/dataset/{ds}.def.sdmx.json"  # dataset definition (verified)
SECTIONS = "150994945...150994965"  # SIC 2007 sections A..U (verified 2026-10-26)
NATIONS_REGIONS = "TYPE499,TYPE480"
LADS = "TYPE424"
KNOWN = set(NAMES)


def parse_nomis_csv(text: str, required: set[str]) -> list[dict]:
    if text.lstrip().startswith("<"):
        raise SourceError("NOMIS returned HTML/XML instead of CSV", kind="validation")
    reader = csv.DictReader(io.StringIO(text))
    cols = set(reader.fieldnames or [])
    if not required.issubset(cols):
        raise SourceError(f"NOMIS CSV missing columns {sorted(required - cols)}", kind="validation")
    return list(reader)


def status_from(name: str | None) -> tuple[str, dict]:
    n = (name or "").lower()
    if not n or "normal" in n:
        return "normal", {}
    if "provisional" in n:
        return "provisional", {"obs_status": name}
    if "unavailable" in n or "disclos" in n or "suppress" in n or "missing" in n:
        return "suppressed", {"obs_status": name}
    if "reliable" in n:
        return "normal", {"obs_status": name, "reliability": "low"}
    return "normal", {"obs_status": name}


def period_from(date_name: str, date_code: str | None, freq: str):
    s = date_name.strip()
    if "-" in s and re.search(r"[A-Za-z]{3} \d{4}-[A-Za-z]{3} \d{4}", s):
        return parse_rolling_window(s)
    if freq == "A" and re.fullmatch(r"\d{4}", s):
        return year_key(int(s))
    if freq == "M":
        return parse_month_name(s)
    if freq == "Q":  # e.g. 'June 2026' (workforce jobs: quarter ending month)
        key, st, en = parse_month_name(s)
        q = (en.month - 1) // 3 + 1
        return f"{en.year}-Q{q}", month_key(en.year, 3 * (q - 1) + 1)[1], en
    if re.fullmatch(r"\d{4}", s):
        return year_key(int(s))
    raise SourceError(f"Unrecognised NOMIS date {date_name!r}", kind="validation")


class NomisConnector(Connector):
    source_id = "nomis"

    def _get(self, ds: str, params: dict) -> tuple[str, list[dict]]:
        uid = get_settings().nomis_uid
        p = dict(params)
        if uid:
            p["uid"] = uid
        r = self.http.get(API.format(ds=ds), params=p)
        # Do not leak the uid into provenance links.
        url = re.sub(r"([?&])uid=[^&]+&?", r"\1", r.url).rstrip("&?")
        return url, parse_nomis_csv(r.text(), {"DATE_NAME", "GEOGRAPHY_CODE", "OBS_VALUE"})

    def _plan(self, sid: str) -> list[tuple[str, dict]]:
        """(dataset, params) requests for a series; regions with long history, LAs with recent history."""
        sd = CATALOGUE[sid]
        ds = sd.params["dataset"]
        base_sel = "date_name,date_code,geography_code,geography_name,obs_value,obs_status_name"
        if ds == "NM_17_5":
            common = {"variable": sd.params["variable"], "measures": "20599,21003",
                      "select": base_sel + ",measures_name"}
            return [(ds, {**common, "geography": NATIONS_REGIONS, "date": "latestMINUS39-latest"}),
                    (ds, {**common, "geography": LADS, "date": "latestMINUS3-latest"})]
        if ds == "NM_162_1":
            common = {"gender": 0, "age": 0, "measure": sd.params["measure"], "measures": 20100, "select": base_sel}
            return [(ds, {**common, "geography": NATIONS_REGIONS, "date": "latestMINUS119-latest"}),
                    (ds, {**common, "geography": LADS, "date": "latestMINUS23-latest"})]
        if ds == "NM_30_1":
            common = {"sex": 8, "item": 2, "pay": 1, "measures": "20100,20701", "select": base_sel + ",measures_name"}
            return [(ds, {**common, "geography": NATIONS_REGIONS, "date": "latestMINUS10-latest"}),
                    (ds, {**common, "geography": LADS, "date": "latestMINUS10-latest"})]
        if ds == "NM_142_1":
            common = {"industry": SECTIONS, "employment_sizeband": 0, "legal_status": 0, "measures": 20100,
                      "select": base_sel + ",industry_code"}
            return [(ds, {**common, "geography": NATIONS_REGIONS, "date": "latestMINUS4-latest"}),
                    (ds, {**common, "geography": LADS, "date": "latestMINUS1-latest"})]
        if ds == "NM_130_1":
            return [(ds, {"industry": SECTIONS, "item": 1, "measures": 20100, "geography": NATIONS_REGIONS,
                          "date": "latestMINUS39-latest", "select": base_sel + ",industry_code"})]
        raise SourceError(f"No NOMIS plan for {sid}", kind="validation")

    def fetch_one(self, sid: str) -> SeriesBatch:
        sd = CATALOGUE[sid]
        merged: dict[tuple, ObsIn] = {}
        urls = []
        geo_names: dict[str, str] = {}
        for ds, params in self._plan(sid):
            url, rows = self._get(ds, params)
            urls.append(url)
            uncertainty: dict[tuple, float] = {}
            is_lad = params["geography"] == LADS
            for row in rows:
                geo = row["GEOGRAPHY_CODE"]
                if not (geo in KNOWN or (is_lad and re.fullmatch(r"[ENSW]\d{8}", geo))):
                    continue  # skip aggregates we do not map, e.g. 'England and Wales'
                geo_names[geo] = row.get("GEOGRAPHY_NAME", geo)
                key, st, en = period_from(row["DATE_NAME"], row.get("DATE_CODE"), sd.frequency)
                dim = row.get("INDUSTRY_CODE") or "_"
                mname = (row.get("MEASURES_NAME") or "Value").lower()
                v = to_float(row["OBS_VALUE"])
                k = (geo, dim, key)
                if mname in ("confidence",):
                    if v is not None:
                        uncertainty[k] = v
                    continue
                status, flags = status_from(row.get("OBS_STATUS_NAME"))
                if v is None and status == "normal":
                    status = "missing"
                merged[k] = ObsIn(period=key, period_start=st, period_end=en, value=v, geo=geo, dim=dim,
                                  status=status, flags=flags)
            for k, u in uncertainty.items():
                if k in merged:
                    if ds == "NM_30_1":
                        merged[k].flags["cv_pct"] = u
                        if u > 20:
                            merged[k].flags["reliability"] = "unreliable (CV > 20%)"
                    else:
                        merged[k].flags["ci95_pp"] = u
        if not merged:
            raise SourceError("NOMIS returned no usable rows", kind="validation")
        ds = sd.params["dataset"]
        return SeriesBatch(sid, list(merged.values()), request_url=urls[0], source_meta={
            "request_urls": urls, "dataset": ds, "page_url": urls[0], "definition_url": DEF.format(ds=ds),
            "geo_names": geo_names,
        })

    def fetch(self, series_ids: list[str] | None = None) -> FetchResult:
        res = FetchResult()
        for s in series_for_source("nomis"):
            if series_ids and s.id not in series_ids:
                continue
            try:
                res.batches.append(self.fetch_one(s.id))
            except SourceError as e:
                res.errors.append({"series_id": s.id, **e.to_dict()})
        return res
