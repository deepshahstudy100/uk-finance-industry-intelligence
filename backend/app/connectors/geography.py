"""ONS Open Geography Portal: ITL1 + LAD boundaries (generalised) and the LAD -> ITL1 lookup."""
from __future__ import annotations

import json

from ..registry.geography import ITL_TO_GSS
from .base import Connector, FetchResult, SourceError

BASE = "https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services"
LAYERS = {
    "itl1": ("ITL1_JAN_2025_UK_BUC", "ITL125CD,ITL125NM"),
    "lad": ("LAD_MAY_2025_UK_BUC", "LAD25CD,LAD25NM"),
}
LOOKUP = "ITL125_ITL225_ITL325_LAU125_LAD25_UK_LU"


def _round_coords(obj, nd=4):
    if isinstance(obj, list):
        if obj and isinstance(obj[0], (int, float)):
            return [round(x, nd) for x in obj]
        return [_round_coords(o, nd) for o in obj]
    return obj


def normalise(level: str, gj: dict) -> dict:
    feats = []
    for f in gj.get("features", []):
        p = f.get("properties") or {}
        if level == "itl1":
            itl = p.get("ITL125CD")
            code, name = ITL_TO_GSS.get(itl), p.get("ITL125NM")
            if not code:
                continue
            props = {"code": code, "name": name, "itl": itl}
        else:
            code, name = p.get("LAD25CD"), p.get("LAD25NM")
            props = {"code": code, "name": name}
        geom = f.get("geometry")
        if not geom or not code:
            continue
        feats.append({"type": "Feature", "properties": props,
                      "geometry": {"type": geom["type"], "coordinates": _round_coords(geom["coordinates"])}})
    if not feats:
        raise SourceError(f"No features in {level} boundary layer", kind="validation")
    return {"type": "FeatureCollection", "features": feats}


class GeographyConnector(Connector):
    source_id = "ons_geography"

    def fetch(self, series_ids: list[str] | None = None) -> FetchResult:
        res = FetchResult()
        boundaries = {}
        for level, (svc, fields) in LAYERS.items():
            url = f"{BASE}/{svc}/FeatureServer/0/query"
            params = {"where": "1=1", "outFields": fields, "outSR": 4326, "f": "geojson",
                      "maxAllowableOffset": 0.002 if level == "lad" else 0.003, "geometryPrecision": 4,
                      "resultRecordCount": 2000}
            try:
                r = self.http.get(url, params=params)
                boundaries[level] = {"geojson": normalise(level, r.json()), "url": r.url}
            except (SourceError, ValueError) as e:
                err = e.to_dict() if isinstance(e, SourceError) else {"kind": "validation", "message": str(e)}
                res.errors.append({"series_id": f"boundaries:{level}", **err})
        try:
            r = self.http.get(f"{BASE}/{LOOKUP}/FeatureServer/0/query", params={
                "where": "1=1", "outFields": "LAD25CD,LAD25NM,ITL125CD", "returnGeometry": "false", "f": "json",
                "resultRecordCount": 2000})
            rows = [f["attributes"] for f in r.json().get("features", [])]
            if not rows:
                raise SourceError("Empty LAD lookup", kind="validation")
            res.extra["lad_lookup"] = {"rows": rows, "url": r.url}
        except (SourceError, ValueError, KeyError) as e:
            err = e.to_dict() if isinstance(e, SourceError) else {"kind": "validation", "message": str(e)}
            res.errors.append({"series_id": "lookup:lad_itl1", **err})
        res.extra["boundaries"] = boundaries
        return res


def dumps(gj: dict) -> str:
    return json.dumps(gj, separators=(",", ":"))
