"""Idle connection reaper thread.

Walks active connections every `interval` seconds and closes those that
have been idle for longer than `keep_alive_timeout`.
"""
from __future__ import annotations
import logging
import threading
import time

logger = logging.getLogger("ember.reaper")


class Reaper(threading.Thread):
    def __init__(
        self,
        connections: set,
        keep_alive_timeout: int = 30,
        interval: float = 5.0,
    ) -> None:
        super().__init__(daemon=True, name="ember-reaper")
        self.connections = connections
        self.keep_alive_timeout = keep_alive_timeout
        self.interval = interval
        self._stop_event = threading.Event()

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        while not self._stop_event.wait(self.interval):
            now = time.monotonic()
            stale = [
                conn for conn in list(self.connections)
                if not conn.closed and now - conn._last_activity > self.keep_alive_timeout
            ]
            for conn in stale:
                try:
                    conn.close()
                except Exception:
                    pass
            if stale:
                logger.debug("Reaped %d idle connections", len(stale))
