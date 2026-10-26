"""Transformations with explicit statistical-appropriateness rules.

A transformation is refused (with the reason) when it would be misleading for the series' measure
type or frequency - e.g. a percentage change of a rate, or month-on-month change of a rolling
12-month survey estimate presented without caveat.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..periods import PERIODS_PER_YEAR
from ..registry.catalogue import SeriesDef

PP_TYPES = {"rate", "growth_rate", "share"}  # changes expressed in percentage points


@dataclass
class Rule:
    allowed: bool
    reason: str = ""
    caveat: str = ""


def change_unit(sd: SeriesDef) -> str:
    return "pp" if sd.measure_type in PP_TYPES else "%"


def rules(sd: SeriesDef) -> dict[str, Rule]:
    mt, f = sd.measure_type, sd.frequency
    r: dict[str, Rule] = {}
    pp = mt in PP_TYPES
    r["pct_change"] = Rule(not pp, "Not meaningful: this series is a rate/share/growth rate. Percentage change of a "
                                   "percentage conflates scale and direction; use the percentage-point difference."
                           if pp else "")
    r["abs_change"] = Rule(True, caveat="Expressed in percentage points." if pp else
                           ("Index points depend on the base period; prefer % change." if mt == "index" else ""))
    rolling_window = "rolling" in sd.definition.lower() or "rolling" in " ".join(sd.notes).lower()
    pop_caveat = ""
    if sd.seasonal_adjustment == "NSA" and f in ("M", "Q", "W"):
        pop_caveat = "Not seasonally adjusted: period-on-period changes include seasonal effects."
    if rolling_window:
        pop_caveat = (pop_caveat + " " if pop_caveat else "") + ("Values are rolling averages; consecutive "
                                                               "periods overlap, so changes are smoothed and not "
                                                               "independent.")
    if mt == "growth_rate":
        pop_caveat = (pop_caveat + " " if pop_caveat else "") + "Changes in a growth rate are shown in pp."
    r["period_on_period"] = Rule(f != "HH", "Half-hourly data: use rolling means." if f == "HH" else "", pop_caveat)
    yoy_ok = f in PERIODS_PER_YEAR and f != "HH"
    yoy_caveat = ""
    if f == "D":
        yoy_caveat = "Daily data: compared with the nearest earlier observation 365 days before."
    if mt == "growth_rate":
        yoy_caveat = ("This series is already a growth rate, so the year-on-year figure is the difference (pp) "
                      "between the rate now and a year earlier - a measure of acceleration, not growth.")
    r["year_on_year"] = Rule(yoy_ok, "" if yoy_ok else "Frequency does not support year-on-year comparison.",
                             yoy_caveat)
    r["index"] = Rule(mt in ("level", "index", "price"),
                      "" if mt in ("level", "index", "price") else "Rebasing a rate/share to 100 is not meaningful.")
    r["rolling_mean"] = Rule(True)
    r["decomposition"] = Rule(
        sd.seasonal_adjustment == "NSA" and f in ("M", "Q"),
        "" if sd.seasonal_adjustment == "NSA" and f in ("M", "Q") else
        ("Already seasonally adjusted by the publisher; re-decomposing would double-adjust."
         if sd.seasonal_adjustment == "SA" else "Seasonal decomposition needs monthly/quarterly NSA data."),
        "STL decomposition is descriptive; it is not the publisher's official seasonal adjustment.")
    return r


def to_series(rows: list[dict]) -> pd.Series:
    """rows: dicts with period_start (date) and value. Returns float Series indexed by Timestamp."""
    if not rows:
        return pd.Series(dtype=float)
    idx = pd.to_datetime([r["period_start"] for r in rows])
    s = pd.Series([np.nan if r["value"] is None else float(r["value"]) for r in rows], index=idx, dtype=float)
    return s.sort_index()


def period_on_period(s: pd.Series, sd: SeriesDef) -> pd.Series:
    return s.diff() if sd.measure_type in PP_TYPES else s.pct_change(fill_method=None) * 100


def year_on_year(s: pd.Series, sd: SeriesDef) -> pd.Series:
    f = sd.frequency
    pp = sd.measure_type in PP_TYPES
    if f in ("M", "Q", "A", "W"):
        # Require exact calendar match k periods back (guards against gaps shifting the comparison).
        prev = s.copy()
        prev.index = prev.index + (pd.DateOffset(years=1) if f != "W" else pd.Timedelta(weeks=52))
        prev = prev.reindex(s.index)
    elif f == "D":
        prev_idx = s.index - pd.Timedelta(days=365)
        clean = s.dropna()
        pos = clean.index.searchsorted(prev_idx, side="right") - 1
        vals = [clean.iloc[p] if p >= 0 and (clean.index[p] >= prev_idx[i] - pd.Timedelta(days=7)) else np.nan
                for i, p in enumerate(pos)]
        prev = pd.Series(vals, index=s.index, dtype=float)
    else:
        return pd.Series(np.nan, index=s.index)
    return (s - prev) if pp else (s / prev - 1) * 100


def rolling_mean(s: pd.Series, window: int) -> pd.Series:
    return s.rolling(window, min_periods=max(1, window // 2 + 1)).mean()


def rebase(s: pd.Series, base: pd.Timestamp | None = None) -> pd.Series:
    clean = s.dropna()
    if clean.empty:
        return s
    if base is None:
        b = clean.iloc[0]
    else:
        pos = clean.index.searchsorted(base)
        b = clean.iloc[min(pos, len(clean) - 1)]
    return s / b * 100 if b else s * np.nan


def default_window(f: str) -> int:
    return {"HH": 48, "D": 20, "W": 4, "M": 3, "Q": 4, "A": 3}.get(f, 3)
