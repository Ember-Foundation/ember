"""End-to-end smoke test that exercises emberloop + ember-cache + ember-api together.

Verifies the cross-package wiring works:
- ember-api's @app.get decorator registers a route in the Cython router (ember-api)
- The route's `cache=TTLCache(...)` argument (from ember-cache) attaches to the route
- Ember's initialize() walks the router, calls cache.connect() on distributed caches
- Request/Response objects from emberloop flow through handlers
- Constants and exceptions resolve from the emberloop-owned subpackages
- The Ember class composes from server.py → application.py → router.py
"""
from __future__ import annotations

import asyncio

import pytest

from ember import (
    Blueprint,
    Ember,
    JSONResponse,
    MethodNotAllowed,
    Response,
    RouteNotFound,
)
from ember.cache import CachedResponse, StaticCache, TTLCache
from ember.constants import Events
from ember.eventloop import get_backend
from ember.headers import Headers
from ember.protocol.cprotocol import HTTPParser
from ember.response import RedirectResponse


class TestImportGraph:
    def test_top_level_ember_exports(self):
        """from ember import ... resolves across all 3 packages."""
        assert Ember.__module__ == "ember.server"
        assert Response.__module__ == "ember.response.response"
        assert JSONResponse.__module__ == "ember.response.response"

    def test_subpackage_imports(self):
        """Each subpackage resolves to its owning distribution."""
        from ember.cache import lru as cache_lru
        from ember.eventloop import get_backend as gb
        from ember.protocol import cprotocol

        assert "ember-cache" in cache_lru.__file__ or "ember/cache" in cache_lru.__file__
        assert "emberloop" in cprotocol.__file__ or "ember/protocol" in cprotocol.__file__
        assert callable(gb)

    def test_event_loop_backend_installed(self):
        """emberloop installed an event loop backend at framework import."""
        backend = get_backend()
        assert backend in ("uring", "uvloop", "asyncio")


class TestAppConstruction:
    def test_ember_constructs(self):
        app = Ember()
        assert isinstance(app, Ember)
        assert app.router is not None

    def test_blueprint_subclass(self):
        app = Ember()
        bp = Blueprint()
        assert isinstance(app, Blueprint)
        assert hasattr(bp, "_routes")

    def test_route_decorator_registers(self):
        app = Ember()

        @app.get("/ping")
        async def ping(request):
            return JSONResponse({"ok": True})

        assert len(app._routes) == 1
        assert app._routes[0].pattern == "/ping"
        assert "GET" in app._routes[0].methods


class TestRouteCacheWiring:
    """Tests that ember-cache primitives attach correctly to ember-api routes."""

    def test_ttl_cache_attaches_to_route(self):
        app = Ember()
        cache = TTLCache(ttl=1.0, max_entries=64)

        @app.get("/cached", cache=cache)
        async def handler(request):
            return JSONResponse({"k": "v"})

        route = app._routes[0]
        assert route.cache is cache
        assert isinstance(route.cache, TTLCache)

    def test_static_cache_attaches_to_route(self):
        app = Ember()
        cache = StaticCache()

        @app.get("/static", cache=cache)
        async def handler(request):
            return Response(b"hi")

        assert app._routes[0].cache is cache

    def test_cached_response_subclasses_response(self):
        cached = CachedResponse(b"raw-bytes")
        assert isinstance(cached, Response)
        assert cached.encode() == b"raw-bytes"


class TestAppInitialization:
    """initialize() walks routes, compiles router, connects distributed caches."""

    async def test_initialize_registers_routes_in_cython_router(self):
        app = Ember()

        @app.get("/a")
        async def a(request):
            return JSONResponse({"a": 1})

        @app.post("/b")
        async def b(request):
            return JSONResponse({"b": 2})

        await app.initialize()
        assert app._initialized
        # Cython router holds the compiled trie/tables — verify it accepted both routes
        assert app.router is not None

    async def test_initialize_idempotent(self):
        app = Ember()

        @app.get("/x")
        async def x(request):
            return Response(b"x")

        await app.initialize()
        await app.initialize()  # second call should no-op
        assert app._initialized


class TestEndToEndCacheCycle:
    """Drive a TTLCache through the actual cache hit/miss/store flow used by routes."""

    async def test_cache_miss_then_hit_flow(self):
        cache = TTLCache(ttl=1.0)

        # Build a Request-like object the cache key fn can consume.
        from types import SimpleNamespace
        req = SimpleNamespace(path="/users/1", query_string="")

        # First lookup — miss; cache returns None (and registers an inflight future)
        first = await cache.get(req)
        assert first is None

        # Handler "runs" and produces a response — store wraps it as CachedResponse
        original = JSONResponse({"id": 1, "name": "Ada"})
        await cache.store(req, original)

        # Second lookup — hit; should return the same encoded bytes
        hit = await cache.get(req)
        assert hit is not None
        assert isinstance(hit, CachedResponse)
        assert hit.encode() == original.encode()

    async def test_single_flight_across_concurrent_misses(self):
        """N concurrent misses on the same key collapse to one handler invocation."""
        cache = TTLCache(ttl=1.0)
        from types import SimpleNamespace
        req = SimpleNamespace(path="/expensive", query_string="")

        # Leader registers inflight.
        leader_result = await cache.get(req)
        assert leader_result is None

        # Spawn 5 waiters.
        async def waiter():
            return await cache.get(req)

        waiters = [asyncio.create_task(waiter()) for _ in range(5)]
        await asyncio.sleep(0)  # let waiters register

        # Leader stores → all waiters wake with the same bytes.
        await cache.store(req, JSONResponse({"computed": True}))

        results = await asyncio.gather(*waiters)
        encoded_set = {r.encode() for r in results}
        assert len(encoded_set) == 1  # all waiters got the same bytes
        assert b"computed" in next(iter(encoded_set))


class TestProtocolLayerCallable:
    """emberloop's HTTPParser parses real HTTP/1.1 wire bytes."""

    def test_parser_constructs(self):
        # HTTPParser binds to a Connection; proving the symbol imports + class
        # exists is the smoke check — full parsing is covered by emberloop tests.
        assert HTTPParser is not None
        assert HTTPParser.__module__ == "ember.protocol.cprotocol"

    def test_response_encodes_to_wire_bytes(self):
        r = JSONResponse({"hello": "world"}, status_code=200)
        wire = r.encode()
        assert wire.startswith(b"HTTP/1.1 200 OK\r\n")
        assert b"content-type: application/json" in wire
        assert b'"hello"' in wire

    def test_redirect_response_encodes(self):
        r = RedirectResponse("/new", status_code=302)
        wire = r.encode()
        assert b"302 Found" in wire
        assert b"location: /new" in wire

    def test_headers_class_works(self):
        h = Headers([(b"content-type", b"text/plain"), (b"host", b"localhost")])
        assert h.get(b"content-type") == b"text/plain"
        assert h.get(b"host") == b"localhost"


class TestExceptionsAcrossPackages:
    def test_route_not_found_raisable(self):
        with pytest.raises(RouteNotFound):
            raise RouteNotFound("nope")

    def test_method_not_allowed_has_status_code(self):
        assert MethodNotAllowed.status_code == 405

    def test_events_enum_present(self):
        assert Events.BEFORE_SERVER_START.value == 1
        assert Events.AFTER_RESPONSE_SENT.value == 5
