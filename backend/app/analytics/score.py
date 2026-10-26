"""Economic Conditions Score - a transparent composite built by this platform (NOT an official statistic).

Method (every step is returned by the API so it can be audited):
  1. Each component is a published monthly series (or a stated arithmetic transform of one).
  2. Values are oriented so that higher = more favourable conditions (direction is stated per component).
  3. Each component is standardised: z = (x - mean) / std over a fixed base window (BASE_START to latest).
  4. Pillar z = mean of its available component z's. Composite z = weighted mean of available pillar z's.
  5. Score = 100 * Phi(composite z), so 50 = historical average; 84 ~ +1 s.d.; 16 ~ -1 s.d.
  6. A month is scored only if >= MIN_PILLARS pillars are available. A component's latest value may be carried
     forward for up to MAX_CARRY months to the scoring month (flagged), never longer.
Only real observations are used; demo (synthetic) data is excluded by construction.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

BASE_START = "2006-01-01"
MAX_CARRY = 3
MIN_PILLARS = 3
INFLATION_TARGET = 2.0  # Bank of England remit: CPI inflation target of 2%


@dataclass(frozen=True)
class Component:
    id: str
    pillar: str
    title: str
    inputs: tuple[str, ...]
    transform: str  # description shown to users
    direction: str  # "higher is better" | "lower is better" | "closer to 2% is better"
    unit: str


COMPONENTS: list[Component] = [
    Component("gdp_3m3m", "growth", "Monthly GDP, 3m-on-3m growth", ("gdp_monthly_index",),
              "% change of the latest 3-month average of the monthly GDP index on the previous 3 months",
              "higher is better", "%"),
    Component("retail_yoy", "growth", "Retail sales volume, year-on-year", ("retail_sales_volume",),
              "% change on the same month a year earlier", "higher is better", "%"),
    Component("unemployment", "labour", "Unemployment rate (16+)", ("unemployment_rate",),
              "level as published", "lower is better", "%"),
    Component("real_pay", "labour", "Regular pay growth minus CPI inflation", ("awe_regular_growth", "cpi_yoy"),
              "AWE regular pay growth (3m avg y/y) minus CPI 12-month rate, same month (approximation; ONS "
              "publishes official real AWE separately)", "higher is better", "pp"),
    Component("cpi_gap", "prices", "CPI inflation distance from 2% target", ("cpi_yoy",),
              "-|CPI 12-month rate - 2|", "closer to 2% is better", "pp"),
    Component("core_gap", "prices", "Core CPI distance from 2%", ("cpi_core_yoy",),
              "-|core CPI 12-month rate - 2| (2% used as the reference; the target applies to headline CPI)",
              "closer to 2% is better", "pp"),
    Component("mortgage_rate", "financial", "2-year fixed mortgage rate (75% LTV)", ("mortgage_2y_75",),
              "level as published", "lower is better", "%"),
    Component("approvals", "financial", "Mortgage approvals for house purchase", ("mortgage_approvals",),
              "level as published (SA)", "higher is better", "number"),
]

PILLARS = {"growth": "Growth", "labour": "Labour market", "prices": "Price stability", "financial": "Financial conditions"}
DEFAULT_WEIGHTS = {p: 1.0 for p in PILLARS}


def _monthly(s: pd.Series) -> pd.Series:
    s = s.dropna()
    if s.empty:
        return s
    s.index = pd.DatetimeIndex(s.index).to_period("M").to_timestamp()
    return s.groupby(level=0).last()


def component_values(c: Component, inputs: dict[str, pd.Series]) -> pd.Series:
    """Raw (oriented-as-published) component values on a monthly index."""
    if c.id == "gdp_3m3m":
        # Reindex to a complete monthly calendar so a missing month yields NaN rather than shifting windows.
        x = _monthly(inputs["gdp_monthly_index"]).asfreq("MS")
        r = x.rolling(3, min_periods=3).mean()
        return ((r / r.shift(3) - 1) * 100).dropna()
    if c.id == "retail_yoy":
        x = _monthly(inputs["retail_sales_volume"])
        prev = x.copy()
        prev.index = prev.index + pd.DateOffset(years=1)
        return ((x / prev.reindex(x.index) - 1) * 100).dropna()
    if c.id == "real_pay":
        a, b = _monthly(inputs["awe_regular_growth"]), _monthly(inputs["cpi_yoy"])
        return (a - b).dropna()
    if c.id == "cpi_gap":
        return -(_monthly(inputs["cpi_yoy"]) - INFLATION_TARGET).abs()
    if c.id == "core_gap":
        return -(_monthly(inputs["cpi_core_yoy"]) - INFLATION_TARGET).abs()
    return _monthly(inputs[c.inputs[0]])


def _orient(c: Component, s: pd.Series) -> pd.Series:
    return -s if c.direction == "lower is better" else s  # gaps are already negated (closer = higher)


def phi(z: float) -> float:
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def band(score: float) -> str:
    if score < 20:
        return "well below historical average"
    if score < 40:
        return "below historical average"
    if score <= 60:
        return "around historical average"
    if score <= 80:
        return "above historical average"
    return "well above historical average"


def compute(inputs: dict[str, pd.Series], weights: dict[str, float] | None = None,
            history_from: str = "2008-01-01") -> dict:
    w = {**DEFAULT_WEIGHTS, **(weights or {})}
    w = {k: max(0.0, float(v)) for k, v in w.items() if k in PILLARS}
    if not any(w.values()):
        raise ValueError("At least one pillar weight must be positive")
    raw: dict[str, pd.Series] = {}
    missing_inputs: list[str] = []
    for c in COMPONENTS:
        if any(i not in inputs or inputs[i].dropna().empty for i in c.inputs):
            missing_inputs.append(c.id)
            continue
        raw[c.id] = component_values(c, inputs)
    if not raw:
        return {"available": False, "reason": "No real input data retrieved yet", "missing_components": missing_inputs}

    last_month = max(s.index.max() for s in raw.values())
    grid = pd.date_range(BASE_START, last_month, freq="MS")
    stats, zs, carried, used_period = {}, {}, {}, {}
    for cid, s in raw.items():
        c = next(x for x in COMPONENTS if x.id == cid)
        o = _orient(c, s)
        base = o[o.index >= pd.Timestamp(BASE_START)]
        mu, sd = float(base.mean()), float(base.std())
        stats[cid] = {"mean": mu, "std": sd, "n": int(base.count())}
        aligned = o.reindex(grid)
        filled = aligned.ffill(limit=MAX_CARRY)
        zs[cid] = (filled - mu) / sd if sd > 0 else filled * np.nan
        carried[cid] = aligned.isna() & filled.notna()
        # which observation month each grid month uses
        src = pd.Series(np.where(aligned.notna(), grid, pd.NaT), index=grid).ffill(limit=MAX_CARRY)
        used_period[cid] = src

    zdf = pd.DataFrame(zs)
    pillar_z = pd.DataFrame({p: zdf[[c.id for c in COMPONENTS if c.pillar == p and c.id in zdf]].mean(axis=1)
                             if any(c.pillar == p and c.id in zdf for c in COMPONENTS) else np.nan
                             for p in PILLARS})
    wser = pd.Series(w)
    avail = pillar_z.notna()
    wsum = (avail * wser).sum(axis=1)
    comp_z = (pillar_z.fillna(0) * wser).sum(axis=1) / wsum.replace(0, np.nan)
    enough = avail.sum(axis=1) >= MIN_PILLARS
    comp_z = comp_z.where(enough)
    valid = comp_z.dropna()
    if valid.empty:
        return {"available": False, "reason": f"Fewer than {MIN_PILLARS} pillars have data", "missing_components": missing_inputs}
    t = valid.index.max()
    # Latest month: at least one component must have a genuinely new (not carried) observation.
    while t in valid.index and not any(not carried[c].get(t, True) and pd.notna(zs[c].get(t)) for c in zs):
        prev = valid.index[valid.index < t]
        if prev.empty:
            break
        t = prev.max()

    cz = float(comp_z[t])
    components = []
    wtot = float(wsum[t])
    for c in COMPONENTS:
        if c.id not in zs:
            components.append({"id": c.id, "pillar": c.pillar, "title": c.title, "inputs": list(c.inputs),
                               "available": False, "reason": "input series has no real data"})
            continue
        z = zs[c.id].get(t)
        n_in_pillar = int(zdf.loc[t, [x.id for x in COMPONENTS if x.pillar == c.pillar and x.id in zdf]].notna().sum())
        contrib = (w[c.pillar] / wtot) * float(z) / n_in_pillar if pd.notna(z) and n_in_pillar and wtot else None
        up = used_period[c.id].get(t)
        rv = raw[c.id].get(up) if pd.notna(up) else None
        components.append({
            "id": c.id, "pillar": c.pillar, "title": c.title, "inputs": list(c.inputs), "transform": c.transform,
            "direction": c.direction, "unit": c.unit, "available": pd.notna(z),
            "value": None if rv is None or pd.isna(rv) else float(rv),
            "period_used": None if pd.isna(up) else pd.Timestamp(up).strftime("%Y-%m"),
            "carried_forward": bool(carried[c.id].get(t, False)),
            "z": None if pd.isna(z) else float(z), "contribution_z": contrib, **stats[c.id],
        })
    pillars = []
    for p, label in PILLARS.items():
        pz = pillar_z.loc[t, p]
        pillars.append({"id": p, "label": label, "weight": w[p], "available": pd.notna(pz),
                        "z": None if pd.isna(pz) else float(pz),
                        "score": None if pd.isna(pz) else 100 * phi(float(pz))})
    hist = []
    for m, z in comp_z.dropna().items():
        if m < pd.Timestamp(history_from) or m > t:
            continue
        hist.append({"period": m.strftime("%Y-%m"), "score": 100 * phi(float(z)), "z": float(z),
                     "pillars": {p: (None if pd.isna(pillar_z.loc[m, p]) else 100 * phi(float(pillar_z.loc[m, p])))
                                 for p in PILLARS}})
    score = 100 * phi(cz)
    prev = [h for h in hist if h["period"] < t.strftime("%Y-%m")]
    yr = [h for h in hist if h["period"] == (t - pd.DateOffset(years=1)).strftime("%Y-%m")]
    return {
        "available": True, "period": t.strftime("%Y-%m"), "score": score, "z": cz, "band": band(score),
        "change_vs_previous": score - prev[-1]["score"] if prev else None,
        "previous_period": prev[-1]["period"] if prev else None,
        "change_vs_year_ago": score - yr[0]["score"] if yr else None,
        "weights": w, "pillars": pillars, "components": components, "history": hist,
        "missing_components": missing_inputs,
        "method": {
            "base_window": f"{BASE_START[:7]} to {last_month.strftime('%Y-%m')}",
            "standardisation": "z = (oriented value - base-window mean) / base-window standard deviation",
            "aggregation": "pillar = mean of component z; composite = weighted mean of available pillar z",
            "mapping": "score = 100 x standard normal CDF(composite z); 50 = historical average",
            "min_pillars": MIN_PILLARS, "max_carry_forward_months": MAX_CARRY,
            "inflation_reference": f"{INFLATION_TARGET}% (Bank of England CPI target)",
        },
        "caveats": [
            "Constructed by this platform from official inputs; it is NOT an official statistic and has no "
            "endorsement from ONS or the Bank of England.",
            "Component choice, direction and weights are judgements. They are shown in full and weights are "
            "adjustable.",
            "History uses the current vintage of each input (revised data), not what was known at the time.",
            "Standardisation uses the full base window, so past scores shift slightly as new data arrive.",
            "A score describes conditions relative to history; it is not a forecast and implies no causation.",
        ],
    }
