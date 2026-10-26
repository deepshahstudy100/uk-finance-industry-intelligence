"""API behaviour: provenance on every metric, demo isolation, exports with traceable metadata."""
import csv
import io
import json

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app.db import session_scope
from app.demo.generator import ensure_demo
from app.ingestion.runner import run_source
from conftest import fixture_text
from test_ingestion import IADB, boe_mock

ONS_URL = "https://www.ons.gov.uk/economy/inflationandpriceindices/timeseries/d7g7/mm23/data"


@pytest.fixture()
def api(db, no_sleep):
    from app.main import app

    with respx.mock(assert_all_called=False) as m:
        m.get(IADB).mock(side_effect=boe_mock())
        m.get(ONS_URL).mock(return_value=httpx.Response(200, text=fixture_text("ons_d7g7.json")))
        run_source("boe")
        run_source("ons", ["cpi_yoy"])
    with session_scope() as s:
        ensure_demo(s)
    with TestClient(app) as c:
        yield c


def test_series_detail_exposes_identity_and_provenance(api):
    d = api.get("/api/series/cpi_yoy").json()
    idn, prov = d["identity"], d["provenance"]
    for k in ("title", "definition", "unit", "frequency", "measure_type", "seasonal_adjustment", "geography"):
        assert idn[k]
    for k in ("publisher", "dataset_identifier", "request_url", "source_page_url", "licence", "attribution",
              "release_date", "next_release", "last_retrieved_at"):
        assert prov[k], k
    assert prov["request_url"] == ONS_URL
    assert d["data_status"] == "real"
    assert d["versions"]  # ONS published version history


def test_real_data_wins_over_demo(api):
    obs = api.get("/api/series/bank_rate/observations").json()
    assert obs["data_status"] == "real"
    assert all(not o["is_demo"] for o in obs["observations"])
    assert len(obs["observations"]) == 2


def test_series_without_real_data_is_labelled_demo(api):
    obs = api.get("/api/series/gdp_qoq/observations").json()
    assert obs["data_status"] == "demo" and obs["observations"]
    assert all(o["is_demo"] for o in obs["observations"])
    summary = next(k for k in api.get("/api/overview").json()["kpis"] if k["id"] == "gdp_qoq")
    assert summary["status"] == "demo" and summary["data_status"] == "demo"


def test_demo_off_returns_empty_not_fake(api, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "demo_mode", "off")
    obs = api.get("/api/series/gdp_qoq/observations").json()
    assert obs["observations"] == [] and obs["data_status"] == "real"


def test_cannot_correlate_real_with_demo(api):
    r = api.get("/api/correlate", params={"a": "cpi_yoy", "b": "gdp_qoq"})
    assert r.status_code == 409


def test_analysis_respects_rules(api):
    a = api.get("/api/series/cpi_yoy/analysis").json()
    assert a["change_unit"] == "pp"
    assert all(p["indexed"] is None for p in a["points"])  # rebasing a rate refused
    assert a["rules"]["pct_change"]["allowed"] is False
    assert a["findings"] and a["missing"]["observations"] == 40


def test_compare_indexed_refuses_rate(api):
    r = api.get("/api/compare", params={"ids": "cpi_yoy", "mode": "indexed"}).json()
    s = r["series"][0]
    assert s["note"] and all(p["value"] is None for p in s["points"])


def test_csv_export_has_traceable_metadata(api):
    r = api.get("/api/export", params={"series_id": "cpi_yoy", "format": "csv", "include_analysis": "true"})
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    rows = list(csv.DictReader(io.StringIO(r.text)))
    assert len(rows) == 40
    row = rows[-1]
    assert row["publisher"] == "Office for National Statistics" and row["request_url"] == ONS_URL
    assert row["licence"].startswith("Open Government Licence") and row["data_status"] == "real"
    assert row["retrieved_at"] and row["ingestion_run_id"] and row["unit"] == "%"
    assert "pop_pp" in row and "yoy_pp" in row


def test_json_export_and_demo_warning(api):
    j = json.loads(api.get("/api/export", params={"series_id": "gdp_qoq", "format": "json"}).text)
    assert j["metadata"]["data_status"] == "demo"
    assert "NOT REAL" in j["metadata"]["demo_warning"]
    assert all(o["data_status"] == "demo" for o in j["observations"])


def test_sources_and_meta(api):
    src = {s["id"]: s for s in api.get("/api/sources").json()}
    assert src["boe"]["status"] == "current" and src["boe"]["licence"]
    assert src["companies_house"]["status"] == "not_configured"
    meta = api.get("/api/meta").json()
    assert meta["paid_dependencies"] == []
    runs = api.get("/api/sources/boe/runs").json()
    assert runs[0]["requests"][0]["url"].startswith(IADB)


def test_search_and_unknown_series(api):
    res = api.get("/api/search", params={"q": "inflation"}).json()["results"]
    assert any(r["id"] == "cpi_yoy" for r in res)
    assert api.get("/api/series/nope").status_code == 404


def test_companies_house_without_key_is_explicit(api):
    r = api.get("/api/companies/search", params={"q": "tesco"})
    assert r.status_code == 503 and "API key" in r.json()["detail"]


def test_saved_views_roundtrip(api):
    vid = api.post("/api/views", json={"name": "London housing", "path": "/regions?geo=E12000007"}).json()["id"]
    assert any(v["id"] == vid for v in api.get("/api/views").json())
    assert api.delete(f"/api/views/{vid}").json()["deleted"]


def test_refresh_requires_admin_token_when_configured(api, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "admin_token", "secret")
    assert api.post("/api/sources/boe/refresh").status_code == 403


def test_score_endpoint_uses_only_real_data(api):
    r = api.get("/api/score").json()
    # Fixture DB has real data only for BoE and cpi_yoy: too few pillars, so the score is unavailable,
    # and demo data (present for every series) must not be used to fill the gap.
    assert r["data_status"] == "real"
    assert r["available"] is False
    assert api.get("/api/score", params={"weights": "growth:x"}).status_code == 422
