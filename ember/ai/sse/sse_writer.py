"""
SSE frame encoder.
In production, compiled by Cython via sse_writer.pxd.
The cdef methods operate on C byte arrays via PyBytes_FromStringAndSize.
"""


class SSEWriter:
    """Encodes Server-Sent Events frames.

    Kept stateful (id counter) so callers don't need to manage sequence IDs.
    All methods are pure byte manipulation — no Python string allocation in
    the compiled form.
    """

    __slots__ = ("event_type", "retry_ms", "_id_counter")

    def __init__(self, event_type: bytes = b"message", retry_ms: int = 3000) -> None:
        self.event_type = event_type
        self.retry_ms = retry_ms
        self._id_counter = 0

    def format_event(self, data: bytes, event_id: bytes | None = None) -> bytes:
        self._id_counter += 1
        eid = event_id or str(self._id_counter).encode()
        return (
            b"id: " + eid + b"\n"
            b"event: " + self.event_type + b"\n"
            b"data: " + data + b"\n\n"
        )

    def format_comment(self, comment: bytes) -> bytes:
        return b": " + comment + b"\n\n"

    def format_retry(self) -> bytes:
        return b"retry: " + str(self.retry_ms).encode() + b"\n\n"

    def format_done(self) -> bytes:
        return b"data: [DONE]\n\n"

    def format_event_chunked(self, data: bytes) -> bytes:
        frame = self.format_event(data)
        return ("{:X}\r\n".format(len(frame))).encode() + frame + b"\r\n"

    def format_done_chunked(self) -> bytes:
        frame = self.format_done()
        return ("{:X}\r\n".format(len(frame))).encode() + frame + b"\r\n" + b"0\r\n\r\n"
