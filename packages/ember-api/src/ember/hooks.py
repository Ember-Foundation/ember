from __future__ import annotations
import asyncio
from dataclasses import dataclass, field
from typing import Callable, Any

from .constants import Events


@dataclass
class Hook:
    type_id: int
    handler: Callable
    is_async: bool = field(init=False)
    route: Any = None

    def __post_init__(self) -> None:
        self.is_async = asyncio.iscoroutinefunction(self.handler)

    async def call(self, *args, **kwargs):
        if self.is_async:
            return await self.handler(*args, **kwargs)
        return self.handler(*args, **kwargs)


def before_server_start(fn: Callable) -> Hook:
    return Hook(type_id=Events.BEFORE_SERVER_START, handler=fn)


def after_server_start(fn: Callable) -> Hook:
    return Hook(type_id=Events.AFTER_SERVER_START, handler=fn)


def before_endpoint(fn: Callable) -> Hook:
    return Hook(type_id=Events.BEFORE_ENDPOINT, handler=fn)


def after_endpoint(fn: Callable) -> Hook:
    return Hook(type_id=Events.AFTER_ENDPOINT, handler=fn)


def after_response_sent(fn: Callable) -> Hook:
    return Hook(type_id=Events.AFTER_RESPONSE_SENT, handler=fn)


def before_server_stop(fn: Callable) -> Hook:
    return Hook(type_id=Events.BEFORE_SERVER_STOP, handler=fn)
