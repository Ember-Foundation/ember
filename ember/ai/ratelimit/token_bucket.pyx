# cython: language_level=3, boundscheck=False, wraparound=False, cdivision=True
"""Cython token bucket — all arithmetic on C doubles, no Python objects."""
import asyncio
from libc.time cimport time as c_time

cdef extern from "time.h":
    double clock() nogil

import time as _time

cdef class TokenBucket:
    def __init__(self, double capacity, double refill_rate):
        self.capacity = capacity
        self.tokens = capacity
        self.refill_rate = refill_rate
        self._last_refill = _time.monotonic()
        self._lock = asyncio.Lock()

    cdef void _refill(self):
        cdef double now = _time.monotonic()
        cdef double elapsed = now - self._last_refill
        self._last_refill = now
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)

    cpdef bint consume(self, int tokens):
        self._refill()
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    cpdef double tokens_until_available(self, int requested):
        self._refill()
        cdef double deficit = requested - self.tokens
        if deficit <= 0.0:
            return 0.0
        return deficit / self.refill_rate

    async def consume_async(self, int tokens):
        async with self._lock:
            return self.consume(tokens)

    @property
    def available(self):
        self._refill()
        return self.tokens


cdef class GlobalTokenBucket(TokenBucket):
    pass
