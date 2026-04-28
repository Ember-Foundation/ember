import asyncio
import logging

logger = logging.getLogger("ember.eventloop")

_BACKEND = "asyncio"
_policy  = None


def install_best_event_loop() -> str:
    global _BACKEND, _policy
    try:
        from .uring import UringEventLoopPolicy, UringSelector
        probe = UringSelector(queue_depth=2)
        probe.close()
        _policy = UringEventLoopPolicy()
        asyncio.set_event_loop_policy(_policy)
        _BACKEND = "uring"
        logger.info("ember: io_uring event loop active")
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
