# cython: language_level=3
from libc.stdint cimport uint64_t, int32_t, uint32_t

cdef extern from "liburing.h":
    struct io_uring:
        pass
    struct io_uring_cqe:
        uint64_t user_data
        int32_t  res
        uint32_t flags
    struct io_uring_buf_ring:
        pass

# Forward declarations — breaks the circular dependency between the two classes.
cdef class UringSelector
cdef class UringTransport

cdef class UringSelector:
    cdef io_uring           _ring
    cdef bint               _ring_open
    cdef int                _pending_submit
    cdef set                _multishot_fds
    cdef dict               _fd_to_key
    cdef object             _map
    cdef dict               _transports
    cdef uint64_t           _next_transport_id
    cdef char*              _buf_pool          # flat slab: NUM_BUFS × BUF_SIZE bytes
    cdef io_uring_buf_ring* _buf_ring          # shared-memory ring; return = memory write

    cdef void      _arm_multishot(self, int fd, int mask)
    cdef void      _cancel_poll(self, int fd)
    cdef void      _drain_batch(self, io_uring_cqe** cqes, int count, list ready)
    cdef void      _return_buffer(self, int buf_id)
    cpdef void     _submit_recv(self, UringTransport transport)
    cpdef void     _submit_send(self, int fd, bytes data, uint64_t transport_id)
    cpdef void     _flush(self)
    cpdef uint64_t _register_transport(self, UringTransport transport)
    cpdef void     _unregister_transport(self, uint64_t id_)

cdef class UringTransport:
    cdef object        __weakref__      # enables loop._transports WeakValueDictionary
    cdef object        _loop
    cdef UringSelector _selector        # typed — C field access, no dict lookup
    cdef object        _sock
    cdef int           _fd
    cdef object        _protocol
    cdef object        _server
    cdef bint          _closing
    cdef int           _conn_lost
    cdef uint64_t      _transport_id
    cdef object        _send_queue
    cdef bint          _send_inflight
    cdef object        _send_inflight_data
    cdef bint          _paused
    cdef bint          _recv_armed       # True while a multishot RECV SQE is live
    cdef dict          _extra

    cpdef void _start_recv_soon(self)
    cpdef void _call_connection_lost(self, object exc)
    cdef void  _on_recv(self, int n, int buf_id, const char* buf_ptr)
    cdef void  _on_send_done(self, int res)
    cdef void  _do_send(self, bytes data)
