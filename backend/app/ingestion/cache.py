from __future__ import annotations

from datetime import timezone

from ..connectors.http import CacheStore, CachedResponse
from ..db import SessionLocal
from ..models import HttpCacheEntry

MAX_BODY = 25 * 1024 * 1024


class DbCacheStore(CacheStore):
    """HTTP response cache in the main database (PostgreSQL/SQLite). Uses its own short sessions."""

    def get(self, key: str) -> CachedResponse | None:
        with SessionLocal() as s:
            e = s.get(HttpCacheEntry, key)
            if not e:
                return None
            fetched = e.fetched_at if e.fetched_at.tzinfo else e.fetched_at.replace(tzinfo=timezone.utc)
            return CachedResponse(e.status, e.body, e.etag, e.last_modified, e.content_type, fetched)

    def put(self, key: str, url: str, resp: CachedResponse) -> None:
        if len(resp.body) > MAX_BODY:
            return
        with SessionLocal() as s:
            e = s.get(HttpCacheEntry, key) or HttpCacheEntry(key=key)
            e.url, e.status, e.etag, e.last_modified = url[:4000], resp.status, resp.etag, resp.last_modified
            e.content_type, e.body, e.fetched_at = resp.content_type, resp.body, resp.fetched_at
            s.merge(e)
            s.commit()
