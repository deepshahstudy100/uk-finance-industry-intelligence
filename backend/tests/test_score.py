"""Economic Conditions Score: orientation, standardisation, weights, carry-forward and coverage rules."""
import math

import numpy as np
import pandas as pd
import pytest

from app.analytics import score as SC


def monthly(values, start="2006-01-01"):
    return pd.Series(values, index=pd.date_range(start, periods=len(values), freq="MS"), dtype=float)


def base_inputs(n=240, seed=0):
    r = np.random.default_rng(seed)
    return {
        "gdp_monthly_index": monthly(100 * np.cumprod(1 + r.normal(0.001, 0.003, n))),
        "retail_sales_volume": monthly(100 * np.cumprod(1 + r.normal(0.001, 0.005, n))),
        "unemployment_rate": monthly(5 + r.normal(0, 0.5, n)),
        "awe_regular_growth": monthly(3 + r.normal(0, 1, n)),
        "cpi_yoy": monthly(2.5 + r.normal(0, 1.5, n)),
        "cpi_core_yoy": monthly(2.3 + r.normal(0, 1, n)),
        "mortgage_2y_75": monthly(3 + r.normal(0, 1, n)),
        "mortgage_approvals": monthly(70000 + r.normal(0, 8000, n)),
    }


def test_score_range_and_mapping():
    out = SC.compute(base_inputs())
    assert out["available"] and 0 < out["score"] < 100
    assert out["score"] == pytest.approx(100 * SC.phi(out["z"]))
    assert {p["id"] for p in out["pillars"]} == set(SC.PILLARS)
    assert "NOT an official statistic" in out["caveats"][0]


def test_contributions_sum_to_composite_z():
    out = SC.compute(base_inputs())
    total = sum(c["contribution_z"] for c in out["components"] if c.get("contribution_z") is not None)
    assert total == pytest.approx(out["z"])


def test_direction_lower_unemployment_raises_score():
    a = base_inputs()
    b = {k: v.copy() for k, v in a.items()}
    b["unemployment_rate"].iloc[-1] -= 3  # sharply lower unemployment in the latest month
    assert SC.compute(b)["score"] > SC.compute(a)["score"]


def test_inflation_gap_is_symmetric_around_target():
    a = base_inputs()
    hi, lo = {k: v.copy() for k, v in a.items()}, {k: v.copy() for k, v in a.items()}
    hi["cpi_yoy"].iloc[-1], lo["cpi_yoy"].iloc[-1] = 4.0, 0.0  # both 2pp from target
    zh = next(c for c in SC.compute(hi)["components"] if c["id"] == "cpi_gap")["z"]
    zl = next(c for c in SC.compute(lo)["components"] if c["id"] == "cpi_gap")["z"]
    assert zh == pytest.approx(zl)


def test_weights_change_result_and_zero_weights_rejected():
    a = base_inputs()
    s1 = SC.compute(a, {"growth": 1, "labour": 1, "prices": 1, "financial": 1})["score"]
    s2 = SC.compute(a, {"growth": 5, "labour": 0, "prices": 0, "financial": 1})["score"]
    assert s1 != s2
    with pytest.raises(ValueError):
        SC.compute(a, {"growth": 0, "labour": 0, "prices": 0, "financial": 0})


def test_carry_forward_is_limited_and_flagged():
    a = base_inputs()
    a["mortgage_approvals"] = a["mortgage_approvals"].iloc[:-2]  # two months older than the rest
    out = SC.compute(a)
    c = next(x for x in out["components"] if x["id"] == "approvals")
    assert c["carried_forward"] is True and c["period_used"] < out["period"]
    a["mortgage_approvals"] = a["mortgage_approvals"].iloc[:-10]  # beyond MAX_CARRY -> unavailable at latest
    c2 = next(x for x in SC.compute(a)["components"] if x["id"] == "approvals")
    assert c2["available"] is False or c2["z"] is None


def test_insufficient_pillars_means_unavailable():
    a = base_inputs()
    only = {k: a[k] for k in ("cpi_yoy", "cpi_core_yoy")}
    out = SC.compute(only)
    assert out["available"] is False


def test_gdp_3m3m_formula():
    x = monthly([100, 100, 100, 103, 103, 103])
    v = SC.component_values(SC.COMPONENTS[0], {"gdp_monthly_index": x})
    assert v.iloc[-1] == pytest.approx(3.0)
    assert math.isfinite(v.iloc[-1])
