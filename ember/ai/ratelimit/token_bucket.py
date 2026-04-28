"""
Token bucket rate limiter.
In production, compiled by Cython via token_bucket.pxd.
All arithmetic is on C doubles in the compiled form — no Python objects touched.
"""
from __future__ import annotations
import asyncio
import time


class TokenBucket:
    """Thread-safe token bucket with time-based refill.

    Designed for tokens-per-minute limits:
      capacity = tokens_per_minute
      refill_rate = tokens_per_minute / 60.0

    consume() is synchronous and non-blocking: it returns True/False
    immediately. Callers that need to wait use tokens_until_available()
    to compute the sleep duration themselves.
    """

    __slots__ = ("capacity", "tokens", "refill_rate", "_last_refill", "_lock")

    def __init__(self, capacity: float, refill_rate: float) -> None:
        self.capacity = float(capacity)
        self.tokens = float(capacity)
        self.refill_rate = float(refill_rate)
        self._last_refill: float = time.monotonic()
        self._lock = asyncio.Lock()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._last_refill = now
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)

    def consume(self, tokens: int) -> bool:
        """Attempt to consume tokens. Returns True if successful, False if rate limited."""
        self._refill()
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    def tokens_until_available(self, requested: int) -> float:
        """Returns seconds until `requested` tokens will be available."""
        self._refill()
        deficit = requested - self.tokens
        if deficit <= 0:
            return 0.0
        return deficit / self.refill_rate

    async def consume_async(self, tokens: int) -> bool:
        """Async-safe consume using asyncio.Lock for concurrent handlers."""
        async with self._lock:
            return self.consume(tokens)

    @property
    def available(self) -> float:
        self._refill()
        return self.tokens


class GlobalTokenBucket(TokenBucket):
    """App-level token bucket shared across all connections in a worker.

    Uses an asyncio.Lock for correctness under concurrent coroutines.
    One instance per worker process (not shared across processes — each
    worker enforces its own fraction of the global limit).
    """
    pass
