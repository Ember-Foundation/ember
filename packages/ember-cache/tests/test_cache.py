import asyncio
from types import SimpleNamespace

from ember.cache import (
    CachedResponse,
    StaticCache,
    TTLCache,
)
from ember.response import JSONResponse, Response


def make_request(path="/", query_string=""):
    return SimpleNamespace(path=path, query_string=query_string)


class TestCachedResponse:
    def test_from_response_preserves_bytes(self):
        original = JSONResponse({"k": "v"})
        cached = CachedResponse.from_response(original)
        assert cached.encode() == original.encode()

    def test_encode_returns_same_bytes_each_call(self):
        cached = CachedResponse.from_response(Response(b"data"))
        assert cached.encode() is cached.encode()

    def test_subclasses_response(self):
        cached = CachedResponse(b"raw")
        assert isinstance(cached, Response)


class TestStaticCache:
    def test_first_store_wins(self):
        cache = StaticCache()
        req = make_request()
        cache.store(req, Response(b"first"))
        cache.store(req, Response(b"second"))
        assert cache.get(req).encode() == Response(b"first").encode()

    def test_invalidate_clears(self):
        cache = StaticCache()
        cache.store(make_request(), Response(b"x"))
        cache.invalidate()
        assert cache.get(make_request()) is None


class TestTTLCache:
    async def test_hit_within_ttl(self):
        cache = TTLCache(ttl=1.0)
        req = make_request("/a")
        await cache.store(req, Response(b"hit"))
        result = await cache.get(req)
        assert result.encode() == Response(b"hit").encode()

    async def test_miss_after_ttl_expiry(self):
        cache = TTLCache(ttl=0.05, coalesce=False)
        req = make_request("/a")
        await cache.store(req, Response(b"v"))
        await asyncio.sleep(0.1)
        assert await cache.get(req) is None

    async def test_distinct_paths_separate_keys(self):
        cache = TTLCache(ttl=1.0)
        a, b = make_request("/a"), make_request("/b")
        await cache.store(a, Response(b"A"))
        await cache.store(b, Response(b"B"))
        assert (await cache.get(a)).encode() == Response(b"A").encode()
        assert (await cache.get(b)).encode() == Response(b"B").encode()

    async def test_query_string_in_key(self):
        cache = TTLCache(ttl=1.0)
        a = make_request("/x", "?id=1")
        b = make_request("/x", "?id=2")
        await cache.store(a, Response(b"one"))
        assert await cache.get(b) is None

    async def test_max_entries_evicts_oldest(self):
        cache = TTLCache(ttl=10.0, max_entries=2, coalesce=False)
        await cache.store(make_request("/a"), Response(b"A"))
        await asyncio.sleep(0.001)
        await cache.store(make_request("/b"), Response(b"B"))
        await asyncio.sleep(0.001)
        await cache.store(make_request("/c"), Response(b"C"))
        # /a should be evicted (oldest)
        assert await cache.get(make_request("/a")) is None
        assert (await cache.get(make_request("/b"))).encode() == Response(b"B").encode()

    async def test_single_flight_coalescing(self):
        """N concurrent misses → 1 handler run, N-1 waiters get the same bytes."""
        cache = TTLCache(ttl=1.0)
        req = make_request("/coalesce")

        # First get: registers an inflight future and returns None (caller is leader).
        leader = await cache.get(req)
        assert leader is None

        # Second get with the same key: should await the inflight future.
        async def waiter():
            return await cache.get(req)

        waiter_task = asyncio.create_task(waiter())
        await asyncio.sleep(0)  # let waiter register

        # Leader stores the response — fulfills the inflight future for waiters.
        await cache.store(req, Response(b"shared"))

        result = await waiter_task
        assert result is not None
        assert result.encode() == Response(b"shared").encode()

    async def test_invalidate_specific_key(self):
        cache = TTLCache(ttl=10.0, coalesce=False)
        req = make_request("/x")
        await cache.store(req, Response(b"v"))
        cache.invalidate("/x")
        assert await cache.get(req) is None

    async def test_invalidate_prefix(self):
        cache = TTLCache(ttl=10.0, coalesce=False)
        await cache.store(make_request("/users/1"), Response(b"u1"))
        await cache.store(make_request("/users/2"), Response(b"u2"))
        await cache.store(make_request("/posts/1"), Response(b"p1"))
        cache.invalidate_prefix("/users")
        assert await cache.get(make_request("/users/1")) is None
        assert await cache.get(make_request("/users/2")) is None
        assert (await cache.get(make_request("/posts/1"))).encode() == Response(b"p1").encode()
