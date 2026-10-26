"""Retries, backoff, Retry-After, rate limiting, conditional requests and error classification."""
from datetime import datetime, timezone

import httpx
import pytest

from app.connectors.http import CachedResponse, CacheStore, HttpClient, SlidingWindowLimiter, SourceError


def client(handler, cache=None):
    return HttpClient("ecb", transport=httpx.MockTransport(handler), cache=cache)


def test_retries_5xx_then_succeeds(no_sleep):
    calls = {"n": 0}

    def h(req):
        calls["n"] += 1
        return httpx.Response(503 if calls["n"] < 3 else 200, text="ok")

    c = client(h)
    r = c.get("https://example.test/a")
    assert r.status == 200 and calls["n"] == 3
    assert [e["status"] for e in c.request_log] == [503, 503, 200]
    assert len([s for s in no_sleep if s >= 1.0]) >= 2  # exponential backoff waits


def test_retry_after_is_honoured(no_sleep):
    calls = {"n": 0}

    def h(req):
        calls["n"] += 1
        return httpx.Response(429, headers={"Retry-After": "7"}) if calls["n"] == 1 else httpx.Response(200)

    client(h).get("https://example.test/b")
    assert 7.0 in no_sleep


def test_rate_limited_exhaustion_raises(no_sleep):
    c = client(lambda req: httpx.Response(429))
    with pytest.raises(SourceError) as e:
        c.get("https://example.test/c")
    assert e.value.kind == "rate_limited" and len(c.request_log) == c.max_attempts


def test_404_and_401_not_retried(no_sleep):
    c = client(lambda req: httpx.Response(404))
    with pytest.raises(SourceError) as e:
        c.get("https://example.test/d")
    assert e.value.kind == "not_found" and len(c.request_log) == 1
    c2 = client(lambda req: httpx.Response(401))
    with pytest.raises(SourceError) as e2:
        c2.get("https://example.test/e")
    assert e2.value.kind == "auth"


def test_timeouts_retried_then_fail(no_sleep):
    def h(req):
        raise httpx.ReadTimeout("slow", request=req)

    c = client(h)
    with pytest.raises(SourceError) as e:
        c.get("https://example.test/f")
    assert e.value.kind == "timeout" and len(c.request_log) == c.max_attempts


def test_redirect_to_error_page_rejected(no_sleep):
    def h(req):
        if "ErrorPage" in str(req.url):
            return httpx.Response(200, text="<html>error</html>")
        return httpx.Response(302, headers={"Location": "https://example.test/ErrorPage.asp?ei=1"})

    with pytest.raises(SourceError) as e:
        client(h).get("https://example.test/data", reject_redirect_to="ErrorPage")
    assert e.value.kind == "not_found"


class MemCache(CacheStore):
    def __init__(self):
        self.d = {}

    def get(self, key):
        return self.d.get(key)

    def put(self, key, url, resp):
        self.d[key] = resp


def test_conditional_request_uses_etag_and_304(no_sleep):
    cache = MemCache()
    seen = []

    def h(req):
        seen.append(req.headers.get("If-None-Match"))
        if req.headers.get("If-None-Match") == '"v1"':
            return httpx.Response(304)
        return httpx.Response(200, text="body", headers={"ETag": '"v1"'})

    c = client(h, cache)
    assert c.get("https://example.test/g").text() == "body"
    r2 = c.get("https://example.test/g")
    assert r2.text() == "body" and r2.from_cache and seen == [None, '"v1"']


def test_ttl_cache_hit_avoids_network(no_sleep):
    cache = MemCache()
    n = {"c": 0}

    def h(req):
        n["c"] += 1
        return httpx.Response(200, text="x")

    c = client(h, cache)
    c.get("https://example.test/h", cache_ttl_s=60)
    c.get("https://example.test/h", cache_ttl_s=60)
    assert n["c"] == 1 and c.request_log[-1]["via"] == "hit"


def test_sliding_window_limiter_blocks_when_full():
    slept = []
    lim = SlidingWindowLimiter(2, 10.0, sleep=lambda s: slept.append(s) or _advance(lim, s))
    lim.acquire()
    lim.acquire()
    lim.acquire()  # must wait for the window
    assert slept and slept[0] > 9


def _advance(lim, s):
    # Simulate time passing by ageing the recorded calls.
    lim._calls = type(lim._calls)([t - s for t in lim._calls])
