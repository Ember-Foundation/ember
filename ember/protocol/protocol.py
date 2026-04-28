"""
HTTP/1.1 asyncio Protocol.
In production, compiled by Cython via cprotocol.pxd.
The on_headers_complete fast-path avoids Python method dispatch entirely.
"""
from __future__ import annotations
import asyncio
import logging
import time
from typing import Any, TYPE_CHECKING

from ..headers import Headers
from ..request import Request, Stream
from ..exceptions import RouteNotFound, MethodNotAllowed

if TYPE_CHECKING:
    from ..application import EmberApplication

logger = logging.getLogger("ember.protocol")

# Connection states
RECEIVING = 0
PROCESSING = 1
PENDING = 2
CLOSING = 3


class SimpleHTTPParser:
    """Minimal HTTP/1.1 parser (pure Python fallback).

    Production uses llhttp via Cython. This implementation handles the
    basic cases needed for development and testing.
    """

    def __init__(self, connection: "Connection") -> None:
        self._conn = connection
        self._buf = b""
        self._headers_done = False
        self._content_length = 0
        self._bytes_received = 0

    def feed_data(self, data: bytes) -> None:
        self._buf += data
        if not self._headers_done:
            self._parse_headers()
        elif self._content_length > 0:
            self._feed_body(data)

    def _parse_headers(self) -> None:
        sep = self._buf.find(b"\r\n\r\n")
        if sep == -1:
            return
        header_section = self._buf[:sep]
        body_start = self._buf[sep + 4:]
        lines = header_section.split(b"\r\n")
        request_line = lines[0]

        parts = request_line.split(b" ", 2)
        if len(parts) < 2:
            return
        method = parts[0]
        url = parts[1]

        raw_headers: list[tuple[bytes, bytes]] = []
        for line in lines[1:]:
            if b":" in line:
                name, _, value = line.partition(b":")
                raw_headers.append((name.strip(), value.strip()))

        headers = Headers(raw_headers)
        cl_header = headers.get(b"content-length", b"0")
        try:
            self._content_length = int(cl_header)
        except ValueError:
            self._content_length = 0

        upgrade = headers.get(b"upgrade", b"")
        self._conn.on_headers_complete(headers, url, method, bool(upgrade))
        self._headers_done = True
        self._buf = body_start

        if body_start:
            self._feed_body(body_start)

        if self._content_length == 0:
            self._conn.on_message_complete()

    def _feed_body(self, data: bytes) -> None:
        self._conn.on_body(data)
        self._bytes_received += len(data)
        if self._bytes_received >= self._content_length:
            self._conn.on_message_complete()


class Connection(asyncio.Protocol):
    """Per-connection asyncio Protocol.

    Lifecycle:
      connection_made → data_received* → connection_lost

    Each HTTP request triggers:
      on_headers_complete → [on_body*] → on_message_complete → handle_request
    """

    def __init__(self, app: "EmberApplication") -> None:
        self.app = app
        self.transport: asyncio.Transport | None = None
        self.status = RECEIVING
        self.keep_alive = True
        self.closed = False
        self.writable = True
        self.write_permission = asyncio.Event()
        self.write_permission.set()

        self._stream = Stream()
        self._parser = SimpleHTTPParser(self)
        self._current_task: asyncio.Task | None = None
        self._timeout_task: asyncio.TimerHandle | None = None
        self._last_activity = time.monotonic()

        self.components = app.components.clone()

    # ── asyncio.Protocol interface ──────────────────────────────────────

    def connection_made(self, transport: asyncio.Transport) -> None:
        self.transport = transport
        transport.set_write_buffer_limits(
            high=getattr(self.app, "_server_limits", None) and
                 self.app._server_limits.write_buffer or 419_430
        )

    def data_received(self, data: bytes) -> None:
        self._last_activity = time.monotonic()
        self._parser.feed_data(data)

    def connection_lost(self, exc: Exception | None) -> None:
        self.closed = True
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

    # ── Parser callbacks ────────────────────────────────────────────────

    def on_headers_complete(
        self, headers: Headers, url: bytes, method: bytes, upgrade: bool
    ) -> None:
        self._stream.clear()
        request = Request(url=url, method=method, headers=headers,
                          stream=self._stream, protocol=self)
        self.components.add_ephemeral(request, Request)

        try:
            route = self.app.router.get_route(request)
        except RouteNotFound:
            self._send_error(404, b"Not Found")
            return
        except MethodNotAllowed:
            self._send_error(405, b"Method Not Allowed")
            return

        # Static cache fast-path: respond without creating a Task
        if route.cache and not route.cache.is_async and route.cache.skip_hooks:
            cached = route.cache.get(request)
            if cached:
                cached.send(self)
                return

        self._current_request = request
        self._current_route = route
        self.status = RECEIVING

    def on_body(self, data: bytes) -> None:
        self._stream.feed(data)

    def on_message_complete(self) -> None:
        self._stream.end()
        self.status = PROCESSING
        loop = asyncio.get_event_loop()
        self._current_task = loop.create_task(
            self._handle_request(self._current_request, self._current_route)
        )
        route_timeout = (
            self._current_route.limits.timeout
            if self._current_route.limits else 300
        )
        self._timeout_task = loop.call_later(route_timeout, self._cancel_request)

    # ── Request handling ─────────────────────────────────────────────────

    async def _handle_request(self, request: Request, route: Any) -> None:
        try:
            # BEFORE_ENDPOINT hooks (auth, rate limiting)
            if self.app._has_before_endpoint:
                early = await self.app.call_hooks_before_endpoint(request, self.components)
                if early is not None:
                    early.send(self)
                    return

            # Async semantic cache check
            if hasattr(route, "semantic_cache") and route.semantic_cache:
                cached = await route.semantic_cache.get(request)
                if cached:
                    cached.send(self)
                    return

            response = await route.call_handler(request, self.components)

            # Store in cache if applicable
            if route.cache and not route.cache.is_async:
                route.cache.store(request, response)
            elif hasattr(route, "semantic_cache") and route.semantic_cache and response:
                await route.semantic_cache.store(request, response)

            # AFTER_ENDPOINT hooks
            if self.app._has_after_endpoint:
                await self.app.call_hooks_after_endpoint(request, response, self.components)

            if response is not None:
                response.send(self)

        except Exception as exc:
            await self._handle_exception(exc, request)

    async def _handle_exception(self, exc: Exception, request: Request) -> None:
        try:
            response = await self.app.process_exception(exc, self.components)
            response.send(self)
        except Exception:
            self._send_error(500, b"Internal Server Error")

    def after_response(self, response: Any) -> None:
        """Called by Response.send() after bytes are written to transport."""
        if self._timeout_task:
            self._timeout_task.cancel()
            self._timeout_task = None
        self.components.reset()
        self.status = PENDING
        if self.keep_alive and not self.closed:
            self._reset_for_next_request()

    def _reset_for_next_request(self) -> None:
        self._stream.clear()
        self._parser = SimpleHTTPParser(self)
        self.status = RECEIVING

    def _cancel_request(self) -> None:
        if self._current_task and not self._current_task.done():
            self._current_task.cancel()
        self._send_error(408, b"Request Timeout")

    def _send_error(self, status_code: int, message: bytes) -> None:
        from ..response import Response
        r = Response(
            body=message,
            status_code=status_code,
            headers={"connection": "close"},
        )
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
