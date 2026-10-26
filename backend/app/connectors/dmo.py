"""UK Debt Management Office: gilts in issue (report D1A, XML)."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime

from ..periods import day_key
from .base import Connector, FetchResult, ObsIn, SeriesBatch, SourceError, to_float

URL = "https://www.dmo.gov.uk/data/XmlDataReport"
PAGE = "https://www.dmo.gov.uk/data/gilt-market/gilts-in-issue/"


def parse_d1a(xml_text: str) -> tuple[list[ObsIn], list[dict]]:
    try:
        root = ET.fromstring(xml_text.strip())
    except ET.ParseError as e:
        raise SourceError("DMO response is not valid XML (possibly a bot-protection challenge)",
                          kind="validation") from e
    rows = [el.attrib for el in root.iter() if el.tag.endswith("GILTS_IN_ISSUE")]
    if not rows:
        raise SourceError("DMO XML contained no gilt rows", kind="validation")
    agg: dict[str, float] = {}
    cob = None
    instruments = []
    for a in rows:
        cob = a.get("CLOSE_OF_BUSINESS_DATE", cob)
        typ = (a.get("INSTRUMENT_TYPE") or "").strip()
        bracket = (a.get("MATURITY_BRACKET") or "").strip()
        amt = to_float(a.get("TOTAL_AMOUNT_IN_ISSUE"))
        if amt is None:
            continue
        for k in (f"{typ}|{bracket}", f"{typ}|All", "All|All"):
            agg[k] = agg.get(k, 0.0) + amt
        instruments.append({"name": a.get("INSTRUMENT_NAME"), "isin": a.get("ISIN_CODE"), "type": typ,
                            "bracket": bracket, "redemption": (a.get("REDEMPTION_DATE") or "")[:10],
                            "amount_m": amt,
                            "amount_incl_uplift_m": to_float(a.get("TOTAL_AMOUNT_INCLUDING_IL_UPLIFT"))})
    if not cob:
        raise SourceError("DMO XML missing CLOSE_OF_BUSINESS_DATE", kind="validation")
    d = datetime.fromisoformat(cob).date()
    key, st, en = day_key(d)
    obs = [ObsIn(period=key, period_start=st, period_end=en, value=v, dim=k) for k, v in agg.items()]
    return obs, instruments


class DmoConnector(Connector):
    source_id = "dmo"

    def fetch(self, series_ids: list[str] | None = None) -> FetchResult:
        res = FetchResult()
        try:
            r = self.http.get(URL, params={"reportCode": "D1A"}, follow_redirects=False)
            if r.status >= 300:
                raise SourceError(f"DMO redirected (HTTP {r.status}); likely bot protection", kind="http",
                                  status=r.status, url=r.url)
            obs, instruments = parse_d1a(r.text())
        except SourceError as e:
            res.errors.append({"series_id": "gilts_in_issue", **e.to_dict()})
            return res
        res.batches.append(SeriesBatch("gilts_in_issue", obs, request_url=r.url, source_meta={
            "page_url": PAGE, "report": "D1A", "instruments": instruments,
            "dim_labels": {o.dim: o.dim.replace("|", " - ").replace("All - All", "All gilts") for o in obs}}))
        return res
