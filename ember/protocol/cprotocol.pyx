# cython: language_level=3, boundscheck=False, wraparound=False, cdivision=True
"""
Cython HTTP protocol — llhttp C state-machine parser + optimised Connection.

Vendored llhttp in ember/vendor/llhttp/:
  llhttp.h   — C header  (cdef extern from)
  llhttp.c   — state machine C code  (extra_sources)
  api.c      — init/reset/execute   (extra_sources)
  http.c     — method/status tables (extra_sources)
"""

import asyncio
import time as _time
import logging

from ember.headers import Headers as _Headers
from ember.constants import STATUS_CODES, HTTP_PREFIX, CRLF
from ember.request import Request as _Request, Stream as _Stream
from ember.exceptions import RouteNotFound as _RouteNotFound, MethodNotAllowed as _MethodNotAllowed
from ember.response import Response as _Response

logger = logging.getLogger("ember.protocol")

RECEIVING  = 0
PROCESSING = 1
PENDING    = 2
CLOSING    = 3


# ── C-level callbacks (called from llhttp, must be C-compatible) ─────────────
# These run with the GIL held (llhttp_execute is called from Python code).
# `noexcept` means Cython won't add a per-call PyErr check, but the exception
# state is still preserved in the thread — feed() uses `except -1` to re-raise.

cdef int _cb_url(llhttp_t* p, const char* at, size_t ln) noexcept:
    (<HTTPParser>p.data)._url_buf += at[:ln]
    return 0


cdef int _cb_header_field(llhttp_t* p, const char* at, size_t ln) noexcept:
    cdef HTTPParser hp = <HTTPParser>p.data
    # A new field name means the previous field+value pair is complete.
    if hp._hdr_value_buf:
        hp._headers.append((bytes(hp._hdr_field_buf), bytes(hp._hdr_value_buf)))
        hp._hdr_field_buf.clear()
        hp._hdr_value_buf.clear()
    hp._hdr_field_buf += at[:ln]
    return 0


cdef int _cb_header_value(llhttp_t* p, const char* at, size_t ln) noexcept:
    (<HTTPParser>p.data)._hdr_value_buf += at[:ln]
    return 0


cdef int _cb_headers_complete(llhttp_t* p) noexcept:
    cdef HTTPParser hp = <HTTPParser>p.data
    cdef const char* mname
    # Flush the last header pair.
    if hp._hdr_field_buf:
        hp._headers.append((bytes(hp._hdr_field_buf), bytes(hp._hdr_value_buf)))
        hp._hdr_field_buf.clear()
        hp._hdr_value_buf.clear()
    hp._headers_done = True
    mname = llhttp_method_name(llhttp_get_method(p))
    _tmp = hp._headers
    hp._headers = []
    hp._conn.on_headers_complete(
        _Headers(_tmp),
        bytes(hp._url_buf),
        <bytes>mname,
        bool(p.upgrade),
    )
    return 0


cdef int _cb_body(llhttp_t* p, const char* at, size_t ln) noexcept:
    (<HTTPParser>p.data)._conn.on_body(at[:ln])
    return 0


cdef int _cb_message_complete(llhttp_t* p) noexcept:
    (<HTTPParser>p.data)._conn.on_message_complete()
    return 0


# ── HTTPParser cdef class ─────────────────────────────────────────────────────

cdef class HTTPParser:
    """
    C-speed HTTP/1.1 parser.

    Embeds llhttp_t and llhttp_settings_t directly in the Python object —
    no heap allocation for the C structs, no indirection.
    reset() zeroes the buffers and re-arms the parser without allocating a
    new object (contrast with SimpleHTTPParser which creates a new instance
    for every keep-alive request).
    """

    def __cinit__(self, conn):
        self._conn          = conn
        self._url_buf       = bytearray()
        self._hdr_field_buf = bytearray()
        self._hdr_value_buf = bytearray()
        self._headers       = []
        self._headers_done  = False

        llhttp_settings_init(&self._settings)
        self._settings.on_url              = _cb_url
        self._settings.on_header_field     = _cb_header_field
        self._settings.on_header_value     = _cb_header_value
        self._settings.on_headers_complete = _cb_headers_complete
        self._settings.on_body             = _cb_body
        self._settings.on_message_complete = _cb_message_complete

        llhttp_init(&self._parser, HTTP_REQUEST, &self._settings)
        # Store a raw pointer to self so C callbacks can reach back into Python.
        # Safe: _parser is embedded in self, so they have identical lifetimes.
        self._parser.data = <void*>self

    cpdef int feed(self, bytes data) except -1:
        """Feed raw bytes into the parser; returns 0 on success."""
        return llhttp_execute(&self._parser, data, len(data))

    cpdef void reset(self):
        """Zero-allocation reset for keep-alive: reuse this object for next request."""
        llhttp_reset(&self._parser)
        self._parser.data = <void*>self   # llhttp_reset zeroes data; restore it
        self._url_buf.clear()
        self._hdr_field_buf.clear()
        self._hdr_value_buf.clear()
        self._headers.clear()
        self._headers_done = False


# ── Connection ────────────────────────────────────────────────────────────────

class Connection(asyncio.Protocol):
    """
    Per-connection asyncio Protocol backed by the Cython HTTPParser.

    Key optimisations vs the pure-Python version:
    - self._loop cached once in __init__ — no asyncio.get_event_loop() per request
    - self._parser.reset() on keep-alive — zero object allocation
    - feed() is a cpdef C call from within the same .so
    """

    __slots__ = (
        "app", "transport", "status", "keep_alive", "closed", "writable",
        "write_permission", "_stream", "_parser", "_current_task",
        "_timeout_task", "_last_activity", "components",
        "_current_request", "_current_route", "_loop", "_feed_active",
    )

    def __init__(self, app):
        self.app              = app
        self.transport        = None
        self._loop            = asyncio.get_event_loop()  # cached for lifetime of connection
        self.status           = RECEIVING
        self.keep_alive       = True
        self.closed           = False
        self.writable         = True
        self.write_permission = asyncio.Event()
        self.write_permission.set()
        self._stream          = _Stream()
        self._parser          = HTTPParser(self)           # Cython C parser
        self._current_task    = None
        self._timeout_task    = None
        self._current_request = None
        self._current_route   = None
        self._last_activity   = _time.monotonic()
        self._feed_active     = False
        self.components       = app.components.clone()

    # ── asyncio.Protocol interface ──────────────────────────────────────────

    def connection_made(self, transport) -> None:
        self.transport = transport
        limits = getattr(self.app, "_server_limits", None)
        buf = limits.write_buffer if limits else 419_430
        transport.set_write_buffer_limits(high=buf)

    def data_received(self, data: bytes) -> None:
        self._feed_active = True
        try:
            rc = self._parser.feed(data)
            if rc != 0:
                self._send_error(400, b"Bad Request")
        except Exception:
            self._send_error(400, b"Bad Request")
        finally:
            self._feed_active = False

    def connection_lost(self, exc) -> None:
        self.closed   = True
        self.writable = False
        self._stream.end()
        if self._current_task and not self._current_task.done():
            self._current_task.cancel()

    def pause_writing(self) -> None:
        self.writable = False
        self.write_permission.clear()

    def resume_writing(self) -> None:
        self.writable = True
        self.write_permission.set()

    # ── Parser callbacks (called by HTTPParser's C callbacks) ───────────────

    def on_headers_complete(self, headers, url: bytes, method: bytes,
                            upgrade: bool) -> None:
        self._stream.clear()
        request = _Request(url=url, method=method, headers=headers,
                           stream=self._stream, protocol=self)
        self.components.add_ephemeral(request, _Request)
        try:
            route = self.app.router.get_route(request)
        except _RouteNotFound:
            self._send_error(404, b"Not Found")
            return
        except _MethodNotAllowed:
            self._send_error(405, b"Method Not Allowed")
            return

        # Synchronous cache fast-path — bypass Task creation entirely.
        if route.cache and not route.cache.is_async and route.cache.skip_hooks:
            cached = route.cache.get(request)
            if cached:
                cached.send(self)
                return

        self._current_request = request
        self._current_route   = route
        self.status           = RECEIVING

    def on_body(self, data: bytes) -> None:
        self._stream.feed(data)

    def on_message_complete(self) -> None:
        self._last_activity = _time.monotonic()
        self._stream.end()
        if self._current_route is None:
            return   # 404/405 already sent in on_headers_complete
        self.status = PROCESSING
        _route = self._current_route   # capture before eager task may reset _current_route
        self._current_task = self._loop.create_task(
            self._handle_request(self._current_request, _route)
        )
        if _route.limits is not None:
            self._timeout_task = self._loop.call_later(
                _route.limits.timeout, self._cancel_request
            )
        else:
            self._timeout_task = None

    # ── Request handling ─────────────────────────────────────────────────────

    async def _handle_request(self, request, route) -> None:
        try:
            if self.app._has_before_endpoint:
                early = await self.app.call_hooks_before_endpoint(
                    request, self.components)
                if early is not None:
                    early.send(self)
                    return

            # Distributed cache (Redis/Memcached) — fast key lookup before handler
            if route.cache and route.cache.is_async:
                cached = await route.cache.get(request)
                if cached:
                    cached.send(self)
                    return

            # Semantic cache (AI vector search) — embedding lookup before handler
            _sem_cache = getattr(route, "semantic_cache", None)
            if _sem_cache:
                cached = await _sem_cache.get(request)
                if cached:
                    cached.send(self)
                    return

            response = await route.call_handler(request, self.components)

            if route.cache and not route.cache.is_async:
                route.cache.store(request, response)
            elif route.cache and route.cache.is_async:
                await route.cache.store(request, response)
            elif _sem_cache and response:
                await _sem_cache.store(request, response)

            if self.app._has_after_endpoint:
                await self.app.call_hooks_after_endpoint(
                    request, response, self.components)

            if response is not None:
                response.send(self)

        except Exception as exc:
            await self._handle_exception(exc, request)

    async def _handle_exception(self, exc, request) -> None:
        try:
            response = await self.app.process_exception(exc, self.components)
            response.send(self)
        except Exception:
            self._send_error(500, b"Internal Server Error")

    def after_response(self, response) -> None:
        if self._timeout_task:
            self._timeout_task.cancel()
            self._timeout_task = None
        self.components.reset()
        self.status = PENDING
        if self.keep_alive and not self.closed:
            if self._feed_active:
                # Defer parser reset: calling llhttp_reset() mid llhttp_execute() causes rc != 0.
                self._loop.call_soon(self._reset_for_next_request)
            else:
                self._reset_for_next_request()

    def _reset_for_next_request(self) -> None:
        self._stream.clear()
        self._parser.reset()        # ← zero-alloc reset, not a new object
        self._current_request = None
        self._current_route   = None
        self.status           = RECEIVING

    def _cancel_request(self) -> None:
        if self._current_task and not self._current_task.done():
            self._current_task.cancel()
        self._send_error(408, b"Request Timeout")

    def _send_error(self, status_code: int, message: bytes) -> None:
        r = _Response(body=message, status_code=status_code,
                      headers={"connection": "close"})
        if self.transport and not self.closed:
            self.transport.write(r.encode())
            self.transport.close()

    def close(self) -> None:
        if self.transport and not self.closed:
            self.transport.close()
        self.closed = True

    @property
    def client_ip(self) -> str:
        if self.transport:
            peer = self.transport.get_extra_info("peername")
            if peer:
                return peer[0]
        return "unknown"
