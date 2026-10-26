import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
FIX = Path(__file__).parent / "fixtures"


def fixture_text(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8-sig")


@pytest.fixture()
def db(tmp_path, monkeypatch):
    """Fresh SQLite database per test with the registry synced. Demo mode defaults to 'fallback'."""
    from app import db as dbmod
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("UKINTEL_DATABASE_URL", f"sqlite:///{tmp_path}/test.db")
    monkeypatch.setenv("UKINTEL_DEMO_MODE", "fallback")
    monkeypatch.setenv("UKINTEL_ADMIN_TOKEN", "")
    get_settings.cache_clear()
    dbmod.reset_engine()
    from app.db import Base, get_engine, session_scope
    from app.ingestion.runner import sync_registry

    Base.metadata.create_all(get_engine())
    with session_scope() as s:
        sync_registry(s)
    yield
    dbmod.reset_engine()
    get_settings.cache_clear()


@pytest.fixture()
def no_sleep(monkeypatch):
    """Make HTTP backoff and rate-limiter waits instantaneous, recording requested delays."""
    slept = []
    import app.connectors.http as h

    monkeypatch.setattr(h.time, "sleep", lambda s: slept.append(s))
    h._limiters.clear()
    return slept
