"""Calculations: units, periods and statistical definitions."""
from datetime import date

import numpy as np
import pandas as pd
import pytest

from app.analytics import findings as F
from app.analytics import stats as S
from app.analytics import transforms as T
from app.registry.catalogue import CATALOGUE


def monthly(values, start="2020-01-01"):
    idx = pd.date_range(start, periods=len(values), freq="MS")
    return pd.Series(values, index=idx, dtype=float)


def test_pct_change_for_levels_and_pp_for_rates():
    level = CATALOGUE["retail_sales_volume"]  # index
    rate = CATALOGUE["unemployment_rate"]  # rate
    s = monthly([100, 110, 99])
    assert T.period_on_period(s, level).iloc[1] == pytest.approx(10.0)
    assert T.period_on_period(s, level).iloc[2] == pytest.approx(-10.0)
    r = monthly([4.0, 4.5, 4.2])
    assert T.period_on_period(r, rate).iloc[1] == pytest.approx(0.5)  # pp, not 12.5%
    assert T.change_unit(rate) == "pp" and T.change_unit(level) == "%"


def test_rules_refuse_inappropriate_transformations():
    r = T.rules(CATALOGUE["cpi_yoy"])
    assert not r["pct_change"].allowed and "percentage-point" in r["pct_change"].reason
    assert not r["index"].allowed
    assert "growth rate" in r["year_on_year"].caveat
    assert not T.rules(CATALOGUE["gva_C"])["decomposition"].allowed  # already SA
    assert T.rules(CATALOGUE["cpi_index"])["decomposition"].allowed  # NSA monthly
    assert "seasonal" in T.rules(CATALOGUE["cpi_index"])["period_on_period"].caveat.lower()
    assert "rolling" in T.rules(CATALOGUE["aps_unemployment_rate"])["period_on_period"].caveat.lower()


def test_yoy_uses_exact_calendar_match_not_position():
    sd = CATALOGUE["retail_sales_volume"]
    s = monthly(list(range(100, 125)))  # 25 months
    s = s.drop(s.index[5])  # gap: a missing month must not shift the comparison
    yoy = T.year_on_year(s, sd)
    t = pd.Timestamp("2021-07-01")
    assert yoy[t] == pytest.approx((s[t] / s[pd.Timestamp("2020-07-01")] - 1) * 100)
    assert np.isnan(yoy[pd.Timestamp("2021-06-01")])  # 2020-06 was dropped -> no comparison


def test_yoy_daily_nearest_prior_within_week():
    sd = CATALOGUE["gilt_10y"]
    idx = pd.bdate_range("2024-01-01", "2025-03-01")
    s = pd.Series(np.linspace(4, 5, len(idx)), index=idx)
    y = T.year_on_year(s, sd).dropna()
    assert len(y) > 0
    t = y.index[-1]
    prior = s[s.index <= t - pd.Timedelta(days=365)].iloc[-1]
    assert y.iloc[-1] == pytest.approx(s[t] - prior)  # pp for a rate


def test_rebase_and_rolling():
    s = monthly([50, 75, 100])
    assert list(T.rebase(s)) == [100, 150, 200]
    assert T.rolling_mean(s, 3).iloc[-1] == pytest.approx(75)


def test_robust_outlier_detection_flags_spike():
    sd = CATALOGUE["retail_sales_volume"]
    rng = np.random.default_rng(1)
    vals = list(100 + np.cumsum(rng.normal(0, 0.3, 60)))
    vals[45] = vals[44] * 1.2  # +20% spike
    out = S.outliers(sd, monthly(vals))
    assert any(o["period"] == monthly(vals).index[45].strftime("%Y-%m") for o in out)
    assert all(abs(o["robust_z"]) >= 3.5 for o in out)


def test_correlation_and_lag_recovery():
    a_def, b_def = CATALOGUE["cpi_index"], CATALOGUE["retail_sales_volume"]
    rng = np.random.default_rng(7)
    x = rng.normal(0, 1, 120)
    lead = np.concatenate([x, rng.normal(0, 1, 3)])
    b = monthly(100 * np.cumprod(1 + lead[:120] / 100))
    a = monthly(100 * np.cumprod(1 + np.concatenate([rng.normal(0, 0.1, 3), x[:117]]) / 100))
    res = S.correlate(a_def, a, b_def, b, max_lag=6)
    assert res["best_lag"]["lag"] == 3  # b leads a by 3 months
    assert res["best_lag"]["pearson"] > 0.9
    assert any("does not show that one series causes" in w for w in res["warnings"])


def test_correlation_requires_overlap():
    sd = CATALOGUE["cpi_index"]
    res = S.correlate(sd, monthly([1, 2, 3]), sd, monthly([1, 2, 3]))
    assert res["contemporaneous"]["pearson"] is None


def test_missing_report_detects_gaps_and_nulls():
    sd = CATALOGUE["cpi_index"]
    rows = [{"period": p, "period_start": date.fromisoformat(p + "-01"), "value": v, "status": "normal"}
            for p, v in [("2026-01", 1), ("2026-02", None), ("2026-04", 3)]]
    m = S.missing_report(sd, rows)
    assert m["gap_periods"] == ["2026-03"] and m["null_periods"] == ["2026-02"]


def test_scenario_is_mechanical_and_labelled():
    sd = CATALOGUE["retail_sales_volume"]
    s = monthly([100, 101, 102.01])
    out = S.scenario(sd, s, mode="custom", periods=2, value=1.0)
    assert out["points"][-1]["value"] == pytest.approx(102.01 * 1.01 ** 2)
    assert "not a forecast" in out["label"]
    rate = CATALOGUE["bank_rate"]
    out2 = S.scenario(rate, monthly([4.0, 3.75]), mode="custom", periods=2, value=-0.25)
    assert out2["points"][-1]["value"] == pytest.approx(3.25) and out2["step_unit"] == "pp"


def test_decomposition_only_when_justified():
    assert not S.decompose(CATALOGUE["gva_C"], monthly(range(60)))["available"]
    rng = np.random.default_rng(3)
    t = np.arange(72)
    s = monthly(100 + t * 0.2 + 3 * np.sin(2 * np.pi * t / 12) + rng.normal(0, 0.2, 72))
    out = S.decompose(CATALOGUE["cpi_index"], s)
    assert out["available"] and out["seasonal_strength"] > 0.8


def test_findings_are_typed_and_cite_evidence():
    sd = CATALOGUE["cpi_yoy"]
    s = monthly([2.0 + 0.1 * i for i in range(30)])
    out = F.build(sd, s, context=S.historical_context(s),
                  correlations=[{"title": "X", "pearson": 0.8, "n": 30}])
    assert {f["type"] for f in out} >= {"fact", "hypothesis"}
    assert any("association only" in f["text"] for f in out if f["type"] == "hypothesis")
    assert all("evidence" in f for f in out)
