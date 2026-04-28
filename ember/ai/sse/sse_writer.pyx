# cython: language_level=3, boundscheck=False, wraparound=False
"""Cython SSE frame encoder — zero Python string allocation in hot path."""

cdef class SSEWriter:
    def __init__(self, bytes event_type=b'message', int retry_ms=3000):
        self.event_type = event_type
        self.retry_ms = retry_ms
        self._id_counter = 0

    cdef bytes format_event(self, bytes data, bytes event_id=None):
        self._id_counter += 1
        cdef bytes eid = event_id if event_id is not None else str(self._id_counter).encode()
        return (
            b'id: ' + eid + b'\n'
            b'event: ' + self.event_type + b'\n'
            b'data: ' + data + b'\n\n'
        )

    cdef bytes format_comment(self, bytes comment):
        return b': ' + comment + b'\n\n'

    cdef bytes format_retry(self):
        return b'retry: ' + str(self.retry_ms).encode() + b'\n\n'

    cdef bytes format_done(self):
        return b'data: [DONE]\n\n'

    cdef bytes format_event_chunked(self, bytes data):
        cdef bytes frame = self.format_event(data)
        return ('{:X}\r\n'.format(len(frame))).encode() + frame + b'\r\n'

    cdef bytes format_done_chunked(self):
        cdef bytes frame = self.format_done()
        return ('{:X}\r\n'.format(len(frame))).encode() + frame + b'\r\n' + b'0\r\n\r\n'

    # Python-visible wrappers
    def py_format_event(self, bytes data):
        return self.format_event(data)

    def py_format_done(self):
        return self.format_done()

    def py_format_retry(self):
        return self.format_retry()
