"""
Route-level response caches.
"""
from __future__ import annotations
import asyncio
import time
from typing import Callable, TYPE_CHECKING

from .cached_response import CachedResponse

if TYPE_CHECKING:
    from ember.request import Request
    from ember.response import Response


class CacheEngine:
    """Base interface for route-level response caching."""

    is_async: bool = False
    skip_hooks: bool = True

    def get(self, request: "Request") -> "Response | None":
        raise NotImplementedError

    def store(self, request: "Request", response: "Response") -> None:
        raise NotImplementedError


class StaticCache(CacheEngine):
    """Single-entry cache for routes with no dynamic parameters.

    The first response is stored as a pre-encoded CachedResponse bytes
    object. Every subsequent request to the same route returns those
    bytes directly — no handler invocation, no response encoding.

    In the Cython version, get() and store() are cpdef so they can be
    called from the on_headers_complete cdef path without acquiring the GIL.
    """

    is_async = False
    skip_hooks = True

    def __init__(self) -> None:
        self._cached: "CachedResponse | None" = None

    def get(self, request: "Request") -> "CachedResponse | None":
        return self._cached

    def store(self, request: "Request", response: "Response") -> None:
        if self._cached is None:
            self._cached = CachedResponse.from_response(response)

    def invalidate(self) -> None:
        self._cached = None


def _default_key(request: "Request") -> str:
    qs = getattr(request, "query_string", "") or ""
    if isinstance(qs, (bytes, bytearray)):
        qs = qs.decode("latin-1")
    path = getattr(request, "path", "") or ""
    if isinstance(path, (bytes, bytearray)):
        path = path.decode("latin-1")
    return path + "?" + qs if qs else path


class TTLCache(CacheEngine):
    """Multi-key route cache with TTL, bounded size, and built-in single-flight.

    Three concurrency wins in one engine:

    * **TTL** — entries expire after `ttl` seconds; stale entries fall through
      to the handler instead of being evicted on a timer.
    * **Single-flight** — when N concurrent requests miss the same key, only the
      first runs the handler. The other N-1 await the leader's response and
      return the same bytes. Cuts pool pressure under thundering-herd loads.
    * **Bounded** — at `max_entries` we evict the oldest entry; memory stays flat.

    The default key derives from `request.path + "?" + request.query_string` so
    each unique URL gets its own slot. Pass `key=` for custom partitioning
    (e.g. by user, by Accept header).
    """

    is_async = True
    skip_hooks = True

    def __init__(
        self,
        ttl: float = 1.0,
        max_entries: int = 1024,
        key: Callable[["Request"], str] | None = None,
        coalesce: bool = True,
        wait_timeout: float = 10.0,
    ) -> None:
        self._ttl = ttl
        self._max = max_entries
        self._key_fn = key or _default_key
        self._coalesce = coalesce
        self._wait_timeout = wait_timeout
        self._entries: dict[str, tuple[float, "CachedResponse"]] = {}
        self._inflight: dict[str, asyncio.Future] = {}

    async def get(self, request: "Request") -> "CachedResponse | None":
        key = self._key_fn(request)
        entry = self._entries.get(key)
        if entry is not None and (time.monotonic() - entry[0]) < self._ttl:
            return entry[1]

        if self._coalesce:
            fut = self._inflight.get(key)
            if fut is not None:
                try:
                    return await asyncio.wait_for(fut, timeout=self._wait_timeout)
                except (asyncio.TimeoutError, asyncio.CancelledError):
                    return None
            loop = asyncio.get_event_loop()
            self._inflight[key] = loop.create_future()
        return None

    async def store(self, request: "Request", response: "Response") -> None:
        key = self._key_fn(request)
        cached = CachedResponse.from_response(response)
        if len(self._entries) >= self._max and key not in self._entries:
            oldest = min(self._entries, key=lambda k: self._entries[k][0])
            self._entries.pop(oldest, None)
        self._entries[key] = (time.monotonic(), cached)
        fut = self._inflight.pop(key, None)
        if fut is not None and not fut.done():
            fut.set_result(cached)

    def invalidate(self, key: str | None = None) -> None:
        if key is None:
            self._entries.clear()
        else:
            self._entries.pop(key, None)

    def invalidate_prefix(self, prefix: str) -> None:
        for k in list(self._entries):
            if k.startswith(prefix):
                self._entries.pop(k, None)
