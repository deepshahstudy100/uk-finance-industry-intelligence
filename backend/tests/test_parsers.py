"""Parsing and schema validation of real (trimmed) source payloads captured 2026-10-26."""
import json
from datetime import date

import pytest

from app.connectors.boe import parse_iadb_csv
from app.connectors.dmo import parse_d1a
from app.connectors.ecb import derive, parse_ecb_csv
from app.connectors.energy import parse_fuel_csv, parse_generation, parse_intensity
from app.connectors.http import SourceError
from app.connectors.land_registry import parse_hpi
from app.connectors.nomis import parse_nomis_csv, period_from, status_from
from app.connectors.ons import parse_timeseries
from app.periods import parse_ons_date, parse_rolling_window
from conftest import fixture_text


def test_ons_monthly_timeseries():
    ts, obs = parse_timeseries(json.loads(fixture_text("ons_d7g7.json")), "M")
    assert ts.description.cdid == "D7G7"
    assert ts.description.unit == "%"
    assert len(obs) == 40
    last = obs[-1]
    assert last.period == "2026-09" and last.value == 3.5
    assert last.period_start == date(2026, 9, 1) and last.period_end == date(2026, 9, 30)
    assert last.release_date is not None


def test_ons_quarterly_and_frequency_mismatch():
    payload = json.loads(fixture_text("ons_ihyq.json"))
    _, obs = parse_timeseries(payload, "Q")
    assert obs[-1].period.endswith(("Q1", "Q2", "Q3", "Q4"))
    with pytest.raises(SourceError) as e:
        parse_timeseries(payload, "M")  # IHYQ has no monthly observations
    assert e.value.kind == "validation"


def test_ons_schema_validation_rejects_garbage():
    with pytest.raises(SourceError) as e:
        parse_timeseries({"foo": 1}, "M")
    assert e.value.kind == "validation"


def test_ons_dates():
    assert parse_ons_date("2026 SEP")[:1] == ("2026-09",)
    assert parse_ons_date("2026 Q3")[1] == date(2026, 7, 1)
    assert parse_ons_date("2025")[3] == "A"
    with pytest.raises(ValueError):
        parse_ons_date("Sept 2026")


def test_boe_csv():
    data = parse_iadb_csv(fixture_text("boe_daily.csv"), ["IUDBEDR", "IUDMNPY"])
    assert data["IUDBEDR"][0][1] == 3.75
    assert all(isinstance(v, float) or v is None for _, v in data["IUDMNPY"])


def test_boe_rejects_html_and_missing_columns():
    with pytest.raises(SourceError):
        parse_iadb_csv("<html>error</html>", ["IUDBEDR"])
    with pytest.raises(SourceError):
        parse_iadb_csv("DATE,IUDBEDR\n01 Jan 2026,4\n", ["IUDBEDR", "XXXX"])


def test_ecb_and_transparent_derivation():
    data = parse_ecb_csv(fixture_text("ecb.csv"))
    assert {"D.GBP.EUR.SP00.A", "D.USD.EUR.SP00.A", "D.JPY.EUR.SP00.A"} <= set(data)
    base = {"ecb_gbp_per_eur": {d.isoformat(): v for d, v in data["D.GBP.EUR.SP00.A"]},
            "ecb_usd_per_eur": {d.isoformat(): v for d, v in data["D.USD.EUR.SP00.A"]}}
    out = derive("fx_gbp_usd", base)
    p = out[-1].period
    assert out[-1].value == pytest.approx(base["ecb_usd_per_eur"][p] / base["ecb_gbp_per_eur"][p])
    assert out[-1].flags["derived"] is True and "ecb_usd_per_eur" in out[-1].flags["formula"]
    inv = derive("fx_gbp_eur", base)
    assert inv[-1].value == pytest.approx(1 / base["ecb_gbp_per_eur"][inv[-1].period])


def test_nomis_aps_with_confidence_and_rolling_window():
    rows = parse_nomis_csv(fixture_text("nomis_aps.csv"), {"DATE_NAME", "GEOGRAPHY_CODE", "OBS_VALUE"})
    assert any(r["MEASURES_NAME"] == "Confidence" for r in rows)
    key, start, end = parse_rolling_window("Jul 2025-Jun 2026")
    assert key == "2026-Q2" and start == date(2025, 7, 1) and end == date(2026, 6, 30)
    assert period_from("Jul 2025-Jun 2026", None, "Q")[0] == "2026-Q2"
    assert period_from("September 2026", None, "M")[0] == "2026-09"
    assert period_from("June 2026", None, "Q")[0] == "2026-Q2"


def test_nomis_status_mapping_and_html_rejection():
    assert status_from("Normal Value") == ("normal", {})
    assert status_from("Estimate unavailable")[0] == "suppressed"
    assert status_from("Provisional")[0] == "provisional"
    with pytest.raises(SourceError):
        parse_nomis_csv("<error/>", {"DATE_NAME"})
    with pytest.raises(SourceError):
        parse_nomis_csv('"A","B"\n1,2\n', {"DATE_NAME"})


def test_nomis_business_counts_sections():
    rows = parse_nomis_csv(fixture_text("nomis_bc.csv"), {"DATE_NAME", "GEOGRAPHY_CODE", "OBS_VALUE", "INDUSTRY_CODE"})
    assert {r["INDUSTRY_CODE"] for r in rows} >= set("ABCFGJKMQ")


def test_land_registry_hpi():
    from app.connectors.land_registry import parse_hpi

    js = json.loads(fixture_text("lr_hpi.json"))
    rows = [{k: v["value"] for k, v in b.items()} for b in js["results"]["bindings"]]
    out = parse_hpi(rows)
    london = [o for o in out["averagePrice"] if o.geo == "E12000007"]
    assert london and all(o.value > 100000 for o in london)
    assert {o.geo for o in out["housePriceIndex"]} == {"E12000007", "K02000001"}


def test_carbon_payloads():
    obs = parse_intensity(json.loads(fixture_text("carbon_intensity.json")))
    assert obs and obs[0].period.endswith("Z") and obs[0].geo == "K03000001"
    assert all(o.status in ("normal", "forecast") for o in obs)
    gen = parse_generation(json.loads(fixture_text("carbon_generation.json")))
    fuels = {o.dim for o in gen}
    assert {"wind", "gas", "nuclear"} <= fuels
    with pytest.raises(SourceError):
        parse_intensity({"error": "x"})


def test_fuel_csv():
    out = parse_fuel_csv(fixture_text("fuel.csv"))
    assert len(out["ULSP"]) == 8 and out["ULSP"][-1].value > 100
    assert out["ULSD"][-1].flags["duty_ppl"] == 52.95
    with pytest.raises(SourceError):
        parse_fuel_csv("a,b\n1,2\n")


def test_dmo_xml_and_bot_challenge():
    obs, inst = parse_d1a(fixture_text("dmo_d1a.xml"))
    tot = {o.dim: o.value for o in obs}
    assert tot["All|All"] == pytest.approx(350.5)
    assert tot["Conventional|All"] == pytest.approx(300.5)
    assert len(inst) == 3
    with pytest.raises(SourceError):
        parse_d1a("<html><body>challenge</body>")  # malformed / challenge page


def test_hmrc_fixture_shape():
    js = json.loads(fixture_text("hmrc_sitc.json"))
    assert "value" in js and {"MonthId", "FlowTypeId", "Value"} <= set(js["value"][0])
