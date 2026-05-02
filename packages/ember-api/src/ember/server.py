"""Ember: top-level server class.

Manages worker process spawning, socket creation with SO_REUSEPORT,
dead-worker revival (necromancer), and graceful shutdown.

Cross-platform notes:
  Linux/macOS — fork-based multi-process workers sharing a SO_REUSEPORT socket.
  Windows      — SO_REUSEPORT unavailable; multiprocessing uses spawn and cannot
                 pickle the app object. Falls back to single-process in-process
                 event loop (workers= parameter is ignored on Windows).
"""
from __future__ import annotations
import asyncio
import logging
import os
import signal
import socket
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from multiprocessing import Process

from .application import EmberApplication

logger = logging.getLogger("ember")

_IS_WINDOWS    = sys.platform == "win32"
_HAS_REUSEPORT = hasattr(socket, "SO_REUSEPORT")


def _print_banner(host: str, port: int, workers: int, debug: bool) -> None:
    mode = "DEBUG" if debug else "PRODUCTION"
    print(
        f"\n  🔥 Ember  |  {host}:{port}  |  {workers} workers  |  {mode}\n",
        flush=True,
    )


def _make_socket(host: str, port: int) -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if _HAS_REUSEPORT:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, port))
    sock.listen(4096)
    sock.setblocking(False)
    return sock


class Ember(EmberApplication):
    """Entry point: configure routes, then call .run()."""

    def run(
        self,
        host: str = "127.0.0.1",
        port: int = 8000,
        workers: int | None = None,
        debug: bool = False,
        block: bool = True,
        necromancer: bool = True,
        startup_message: bool = True,
        thread_pool_workers: int | None = None,
        io_uring_num_bufs: int = 256,
        io_uring_buf_size: int = 8192,
    ) -> None:
        """Start the Ember server.

        io_uring_num_bufs / io_uring_buf_size tune the io_uring shared buffer
        pool (Linux only; ignored on macOS/Windows). Defaults: 256 × 8 KB =
        2 MB. Raise for very high concurrency or large request bodies; e.g.
        1024 × 32 KB = 32 MB matches the legacy default.
        num_bufs must be a power of two; buf_size must be ≤ 65535.
        """
        self.debug = debug

        if _IS_WINDOWS:
            # Windows: no SO_REUSEPORT, no fork — run single-process in-process.
            if workers and workers > 1:
                logger.warning(
                    "Windows does not support multi-process workers. "
                    "Running with 1 worker (in-process event loop)."
                )
            num_workers = 1
            if startup_message:
                _print_banner(host, port, num_workers, debug)
            sock = _make_socket(host, port)
            self._run_inprocess(host, port, sock, thread_pool_workers,
                                io_uring_num_bufs, io_uring_buf_size)
            return

        # ── Linux / macOS: fork-based multi-process workers ──────────────────
        num_workers = workers or (os.cpu_count() or 2) + 2
        if startup_message:
            _print_banner(host, port, num_workers, debug)

        sock = _make_socket(host, port)

        # workers=1: skip the supervisor and serve in-process. Saves ~22 MB
        # (one Python interpreter) compared to fork+monitor when there's
        # nothing to load-balance and nothing to revive.
        if num_workers == 1:
            self._run_inprocess(host, port, sock, thread_pool_workers,
                                io_uring_num_bufs, io_uring_buf_size)
            return

        from .workers.handler import RequestHandler

        keep_alive = self._server_limits.keep_alive_timeout
        worker_processes: list[Process] = []

        for _ in range(num_workers):
            p = RequestHandler(
                app=self,
                host=host,
                port=port,
                sock=sock,
                thread_pool_workers=thread_pool_workers,
                keep_alive_timeout=keep_alive,
                debug=debug,
                io_uring_num_bufs=io_uring_num_bufs,
                io_uring_buf_size=io_uring_buf_size,
            )
            p.start()
            worker_processes.append(p)

        if not block:
            return

        def _shutdown(signum, frame):
            logger.info("Received signal %d, shutting down...", signum)
            for p in worker_processes:
                if p.is_alive():
                    p.terminate()
            sys.exit(0)

        signal.signal(signal.SIGTERM, _shutdown)
        signal.signal(signal.SIGINT, _shutdown)

        try:
            while True:
                for i, p in enumerate(worker_processes):
                    if not p.is_alive():
                        if necromancer:
                            logger.warning("Worker %d (PID %d) died, reviving...", i, p.pid)
                            new_p = RequestHandler(
                                app=self,
                                host=host,
                                port=port,
                                sock=sock,
                                thread_pool_workers=thread_pool_workers,
                                keep_alive_timeout=keep_alive,
                                debug=debug,
                                io_uring_num_bufs=io_uring_num_bufs,
                                io_uring_buf_size=io_uring_buf_size,
                            )
                            new_p.start()
                            worker_processes[i] = new_p
                        else:
                            logger.error("Worker %d died. necromancer=False, not reviving.", i)
                time.sleep(1)
        except (KeyboardInterrupt, SystemExit):
            logger.info("Shutting down %d workers...", len(worker_processes))
            for p in worker_processes:
                if p.is_alive():
                    p.terminate()
            for p in worker_processes:
                p.join(timeout=10)
            sock.close()

    def _run_inprocess(
        self,
        host: str,
        port: int,
        sock: socket.socket,
        thread_pool_workers: int | None,
        io_uring_num_bufs: int = 256,
        io_uring_buf_size: int = 8192,
    ) -> None:
        """Single-process event loop — used on Windows and when workers=1 is forced."""
        try:
            from .eventloop import install_best_event_loop, new_event_loop
            install_best_event_loop(num_bufs=io_uring_num_bufs, buf_size=io_uring_buf_size)
            loop = new_event_loop()
        except Exception:
            loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        n_threads = thread_pool_workers or min(32, (os.cpu_count() or 4) + 4)
        executor = ThreadPoolExecutor(max_workers=n_threads, thread_name_prefix="ember-worker")
        loop.set_default_executor(executor)

        shutdown = asyncio.Event()

        # SIGTERM not available on Windows; Ctrl+C raises KeyboardInterrupt instead.
        if not _IS_WINDOWS:
            def _sig(*_):
                loop.call_soon_threadsafe(shutdown.set)
            signal.signal(signal.SIGTERM, _sig)
            signal.signal(signal.SIGINT, _sig)

        from .workers.handler import RequestHandler
        handler = RequestHandler(
            app=self,
            host=host,
            port=port,
            sock=sock,
            thread_pool_workers=thread_pool_workers,
            keep_alive_timeout=self._server_limits.keep_alive_timeout,
            debug=self.debug,
            io_uring_num_bufs=io_uring_num_bufs,
            io_uring_buf_size=io_uring_buf_size,
        )

        try:
            loop.run_until_complete(handler._serve(loop, shutdown))
        except KeyboardInterrupt:
            loop.run_until_complete(handler._serve_shutdown(shutdown))
        finally:
            executor.shutdown(wait=False)
            sock.close()
