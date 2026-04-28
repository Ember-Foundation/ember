# cython: language_level=3
# Declaration file for response extension.
# StreamingResponse / SSEResponse / TokenStreamResponse are regular Python
# classes in the .pyx; only the three below are cdef classes.

cdef class Response:
    cdef public bytes body
    cdef public int   status_code
    cdef public dict  _headers
    cdef public bytes _header_prefix   # pre-built status + static headers
    cdef public bytes _cached_bytes

    cpdef bytes _encode_headers(self)
    cpdef bytes encode(self)
    cpdef void  send(self, object protocol)

cdef class JSONResponse(Response):
    pass

cdef class CachedResponse(Response):
    pass
