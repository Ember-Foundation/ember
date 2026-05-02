"""
Pre-encoded response for cache hits.

CachedResponse stores the bytes produced by a previous Response.encode() call
and returns them directly on subsequent encode() invocations — no header
re-build, no body copy, no JSON re-serialization. The cache layer wraps every
stored response in one of these so cache hits are pure byte returns.
"""
from __future__ import annotations

from ember.response import Response


class CachedResponse(Response):
    """Pre-encoded response — encode() returns the stored bytes directly."""

    __slots__ = ("_raw",)

    def __init__(self, raw: bytes) -> None:
        self._raw = raw
        self.body = b""
        self.status_code = 200
        self._headers = {}
        self._header_prefix = b""
        self._cached_bytes = raw

    def encode(self) -> bytes:
        return self._raw

    @classmethod
    def from_response(cls, response: Response) -> "CachedResponse":
        return cls(response.encode())
