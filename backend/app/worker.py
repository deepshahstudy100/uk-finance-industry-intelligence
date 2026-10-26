"""Scheduler process. Polls each source at its registry `refresh_minutes` (within documented limits),
staggered so sources do not start simultaneously. Run with: python -m app.worker"""
from __future__ import annotations

import logging
import signal
import time
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler

from .db import session_scope
from .ingestion.runner import run_source
from .ingestion.sweep import health_sweep
from .main import init_db
from .registry.sources import SOURCES

log = logging.getLogger("ukintel.worker")


def _job(source_id: str):
    try:
        res = run_source(source_id, job="scheduled")
        log.info("%s -> %s (fetched=%s inserted=%s revised=%s errors=%d)", source_id, res["status"],
                 res.get("fetched"), res.get("inserted"), res.get("revised"), len(res.get("errors") or []))
    except Exception:  # noqa: BLE001
        log.exception("Scheduled run failed for %s", source_id)


def due_releases(now: datetime | None = None) -> list[str]:
    """ONS series whose publisher-announced release day has arrived (07:00 UK onwards) but whose newer release
    has not yet been retrieved."""
    from zoneinfo import ZoneInfo

    from .ingestion.health import parse_next_release
    from .models import Series

    uk = (now or datetime.now(timezone.utc)).astimezone(ZoneInfo("Europe/London"))
    if uk.hour < 7:
        return []
    due = []
    with session_scope() as s:
        for ser in s.query(Series).filter(Series.source_id == "ons").all():
            nr = parse_next_release(ser.next_release)
            rd = ser.release_date
            if nr and nr <= uk.date() and (rd is None or rd.date() < nr):
                due.append(ser.id)
    return due


def _release_watch():
    ids = due_releases()
    if ids:
        log.info("release watch: %d ONS series due (%s)", len(ids), ", ".join(ids[:6]))
        try:
            run_source("ons", ids, job="release-watch")
        except Exception:  # noqa: BLE001
            log.exception("release watch run failed")


def _sweep():
    with session_scope() as s:
        log.info("health sweep: %s", health_sweep(s))


def main(run_now: bool = True):
    init_db()
    sched = BackgroundScheduler(timezone="UTC", job_defaults={"coalesce": True, "max_instances": 1,
                                                              "misfire_grace_time": 3600})
    delay = 0
    for sid, sd in SOURCES.items():
        if sd.latency_class == "on_demand" or not sd.refresh_minutes:
            continue
        sched.add_job(_job, "interval", minutes=sd.refresh_minutes, args=[sid], id=sid, jitter=60)
        if run_now:
            sched.add_job(_job, "date", run_date=datetime.now(timezone.utc) + timedelta(seconds=delay),
                          args=[sid], id=f"{sid}-boot")
            delay += 20
    sched.add_job(_sweep, "interval", minutes=30, id="sweep")
    # Release-aware polling: fetch ONS series within ~15 minutes of their announced publication.
    sched.add_job(_release_watch, "interval", minutes=15, id="release-watch")
    sched.start()
    log.info("Scheduler started with %d jobs", len(sched.get_jobs()))
    stop = {"flag": False}
    signal.signal(signal.SIGTERM, lambda *_: stop.update(flag=True))
    signal.signal(signal.SIGINT, lambda *_: stop.update(flag=True))
    while not stop["flag"]:
        time.sleep(1)
    sched.shutdown(wait=False)


if __name__ == "__main__":
    main()
