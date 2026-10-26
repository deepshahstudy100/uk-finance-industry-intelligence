"""Deterministic, explainable findings. Every item cites the values it rests on and is typed:
  fact           - directly read from or computed arithmetically on the displayed observations
  interpretation - a comparison against history, judgement-free but contextual
  hypothesis     - a possible relationship suggested by association; explicitly unproven
"""
from __future__ import annotations

import pandas as pd

from ..periods import key_for
from ..registry.catalogue import SeriesDef
from .transforms import PP_TYPES, period_on_period, year_on_year


def _ordinal(n: int) -> str:
    suf = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suf}"


def _fmt(v: float, sd: SeriesDef) -> str:
    d = sd.decimals
    return f"{v:,.{d}f}"


def build(sd: SeriesDef, s: pd.Series, *, revisions: int = 0, outliers: list[dict] | None = None,
          context: dict | None = None, correlations: list[dict] | None = None) -> list[dict]:
    out: list[dict] = []
    c = s.dropna()
    if c.empty:
        return out
    f = sd.frequency if sd.frequency in ("A", "Q", "M") else "D"
    last_ts, last = c.index[-1], float(c.iloc[-1])
    lk = key_for(f, last_ts.date())
    unit = sd.unit
    out.append({"type": "fact", "text": f"Latest value is {_fmt(last, sd)} {unit} for {lk}.",
                "evidence": [{"period": lk, "value": last}]})
    if len(c) > 1 and sd.frequency != "HH":
        ch = period_on_period(c, sd)
        prev_k = key_for(f, c.index[-2].date())
        u = "pp" if sd.measure_type in PP_TYPES else "%"
        if pd.notna(ch.iloc[-1]):
            direction = "up" if ch.iloc[-1] > 0 else "down" if ch.iloc[-1] < 0 else "unchanged"
            out.append({"type": "fact",
                        "text": f"Compared with {prev_k} ({_fmt(float(c.iloc[-2]), sd)}), it is {direction} "
                                f"{abs(float(ch.iloc[-1])):.2f}{u}.",
                        "evidence": [{"period": prev_k, "value": float(c.iloc[-2])}, {"period": lk, "value": last}]})
    if sd.frequency in ("M", "Q", "W", "D"):
        yy = year_on_year(c, sd)
        if len(yy) and pd.notna(yy.iloc[-1]):
            u = "pp" if sd.measure_type in PP_TYPES else "%"
            lbl = "Difference from a year earlier" if sd.measure_type in PP_TYPES else "Change over the year"
            out.append({"type": "fact", "text": f"{lbl} to {lk}: {float(yy.iloc[-1]):+.2f}{u}.",
                        "evidence": [{"period": lk, "yoy": float(yy.iloc[-1])}]})
    if context:
        if context.get("percentile_10y") is not None:
            p = context["percentile_10y"]
            pos = "high" if p >= 80 else "low" if p <= 20 else "middle"
            out.append({"type": "interpretation",
                        "text": f"The latest value sits at the {_ordinal(round(p))} percentile of the last 10 years "
                                f"(10-year mean {_fmt(context['mean_10y'], sd)}), i.e. in the {pos} part of its "
                                f"recent range.",
                        "evidence": [{"percentile_10y": p, "mean_10y": context["mean_10y"]}]})
        if last >= context.get("max", float("inf")):
            out.append({"type": "fact", "text": f"This is the highest value since the series starts in "
                                                f"{context['first']} (within retrieved history).",
                        "evidence": [{"max": context["max"]}]})
        elif context.get("last_higher"):
            since = key_for(f, pd.Timestamp(context["last_higher"]).date())
            out.append({"type": "fact", "text": f"Highest value since {since}, the last period with a higher value.",
                        "evidence": [{"period": since}]})
    recent_cut = c.index[-min(len(c), 24)].date().isoformat()
    for o in [o for o in (outliers or []) if o["period_start"] >= recent_cut][-3:]:
        out.append({"type": "interpretation",
                    "text": f"Unusually large change in {o['period']}: {o['change']:+.2f}{o['change_unit']} "
                            f"(robust z = {o['robust_z']}).", "evidence": [o]})
    if revisions:
        out.append({"type": "fact", "text": f"{revisions} revision(s) to previously retrieved values have been "
                                            f"detected by this platform.", "evidence": []})
    for c_ in (correlations or [])[:2]:
        r = c_.get("pearson")
        if r is None or abs(r) < 0.5:
            continue
        out.append({"type": "hypothesis",
                    "text": f"Changes in this series have moved {'with' if r > 0 else 'against'} "
                            f"{c_['title']} (r = {r:.2f}, n = {c_['n']}). This is an association only; a common "
                            f"driver or coincidence cannot be ruled out.",
                    "evidence": [c_]})
    return out
