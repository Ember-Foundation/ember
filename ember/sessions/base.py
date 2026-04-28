from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any


class Session:
    """Per-request session wrapper."""

    def __init__(self, session_id: str, engine: "SessionEngine") -> None:
        self.session_id = session_id
        self._engine = engine
        self._data: dict[str, Any] = {}
        self._dirty = False

    async def get(self, key: str) -> Any:
        if key in self._data:
            return self._data[key]
        value = await self._engine.get(self.session_id, key)
        if value is not None:
            self._data[key] = value
        return value

    async def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self._dirty = True

    async def delete(self, key: str) -> None:
        self._data.pop(key, None)
        await self._engine.delete(self.session_id, key)

    async def flush(self) -> None:
        if self._dirty:
            await self._engine.set_many(self.session_id, self._data)
            self._dirty = False


class SessionEngine(ABC):
    @abstractmethod
    async def get(self, session_id: str, key: str) -> Any: ...

    @abstractmethod
    async def set(self, session_id: str, key: str, value: Any) -> None: ...

    @abstractmethod
    async def set_many(self, session_id: str, data: dict) -> None: ...

    @abstractmethod
    async def delete(self, session_id: str, key: str) -> None: ...

    @abstractmethod
    async def destroy(self, session_id: str) -> None: ...
