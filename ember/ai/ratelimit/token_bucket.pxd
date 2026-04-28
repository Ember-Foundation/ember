cdef class TokenBucket:
    cdef public double capacity
    cdef public double tokens
    cdef public double refill_rate
    cdef double _last_refill
    cdef object _lock

    cdef void _refill(self)
    cpdef bint consume(self, int tokens)
    cpdef double tokens_until_available(self, int requested)

cdef class GlobalTokenBucket(TokenBucket):
    pass
