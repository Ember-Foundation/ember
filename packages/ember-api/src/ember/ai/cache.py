from __future__ import annotations
import hashlib
import time
from typing import Any, TYPE_CHECKING

from ember.cache import CachedResponse

if TYPE_CHECKING:
    from ember.request import Request
    from ember.response import Response


class SemanticCache:
    """Vector-similarity cache for LLM responses.

    Uses an embedding model to convert request prompts to vectors, then
    finds cached responses for semantically similar past requests.

    The embedding + vector-search I/O dominates any Python overhead here,
    so this is intentionally pure Python (no Cython).

    Usage:
        cache = SemanticCache(
            embedding_fn=my_embed_fn,  # async (text: str) -> list[float]
            similarity_threshold=0.92,
            ttl_seconds=3600,
        )
    """

    def __init__(
        self,
        embedding_fn: Any | None = None,
        vector_backend: Any | None = None,
        similarity_threshold: float = 0.92,
        ttl_seconds: int = 3600,
    ) -> None:
        self.embedding_fn = embedding_fn
        self.vector_backend = vector_backend
        self.similarity_threshold = similarity_threshold
        self.ttl_seconds = ttl_seconds
        # In-memory fallback when no vector backend is configured
        self._mem_cache: dict[str, tuple[bytes, float]] = {}
        self.is_async = True
        self.skip_hooks = False

    async def _extract_prompt(self, request: "Request") -> str:
        if request._body_cache:
            try:
                import json
                data = json.loads(request._body_cache)
                messages = data.get("messages", [])
                if messages:
                    return " ".join(m.get("content", "") for m in messages[-3:])
                return request._body_cache.decode("utf-8", errors="replace")
            except Exception:
                return request._body_cache.decode("utf-8", errors="replace")
        return request.url.decode("latin-1")

    async def get(self, request: "Request") -> "Response | None":
        if not self._mem_cache and self.vector_backend is None:
            return None

        prompt = await self._extract_prompt(request)

        if self.vector_backend is not None and self.embedding_fn is not None:
            embedding = await self.embedding_fn(prompt)
            result = await self.vector_backend.query(embedding, self.similarity_threshold)
            if result:
                return CachedResponse(result)
            return None

        # Exact hash fallback (no semantic similarity)
        key = hashlib.sha256(prompt.encode()).hexdigest()
        entry = self._mem_cache.get(key)
        if entry:
            raw, expires_at = entry
            if time.monotonic() < expires_at:
                return CachedResponse(raw)
            del self._mem_cache[key]
        return None

    async def store(self, request: "Request", response: "Response") -> None:
        prompt = await self._extract_prompt(request)
        encoded = response.encode() if hasattr(response, "encode") else b""
        if not encoded:
            return

        if self.vector_backend is not None and self.embedding_fn is not None:
            embedding = await self.embedding_fn(prompt)
            await self.vector_backend.store(embedding, encoded, ttl=self.ttl_seconds)
            return

        key = hashlib.sha256(prompt.encode()).hexdigest()
        self._mem_cache[key] = (encoded, time.monotonic() + self.ttl_seconds)

    async def invalidate(self, pattern: str) -> int:
        if self.vector_backend is not None and self.embedding_fn is not None:
            embedding = await self.embedding_fn(pattern)
            return await self.vector_backend.delete_similar(embedding, self.similarity_threshold)
        removed = 0
        keys_to_remove = [k for k in self._mem_cache if pattern in k]
        for k in keys_to_remove:
            del self._mem_cache[k]
            removed += 1
        return removed
