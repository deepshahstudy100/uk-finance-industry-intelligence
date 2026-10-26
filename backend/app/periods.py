"""Canonical period keys.

  A  -> "2026"            Q -> "2026-Q3"         M -> "2026-09"
  W  -> "2026-10-19"      D -> "2026-10-23"      HH -> "2026-10-26T12:30Z"

Each key maps to an inclusive [start, end] date range so that series of different
frequencies can be aligned for comparison.
"""
from __future__ import annotations

import calendar
import re
from datetime import date, datetime, timedelta, timezone

MONTHS = {m.upper(): i for i, m in enumerate(calendar.month_abbr) if m}
MONTHS_FULL = {m.upper(): i for i, m in enumerate(calendar.month_name) if m}


def month_key(y: int, m: int) -> tuple[str, date, date]:
    last = calendar.monthrange(y, m)[1]
    return f"{y:04d}-{m:02d}", date(y, m, 1), date(y, m, last)


def quarter_key(y: int, q: int) -> tuple[str, date, date]:
    sm = 3 * (q - 1) + 1
    em = sm + 2
    return f"{y:04d}-Q{q}", date(y, sm, 1), date(y, em, calendar.monthrange(y, em)[1])


def year_key(y: int) -> tuple[str, date, date]:
    return f"{y:04d}", date(y, 1, 1), date(y, 12, 31)


def day_key(d: date) -> tuple[str, date, date]:
    return d.isoformat(), d, d


def week_key(d: date) -> tuple[str, date, date]:
    return d.isoformat(), d, d + timedelta(days=6)


def halfhour_key(dt: datetime) -> tuple[str, date, date]:
    dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%MZ"), dt.date(), dt.date()


def parse_ons_date(s: str) -> tuple[str, date, date, str]:
    """ONS website JSON dates: '2026 SEP', '2026 Q3', '2026'. Returns key, start, end, frequency."""
    s = s.strip().upper()
    if m := re.fullmatch(r"(\d{4}) ([A-Z]{3})", s):
        return (*month_key(int(m[1]), MONTHS[m[2]]), "M")
    if m := re.fullmatch(r"(\d{4}) Q([1-4])", s):
        return (*quarter_key(int(m[1]), int(m[2])), "Q")
    if m := re.fullmatch(r"(\d{4})", s):
        return (*year_key(int(m[1])), "A")
    raise ValueError(f"Unrecognised ONS date: {s!r}")


def parse_month_name(s: str) -> tuple[str, date, date]:
    """'September 2026' or 'Sep 2026' or 'June 2026'."""
    parts = s.strip().upper().split()
    if len(parts) != 2:
        raise ValueError(s)
    mon, yr = parts
    m = MONTHS_FULL.get(mon) or MONTHS.get(mon[:3])
    if not m:
        raise ValueError(s)
    return month_key(int(yr), m)


def parse_rolling_window(s: str) -> tuple[str, date, date]:
    """NOMIS APS 'Jul 2025-Jun 2026' -> keyed by the quarter of the end month, spanning the full window."""
    a, b = [p.strip() for p in s.split("-")]
    _, start, _ = parse_month_name(a)
    _, _, end = parse_month_name(b)
    q = (end.month - 1) // 3 + 1
    return f"{end.year:04d}-Q{q}", start, end


def key_for(frequency: str, d: date) -> str:
    if frequency == "A":
        return f"{d.year:04d}"
    if frequency == "Q":
        return f"{d.year:04d}-Q{(d.month - 1) // 3 + 1}"
    if frequency == "M":
        return f"{d.year:04d}-{d.month:02d}"
    return d.isoformat()


FREQ_ORDER = {"HH": 0, "D": 1, "W": 2, "M": 3, "Q": 4, "A": 5}
PERIODS_PER_YEAR = {"D": 365, "W": 52, "M": 12, "Q": 4, "A": 1}
EXPECTED_GAP_DAYS = {"HH": 1 / 48, "D": 1, "W": 7, "M": 31, "Q": 92, "A": 366}
