# cython: language_level=3, boundscheck=False, wraparound=False, cdivision=True
import asyncio
import collections
import selectors
import logging
import os
from selectors import SelectorKey, EVENT_READ, EVENT_WRITE
from libc.stdint cimport uint32_t, uint64_t, int32_t, int64_t, uint8_t, uint16_t
from libc.stdlib cimport malloc, free
from cpython.bytes cimport PyBytes_FromStringAndSize

cdef extern from "poll.h":
    int POLLIN
    int POLLOUT
    int POLLERR
    int POLLHUP

cdef extern from "sys/socket.h":
    int MSG_NOSIGNAL "MSG_NOSIGNAL"

cdef extern from "liburing.h":
    struct io_uring:
        pass
    struct io_uring_sqe:
        uint8_t  opcode
        uint8_t  flags
        int32_t  fd
        uint32_t len
        uint32_t poll32_events
        uint64_t user_data
        uint16_t buf_group
    struct io_uring_cqe:
        uint64_t user_data
        int32_t  res
        uint32_t flags
    struct io_uring_buf_ring:
        pass
    struct __kernel_timespec:
        int64_t tv_sec
        int64_t tv_nsec

    unsigned int IORING_SETUP_SINGLE_ISSUER "IORING_SETUP_SINGLE_ISSUER"
    unsigned int IORING_SETUP_COOP_TASKRUN  "IORING_SETUP_COOP_TASKRUN"
    unsigned int IORING_SETUP_DEFER_TASKRUN "IORING_SETUP_DEFER_TASKRUN"
    unsigned int IORING_POLL_ADD_MULTI      "IORING_POLL_ADD_MULTI"
    unsigned int IORING_CQE_F_MORE          "IORING_CQE_F_MORE"
    unsigned int IORING_CQE_F_BUFFER        "IORING_CQE_F_BUFFER"
    unsigned int IOSQE_BUFFER_SELECT        "IOSQE_BUFFER_SELECT"

    int  io_uring_queue_init(unsigned, io_uring*, unsigned) nogil
    void io_uring_queue_exit(io_uring*) nogil
    io_uring_sqe* io_uring_get_sqe(io_uring*) nogil
    void io_uring_prep_poll_add(io_uring_sqe*, int fd, uint32_t mask) nogil
    void io_uring_prep_poll_remove(io_uring_sqe*, uint64_t user_data) nogil
    void io_uring_prep_send(io_uring_sqe*, int fd, const void* buf, size_t len, int flags) nogil
    void io_uring_prep_recv_multishot(io_uring_sqe*, int fd, void* buf, size_t len, int flags) nogil
    void io_uring_sqe_set_data64(io_uring_sqe*, uint64_t) nogil
    int  io_uring_submit(io_uring*) nogil
    int  io_uring_submit_and_wait_timeout(
             io_uring*, io_uring_cqe**, unsigned, __kernel_timespec*, void*) nogil
    int  io_uring_peek_batch_cqe(io_uring*, io_uring_cqe**, unsigned) nogil
    void io_uring_cq_advance(io_uring*, unsigned) nogil
    io_uring_buf_ring* io_uring_setup_buf_ring(
             io_uring*, unsigned int, int, unsigned int, int*)
    int  io_uring_free_buf_ring(io_uring*, io_uring_buf_ring*, unsigned int, int)
    void io_uring_buf_ring_add(
             io_uring_buf_ring*, void*, unsigned short, unsigned short, int, int) nogil
    void io_uring_buf_ring_advance(io_uring_buf_ring*, int) nogil
    int  io_uring_buf_ring_mask(unsigned int) nogil


# ── Constants ─────────────────────────────────────────────────────────────────

DEF RING_DEPTH   = 4096
DEF BATCH_SIZE   = 64
DEF _EVENT_READ  = 1
DEF _EVENT_WRITE = 2
DEF NUM_BUFS      = 1024
DEF BUF_SIZE      = 32768   # unsigned short max = 65535; 32768 is safe
DEF BUF_GROUP     = 1
DEF BUF_RING_MASK = NUM_BUFS - 1   # compile-time constant; avoids io_uring_buf_ring_mask() call

# user_data encoding: bits 32+ clear = POLL (fd in bits 0–31)
#                     bit 32 set only = RECV (transport_id in bits 0–31)
#                     bit 33 set      = SEND (transport_id in bits 0–31)
DEF _RECV_BASE = 4294967296    # 1 << 32
DEF _SEND_BASE = 8589934592    # 2 << 32

logger = logging.getLogger("ember.eventloop.uring")


# ── UringSelector ─────────────────────────────────────────────────────────────

cdef class UringSelector:

    def __init__(self, unsigned int queue_depth=RING_DEPTH):
        self._fd_to_key         = {}
        self._map               = _SelectorMappingProxy(self._fd_to_key)
        self._multishot_fds     = set()
        self._pending_submit    = 0
        self._ring_open         = False
        self._transports        = {}
        self._next_transport_id = 0
        self._buf_pool          = NULL
        self._buf_ring          = NULL

        cdef unsigned int flags = (IORING_SETUP_SINGLE_ISSUER |
                                   IORING_SETUP_COOP_TASKRUN  |
                                   IORING_SETUP_DEFER_TASKRUN)
        cdef int ret = io_uring_queue_init(queue_depth, &self._ring, flags)
        if ret == -22:   # EINVAL — kernel < 6.1, retry without DEFER_TASKRUN
            ret = io_uring_queue_init(queue_depth, &self._ring,
                                      IORING_SETUP_COOP_TASKRUN)
        if ret < 0:
            raise OSError(-ret,
                f"io_uring_queue_init failed errno={-ret}. "
                f"Requires Linux 5.1+, /proc/sys/kernel/io_uring_disabled=0")
        self._ring_open = True

        self._buf_pool = <char*>malloc(NUM_BUFS * BUF_SIZE)
        if self._buf_pool == NULL:
            io_uring_queue_exit(&self._ring)
            self._ring_open = False
            raise MemoryError("Failed to allocate io_uring buffer pool")

        cdef int buf_ret = 0
        self._buf_ring = io_uring_setup_buf_ring(
            &self._ring, NUM_BUFS, BUF_GROUP, 0, &buf_ret)
        if self._buf_ring == NULL:
            free(self._buf_pool);  self._buf_pool = NULL
            io_uring_queue_exit(&self._ring);  self._ring_open = False
            raise OSError(-buf_ret,
                f"io_uring_setup_buf_ring failed errno={-buf_ret}")

        # Populate all buffers into the ring in one batch
        cdef int mask = BUF_RING_MASK
        cdef int i
        for i in range(NUM_BUFS):
            io_uring_buf_ring_add(
                self._buf_ring, self._buf_pool + i * BUF_SIZE,
                BUF_SIZE, i, mask, i)
        io_uring_buf_ring_advance(self._buf_ring, NUM_BUFS)

    # ── Selector interface ────────────────────────────────────────────────────

    def register(self, fileobj, int events, data=None):
        cdef int fd = _fd_from_fileobj(fileobj)
        if fd in self._fd_to_key:
            raise KeyError(f"{fileobj!r} is already registered")
        key = SelectorKey(fileobj=fileobj, fd=fd, events=events, data=data)
        self._fd_to_key[fd] = key
        self._arm_multishot(fd, _events_to_poll_mask(events))
        if self._pending_submit > 0:
            io_uring_submit(&self._ring)
            self._pending_submit = 0
        return key

    def unregister(self, fileobj):
        cdef int fd = _fd_from_fileobj(fileobj)
        key = self._fd_to_key.pop(fd, None)
        if key is None:
            raise KeyError(f"{fileobj!r} is not registered")
        if fd in self._multishot_fds:
            self._cancel_poll(fd)
            self._multishot_fds.discard(fd)
            if self._pending_submit > 0:
                io_uring_submit(&self._ring)
                self._pending_submit = 0
        return key

    def modify(self, fileobj, int events, data=None):
        cdef int fd = _fd_from_fileobj(fileobj)
        existing = self._fd_to_key.get(fd)
        if existing is None:
            raise KeyError(f"{fileobj!r} is not registered")
        if events != existing.events:
            self.unregister(fileobj)
            return self.register(fileobj, events, data)
        if data != existing.data:
            new_key = existing._replace(data=data)
            self._fd_to_key[fd] = new_key
            return new_key
        return existing

    def select(self, timeout=None):
        cdef __kernel_timespec ts
        cdef io_uring_cqe*  cqe_ptr = NULL
        cdef io_uring_cqe*  cqes[BATCH_SIZE]
        cdef int ret, n
        cdef list ready = []

        if timeout == 0:
            if self._pending_submit > 0:
                io_uring_submit(&self._ring)
                self._pending_submit = 0
            n = io_uring_peek_batch_cqe(&self._ring, cqes, BATCH_SIZE)
            if n > 0:
                self._drain_batch(cqes, n, ready)
                io_uring_cq_advance(&self._ring, n)
                if self._pending_submit > 0:
                    io_uring_submit(&self._ring)
                    self._pending_submit = 0
            return ready

        if timeout is None or timeout < 0:
            ts.tv_sec  = 0x7FFFFFFFFFFFFFFF
            ts.tv_nsec = 0
        else:
            ts.tv_sec  = <int64_t>timeout
            ts.tv_nsec = <int64_t>((timeout - <double>ts.tv_sec) * 1_000_000_000)

        with nogil:
            self._pending_submit = 0
            ret = io_uring_submit_and_wait_timeout(&self._ring, &cqe_ptr, 1, &ts, NULL)
            n = io_uring_peek_batch_cqe(&self._ring, cqes, BATCH_SIZE)

        if ret < 0 and ret != -62 and ret != -4:   # ignore ETIME, EINTR
            logger.warning("io_uring_submit_and_wait_timeout ret=%d", ret)

        if n > 0:
            self._drain_batch(cqes, n, ready)
            io_uring_cq_advance(&self._ring, n)
            if self._pending_submit > 0:
                io_uring_submit(&self._ring)
                self._pending_submit = 0
        return ready

    def get_key(self, fileobj):
        fd = _fd_from_fileobj(fileobj)
        key = self._fd_to_key.get(fd)
        if key is None:
            raise KeyError(f"{fileobj!r} is not registered")
        return key

    def get_map(self):
        return self._map

    def close(self):
        self._fd_to_key.clear()
        self._multishot_fds.clear()
        self._transports.clear()
        if self._buf_ring != NULL and self._ring_open:
            io_uring_free_buf_ring(&self._ring, self._buf_ring, NUM_BUFS, BUF_GROUP)
            self._buf_ring = NULL
        if self._buf_pool != NULL:
            free(self._buf_pool)
            self._buf_pool = NULL
        if self._ring_open:
            io_uring_queue_exit(&self._ring)
            self._ring_open = False

    def __enter__(self): return self
    def __exit__(self, *a): self.close()

    # ── Transport registration ────────────────────────────────────────────────

    cpdef uint64_t _register_transport(self, UringTransport transport):
        cdef uint64_t id_ = self._next_transport_id
        self._next_transport_id += 1
        self._transports[id_] = transport
        return id_

    cpdef void _unregister_transport(self, uint64_t id_):
        self._transports.pop(id_, None)

    cpdef void _flush(self):
        if self._pending_submit > 0:
            io_uring_submit(&self._ring)
            self._pending_submit = 0

    # ── Internal cdef helpers ─────────────────────────────────────────────────

    cdef void _arm_multishot(self, int fd, int mask):
        cdef io_uring_sqe* sqe = io_uring_get_sqe(&self._ring)
        if sqe == NULL:
            io_uring_submit(&self._ring);  self._pending_submit = 0
            sqe = io_uring_get_sqe(&self._ring)
        if sqe == NULL:
            logger.error("SQ full: POLL fd %d dropped", fd);  return
        io_uring_prep_poll_add(sqe, fd, mask)
        io_uring_sqe_set_data64(sqe, <uint64_t>fd)
        sqe.len = IORING_POLL_ADD_MULTI      # MUST be after prep_poll_add (zeroes len)
        self._multishot_fds.add(fd)
        self._pending_submit += 1

    cdef void _cancel_poll(self, int fd):
        cdef io_uring_sqe* sqe = io_uring_get_sqe(&self._ring)
        if sqe == NULL:
            io_uring_submit(&self._ring);  self._pending_submit = 0
            sqe = io_uring_get_sqe(&self._ring)
        if sqe != NULL:
            io_uring_prep_poll_remove(sqe, <uint64_t>fd)
            io_uring_sqe_set_data64(sqe, <uint64_t>fd)
            self._pending_submit += 1

    cpdef void _submit_recv(self, UringTransport transport):
        cdef io_uring_sqe* sqe = io_uring_get_sqe(&self._ring)
        if sqe == NULL:
            io_uring_submit(&self._ring);  self._pending_submit = 0
            sqe = io_uring_get_sqe(&self._ring)
        if sqe == NULL:
            logger.error("SQ full: RECV dropped");  return
        io_uring_prep_recv_multishot(sqe, transport._fd, NULL, 0, 0)
        sqe.flags    |= IOSQE_BUFFER_SELECT
        sqe.buf_group = BUF_GROUP
        io_uring_sqe_set_data64(sqe, <uint64_t>_RECV_BASE + transport._transport_id)
        transport._recv_armed = True
        self._pending_submit += 1

    cpdef void _submit_send(self, int fd, bytes data, uint64_t transport_id):
        cdef io_uring_sqe* sqe = io_uring_get_sqe(&self._ring)
        if sqe == NULL:
            io_uring_submit(&self._ring);  self._pending_submit = 0
            sqe = io_uring_get_sqe(&self._ring)
        if sqe == NULL:
            logger.error("SQ full: SEND dropped");  return
        io_uring_prep_send(sqe, fd, <const char*>data, len(data), MSG_NOSIGNAL)
        io_uring_sqe_set_data64(sqe, <uint64_t>_SEND_BASE + transport_id)
        self._pending_submit += 1

    cdef void _return_buffer(self, int buf_id):
        # Pure memory write — no SQE, no syscall.
        io_uring_buf_ring_add(
            self._buf_ring, self._buf_pool + buf_id * BUF_SIZE,
            BUF_SIZE, buf_id, BUF_RING_MASK, 0)
        io_uring_buf_ring_advance(self._buf_ring, 1)

    cdef void _drain_batch(self, io_uring_cqe** cqes, int count, list ready):
        cdef int i, fd, res, sel_events, buf_id
        cdef uint32_t cqe_flags
        cdef uint64_t user_data
        cdef io_uring_cqe* cqe
        cdef object py_transport, py_key
        cdef UringTransport t

        for i in range(count):
            cqe       = cqes[i]
            user_data = cqe.user_data
            res       = cqe.res
            cqe_flags = cqe.flags

            if user_data >= <uint64_t>_SEND_BASE:
                py_transport = self._transports.get(user_data - <uint64_t>_SEND_BASE)
                if py_transport is not None:
                    (<UringTransport>py_transport)._on_send_done(res)
                continue

            if user_data >= <uint64_t>_RECV_BASE:
                py_transport = self._transports.get(user_data - <uint64_t>_RECV_BASE)
                if py_transport is not None:
                    t = <UringTransport>py_transport
                    if not (cqe_flags & IORING_CQE_F_MORE):
                        t._recv_armed = False
                    if res == -105:   # ENOBUFS — pool exhausted, SQE cancelled
                        if not t._closing and not t._paused:
                            self._submit_recv(t)
                    elif cqe_flags & IORING_CQE_F_BUFFER:
                        buf_id = <int>(cqe_flags >> 16)
                        t._on_recv(res, buf_id, self._buf_pool + buf_id * BUF_SIZE)
                        if not t._recv_armed and not t._closing and not t._paused:
                            self._submit_recv(t)
                    else:
                        # EOF or error with no buffer assigned
                        t._on_recv(res, -1, NULL)
                continue

            # ── POLL event (self-pipe / timer fds) ────────────────────────────
            fd = <int>user_data
            if res == -125:   # -ECANCELED from POLL_REMOVE
                self._multishot_fds.discard(fd)
                continue
            py_key = self._fd_to_key.get(fd)
            if py_key is None:
                self._multishot_fds.discard(fd)
                continue
            if res < 0:
                ready.append((py_key, py_key.events))
                self._multishot_fds.discard(fd)
                if fd in self._fd_to_key:
                    self._arm_multishot(fd, _events_to_poll_mask(py_key.events))
                continue
            sel_events = _poll_to_selector(res, py_key.events)
            if sel_events:
                ready.append((py_key, sel_events))
            if not (cqe_flags & IORING_CQE_F_MORE):
                self._multishot_fds.discard(fd)
                if fd in self._fd_to_key:
                    self._arm_multishot(fd, _events_to_poll_mask(py_key.events))


# ── Helper functions ──────────────────────────────────────────────────────────

cdef inline int _events_to_poll_mask(int events) nogil:
    cdef int mask = POLLERR | POLLHUP
    if events & _EVENT_READ:  mask |= POLLIN
    if events & _EVENT_WRITE: mask |= POLLOUT
    return mask


cdef inline int _poll_to_selector(int res, int registered) nogil:
    cdef int events = 0
    if res & (POLLIN  | POLLERR | POLLHUP): events |= _EVENT_READ
    if res & (POLLOUT | POLLERR | POLLHUP): events |= _EVENT_WRITE
    return events & registered


def _fd_from_fileobj(fileobj):
    if isinstance(fileobj, int):
        return fileobj
    return fileobj.fileno()


class _SelectorMappingProxy:
    __slots__ = ("_fd_to_key",)

    def __init__(self, fd_to_key):
        self._fd_to_key = fd_to_key

    def __len__(self):
        return len(self._fd_to_key)

    def __getitem__(self, fileobj):
        fd = _fd_from_fileobj(fileobj)
        key = self._fd_to_key.get(fd)
        if key is None:
            raise KeyError(fileobj)
        return key

    def __iter__(self):
        return iter(self._fd_to_key)

    def __contains__(self, fileobj):
        try:
            return _fd_from_fileobj(fileobj) in self._fd_to_key
        except (AttributeError, TypeError):
            return False

    # asyncio 3.13's selector_events calls selector.get_map().get(fd) directly
    # (3.12 used __getitem__ with try/except). Provide the Mapping-style get.
    def get(self, fileobj, default=None):
        try:
            fd = _fd_from_fileobj(fileobj)
        except (AttributeError, TypeError):
            return default
        return self._fd_to_key.get(fd, default)

    def values(self):
        return self._fd_to_key.values()


# ── UringTransport ────────────────────────────────────────────────────────────

cdef class UringTransport:
    """asyncio Transport backed by io_uring multishot RECV / SEND.

    Hot-path methods (_on_recv, _on_send_done, _do_send) are cdef — dispatched
    via C vtable from _drain_batch with no Python method lookup.
    """

    def __init__(self, loop, sock, protocol, waiter=None, extra=None, server=None):
        cdef UringSelector selector = loop._selector

        self._extra = extra if extra is not None else {}
        try:
            self._extra["socket"]   = sock
            self._extra["sockname"] = sock.getsockname()
            self._extra["peername"] = sock.getpeername()
        except Exception:
            pass

        self._loop               = loop
        self._selector           = selector
        self._sock               = sock
        self._fd                 = sock.fileno()
        self._protocol           = protocol
        self._server             = server
        self._closing            = False
        self._conn_lost          = 0
        self._recv_armed         = False
        self._send_queue         = collections.deque()
        self._send_inflight      = False
        self._send_inflight_data = None
        self._paused             = False

        self._transport_id = selector._register_transport(self)
        loop._transports[self._fd] = self

        if server is not None:
            server._attach()

        sock.setblocking(False)

        # Defer RECV until after connection_made runs — prevents data_received
        # from firing before connection_made on fast clients.
        loop.call_soon(protocol.connection_made, self)
        loop.call_soon(self._start_recv_soon)
        if waiter is not None:
            loop.call_soon(waiter.set_result, None)

    # ── asyncio Transport interface ───────────────────────────────────────────

    cpdef void _start_recv_soon(self):
        if not self._closing and not self._paused and not self._recv_armed:
            self._selector._submit_recv(self)
            self._selector._flush()

    def is_reading(self):
        return not self._paused and not self._closing

    def pause_reading(self):
        self._paused = True

    def resume_reading(self):
        if self._paused and not self._closing:
            self._paused = False
            if not self._recv_armed:
                self._selector._submit_recv(self)
                self._selector._flush()

    def write(self, data):
        if not data or self._conn_lost or self._closing:
            return
        if not isinstance(data, bytes):
            data = bytes(data)
        if self._send_inflight:
            self._send_queue.append(data)
            return
        try:
            n = self._sock.send(data)
            if n == len(data):
                return
            data = data[n:]
        except (BlockingIOError, InterruptedError):
            pass
        except Exception:
            self._conn_lost += 1
            return
        self._do_send(data)

    def write_eof(self):
        pass

    def can_write_eof(self):
        return False

    def set_write_buffer_limits(self, high=None, low=None):
        pass

    def get_write_buffer_size(self):
        n = sum(len(d) for d in self._send_queue)
        if self._send_inflight_data is not None:
            n += len(self._send_inflight_data)
        return n

    def is_closing(self):
        return self._closing

    def close(self):
        if self._closing:
            return
        self._closing = True
        if not self._send_inflight:
            self._loop.call_soon(self._call_connection_lost, None)

    def abort(self):
        self._closing = True
        self._send_queue.clear()
        self._send_inflight      = False
        self._send_inflight_data = None
        self._call_connection_lost(None)

    def get_extra_info(self, name, default=None):
        return self._extra.get(name, default)

    # ── Called by UringSelector._drain_batch via C vtable ────────────────────

    cdef void _on_recv(self, int n, int buf_id, const char* buf_ptr):
        cdef bytes data
        if self._closing:
            if buf_ptr != NULL:
                self._selector._return_buffer(buf_id)
            return
        if buf_ptr == NULL or n <= 0:
            # EOF (n==0), error (n<0), or no-buffer case
            if buf_ptr != NULL:
                self._selector._return_buffer(buf_id)
            self._closing = True
            self._loop.call_soon(
                self._call_connection_lost,
                None if n >= 0 else OSError(-n, os.strerror(-n)))
            return
        # Single copy from kernel buffer into a new bytes object, then
        # immediately return the buffer slot back to the ring (memory write only).
        data = PyBytes_FromStringAndSize(buf_ptr, n)
        self._selector._return_buffer(buf_id)
        try:
            self._protocol.data_received(data)
        except Exception as exc:
            self._loop.call_exception_handler({
                "message": "protocol.data_received() raised",
                "exception": exc,
                "transport": self,
                "protocol": self._protocol,
            })
        # Multishot SQE stays live — _drain_batch re-arms only when CQE_F_MORE absent.

    cdef void _on_send_done(self, int res):
        self._send_inflight_data = None
        self._send_inflight      = False
        if res < 0 and res not in (-32, -104):   # ignore EPIPE, ECONNRESET
            self._conn_lost += 1
        if self._send_queue:
            self._do_send(self._send_queue.popleft())
        elif self._closing:
            self._loop.call_soon(self._call_connection_lost, None)

    # ── Internal ──────────────────────────────────────────────────────────────

    cdef void _do_send(self, bytes data):
        self._send_inflight      = True
        self._send_inflight_data = data
        self._selector._submit_send(self._fd, data, self._transport_id)

    cpdef void _call_connection_lost(self, object exc):
        try:
            self._protocol.connection_lost(exc)
        finally:
            self._sock.close()
            self._selector._unregister_transport(self._transport_id)
            self._loop._transports.pop(self._fd, None)
            server = self._server
            self._server = None
            if server is not None:
                server._detach()


# ── UringEventLoop ────────────────────────────────────────────────────────────

class UringEventLoop(asyncio.SelectorEventLoop):
    """asyncio event loop backed by io_uring POLL + multishot RECV/SEND."""

    def __init__(self):
        super().__init__(selector=UringSelector(queue_depth=RING_DEPTH))
        self.set_task_factory(asyncio.eager_task_factory)

    def _make_socket_transport(self, sock, protocol, waiter=None,
                               extra=None, server=None):
        return UringTransport(self, sock, protocol, waiter, extra, server)


class UringEventLoopPolicy(asyncio.DefaultEventLoopPolicy):
    def new_event_loop(self):
        return UringEventLoop()
