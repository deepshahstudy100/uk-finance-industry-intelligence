"""Source and series status: current | delayed | stale | unavailable | provisional | demo | disabled.

  stale       - our copy has not been refreshed successfully within the source's stale_after_hours.
  delayed     - the publisher's announced next release has passed (+1 day grace) without new data, or the
                latest period is older than is normal for the frequency (heuristic; reason is stated).
  unavailable - no real observations have ever been retrieved.
  provisional - the latest observation is flagged provisional by the source (or by documented practice).
  current     - none of the above.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from dateutil import parser as dparser

from ..registry.catalogue import SeriesDef
from ..registry.sources import SourceDef

# Max normal gap between a period's end and today before we call a series "delayed" (heuristic).
EXPECTED_LAG_DAYS = {"HH": 0.25, "D": 6, "W": 16, "M": 100, "Q": 200, "A": 760}


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def parse_next_release(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return dparser.parse(s, dayfirst=True, fuzzy=True).date()
    except (ValueError, OverflowError):
        return None


def series_status(sd: SeriesDef, src: SourceDef, *, last_success_at: datetime | None, release_date: datetime | None,
                  next_release: str | None, last_period_end: date | None, last_status: str | None,
                  has_real: bool, has_demo: bool, source_enabled: bool = True,
                  now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    reasons: list[str] = []
    if not sd.enabled or not source_enabled:
        return {"status": "disabled", "reasons": ["Disabled in configuration (see source caveats)."]}
    if not has_real:
        if has_demo:
            return {"status": "demo", "reasons": ["No real observations retrieved; showing labelled sample data."]}
        return {"status": "unavailable", "reasons": ["No observations have been retrieved from the source yet."]}
    status = "current"
    lsa = _aware(last_success_at)
    if src.stale_after_hours and (lsa is None or now - lsa > timedelta(hours=src.stale_after_hours)):
        status = "stale"
        age = "never" if lsa is None else f"{(now - lsa).total_seconds() / 3600:.0f} h ago"
        reasons.append(f"Last successful retrieval {age}; expected within {src.stale_after_hours} h.")
    nr = parse_next_release(next_release)
    rd = _aware(release_date)
    if nr and nr + timedelta(days=1) < now.date() and (rd is None or rd.date() < nr):
        if status == "current":
            status = "delayed"
        reasons.append(f"Publisher announced next release {nr.isoformat()}; no newer release retrieved.")
    on_calendar = nr is not None and nr >= now.date()
    if on_calendar:
        reasons.append(f"Next release announced by the publisher: {nr.isoformat()}.")
    # The lag heuristic applies only when the publisher gives no future release date.
    if last_period_end and sd.frequency in EXPECTED_LAG_DAYS and not on_calendar and sd.frequency != "HH":
        lag = (now.date() - last_period_end).days
        limit = sd.max_lag_days or EXPECTED_LAG_DAYS[sd.frequency]
        if lag > limit:
            if status == "current":
                status = "delayed"
            reasons.append(f"Latest period ended {lag} days ago; typical maximum for {sd.frequency} data is "
                           f"~{limit:.0f} days (heuristic).")
    if status == "current" and last_status == "provisional":
        status = "provisional"
        reasons.append("Latest observation is provisional and may be revised.")
    if status == "current":
        reasons.insert(0, "Retrieved within schedule; latest period consistent with the publication calendar.")
    return {"status": status, "reasons": reasons}


def source_status(src: SourceDef, *, enabled: bool, last_success_at: datetime | None, last_attempt_at: datetime | None,
                  consecutive_failures: int, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    if not enabled:
        return {"status": "disabled", "reasons": ["Disabled"]}
    if src.latency_class == "on_demand":
        return {"status": "on_demand", "reasons": ["Queried on demand; not scheduled."]}
    lsa = _aware(last_success_at)
    if lsa is None:
        if last_attempt_at:
            return {"status": "unavailable", "reasons": [f"{consecutive_failures} consecutive failed attempt(s)."]}
        return {"status": "unavailable", "reasons": ["Never retrieved."]}
    age_h = (now - lsa).total_seconds() / 3600
    if age_h > src.stale_after_hours:
        return {"status": "stale", "reasons": [f"Last success {age_h:.0f} h ago (> {src.stale_after_hours} h)."]}
    if consecutive_failures:
        return {"status": "degraded", "reasons": [f"{consecutive_failures} failure(s) since last success."]}
    return {"status": "current", "reasons": [f"Last success {age_h:.1f} h ago."]}
