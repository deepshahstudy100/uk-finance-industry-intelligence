"""Polite HTTP client: per-source rate limiting, retries with exponential backoff + jitter,
Retry-After handling, conditional requests (ETag / Last-Modified) and a request log for provenance."""
from __future__ import annotations

import hashlib
import random
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

import httpx

from ..config import get_settings
from ..registry.sources import SOURCES


class SourceError(Exception):
    def __init__(self, message: str, *, kind: str = "http", status: int | None = None, url: str | None = None):
        super().__init__(message)
        self.kind = kind  # http | timeout | validation | rate_limited | auth | disabled | not_found
        self.status = status
        self.url = url

    def to_dict(self) -> dict:
        return {"kind": self.kind, "status": self.status, "url": self.url, "message": str(self)}


class SlidingWindowLimiter:
    """Allows at most `requests` calls in any `per_seconds` window (thread-safe)."""

    def __init__(self, requests: int, per_seconds: float, sleep: Callable[[float], None] | None = None):
        self.requests = max(1, requests)
        self.per = per_seconds
        self._calls: deque[float] = deque()
        self._lock = threading.Lock()
        self._sleep = sleep or (lambda secs: time.sleep(secs))

    def acquire(self) -> float:
        waited = 0.0
        while True:
            with self._lock:
                now = time.monotonic()
                while self._calls and now - self._calls[0] >= self.per:
                    self._calls.popleft()
                if len(self._calls) < self.requests:
                    self._calls.append(now)
                    return waited
                wait = self.per - (now - self._calls[0]) + 0.01
            self._sleep(wait)
            waited += wait


_limiters: dict[str, SlidingWindowLimiter] = {}
_limiters_lock = threading.Lock()


def limiter_for(source_id: str) -> SlidingWindowLimiter:
    with _limiters_lock:
        if source_id not in _limiters:
            rl = SOURCES[source_id].rate_limit
            # Stay at or below 80% of documented limits.
            req = rl.requests if not rl.documented else max(1, int(rl.requests * 0.8))
            _limiters[source_id] = SlidingWindowLimiter(req, rl.per_seconds)
        return _limiters[source_id]


@dataclass
class CachedResponse:
    status: int
    body: bytes
    etag: str | None
    last_modified: str | None
    content_type: str | None
    fetched_at: datetime


class CacheStore:
    """Interface; the DB-backed implementation lives in ingestion/cache.py."""

    def get(self, key: str) -> CachedResponse | None:  # pragma: no cover - interface
        return None

    def put(self, key: str, url: str, resp: CachedResponse) -> None:  # pragma: no cover - interface
        pass


@dataclass
class Response:
    url: str
    status: int
    body: bytes
    content_type: str | None
    from_cache: bool
    fetched_at: datetime

    def text(self) -> str:
        return self.body.decode("utf-8-sig", errors="replace")

    def json(self) -> Any:
        import json

        return json.loads(self.body)


@dataclass
class HttpClient:
    source_id: str
    request_log: list[dict] = field(default_factory=list)
    cache: CacheStore | None = None
    transport: httpx.BaseTransport | None = None
    sleep: Callable[[float], None] | None = None  # None -> time.sleep resolved at call time

    def __post_init__(self):
        s = get_settings()
        self._client = httpx.Client(
            timeout=s.http_timeout_s,
            headers={"User-Agent": s.user_agent, "Accept-Encoding": "gzip, deflate"},
            follow_redirects=False,
            transport=self.transport,
        )
        self.max_attempts = s.http_max_attempts

    def close(self):
        self._client.close()

    def request(
        self,
        method: str,
        url: str,
        *,
        params: dict | None = None,
        data: dict | None = None,
        headers: dict | None = None,
        auth: tuple[str, str] | None = None,
        cache_ttl_s: float | None = None,
        conditional: bool = True,
        follow_redirects: bool = True,
        reject_redirect_to: str | None = None,
    ) -> Response:
        full_url = str(httpx.URL(url, params=params)) if params else url
        key = hashlib.sha256((method + full_url + repr(sorted((data or {}).items()))).encode()).hexdigest()
        cached = self.cache.get(key) if self.cache else None
        now = datetime.now(timezone.utc)
        if cached and cache_ttl_s and (now - cached.fetched_at).total_seconds() < cache_ttl_s:
            self._log(full_url, cached.status, 0, 0.0, len(cached.body), "hit")
            return Response(full_url, cached.status, cached.body, cached.content_type, True, cached.fetched_at)

        hdrs = dict(headers or {})
        if cached and conditional:
            if cached.etag:
                hdrs["If-None-Match"] = cached.etag
            if cached.last_modified:
                hdrs["If-Modified-Since"] = cached.last_modified

        limiter = limiter_for(self.source_id)
        last_exc: SourceError | None = None
        for attempt in range(1, self.max_attempts + 1):
            limiter.acquire()
            t0 = time.monotonic()
            try:
                r = self._client.request(method, full_url, data=data, headers=hdrs, auth=auth)
                hops = 0
                while (follow_redirects and r.status_code in (301, 302, 303, 307, 308)
                       and r.headers.get("location") and hops < 5):
                    loc = r.headers.get("location", "")
                    if reject_redirect_to and reject_redirect_to.lower() in loc.lower():
                        raise SourceError(f"Source redirected to error page ({loc})", kind="not_found",
                                          status=r.status_code, url=full_url)
                    r = self._client.request("GET", str(r.url.join(loc)))
                    hops += 1
            except httpx.TimeoutException:
                ms = (time.monotonic() - t0) * 1000
                self._log(full_url, None, attempt, ms, 0, "timeout")
                last_exc = SourceError("Request timed out", kind="timeout", url=full_url)
                self._backoff(attempt, None)
                continue
            except httpx.TransportError as e:
                ms = (time.monotonic() - t0) * 1000
                self._log(full_url, None, attempt, ms, 0, f"transport:{type(e).__name__}")
                last_exc = SourceError(f"Network error: {e}", kind="http", url=full_url)
                self._backoff(attempt, None)
                continue
            ms = (time.monotonic() - t0) * 1000
            status = r.status_code
            if status == 304 and cached:
                self._log(full_url, 304, attempt, ms, len(cached.body), "revalidated")
                if self.cache:
                    self.cache.put(key, full_url, CachedResponse(cached.status, cached.body, cached.etag,
                                                                 cached.last_modified, cached.content_type, now))
                return Response(full_url, cached.status, cached.body, cached.content_type, True, now)
            self._log(full_url, status, attempt, ms, len(r.content), "network")
            if status == 429 or status >= 500:
                kind = "rate_limited" if status == 429 else "http"
                last_exc = SourceError(f"HTTP {status}", kind=kind, status=status, url=full_url)
                self._backoff(attempt, r.headers.get("retry-after"))
                continue
            if status in (401, 403):
                raise SourceError(f"HTTP {status}: authorisation required or refused", kind="auth",
                                  status=status, url=full_url)
            if status == 404:
                raise SourceError("HTTP 404: not found", kind="not_found", status=404, url=full_url)
            if status >= 400:
                raise SourceError(f"HTTP {status}: {r.text[:200]}", kind="http", status=status, url=full_url)
            resp = Response(full_url, status, r.content, r.headers.get("content-type"), False, now)
            if self.cache:
                self.cache.put(key, full_url, CachedResponse(status, r.content, r.headers.get("etag"),
                                                             r.headers.get("last-modified"),
                                                             r.headers.get("content-type"), now))
            return resp
        assert last_exc is not None
        raise last_exc

    def get(self, url: str, **kw) -> Response:
        return self.request("GET", url, **kw)

    def post(self, url: str, **kw) -> Response:
        return self.request("POST", url, **kw)

    def _backoff(self, attempt: int, retry_after: str | None) -> None:
        if attempt >= self.max_attempts:
            return
        delay = None
        if retry_after:
            try:
                delay = float(retry_after)
            except ValueError:
                delay = None
        if delay is None:
            delay = min(60.0, (2 ** (attempt - 1)) * 1.0) + random.uniform(0, 0.5)
        (self.sleep or time.sleep)(min(delay, 120.0))

    def _log(self, url, status, attempt, ms, size, via):
        self.request_log.append({
            "url": url, "status": status, "attempt": attempt, "ms": round(ms, 1), "bytes": size, "via": via,
            "at": datetime.now(timezone.utc).isoformat(),
        })
