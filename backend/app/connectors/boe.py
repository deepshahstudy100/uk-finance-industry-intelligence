"""Bank of England IADB CSV export."""
from __future__ import annotations

import csv
import io
from datetime import datetime

from ..config import get_settings
from ..periods import day_key, month_key
from ..registry.catalogue import CATALOGUE, series_for_source
from .base import Connector, FetchResult, ObsIn, SeriesBatch, SourceError, to_float

IADB = "https://www.bankofengland.co.uk/boeapps/database/_iadb-fromshowcolumns.asp"
PAGE = "https://www.bankofengland.co.uk/boeapps/database/fromshowcolumns.asp?Travel=NIxAZxSUx&FromSeries=1&ToSeries=50&DAT=RNG&FD=1&FM=Jan&FY=2000&TD=31&TM=Dec&TY=2030&FNY=Y&CSVF=TT&html.x=66&html.y=26&C=&Filter=N&SeriesCodes={code}&UsingCodes=Y"


def parse_iadb_csv(text: str, codes: list[str]) -> dict[str, list[tuple[datetime, float | None]]]:
    if text.lstrip().startswith("<"):
        raise SourceError("BoE returned HTML instead of CSV (invalid code or error page)", kind="validation")
    reader = csv.reader(io.StringIO(text))
    header = next(reader, None)
    if not header or header[0].strip().upper() != "DATE":
        raise SourceError(f"Unexpected BoE CSV header: {header}", kind="validation")
    cols = [h.strip() for h in header[1:]]
    missing = set(codes) - set(cols)
    if missing:
        raise SourceError(f"BoE CSV missing requested series {sorted(missing)}", kind="validation")
    out: dict[str, list] = {c: [] for c in cols}
    for row in reader:
        if not row or not row[0].strip():
            continue
        d = datetime.strptime(row[0].strip(), "%d %b %Y")
        for c, v in zip(cols, row[1:]):
            out[c].append((d, to_float(v)))
    return out


class BoeConnector(Connector):
    source_id = "boe"

    def fetch(self, series_ids: list[str] | None = None) -> FetchResult:
        res = FetchResult()
        allow_fx = get_settings().enable_boe_fx
        defs = [s for s in series_for_source("boe") if (s.enabled or (allow_fx and s.source_key.startswith("XUDL")))]
        if series_ids:
            defs = [s for s in defs if s.id in series_ids]
        for freq, start in (("D", "01/Jan/2000"), ("M", "01/Jan/1995")):
            group = [s for s in defs if s.frequency == freq]
            if not group:
                continue
            codes = [s.source_key for s in group]
            params = {"csv.x": "yes", "Datefrom": start, "Dateto": "now", "SeriesCodes": ",".join(codes),
                      "CSVF": "TN", "UsingCodes": "Y", "VPD": "Y", "VFD": "N"}
            try:
                r = self.http.get(IADB, params=params, reject_redirect_to="ErrorPage")
                data = parse_iadb_csv(r.text(), codes)
            except SourceError as e:
                for s in group:
                    res.errors.append({"series_id": s.id, **e.to_dict()})
                continue
            for s in group:
                obs = []
                for d, v in data[s.source_key]:
                    if freq == "D":
                        key, st, en = day_key(d.date())
                    else:
                        key, st, en = month_key(d.year, d.month)
                    if v is None:
                        continue  # BoE leaves non-business days blank; these are not missing observations
                    obs.append(ObsIn(period=key, period_start=st, period_end=en, value=v))
                if not obs:
                    res.errors.append({"series_id": s.id, "kind": "validation", "message": "No observations"})
                    continue
                res.batches.append(SeriesBatch(
                    series_id=s.id, observations=obs, request_url=r.url,
                    source_meta={"page_url": PAGE.format(code=s.source_key), "code": s.source_key},
                ))
        return res


def fx_enabled_series() -> list[str]:
    return [s.id for s in CATALOGUE.values() if s.source_id == "boe" and s.source_key.startswith("XUDL")]
