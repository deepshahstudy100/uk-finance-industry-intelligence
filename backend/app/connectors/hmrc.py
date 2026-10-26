"""HMRC Overseas Trade Statistics via the uktradeinfo OData API (aggregated server-side with $apply)."""
from __future__ import annotations

from datetime import date

from ..periods import month_key
from ..registry.catalogue import series_for_source
from .base import Connector, FetchResult, ObsIn, SeriesBatch, SourceError, to_float

API = "https://api.uktradeinfo.com"
PAGE = "https://www.uktradeinfo.com/trade-data/"


def months_back(n: int, today: date | None = None) -> int:
    t = today or date.today()
    y, m = t.year, t.month - n
    while m <= 0:
        m += 12
        y -= 1
    return y * 100 + m


class HmrcConnector(Connector):
    source_id = "hmrc_ots"

    def _odata_all(self, url: str, params: dict | None = None, ttl: float | None = None) -> list[dict]:
        rows: list[dict] = []
        next_url, p = url, params
        pages = 0
        while next_url and pages < 20:
            r = self.http.get(next_url, params=p, cache_ttl_s=ttl)
            try:
                js = r.json()
            except ValueError as e:
                raise SourceError(f"HMRC returned non-JSON: {r.text()[:120]}", kind="validation", url=r.url) from e
            if "value" not in js:
                raise SourceError("HMRC payload has no 'value' array", kind="validation", url=r.url)
            rows.extend(js["value"])
            next_url, p = js.get("@odata.nextLink"), None
            pages += 1
        return rows

    def lookups(self) -> tuple[dict, dict]:
        countries = {c["CountryId"]: c for c in self._odata_all(f"{API}/Country", ttl=86400 * 7)}
        sitc = {c["CommoditySitcId"]: c for c in self._odata_all(f"{API}/SITC", ttl=86400 * 7)}
        return countries, sitc

    def fetch(self, series_ids: list[str] | None = None) -> FetchResult:
        res = FetchResult()
        defs = [s for s in series_for_source("hmrc_ots") if not series_ids or s.id in series_ids]
        try:
            countries, sitc = self.lookups()
        except SourceError as e:
            for s in defs:
                res.errors.append({"series_id": s.id, **e.to_dict()})
            return res
        since = months_back(26)
        sitc1_labels = {(c.get("Sitc1Code") or "").strip(): (c.get("Sitc1Desc") or "").strip()
                        for c in sitc.values() if c.get("Sitc1Code")}
        cache: dict[str, tuple[str, list[dict]]] = {}
        for s in defs:
            by = s.params["by"]
            try:
                if by not in cache:
                    group = by if by == "CountryId" else "SITC/Sitc1Code"  # navigation groupby: ~11 rows/month
                    apply = (f"filter(MonthId ge {since})/groupby((MonthId,FlowTypeId,{group}),"
                             f"aggregate(Value with sum as Value))")
                    rows = self._odata_all(f"{API}/OTS", params={"$apply": apply})
                    cache[by] = (self.http.request_log[-1]["url"], rows)
                url, rows = cache[by]
            except SourceError as e:
                res.errors.append({"series_id": s.id, **e.to_dict()})
                continue
            agg: dict[tuple[str, str], float] = {}
            labels: dict[str, str] = {}
            for row in rows:
                if row.get("FlowTypeId") not in s.params["flows"]:
                    continue
                mid = int(row["MonthId"])
                if mid % 100 == 0 or mid % 100 > 12:
                    continue  # annual/aggregate pseudo-months are not monthly observations
                key = f"{mid // 100:04d}-{mid % 100:02d}"
                if by == "CountryId":
                    c = countries.get(row["CountryId"])
                    code = (c or {}).get("CountryCodeAlpha") or f"ID{row['CountryId']}"
                    labels[code] = ((c or {}).get("CountryName") or f"Unknown country id {row['CountryId']}").strip()
                else:
                    code = (((row.get("SITC") or {}).get("Sitc1Code")) or "X").strip()
                    labels[code] = sitc1_labels.get(code, "Not allocated to a SITC section")
                v = to_float(row.get("Value")) or 0.0
                agg[(key, code)] = agg.get((key, code), 0.0) + v
            obs = []
            for (key, code), v in agg.items():
                y, m = map(int, key.split("-"))
                k, st, en = month_key(y, m)
                obs.append(ObsIn(period=k, period_start=st, period_end=en, value=v, geo="K02000001", dim=code))
            if not obs:
                res.errors.append({"series_id": s.id, "kind": "validation", "message": "No rows"})
                continue
            res.batches.append(SeriesBatch(s.id, obs, request_url=url, source_meta={
                "page_url": PAGE, "dim_labels": labels, "flows": s.params["flows"],
                "note": "Sum of EU and non-EU flows (FlowTypeId " + ",".join(map(str, s.params["flows"])) + ")",
            }))
        return res
