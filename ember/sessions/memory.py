from __future__ import annotations
from typing import Any

from .base import SessionEngine


class InMemorySessionEngine(SessionEngine):
    """In-memory session engine for development and testing."""

    def __init__(self) -> None:
        self._store: dict[str, dict] = {}

    async def get(self, session_id: str, key: str) -> Any:
        return self._store.get(session_id, {}).get(key)

    async def set(self, session_id: str, key: str, value: Any) -> None:
        if session_id not in self._store:
            self._store[session_id] = {}
        self._store[session_id][key] = value

    async def set_many(self, session_id: str, data: dict) -> None:
        if session_id not in self._store:
            self._store[session_id] = {}
        self._store[session_id].update(data)

    async def delete(self, session_id: str, key: str) -> None:
        if session_id in self._store:
            self._store[session_id].pop(key, None)

    async def destroy(self, session_id: str) -> None:
        self._store.pop(session_id, None)
