# cython: language_level=3, boundscheck=False, wraparound=False
"""
Cython request module — Stream and Request as cdef classes.

Hot-path gains:
- Stream.feed/end/clear: cpdef void — C-speed, no Python dispatch per body chunk
- Request fields: cdef public bytes url/method — direct C struct access, no __dict__
- _done: cdef bint — C boolean, no PyObject boxing
"""
from __future__ import annotations
import asyncio
import json
from dataclasses import dataclass
from typing import Any, TYPE_CHECKING
from urllib.parse import parse_qs

from ..headers.headers cimport Headers

if TYPE_CHECKING:
    from ..ai.context import ConversationContext


cdef class Stream:

    def __init__(self):
        self._queue  = asyncio.Queue()
        self._done   = False
        self._chunks = []

    cpdef void feed(self, bytes chunk):
        if not self._done:
            self._queue.put_nowait(chunk)

    cpdef void end(self):
        self._done = True
        self._queue.put_nowait(None)

    cpdef void clear(self):
        self._done = False
        self._chunks = []
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except Exception:
                break

    cpdef object read(self):
        return self._read_async()

    async def _read_async(self):
        cdef list chunks = []
        async for chunk in self:
            chunks.append(chunk)
        return b"".join(chunks)

    def __aiter__(self):
        return self

    async def __anext__(self):
        chunk = await self._queue.get()
        if chunk is None:
            raise StopAsyncIteration
        return chunk


@dataclass
class AIRequestBody:
    model: str | None = None
    messages: list | None = None
    stream: bool = False
    tools: list | None = None
    tool_choice: object = None
    temperature: float = 1.0
    max_tokens: int | None = None
    top_p: float = 1.0
    stop: list | None = None
    user: str | None = None
    extra: dict | None = None

    @classmethod
    def from_dict(cls, data: dict):
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


cdef class Request:

    def __init__(self, bytes url, bytes method, Headers headers, Stream stream, protocol):
        self.url          = url
        self.method       = method
        self.headers      = headers
        self.stream       = stream
        self.protocol     = protocol
        self._path        = None
        self._query_str   = None
        self._args        = None
        self._json        = None
        self._form        = None
        self._body_cache  = None
        self._token_count = -1
        self.context      = {}
        self._path_params = {}

    @property
    def path(self):
        cdef bytes raw
        cdef int q
        if self._path is None:
            raw = self.url
            q = raw.find(b"?")
            self._path = raw[:q].decode("latin-1") if q >= 0 else raw.decode("latin-1")
        return self._path

    @property
    def query_string(self):
        cdef bytes raw
        cdef int q
        if self._query_str is None:
            raw = self.url
            q = raw.find(b"?")
            self._query_str = raw[q + 1:].decode("latin-1") if q >= 0 else ""
        return self._query_str

    @property
    def args(self):
        if self._args is None:
            self._args = parse_qs(self.query_string)
        return self._args

    def get_arg(self, str name, default=None):
        values = self.args.get(name)
        if values:
            return values[0]
        return default

    @property
    def client_ip(self):
        forwarded = self.headers.get(b"x-forwarded-for")
        if forwarded:
            return forwarded.split(b",")[0].strip().decode("latin-1")
        if self.protocol and self.protocol.transport:
            peer = self.protocol.transport.get_extra_info("peername")
            if peer:
                return peer[0]
        return "unknown"

    @property
    def stream_requested(self):
        accept = self.headers.get(b"accept", b"")
        return b"text/event-stream" in accept

    async def body(self):
        if self._body_cache is None:
            self._body_cache = await self.stream._read_async()
        return self._body_cache

    async def json(self):
        if self._json is None:
            raw = await self.body()
            self._json = json.loads(raw)
        return self._json

    async def ai_body(self):
        data = await self.json()
        return AIRequestBody.from_dict(data)

    async def form(self):
        if self._form is None:
            raw = await self.body()
            parsed = parse_qs(raw.decode("utf-8", errors="replace"))
            self._form = {k: v[0] if len(v) == 1 else v for k, v in parsed.items()}
        return self._form

    async def conversation(self):
        from ..ai.context import ConversationContext
        session  = self.context.get("session")
        conv_id  = self.get_arg("conversation_id") or self.headers.get_str("x-conversation-id")
        if conv_id and session:
            return await ConversationContext.load(session, conv_id)
        return ConversationContext(conversation_id=conv_id or _new_conversation_id())

    cpdef int estimate_tokens(self):
        if self._token_count >= 0:
            return self._token_count
        if self._body_cache:
            self._token_count = max(1, len(self._body_cache) // 4)
        return self._token_count if self._token_count >= 0 else 0


def _new_conversation_id():
    import uuid
    return str(uuid.uuid4())
