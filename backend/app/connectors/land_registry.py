"""HM Land Registry linked data: UK HPI (stored) and Price Paid (queried on demand)."""
from __future__ import annotations

import re
from datetime import date

from ..periods import month_key
from ..registry.catalogue import series_for_source
from ..registry.geography import LR_SLUG_TO_GSS
from .base import Connector, FetchResult, ObsIn, SeriesBatch, SourceError, to_float

SPARQL = "https://landregistry.data.gov.uk/landregistry/query"
REGION = "http://landregistry.data.gov.uk/id/region/"
HPI_PAGE = "https://landregistry.data.gov.uk/app/ukhpi/browse?location=http%3A%2F%2Flandregistry.data.gov.uk%2Fid%2Fregion%2F{slug}"
PPD_PAGE = "https://landregistry.data.gov.uk/app/ppd"

HPI_QUERY = """PREFIX ukhpi: <http://landregistry.data.gov.uk/def/ukhpi/>
SELECT ?region ?month ?averagePrice ?housePriceIndex ?percentageAnnualChange ?salesVolume WHERE {{
  VALUES ?region {{ {regions} }}
  ?obs ukhpi:refRegion ?region ; ukhpi:refMonth ?month .
  OPTIONAL {{ ?obs ukhpi:averagePrice ?averagePrice }}
  OPTIONAL {{ ?obs ukhpi:housePriceIndex ?housePriceIndex }}
  OPTIONAL {{ ?obs ukhpi:percentageAnnualChange ?percentageAnnualChange }}
  OPTIONAL {{ ?obs ukhpi:salesVolume ?salesVolume }}
  FILTER(?month >= "{since}"^^<http://www.w3.org/2001/XMLSchema#gYearMonth>)
}}"""

PPD_QUERY = """PREFIX lrppi: <http://landregistry.data.gov.uk/def/ppi/>
PREFIX lrcommon: <http://landregistry.data.gov.uk/def/common/>
SELECT ?tx ?amount ?date ?postcode ?ptype ?estate ?newbuild ?category WHERE {{
  ?tx lrppi:pricePaid ?amount ; lrppi:transactionDate ?date ; lrppi:propertyAddress ?addr ;
      lrppi:propertyType ?ptype ; lrppi:estateType ?estate ; lrppi:newBuild ?newbuild ;
      lrppi:transactionCategory ?category .
  ?addr lrcommon:district "{district}"^^<http://www.w3.org/2001/XMLSchema#string> .
  OPTIONAL {{ ?addr lrcommon:postcode ?postcode }}
  FILTER(?date >= "{since}"^^<http://www.w3.org/2001/XMLSchema#date>)
}} ORDER BY DESC(?date) LIMIT {limit}"""


def sparql(http, query: str) -> list[dict]:
    r = http.post(SPARQL, data={"query": query}, headers={"Accept": "application/sparql-results+json"})
    try:
        js = r.json()
        bindings = js["results"]["bindings"]
    except (ValueError, KeyError) as e:
        raise SourceError("Land Registry SPARQL returned an unexpected payload", kind="validation", url=r.url) from e
    return [{k: v.get("value") for k, v in b.items()} for b in bindings]


def parse_hpi(rows: list[dict]) -> dict[str, list[ObsIn]]:
    out: dict[str, list[ObsIn]] = {p: [] for p in ("averagePrice", "housePriceIndex", "percentageAnnualChange",
                                                    "salesVolume")}
    for row in rows:
        slug = row["region"].removeprefix(REGION)
        geo = LR_SLUG_TO_GSS.get(slug)
        if not geo:
            continue
        m = re.fullmatch(r"(\d{4})-(\d{2})", row["month"])
        if not m:
            raise SourceError(f"Bad UK HPI month {row['month']!r}", kind="validation")
        key, st, en = month_key(int(m[1]), int(m[2]))
        for prop in out:
            if prop in row:
                out[prop].append(ObsIn(period=key, period_start=st, period_end=en, value=to_float(row[prop]),
                                       geo=geo, flags={"lr_region": slug}))
    return out


class LandRegistryConnector(Connector):
    source_id = "land_registry"

    def fetch(self, series_ids: list[str] | None = None) -> FetchResult:
        res = FetchResult()
        defs = [s for s in series_for_source("land_registry") if not series_ids or s.id in series_ids]
        regions = " ".join(f"<{REGION}{slug}>" for slug in LR_SLUG_TO_GSS if slug != "great-britain")
        try:
            rows = sparql(self.http, HPI_QUERY.format(regions=regions, since="2005-01"))
        except SourceError as e:
            for s in defs:
                res.errors.append({"series_id": s.id, **e.to_dict()})
            return res
        parsed = parse_hpi(rows)
        url = self.http.request_log[-1]["url"] if self.http.request_log else SPARQL
        latest = max((o.period for v in parsed.values() for o in v), default=None)
        for s in defs:
            obs = parsed.get(s.params["property"], [])
            # The most recent two months are provisional under UK HPI revision practice.
            if latest:
                y, m = map(int, latest.split("-"))
                recent = {latest, f"{y if m > 1 else y - 1:04d}-{(m - 2) % 12 + 1:02d}"}
                for o in obs:
                    if o.period in recent:
                        o.status = "provisional"
            if not obs:
                res.errors.append({"series_id": s.id, "kind": "validation", "message": "No rows"})
                continue
            res.batches.append(SeriesBatch(s.id, obs, request_url=url, source_meta={
                "page_url": HPI_PAGE.format(slug="united-kingdom"), "sparql_endpoint": SPARQL,
                "query": HPI_QUERY.format(regions="...", since="2005-01"),
            }))
        return res

    def price_paid(self, district: str, since: date, limit: int = 200) -> tuple[str, list[dict]]:
        district = district.strip().upper()
        if not re.fullmatch(r"[A-Z0-9 ,'\-\.&]{2,60}", district):
            raise SourceError("Invalid district name", kind="validation")
        q = PPD_QUERY.format(district=district.replace('"', ""), since=since.isoformat(), limit=min(limit, 500))
        rows = sparql(self.http, q)
        out = []
        for r in rows:
            out.append({
                "transaction_uri": r.get("tx"),
                "price": to_float(r.get("amount")),
                "date": r.get("date"),
                "postcode": r.get("postcode"),
                "property_type": (r.get("ptype") or "").rsplit("/", 1)[-1],
                "estate_type": (r.get("estate") or "").rsplit("/", 1)[-1],
                "new_build": r.get("newbuild") == "true",
                "category": (r.get("category") or "").rsplit("/", 1)[-1],
            })
        return q, out
