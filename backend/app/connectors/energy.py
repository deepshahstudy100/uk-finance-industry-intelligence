"""Energy: NESO Carbon Intensity API (half-hourly) and DESNZ weekly road fuel prices."""
from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta, timezone

from ..periods import halfhour_key, week_key
from ..registry.catalogue import series_for_source
from .base import Connector, FetchResult, ObsIn, SeriesBatch, SourceError, to_float

CI = "https://api.carbonintensity.org.uk"
GOVUK = "https://www.gov.uk/api/content/government/statistics/weekly-road-fuel-prices"
FUEL_PAGE = "https://www.gov.uk/government/statistics/weekly-road-fuel-prices"
GB = "K03000001"


def _hh(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc)


def parse_intensity(js: dict) -> list[ObsIn]:
    if "data" not in js or not isinstance(js["data"], list):
        raise SourceError("Carbon Intensity payload missing data[]", kind="validation")
    out = []
    for row in js["data"]:
        it = row.get("intensity") or {}
        actual, forecast = it.get("actual"), it.get("forecast")
        v = actual if actual is not None else forecast
        key, st, en = halfhour_key(_hh(row["from"]))
        out.append(ObsIn(period=key, period_start=st, period_end=en, value=to_float(v), geo=GB,
                         status="normal" if actual is not None else "forecast",
                         flags={"forecast": forecast, "actual": actual, "index": it.get("index"),
                                "to": row.get("to")}))
    return out


def parse_generation(js: dict) -> list[ObsIn]:
    if "data" not in js:
        raise SourceError("Generation payload missing data", kind="validation")
    rows = js["data"] if isinstance(js["data"], list) else [js["data"]]
    out = []
    for row in rows:
        key, st, en = halfhour_key(_hh(row["from"]))
        for g in row.get("generationmix", []):
            out.append(ObsIn(period=key, period_start=st, period_end=en, value=to_float(g.get("perc")), geo=GB,
                             dim=g["fuel"]))
    return out


class CarbonConnector(Connector):
    source_id = "neso_carbon"

    def fetch(self, series_ids: list[str] | None = None) -> FetchResult:
        res = FetchResult()
        now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        frm = (now - timedelta(days=7)).strftime("%Y-%m-%dT%H:%MZ")
        to = now.strftime("%Y-%m-%dT%H:%MZ")
        for sid, path, parser in (("carbon_intensity", "intensity", parse_intensity),
                                  ("generation_mix", "generation", parse_generation)):
            if series_ids and sid not in series_ids:
                continue
            try:
                r = self.http.get(f"{CI}/{path}/{frm}/{to}")
                obs = parser(r.json())
            except (SourceError, ValueError, KeyError) as e:
                err = e.to_dict() if isinstance(e, SourceError) else {"kind": "validation", "message": str(e)}
                res.errors.append({"series_id": sid, **err})
                continue
            res.batches.append(SeriesBatch(sid, obs, request_url=r.url, source_meta={
                "page_url": "https://carbonintensity.org.uk/", "docs": "https://carbon-intensity.github.io/api-definitions/"}))
        return res


def parse_fuel_csv(text: str) -> dict[str, list[ObsIn]]:
    reader = csv.reader(io.StringIO(text))
    header = next(reader, None) or []
    hdr = [h.strip() for h in header]
    try:
        i_date = hdr.index("Date")
        i_p = next(i for i, h in enumerate(hdr) if h.startswith("ULSP") and "Pump price" in h)
        i_d = next(i for i, h in enumerate(hdr) if h.startswith("ULSD") and "Pump price" in h)
    except (ValueError, StopIteration) as e:
        raise SourceError(f"Fuel CSV header not recognised: {hdr[:4]}", kind="validation") from e
    duty_p = next((i for i, h in enumerate(hdr) if h.startswith("ULSP") and "Duty" in h), None)
    duty_d = next((i for i, h in enumerate(hdr) if h.startswith("ULSD") and "Duty" in h), None)
    out = {"ULSP": [], "ULSD": []}
    for row in reader:
        if len(row) <= max(i_p, i_d) or not row[i_date].strip():
            continue
        d = datetime.strptime(row[i_date].strip(), "%d/%m/%Y").date()
        key, st, en = week_key(d)
        for code, idx, didx in (("ULSP", i_p, duty_p), ("ULSD", i_d, duty_d)):
            flags = {"duty_ppl": to_float(row[didx])} if didx is not None and didx < len(row) else {}
            out[code].append(ObsIn(period=key, period_start=st, period_end=en, value=to_float(row[idx]),
                                   flags=flags))
    return out


class FuelConnector(Connector):
    source_id = "desnz_fuel"

    def fetch(self, series_ids: list[str] | None = None) -> FetchResult:
        res = FetchResult()
        defs = [s for s in series_for_source("desnz_fuel") if not series_ids or s.id in series_ids]
        try:
            meta = self.http.get(GOVUK).json()
            atts = meta.get("details", {}).get("attachments", [])
            csvs = [a for a in atts if (a.get("content_type") or "").startswith("text/csv")]
            # The current CSV is the one whose title range starts at 2018 ("2018 to <year>").
            current = next((a for a in csvs if "2018" in (a.get("title") or "")), csvs[0] if csvs else None)
            if not current:
                raise SourceError("No CSV attachment found on GOV.UK content item", kind="validation")
            r = self.http.get(current["url"])
            parsed = parse_fuel_csv(r.text())
        except SourceError as e:
            for s in defs:
                res.errors.append({"series_id": s.id, **e.to_dict()})
            return res
        published = meta.get("public_updated_at")
        rel = datetime.fromisoformat(published) if published else None
        for s in defs:
            res.batches.append(SeriesBatch(s.id, parsed[s.source_key], request_url=r.url, release_date=rel,
                                           source_title=current.get("title"), source_meta={
                                               "page_url": FUEL_PAGE, "content_api": GOVUK,
                                               "attachment_title": current.get("title")}))
        return res
