import asyncio
import logging

logger = logging.getLogger("ember.eventloop")

_BACKEND = "asyncio"
_policy  = None


def install_best_event_loop(num_bufs: int = 256, buf_size: int = 8192) -> str:
    """Install the best available event-loop policy.

    num_bufs / buf_size configure the io_uring buffer pool when present.
    Defaults: 256 × 8 KB = 2 MB. The probe uses tiny buffers to avoid paying
    the full pool cost just to detect kernel support.
    """
    global _BACKEND, _policy
    try:
        from .uring import UringEventLoopPolicy, UringSelector
        probe = UringSelector(queue_depth=2, num_bufs=2, buf_size=4096)
        probe.close()
        _policy = UringEventLoopPolicy(num_bufs=num_bufs, buf_size=buf_size)
        asyncio.set_event_loop_policy(_policy)
        _BACKEND = "uring"
        logger.info("ember: io_uring event loop active (pool: %d × %d bytes = %.1f MB)",
                    num_bufs, buf_size, num_bufs * buf_size / 1024 / 1024)
        return "uring"
    except Exception as exc:
        logger.debug("io_uring unavailable (%s), trying uvloop", exc)
    try:
        import uvloop
        uvloop.install()
        _BACKEND = "uvloop"
        return "uvloop"
    except ImportError:
        pass
    return "asyncio"


def new_event_loop():
    return _policy.new_event_loop() if _policy else asyncio.new_event_loop()


def get_backend() -> str:
    return _BACKEND
