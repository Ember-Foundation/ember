from ..headers.headers cimport Headers

cdef class Stream:
    cdef object _queue
    cdef public bint _done
    cdef list _chunks

    cpdef void feed(self, bytes chunk)
    cpdef void end(self)
    cpdef void clear(self)
    cpdef object read(self)

cdef class Request:
    cdef public bytes url
    cdef public bytes method
    cdef public Headers headers
    cdef public Stream stream
    cdef public object protocol
    cdef object _path
    cdef object _query_str
    cdef dict _args
    cdef object _json
    cdef dict _form
    cdef public bytes _body_cache
    cdef public int _token_count
    cdef public dict context
    cdef public dict _path_params

    cpdef int estimate_tokens(self)
