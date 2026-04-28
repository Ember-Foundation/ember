cdef class SSEWriter:
    cdef public bytes event_type
    cdef public int retry_ms
    cdef int _id_counter

    cdef bytes format_event(self, bytes data, bytes event_id=*)
    cdef bytes format_comment(self, bytes comment)
    cdef bytes format_retry(self)
    cdef bytes format_done(self)
    cdef bytes format_event_chunked(self, bytes data)
    cdef bytes format_done_chunked(self)
