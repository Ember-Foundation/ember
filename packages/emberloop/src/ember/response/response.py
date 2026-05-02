"""
HTTP response hierarchy.
In production, the core classes are compiled by Cython via response.pxd.
SSEWriter frame formatting is compiled separately via sse_writer.pxd.
"""
from __future__ import annotations
import asyncio
import json
from typing import Any, AsyncGenerator, TYPE_CHECKING

from ..constants import STATUS_CODES, HTTP_PREFIX, CRLF, CONTENT_TYPE_JSON

if TYPE_CHECKING:
    from ..protocol.protocol import Connection
    from ..ai.ratelimit.token_bucket import TokenBucket


class Response:
    """Base HTTP response. Holds pre-encoded body bytes."""

    __slots__ = ("body", "status_code", "_headers", "_cached_bytes")

    def __init__(
        self,
        body: bytes | str = b"",
        status_code: int = 200,
        headers: dict[str, str] | None = None,
        content_type: bytes = b"text/plain; charset=utf-8",
    ) -> None:
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.body = body
        self.status_code = status_code
        self._headers = headers or {}
        self._cached_bytes: bytes | None = None
        if content_type and "content-type" not in {k.lower() for k in self._headers}:
            self._headers["content-type"] = content_type.decode("latin-1")

    def _encode_headers(self) -> bytes:
        status = STATUS_CODES.get(self.status_code, b"200 OK")
        lines = [HTTP_PREFIX + status + CRLF]
        for k, v in self._headers.items():
            lines.append(k.encode("latin-1") + b": " + v.encode("latin-1") + CRLF)
        lines.append(b"content-length: " + str(len(self.body)).encode() + CRLF)
        lines.append(CRLF)
        return b"".join(lines)

    def encode(self) -> bytes:
        if self._cached_bytes is None:
            self._cached_bytes = self._encode_headers() + self.body
        return self._cached_bytes

    def send(self, protocol: "Connection") -> None:
        protocol.transport.write(self.encode())
        protocol.after_response(self)


class JSONResponse(Response):
    """Serialize a Python object to a JSON response."""

    def __init__(
        self,
        data: Any,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
    ) -> None:
        try:
            import ujson
            body = ujson.dumps(data).encode("utf-8")
        except ImportError:
            body = json.dumps(data, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        super().__init__(body=body, status_code=status_code, headers=headers,
                         content_type=CONTENT_TYPE_JSON)


class RedirectResponse(Response):
    def __init__(self, location: str, status_code: int = 302) -> None:
        super().__init__(
            body=b"",
            status_code=status_code,
            headers={"location": location},
        )


class StreamingResponse(Response):
    """Chunked-transfer response backed by an async generator."""

    __slots__ = ("stream", "complete_timeout", "chunk_timeout", "_headers", "status_code")

    def __init__(
        self,
        stream: AsyncGenerator[bytes, None],
        status_code: int = 200,
        headers: dict[str, str] | None = None,
        content_type: bytes = b"application/octet-stream",
        complete_timeout: int = 300,
        chunk_timeout: int = 30,
    ) -> None:
        self.stream = stream
        self.status_code = status_code
        self._headers = headers or {}
        self.complete_timeout = complete_timeout
        self.chunk_timeout = chunk_timeout
        if "content-type" not in {k.lower() for k in self._headers}:
            self._headers["content-type"] = content_type.decode("latin-1")

    def _encode_headers(self) -> bytes:
        status = STATUS_CODES.get(self.status_code, b"200 OK")
        lines = [HTTP_PREFIX + status + CRLF]
        for k, v in self._headers.items():
            lines.append(k.encode("latin-1") + b": " + v.encode("latin-1") + CRLF)
        lines.append(b"transfer-encoding: chunked" + CRLF)
        lines.append(CRLF)
        return b"".join(lines)

    def send(self, protocol: "Connection") -> None:
        protocol.transport.write(self._encode_headers())
        loop = asyncio.get_event_loop()
        loop.create_task(self._stream_loop(protocol))

    async def _stream_loop(self, protocol: "Connection") -> None:
        try:
            async for chunk in self.stream:
                if not isinstance(chunk, bytes):
                    chunk = chunk.encode("utf-8")
                frame = ("{:X}\r\n".format(len(chunk))).encode() + chunk + b"\r\n"
                protocol.transport.write(frame)
                if not protocol.writable:
                    await protocol.write_permission.wait()
                    protocol.write_permission.clear()
            protocol.transport.write(b"0\r\n\r\n")
        finally:
            protocol.after_response(self)


class SSEResponse(StreamingResponse):
    """Server-Sent Events response for streaming LLM token output.

    The SSEWriter formats each token into a proper SSE frame:
      id: <n>\\nevent: message\\ndata: <token>\\n\\n

    In production, _format_event() is replaced by the Cython SSEWriter.
    """

    __slots__ = ("event_type", "retry_ms", "_id_counter", "include_done_sentinel")

    SSE_HEADERS = {
        "content-type": "text/event-stream; charset=utf-8",
        "cache-control": "no-cache",
        "x-accel-buffering": "no",
    }

    def __init__(
        self,
        stream: AsyncGenerator[str, None],
        status_code: int = 200,
        headers: dict[str, str] | None = None,
        event_type: str = "message",
        retry_ms: int = 3000,
        include_done_sentinel: bool = True,
        complete_timeout: int = 300,
        chunk_timeout: int = 30,
    ) -> None:
        merged_headers = {**self.SSE_HEADERS, **(headers or {})}
        # SSE uses its own async generator wrapping internally
        super().__init__(
            stream=self._token_to_bytes(stream),
            status_code=status_code,
            headers=merged_headers,
            complete_timeout=complete_timeout,
            chunk_timeout=chunk_timeout,
        )
        self.event_type = event_type.encode("utf-8")
        self.retry_ms = retry_ms
        self._id_counter = 0
        self.include_done_sentinel = include_done_sentinel

    def _format_event(self, data: bytes) -> bytes:
        self._id_counter += 1
        return (
            b"id: " + str(self._id_counter).encode() + b"\n"
            b"event: " + self.event_type + b"\n"
            b"data: " + data + b"\n\n"
        )

    def _format_done(self) -> bytes:
        return b"data: [DONE]\n\n"

    def _format_retry(self) -> bytes:
        return b"retry: " + str(self.retry_ms).encode() + b"\n\n"

    async def _token_to_bytes(self, source: AsyncGenerator[str, None]) -> AsyncGenerator[bytes, None]:
        yield self._format_retry()
        async for token in source:
            if not isinstance(token, bytes):
                token = token.encode("utf-8")
            yield self._format_event(token)
        if self.include_done_sentinel:
            yield self._format_done()

    def send(self, protocol: "Connection") -> None:
        protocol.transport.write(self._encode_headers())
        loop = asyncio.get_event_loop()
        loop.create_task(self._stream_loop(protocol))


class TokenStreamResponse(SSEResponse):
    """SSE response that also accounts for tokens against a rate-limit bucket.

    Tracks actual tokens emitted so the AFTER_ENDPOINT hook can record
    real usage for billing and quota enforcement.
    """

    __slots__ = ("bucket", "tokens_sent")

    def __init__(
        self,
        stream: AsyncGenerator[str, None],
        bucket: "TokenBucket",
        **kwargs,
    ) -> None:
        self.bucket = bucket
        self.tokens_sent = 0
        super().__init__(stream=self._gated_stream(stream), **kwargs)

    async def _gated_stream(self, source: AsyncGenerator[str, None]) -> AsyncGenerator[str, None]:
        async for token in source:
            token_ids = len(token) // 4 + 1  # rough estimate
            if not self.bucket.consume(token_ids):
                wait = self.bucket.tokens_until_available(token_ids)
                if wait > 0:
                    await asyncio.sleep(wait)
                self.bucket.consume(token_ids)
            self.tokens_sent += token_ids
            yield token
