"""Ingestion guarantees: revisions, failure handling, demo isolation, stale/delayed status, alerts."""
from datetime import date, datetime, timedelta, timezone

import httpx
import pytest
import respx
from sqlalchemy import func, select

from app.db import session_scope
from app.ingestion.health import series_status, source_status
from app.ingestion.runner import run_source
from app.models import Alert, IngestionRun, Observation, ObservationRevision, Source
from app.registry.catalogue import CATALOGUE
from app.registry.sources import SOURCES
from conftest import fixture_text

IADB = "https://www.bankofengland.co.uk/boeapps/database/_iadb-fromshowcolumns.asp"

DAILY = "DATE,IUDBEDR,IUDSOIA,IUDSNPY,IUDMNPY,IUDLNPY\n01 Oct 2026,3.75,3.73,4.9,5.2,5.5\n02 Oct 2026,3.75,3.74,4.91,5.21,5.51\n"
MONTHLY = "DATE,IUMBV34,IUMBV42,LPMVTVX\n31 Aug 2026,4.92,4.78,54918\n30 Sep 2026,5.13,4.98,55000\n"


def boe_mock(daily=DAILY, monthly=MONTHLY, status=200):
    def h(request):
        codes = request.url.params.get("SeriesCodes", "")
        if status != 200:
            return httpx.Response(status)
        return httpx.Response(200, text=daily if "IUDBEDR" in codes else monthly)

    return h


def count(model, **filters):
    with session_scope() as s:
        q = select(func.count()).select_from(model)
        for k, v in filters.items():
            q = q.where(getattr(model, k) == v)
        return s.scalar(q)


@respx.mock
def test_ingest_then_idempotent_then_revision(db, no_sleep):
    route = respx.get(IADB).mock(side_effect=boe_mock())
    r1 = run_source("boe")
    assert r1["status"] == "success" and r1["inserted"] == 16
    r2 = run_source("boe")
    assert r2["inserted"] == 0 and r2["revised"] == 0  # identical payload: no false revisions
    route.mock(side_effect=boe_mock(monthly=MONTHLY.replace("5.13", "5.10")))
    r3 = run_source("boe")
    assert r3["revised"] == 1
    with session_scope() as s:
        rev = s.scalars(select(ObservationRevision)).one()
        assert (rev.series_id, rev.period, rev.old_value, rev.new_value) == ("mortgage_2y_75", "2026-09", 5.13, 5.10)
        assert s.scalar(select(Alert).where(Alert.kind == "revision")) is not None
        runs = s.scalars(select(IngestionRun).where(IngestionRun.source_id == "boe")).all()
        assert all(r.requests for r in runs)  # every run logs its HTTP requests


@respx.mock
def test_failed_source_never_fabricates_and_keeps_history(db, no_sleep):
    route = respx.get(IADB).mock(side_effect=boe_mock())
    run_source("boe")
    before = count(Observation, series_id="bank_rate", is_demo=False)
    route.mock(side_effect=boe_mock(status=503))
    r = run_source("boe")
    assert r["status"] == "failed"
    assert count(Observation, series_id="bank_rate", is_demo=False) == before  # nothing written or deleted
    with session_scope() as s:
        src = s.get(Source, "boe")
        assert src.consecutive_failures == 1 and src.last_error
        a = s.scalars(select(Alert).where(Alert.kind == "source_failure")).all()
        assert a and all("nothing was substituted" in x.detail for x in a)


@respx.mock
def test_schema_change_is_rejected_not_ingested(db, no_sleep):
    respx.get(IADB).mock(return_value=httpx.Response(200, text="<html>Service unavailable</html>"))
    r = run_source("boe")
    assert r["status"] == "failed"
    assert count(Observation, is_demo=False) == 0
    with session_scope() as s:
        assert s.scalar(select(Alert).where(Alert.kind == "validation")) is not None


@respx.mock
def test_recovery_resolves_failure_alerts(db, no_sleep):
    route = respx.get(IADB).mock(side_effect=boe_mock(status=500))
    run_source("boe")
    route.mock(side_effect=boe_mock())
    run_source("boe")
    with session_scope() as s:
        active = s.scalars(select(Alert).where(Alert.kind == "source_failure", Alert.active.is_(True))).all()
        assert active == []
        assert s.get(Source, "boe").consecutive_failures == 0


def test_status_rules():
    sd, src = CATALOGUE["cpi_yoy"], SOURCES["ons"]
    now = datetime(2026, 10, 26, tzinfo=timezone.utc)
    base = dict(release_date=datetime(2026, 10, 21, tzinfo=timezone.utc), next_release="18 November 2026",
                last_period_end=date(2026, 9, 30), last_status="normal", has_real=True, has_demo=False, now=now)
    assert series_status(sd, src, last_success_at=now - timedelta(hours=2), **base)["status"] == "current"
    assert series_status(sd, src, last_success_at=now - timedelta(days=5), **base)["status"] == "stale"
    late = {**base, "next_release": "20 October 2026", "release_date": datetime(2026, 9, 16, tzinfo=timezone.utc)}
    st = series_status(sd, src, last_success_at=now, **late)
    assert st["status"] == "delayed" and "2026-10-20" in st["reasons"][0]
    prov = {**base, "last_status": "provisional"}
    assert series_status(sd, src, last_success_at=now, **prov)["status"] == "provisional"
    none = {**base, "has_real": False}
    assert series_status(sd, src, last_success_at=None, **none)["status"] == "unavailable"
    assert series_status(sd, src, last_success_at=None, **{**none, "has_demo": True})["status"] == "demo"
    # Publisher calendar overrides the lag heuristic
    q = CATALOGUE["productivity_oph"]
    cal = {**base, "last_period_end": date(2026, 3, 31), "next_release": "17 November 2026"}
    assert series_status(q, src, last_success_at=now, **cal)["status"] == "current"
    nocal = {**cal, "next_release": None}
    assert series_status(q, src, last_success_at=now, **nocal)["status"] == "delayed"


def test_source_status():
    src = SOURCES["neso_carbon"]
    now = datetime(2026, 10, 26, 12, tzinfo=timezone.utc)
    assert source_status(src, enabled=True, last_success_at=now - timedelta(minutes=40), last_attempt_at=now,
                         consecutive_failures=0, now=now)["status"] == "current"
    assert source_status(src, enabled=True, last_success_at=now - timedelta(hours=5), last_attempt_at=now,
                         consecutive_failures=3, now=now)["status"] == "stale"
    assert source_status(src, enabled=True, last_success_at=None, last_attempt_at=now, consecutive_failures=2,
                         now=now)["status"] == "unavailable"


def test_release_watch_finds_series_whose_release_day_arrived(db):
    from app.db import session_scope
    from app.models import Series
    from app.worker import due_releases

    with session_scope() as s:
        a, b = s.get(Series, "cpi_yoy"), s.get(Series, "gdp_qoq")
        a.next_release, a.release_date = "18 November 2026", datetime(2026, 10, 20, 23, tzinfo=timezone.utc)
        b.next_release, b.release_date = "12 November 2026", datetime(2026, 9, 29, 23, tzinfo=timezone.utc)
    at = datetime(2026, 11, 12, 7, 5, tzinfo=timezone.utc)  # 07:05 UK (GMT in November)
    assert due_releases(at) == ["gdp_qoq"]
    assert due_releases(datetime(2026, 11, 12, 6, 30, tzinfo=timezone.utc)) == []  # before 07:00 UK
