"""
Request object and async body stream.
In production this file is compiled by Cython via request.pxd.
"""
from __future__ import annotations
import asyncio
import json
from dataclasses import dataclass
from typing import Any, TYPE_CHECKING
from urllib.parse import parse_qs, urlparse

from ..headers import Headers

if TYPE_CHECKING:
    from ..ai.context import ConversationContext


class Stream:
    """Async byte stream for the request body.

    Producer (protocol layer) calls feed()/end().
    Consumer (handler) calls read() / __aiter__.
    """

    __slots__ = ("_queue", "_done", "_chunks")

    def __init__(self) -> None:
        self._queue: asyncio.Queue[bytes | None] = asyncio.Queue()
        self._done = False
        self._chunks: list[bytes] = []

    def feed(self, chunk: bytes) -> None:
        if not self._done:
            self._queue.put_nowait(chunk)

    def end(self) -> None:
        self._done = True
        self._queue.put_nowait(None)

    def clear(self) -> None:
        self._done = False
        self._chunks.clear()
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break

    async def read(self) -> bytes:
        chunks: list[bytes] = []
        async for chunk in self:
            chunks.append(chunk)
        return b"".join(chunks)

    def __aiter__(self):
        return self

    async def __anext__(self) -> bytes:
        chunk = await self._queue.get()
        if chunk is None:
            raise StopAsyncIteration
        return chunk


@dataclass
class AIRequestBody:
    """Parsed OpenAI-compatible chat completion request body."""
    model: str | None = None
    messages: list[dict[str, Any]] | None = None
    stream: bool = False
    tools: list[dict] | None = None
    tool_choice: str | dict | None = None
    temperature: float = 1.0
    max_tokens: int | None = None
    top_p: float = 1.0
    stop: list[str] | None = None
    user: str | None = None
    extra: dict[str, Any] | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "AIRequestBody":
        known = {
            "model", "messages", "stream", "tools", "tool_choice",
            "temperature", "max_tokens", "top_p", "stop", "user",
        }
        extra = {k: v for k, v in data.items() if k not in known}
        return cls(
            model=data.get("model"),
            messages=data.get("messages", []),
            stream=bool(data.get("stream", False)),
            tools=data.get("tools"),
            tool_choice=data.get("tool_choice"),
            temperature=float(data.get("temperature", 1.0)),
            max_tokens=data.get("max_tokens"),
            top_p=float(data.get("top_p", 1.0)),
            stop=data.get("stop"),
            user=data.get("user"),
            extra=extra or None,
        )


class Request:
    """HTTP request object.

    Constructed once per connection by the protocol layer, populated via
    the Stream as body bytes arrive. All parsing is lazy.

    In production, the hot fields (url, method, headers, stream) are cdef
    in request.pxd and access involves no Python dictionary lookup.
    """

    __slots__ = (
        "url", "method", "headers", "stream", "protocol",
        "_parsed_url", "_args", "_json", "_form", "_body_cache",
        "_token_count", "context", "_path_params",
    )

    def __init__(
        self,
        url: bytes,
        method: bytes,
        headers: Headers,
        stream: Stream,
        protocol: Any,
    ) -> None:
        self.url = url
        self.method = method
        self.headers = headers
        self.stream = stream
        self.protocol = protocol
        self._parsed_url = None
        self._args: dict | None = None
        self._json: Any = None
        self._form: dict | None = None
        self._body_cache: bytes | None = None
        self._token_count: int = -1
        self.context: dict = {}
        self._path_params: dict = {}

    @property
    def path(self) -> str:
        if self._parsed_url is None:
            self._parsed_url = urlparse(self.url.decode("latin-1"))
        return self._parsed_url.path

    @property
    def query_string(self) -> str:
        if self._parsed_url is None:
            self._parsed_url = urlparse(self.url.decode("latin-1"))
        return self._parsed_url.query or ""

    @property
    def args(self) -> dict[str, list[str]]:
        if self._args is None:
            self._args = parse_qs(self.query_string)
        return self._args

    def get_arg(self, name: str, default: str | None = None) -> str | None:
        values = self.args.get(name)
        if values:
            return values[0]
        return default

    @property
    def client_ip(self) -> str:
        forwarded = self.headers.get(b"x-forwarded-for")
        if forwarded:
            return forwarded.split(b",")[0].strip().decode("latin-1")
        if self.protocol and self.protocol.transport:
            peer = self.protocol.transport.get_extra_info("peername")
            if peer:
                return peer[0]
        return "unknown"

    @property
    def stream_requested(self) -> bool:
        """True if client explicitly requests SSE or streaming."""
        accept = self.headers.get(b"accept", b"")
        if b"text/event-stream" in accept:
            return True
        # Checked again after body parse in ai_body()
        return False

    async def body(self) -> bytes:
        if self._body_cache is None:
            self._body_cache = await self.stream.read()
        return self._body_cache

    async def json(self) -> Any:
        if self._json is None:
            raw = await self.body()
            self._json = json.loads(raw)
        return self._json

    async def ai_body(self) -> AIRequestBody:
        data = await self.json()
        return AIRequestBody.from_dict(data)

    async def form(self) -> dict[str, str]:
        if self._form is None:
            raw = await self.body()
            parsed = parse_qs(raw.decode("utf-8", errors="replace"))
            self._form = {k: v[0] if len(v) == 1 else v for k, v in parsed.items()}
        return self._form

    async def conversation(self) -> "ConversationContext":
        from ..ai.context import ConversationContext
        # Attempt to load from session; fall back to ephemeral
        session = self.context.get("session")
        conv_id = self.get_arg("conversation_id") or self.headers.get_str("x-conversation-id")
        if conv_id and session:
            return await ConversationContext.load(session, conv_id)
        return ConversationContext(conversation_id=conv_id or _new_conversation_id())

    def estimate_tokens(self) -> int:
        """Rough estimate: 4 chars ≈ 1 token, without tiktoken dependency."""
        if self._token_count >= 0:
            return self._token_count
        if self._body_cache:
            self._token_count = max(1, len(self._body_cache) // 4)
        return self._token_count if self._token_count >= 0 else 0


def _new_conversation_id() -> str:
    import uuid
    return str(uuid.uuid4())
