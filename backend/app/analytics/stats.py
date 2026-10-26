"""Statistical context: missing data, outliers, volatility, correlation and lag analysis, decomposition,
scenario projection. Everything here is descriptive; correlations are associations, never causal claims."""
from __future__ import annotations

import math
import warnings

import numpy as np
import pandas as pd
from scipy import stats as sps

from ..periods import FREQ_ORDER, key_for
from ..registry.catalogue import SeriesDef
from .transforms import PP_TYPES, period_on_period

ASSOCIATION_NOTE = ("Correlation measures co-movement only. It does not show that one series causes the other; "
                    "both may respond to common drivers, and significance is overstated when series are "
                    "autocorrelated.")


def expected_periods(sd: SeriesDef, first: pd.Timestamp, last: pd.Timestamp) -> list[str]:
    f = sd.frequency
    if f == "M":
        rng = pd.period_range(first, last, freq="M")
        return [f"{p.year:04d}-{p.month:02d}" for p in rng]
    if f == "Q":
        rng = pd.period_range(first, last, freq="Q")
        return [f"{p.year:04d}-Q{p.quarter}" for p in rng]
    if f == "A":
        return [f"{y:04d}" for y in range(first.year, last.year + 1)]
    return []  # daily/weekly/half-hourly: business-day and publication gaps are normal; not enumerated


def missing_report(sd: SeriesDef, rows: list[dict]) -> dict:
    present = {r["period"] for r in rows}
    null_periods = [r["period"] for r in rows if r["value"] is None]
    gaps: list[str] = []
    if rows and sd.frequency in ("M", "Q", "A"):
        starts = [pd.Timestamp(r["period_start"]) for r in rows]
        exp = expected_periods(sd, min(starts), max(starts))
        gaps = [p for p in exp if p not in present]
    suppressed = [r["period"] for r in rows if r.get("status") == "suppressed"]
    return {
        "observations": len(rows), "null_values": len(null_periods), "null_periods": null_periods[-50:],
        "gaps_in_sequence": len(gaps), "gap_periods": gaps[-50:], "suppressed": suppressed[-50:],
        "note": ("Daily/weekly/half-hourly series skip non-publication days; gaps are not enumerated."
                 if sd.frequency in ("D", "W", "HH") else "Gaps are periods missing between the first and last "
                                                          "observation."),
    }


def robust_z(x: pd.Series) -> pd.Series:
    c = x.dropna()
    if len(c) < 8:
        return pd.Series(np.nan, index=x.index)
    med = c.median()
    mad = (c - med).abs().median()
    if mad == 0 or not np.isfinite(mad):
        return pd.Series(np.nan, index=x.index)
    return 0.6745 * (x - med) / mad


def outliers(sd: SeriesDef, s: pd.Series, threshold: float = 3.5, lookback: int | None = None) -> list[dict]:
    """Flags unusually large period-on-period changes using a robust (median/MAD) z-score."""
    ch = period_on_period(s, sd)
    if lookback:
        ch = ch.iloc[-lookback:]
    z = robust_z(ch)
    out = []
    for ts, zv in z.items():
        if np.isfinite(zv) and abs(zv) >= threshold:
            out.append({"period": key_for(sd.frequency if sd.frequency in ("A", "Q", "M") else "D", ts.date()),
                        "period_start": ts.date().isoformat(), "change": float(ch[ts]),
                        "change_unit": "pp" if sd.measure_type in PP_TYPES else "%", "robust_z": round(float(zv), 2),
                        "method": f"|robust z| >= {threshold} on period-on-period change (median/MAD)"})
    return out


def volatility(sd: SeriesDef, s: pd.Series) -> dict:
    ch = period_on_period(s, sd).dropna()
    if len(ch) < 4:
        return {"available": False, "reason": "Fewer than 4 changes"}
    recent = ch.iloc[-min(len(ch), 24):]
    return {"available": True, "unit": "pp" if sd.measure_type in PP_TYPES else "%",
            "std_all": float(ch.std()), "std_recent": float(recent.std()), "recent_n": int(len(recent)),
            "mean_abs_change": float(ch.abs().mean()), "n": int(len(ch))}


def historical_context(s: pd.Series) -> dict:
    c = s.dropna()
    if c.empty:
        return {}
    last = float(c.iloc[-1])
    ten = c[c.index >= c.index[-1] - pd.DateOffset(years=10)]
    pct = float(sps.percentileofscore(ten.values, last, kind="weak")) if len(ten) > 2 else None
    higher_before = c[c > last]
    lower_before = c[c < last]
    return {
        "min": float(c.min()), "min_at": c.idxmin().date().isoformat(),
        "max": float(c.max()), "max_at": c.idxmax().date().isoformat(),
        "mean_10y": float(ten.mean()) if len(ten) else None, "percentile_10y": pct,
        "last_higher": higher_before.index[-1].date().isoformat() if len(higher_before) else None,
        "last_lower": lower_before.index[-1].date().isoformat() if len(lower_before) else None,
        "first": c.index[0].date().isoformat(), "count": int(len(c)),
    }


def to_frequency(s: pd.Series, freq: str) -> pd.Series:
    """Aggregate to a lower frequency by mean of observations within each target period."""
    c = s.dropna()
    if c.empty:
        return c
    rule = {"A": "YS", "Q": "QS", "M": "MS", "W": "W-MON", "D": "D"}[freq]
    return c.resample(rule).mean().dropna()


def common_frequency(a: SeriesDef, b: SeriesDef) -> str:
    fa, fb = a.frequency, b.frequency
    f = fa if FREQ_ORDER[fa] >= FREQ_ORDER[fb] else fb
    return "D" if f == "HH" else f


def stationary_view(sd: SeriesDef, s: pd.Series) -> pd.Series:
    return period_on_period(s, sd)


def _corr(x: pd.Series, y: pd.Series) -> dict:
    df = pd.concat([x, y], axis=1).dropna()
    n = len(df)
    if n < 8 or df.iloc[:, 0].std() == 0 or df.iloc[:, 1].std() == 0:
        return {"n": n, "pearson": None, "spearman": None, "p_value": None}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        r, p = sps.pearsonr(df.iloc[:, 0], df.iloc[:, 1])
        rho, _ = sps.spearmanr(df.iloc[:, 0], df.iloc[:, 1])
    # Fisher-z 95% interval for Pearson r.
    ci = None
    if n > 3 and abs(r) < 1:
        z, se = math.atanh(r), 1 / math.sqrt(n - 3)
        ci = [math.tanh(z - 1.96 * se), math.tanh(z + 1.96 * se)]
    return {"n": n, "pearson": float(r), "spearman": float(rho), "p_value": float(p), "pearson_ci95": ci,
            "start": df.index[0].date().isoformat(), "end": df.index[-1].date().isoformat()}


def correlate(a_def: SeriesDef, a: pd.Series, b_def: SeriesDef, b: pd.Series, *, max_lag: int = 12,
              basis: str = "changes") -> dict:
    f = common_frequency(a_def, b_def)
    xa, xb = to_frequency(a, f), to_frequency(b, f)
    if basis == "changes":
        va, vb = stationary_view(a_def, xa), stationary_view(b_def, xb)
        basis_desc = (f"Period-on-period changes at {f} frequency ({'pp' if a_def.measure_type in PP_TYPES else '%'}"
                      f" for {a_def.id}, {'pp' if b_def.measure_type in PP_TYPES else '%'} for {b_def.id}).")
    else:
        va, vb = xa, xb
        basis_desc = f"Levels at {f} frequency. Trending levels often show spurious correlation."
    contemporaneous = _corr(va, vb)
    lags = []
    for k in range(-max_lag, max_lag + 1):
        res = _corr(va, vb.shift(k))  # k>0: b leads a by k periods
        lags.append({"lag": k, "pearson": res["pearson"], "n": res["n"]})
    valid = [l for l in lags if l["pearson"] is not None]
    best = max(valid, key=lambda l: abs(l["pearson"])) if valid else None
    warnings_ = [ASSOCIATION_NOTE]
    if basis == "levels":
        warnings_.append("Levels of trending series are frequently correlated by coincidence; prefer 'changes'.")
    if contemporaneous["n"] < 24:
        warnings_.append(f"Only {contemporaneous['n']} overlapping observations; estimates are imprecise.")
    if best and best["lag"] != 0:
        warnings_.append("A peak at a non-zero lag indicates timing of co-movement, not that the leading series "
                         "predicts or causes the other. Testing many lags inflates the chance of a spurious peak.")
    return {"frequency": f, "basis": basis, "basis_description": basis_desc,
            "aggregation": f"Each series averaged within {f} periods before comparison.",
            "contemporaneous": contemporaneous, "lags": lags, "best_lag": best,
            "lag_convention": f"lag k > 0 means {b_def.id} is shifted k periods earlier (it leads {a_def.id}).",
            "warnings": warnings_}


def decompose(sd: SeriesDef, s: pd.Series) -> dict:
    from statsmodels.tsa.seasonal import STL

    period = {"M": 12, "Q": 4}.get(sd.frequency)
    c = s.dropna()
    if not period or sd.seasonal_adjustment != "NSA":
        return {"available": False, "reason": "Decomposition is only justified for NSA monthly/quarterly data."}
    c = c.asfreq("MS" if period == 12 else "QS")
    if c.isna().any():
        c = c.interpolate(limit=2)
    c = c.dropna()
    if len(c) < 3 * period:
        return {"available": False, "reason": f"Needs at least {3 * period} consecutive observations."}
    c = c.iloc[-min(len(c), 20 * period):]
    res = STL(c, period=period, robust=True).fit()
    var_resid = float(np.var(res.resid))
    strength = max(0.0, 1 - var_resid / float(np.var(res.seasonal + res.resid))) if np.var(res.seasonal + res.resid) else 0
    return {"available": True, "method": f"STL (robust, period={period}) on the last {len(c)} observations",
            "seasonal_strength": strength,
            "points": [{"period_start": i.date().isoformat(), "trend": float(t), "seasonal": float(se),
                        "resid": float(r)} for i, t, se, r in zip(c.index, res.trend, res.seasonal, res.resid)],
            "caveat": "Descriptive decomposition, not the publisher's official seasonal adjustment."}


def scenario(sd: SeriesDef, s: pd.Series, *, mode: str, periods: int, value: float | None = None,
             lookback: int = 12) -> dict:
    """Transparent what-if projection. Not a forecast."""
    c = s.dropna()
    if c.empty:
        return {"available": False, "reason": "No data"}
    periods = max(1, min(periods, 60))
    pp = sd.measure_type in PP_TYPES
    last_ts, last = c.index[-1], float(c.iloc[-1])
    if mode == "flat":
        step, formula = 0.0, "x[t+1] = x[t]"
    elif mode == "custom":
        if value is None:
            return {"available": False, "reason": "Custom scenario requires a value"}
        step = float(value)
        formula = f"x[t+1] = x[t] {'+' if step >= 0 else '-'} {abs(step)}{' pp' if pp else '%'} per period" if pp else \
            f"x[t+1] = x[t] * (1 + {step}/100)"
    elif mode == "trend":
        ch = period_on_period(c, sd).dropna().iloc[-lookback:]
        if ch.empty:
            return {"available": False, "reason": "Not enough history"}
        step = float(ch.mean())
        formula = (f"x[t+1] = x[t] + mean change of last {len(ch)} periods ({step:.3f} pp)" if pp else
                   f"x[t+1] = x[t] * (1 + mean % change of last {len(ch)} periods ({step:.3f}%)/100)")
    else:
        return {"available": False, "reason": f"Unknown mode {mode}"}
    off = {"M": pd.DateOffset(months=1), "Q": pd.DateOffset(months=3), "A": pd.DateOffset(years=1),
           "W": pd.Timedelta(weeks=1), "D": pd.Timedelta(days=1), "HH": pd.Timedelta(minutes=30)}[sd.frequency]
    pts, x, t = [], last, last_ts
    for _ in range(periods):
        x = x + step if pp else x * (1 + step / 100)
        t = t + off
        pts.append({"period_start": t.date().isoformat(), "value": x})
    return {"available": True, "mode": mode, "step": step, "step_unit": "pp" if pp else "%", "formula": formula,
            "start": {"period_start": last_ts.date().isoformat(), "value": last}, "points": pts,
            "label": "Scenario (mechanical what-if) - not a forecast and not an official projection."}
