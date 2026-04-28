# cython: language_level=3, boundscheck=False, wraparound=False, cdivision=True
"""
Cython response classes.

Key optimisations vs the pure-Python version:
- ujson/json selected ONCE at module import — no try/except per JSONResponse
- Response._header_prefix built in __init__ — no .encode('latin-1') per send()
- Response, JSONResponse, CachedResponse are cdef classes — C-typed fields,
  no __dict__, cpdef send/encode avoids Python method dispatch from hot path
- StreamingResponse / SSEResponse / TokenStreamResponse stay as Python classes
  (async generators and complex async methods; Cython gain there is minimal)
"""

import asyncio
import json as _stdlib_json
from typing import Any, AsyncGenerator, TYPE_CHECKING

from ember.constants import (
    STATUS_CODES, HTTP_PREFIX, CRLF,
    CONTENT_TYPE_JSON, CONTENT_TYPE_SSE,
)

if TYPE_CHECKING:
    from ember.protocol.protocol import Connection
    from ember.ai.ratelimit.token_bucket import TokenBucket

# ── Module-level JSON encoder — chosen once, never re-imported ───────────────

try:
    import orjson as _fast_json
    _HAS_ORJSON = True
except ImportError:
    _HAS_ORJSON = False

cdef inline bytes _json_encode(object data):
    if _HAS_ORJSON:
        return _fast_json.dumps(data)   # orjson returns bytes directly — no encode step
    return _stdlib_json.dumps(
        data, separators=(',', ':'), ensure_ascii=False
    ).encode('utf-8')


# ── Header prefix builder — called once in __init__, not on every send ───────

cdef bytes _build_prefix(int status_code, dict headers):
    """Build 'HTTP/1.1 <status>\r\n<headers>\r\n' as bytes once."""
    cdef list lines = [HTTP_PREFIX + STATUS_CODES.get(status_code, b'200 OK') + CRLF]
    for k, v in headers.items():
        lines.append(k.encode('latin-1') + b': ' + v.encode('latin-1') + CRLF)
    return b''.join(lines)


# ── Response ──────────────────────────────────────────────────────────────────

cdef class Response:
    """Base HTTP response with pre-encoded header prefix."""

    def __init__(
        self,
        body=b'',
        int status_code=200,
        dict headers=None,
        bytes content_type=b'text/plain; charset=utf-8',
    ):
        if isinstance(body, str):
            body = (<str>body).encode('utf-8')
        self.body         = body
        self.status_code  = status_code
        self._headers     = dict(headers) if headers else {}
        self._cached_bytes = None

        if content_type:
            ct_key = 'content-type'
            if ct_key not in {k.lower() for k in self._headers}:
                self._headers[ct_key] = content_type.decode('latin-1')

        self._header_prefix = _build_prefix(status_code, self._headers)

    cpdef bytes _encode_headers(self):
        return (
            self._header_prefix
            + b'content-length: ' + str(len(self.body)).encode() + CRLF
            + CRLF
        )

    cpdef bytes encode(self):
        if self._cached_bytes is None:
            self._cached_bytes = self._encode_headers() + self.body
        return self._cached_bytes

    cpdef void send(self, object protocol):
        protocol.transport.write(self.encode())
        protocol.after_response(self)


# ── JSONResponse ──────────────────────────────────────────────────────────────

cdef class JSONResponse(Response):
    """Serialize Python object to JSON, header prefix pre-encoded."""

    def __init__(self, object data, int status_code=200, dict headers=None):
        super().__init__(
            body=_json_encode(data),
            status_code=status_code,
            headers=headers,
            content_type=CONTENT_TYPE_JSON,
        )


# ── CachedResponse ────────────────────────────────────────────────────────────

cdef class CachedResponse(Response):
    """Pre-encoded response — encode() returns the stored bytes directly."""

    def __init__(self, bytes raw):
        self.body           = b''
        self.status_code    = 200
        self._headers       = {}
        self._header_prefix = b''
        self._cached_bytes  = raw

    cpdef bytes encode(self):
        return self._cached_bytes

    @classmethod
    def from_response(cls, Response response):
        return cls(response.encode())


# ── RedirectResponse ──────────────────────────────────────────────────────────

class RedirectResponse(Response):
    def __init__(self, location: str, status_code: int = 302):
        super().__init__(
            body=b'',
            status_code=status_code,
            headers={'location': location},
            content_type=b'',
        )


# ── StreamingResponse ─────────────────────────────────────────────────────────

class StreamingResponse(Response):
    """Chunked-transfer response backed by an async generator."""

    def __init__(
        self,
        stream: 'AsyncGenerator[bytes, None]',
        status_code: int = 200,
        headers: dict | None = None,
        content_type: bytes = b'application/octet-stream',
        complete_timeout: int = 300,
        chunk_timeout: int = 30,
    ):
        self.stream           = stream
        self.complete_timeout = complete_timeout
        self.chunk_timeout    = chunk_timeout
        merged = dict(headers) if headers else {}
        ct_key = 'content-type'
        if ct_key not in {k.lower() for k in merged}:
            merged[ct_key] = content_type.decode('latin-1')
        # Let Response.__init__ initialise all cdef fields properly.
        super().__init__(body=b'', status_code=status_code,
                         headers=merged, content_type=b'')

    def _encode_headers(self) -> bytes:
        lines = [HTTP_PREFIX + STATUS_CODES.get(self.status_code, b'200 OK') + CRLF]
        for k, v in self._headers.items():
            lines.append(k.encode('latin-1') + b': ' + v.encode('latin-1') + CRLF)
        lines.append(b'transfer-encoding: chunked' + CRLF)
        lines.append(CRLF)
        return b''.join(lines)

    def send(self, protocol) -> None:
        protocol.transport.write(self._encode_headers())
        asyncio.get_running_loop().create_task(self._stream_loop(protocol))

    async def _stream_loop(self, protocol) -> None:
        try:
            async for chunk in self.stream:
                if not isinstance(chunk, bytes):
                    chunk = chunk.encode('utf-8')
                frame = ('{:X}\r\n'.format(len(chunk))).encode() + chunk + b'\r\n'
                protocol.transport.write(frame)
                if not protocol.writable:
                    await protocol.write_permission.wait()
                    protocol.write_permission.clear()
            protocol.transport.write(b'0\r\n\r\n')
        finally:
            protocol.after_response(self)


# ── SSEResponse ───────────────────────────────────────────────────────────────

class SSEResponse(StreamingResponse):
    """Server-Sent Events response for streaming LLM token output."""

    SSE_HEADERS = {
        'content-type': 'text/event-stream; charset=utf-8',
        'cache-control': 'no-cache',
        'x-accel-buffering': 'no',
    }

    def __init__(
        self,
        stream: 'AsyncGenerator[str, None]',
        status_code: int = 200,
        headers: dict | None = None,
        event_type: str = 'message',
        retry_ms: int = 3000,
        include_done_sentinel: bool = True,
        complete_timeout: int = 300,
        chunk_timeout: int = 30,
    ):
        merged = {**self.SSE_HEADERS, **(headers or {})}
        super().__init__(
            stream=self._token_to_bytes(stream),
            status_code=status_code,
            headers=merged,
            complete_timeout=complete_timeout,
            chunk_timeout=chunk_timeout,
        )
        self.event_type            = event_type.encode('utf-8')
        self.retry_ms              = retry_ms
        self._id_counter           = 0
        self.include_done_sentinel = include_done_sentinel

    def _format_event(self, data: bytes) -> bytes:
        self._id_counter += 1
        return (
            b'id: ' + str(self._id_counter).encode() + b'\n'
            b'event: ' + self.event_type + b'\n'
            b'data: ' + data + b'\n\n'
        )

    def _format_done(self) -> bytes:
        return b'data: [DONE]\n\n'

    def _format_retry(self) -> bytes:
        return b'retry: ' + str(self.retry_ms).encode() + b'\n\n'

    async def _token_to_bytes(self, source: 'AsyncGenerator[str, None]'):
        yield self._format_retry()
        async for token in source:
            if not isinstance(token, bytes):
                token = token.encode('utf-8')
            yield self._format_event(token)
        if self.include_done_sentinel:
            yield self._format_done()

    def send(self, protocol) -> None:
        protocol.transport.write(self._encode_headers())
        asyncio.get_running_loop().create_task(self._stream_loop(protocol))


# ── TokenStreamResponse ───────────────────────────────────────────────────────

class TokenStreamResponse(SSEResponse):
    """SSE response with per-token rate-limiting against a TokenBucket."""

    def __init__(
        self,
        stream: 'AsyncGenerator[str, None]',
        bucket: 'TokenBucket',
        **kwargs,
    ):
        self.bucket      = bucket
        self.tokens_sent = 0
        super().__init__(stream=self._gated_stream(stream), **kwargs)

    async def _gated_stream(self, source: 'AsyncGenerator[str, None]'):
        async for token in source:
            token_ids = len(token) // 4 + 1
            if not self.bucket.consume(token_ids):
                wait = self.bucket.tokens_until_available(token_ids)
                if wait > 0:
                    await asyncio.sleep(wait)
                self.bucket.consume(token_ids)
            self.tokens_sent += token_ids
            yield token
