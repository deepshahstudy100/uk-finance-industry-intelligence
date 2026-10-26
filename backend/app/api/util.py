from __future__ import annotations

import math
from datetime import date, datetime, timezone

import numpy as np
import pandas as pd
from fastapi import Header, HTTPException

from ..config import get_settings


def clean(v):
    """Make values JSON-safe (NaN/inf -> None, numpy -> python, timestamps -> ISO)."""
    if isinstance(v, dict):
        return {k: clean(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [clean(x) for x in v]
    if isinstance(v, (np.floating, float)):
        f = float(v)
        return None if not math.isfinite(f) else f
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, pd.Timestamp):
        return v.isoformat()
    if isinstance(v, datetime):
        # All stored timestamps are UTC; emit an explicit offset so clients never parse them as local time.
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(v, date):
        return v.isoformat()
    return v


def parse_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        if len(s) == 4:
            return date(int(s), 1, 1)
        if len(s) == 7:
            return date(int(s[:4]), int(s[5:7]), 1)
        return date.fromisoformat(s[:10])
    except ValueError as e:
        raise HTTPException(422, f"Invalid date {s!r}; use YYYY, YYYY-MM or YYYY-MM-DD") from e


def require_admin(x_admin_token: str | None = Header(default=None)):
    token = get_settings().admin_token
    if token and x_admin_token != token:
        raise HTTPException(403, "Admin token required (X-Admin-Token)")
