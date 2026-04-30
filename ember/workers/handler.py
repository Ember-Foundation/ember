"""Worker process: owns one uvloop event loop + thread pool executor.

Each worker process binds to the shared socket via SO_REUSEPORT so the
kernel load-balances incoming connections without a master process.

Thread pool: for CPU-bound AI inference calls (local model inference,
tokenization, embedding) that must not block the event loop.
"""
from __future__ import annotations
import asyncio
import logging
import os
import signal
import socket
import sys
from concurrent.futures import ThreadPoolExecutor
from multiprocessing import Process
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..application import EmberApplication

logger = logging.getLogger("ember.worker")

_IS_WINDOWS    = sys.platform == "win32"
_HAS_REUSEPORT = hasattr(socket, "SO_REUSEPORT")


class RequestHandler(Process):
    def __init__(
        self,
        app: "EmberApplication",
        host: str,
        port: int,
        sock: socket.socket | None = None,
        thread_pool_workers: int | None = None,
        keep_alive_timeout: int = 30,
        debug: bool = False,
        io_uring_num_bufs: int = 256,
        io_uring_buf_size: int = 8192,
    ) -> None:
        super().__init__()
        self.app = app
        self.host = host
        self.port = port
        self.sock = sock
        self.thread_pool_workers = thread_pool_workers or min(32, (os.cpu_count() or 4) + 4)
        self.keep_alive_timeout = keep_alive_timeout
        self.debug = debug
        self.io_uring_num_bufs = io_uring_num_bufs
        self.io_uring_buf_size = io_uring_buf_size
        self.daemon = True

    def run(self) -> None:
        try:
            from ember.eventloop import install_best_event_loop, new_event_loop
            # Re-install the policy in the forked worker so each worker gets
            # its own io_uring ring + buffer pool sized as the user requested.
            install_best_event_loop(
                num_bufs=self.io_uring_num_bufs,
                buf_size=self.io_uring_buf_size,
            )
            loop = new_event_loop()
        except Exception:
            loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        executor = ThreadPoolExecutor(
            max_workers=self.thread_pool_workers,
            thread_name_prefix="ember-worker",
        )
        loop.set_default_executor(executor)

        _shutdown = asyncio.Event()

        # SIGTERM is not a real signal on Windows — skip registration there.
        if not _IS_WINDOWS:
            def _handle_sigterm(*_):
                loop.call_soon_threadsafe(_shutdown.set)
            signal.signal(signal.SIGTERM, _handle_sigterm)
            signal.signal(signal.SIGINT, _handle_sigterm)

        loop.run_until_complete(self._serve(loop, _shutdown))
        executor.shutdown(wait=True)

    async def _serve(self, loop: asyncio.AbstractEventLoop, shutdown: asyncio.Event) -> None:
        import gc
        from ..protocol import Connection
        from ..constants import Events
        from .reaper import Reaper

        connections: set = set()

        await self.app.initialize()
        await self.app.call_hooks_by_event(Events.BEFORE_SERVER_START, self.app.components)

        # Move every long-lived startup object out of the GC scan set so
        # gen-2 collections don't traverse them on every request. The router,
        # route table, and component graph never become unreachable.
        gc.collect()
        gc.freeze()

        def protocol_factory():
            conn = Connection(self.app)
            connections.add(conn)
            return conn

        # reuse_port is Linux/macOS only; pass False on Windows.
        use_reuse_port = _HAS_REUSEPORT

        if self.sock:
            server = await loop.create_server(
                protocol_factory,
                sock=self.sock,
                reuse_port=use_reuse_port,
                backlog=4096,
            )
        else:
            server = await loop.create_server(
                protocol_factory,
                host=self.host,
                port=self.port,
                reuse_port=use_reuse_port,
                backlog=4096,
            )

        reaper = Reaper(connections, keep_alive_timeout=self.keep_alive_timeout)
        reaper.start()

        await self.app.call_hooks_by_event(Events.AFTER_SERVER_START, self.app.components)
        logger.info("Worker PID %d listening on %s:%d", os.getpid(), self.host, self.port)

        await shutdown.wait()
        await self._serve_shutdown(shutdown, server, connections, reaper)

    async def _serve_shutdown(
        self,
        shutdown: asyncio.Event,
        server=None,
        connections: set | None = None,
        reaper=None,
    ) -> None:
        from ..constants import Events
        import asyncio

        await self.app.call_hooks_by_event(Events.BEFORE_SERVER_STOP, self.app.components)

        for cache in self.app._route_caches:
            await cache.close()

        if server:
            server.close()
        if reaper:
            reaper.stop()

        if connections:
            loop = asyncio.get_event_loop()
            deadline = loop.time() + 10.0
            while connections and loop.time() < deadline:
                await asyncio.sleep(0.1)
            for conn in list(connections):
                if not conn.closed:
                    conn.close()

        if server:
            await server.wait_closed()

        logger.info("Worker PID %d shut down cleanly", os.getpid())
