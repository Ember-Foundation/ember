"""
Route-level response caches.
StaticCache is compiled by Cython via cache.pxd.
"""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..request import Request
    from ..response import Response, CachedResponse


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
        from ..response import CachedResponse
        if self._cached is None:
            self._cached = CachedResponse.from_response(response)

    def invalidate(self) -> None:
        self._cached = None
