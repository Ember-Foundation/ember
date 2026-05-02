"""
Distributed cache backends for Ember — Redis and Memcached.

Usage:
    from ember import RedisCache, MemcachedCache

    task_cache = RedisCache(url="redis://localhost:6379", ttl=30)

    @app.get("/tasks", cache=task_cache)
    async def list_tasks(request): ...

    @app.get("/tasks/{task_id}", cache=task_cache)
    async def get_task(request, task_id: str): ...

Ember auto-connects on server start and auto-disconnects on server stop
by scanning route caches during initialize() — no user lifecycle code needed.
"""
from __future__ import annotations
import logging
import warnings
from typing import Callable, Any, TYPE_CHECKING

from .lru import CacheEngine
from .cached_response import CachedResponse

try:
    import redis.asyncio as aioredis
except ImportError:
    aioredis = None

try:
    import aiomcache
except ImportError:
    aiomcache = None

if TYPE_CHECKING:
    from ember.request import Request
    from ember.response import Response

logger = logging.getLogger("ember.cache")


class DistributedCache(CacheEngine):
    """Base class for async distributed cache backends (Redis, Memcached).

    Subclasses implement connect(), close(), get(), store(), invalidate().
    is_async=True tells cprotocol to await get()/store() inside _handle_request.
    skip_hooks=False means BEFORE_ENDPOINT hooks still run (auth, rate-limiting).
    """

    is_async   = True
    skip_hooks = False

    def __init__(
        self,
        ttl: int = 60,
        key_prefix: str = "ember:",
        key_fn: Callable | None = None,
        vary_headers: list[str] | None = None,
        max_size: int = 1_048_576,
    ) -> None:
        self.ttl          = ttl
        self.key_prefix   = key_prefix
        self.key_fn       = key_fn
        self.vary_headers = vary_headers or []
        self.max_size     = max_size
        self._client: Any = None

    async def connect(self) -> None:
        raise NotImplementedError

    async def close(self) -> None:
        raise NotImplementedError

    async def get(self, request: "Request") -> "CachedResponse | None":
        raise NotImplementedError

    async def store(self, request: "Request", response: "Response") -> None:
        raise NotImplementedError

    async def invalidate(self, pattern: str | None = None, key: str | None = None) -> None:
        raise NotImplementedError

    def _make_key(self, request: "Request") -> str:
        if self.key_fn:
            return self.key_prefix + self.key_fn(request)
        method = request.method.decode("latin-1")
        path   = request.path
        qs     = request.query_string
        k      = f"{method}:{path}?{qs}" if qs else f"{method}:{path}"
        for header in self.vary_headers:
            val = request.headers.get(header.encode(), b"").decode("latin-1")
            k  += f":{val}"
        return self.key_prefix + k

    def _should_cache(self, request: "Request", response: "Response") -> bool:
        if request.method != b"GET":
            return False
        if not (200 <= response.status_code < 300):
            return False
        if len(response.body) > self.max_size:
            return False
        return True


class RedisCache(DistributedCache):
    """Redis-backed response cache using redis.asyncio.

    Install: pip install "redis[asyncio]>=5.0"

    Args:
        url:          Redis connection URL (default: redis://localhost:6379)
        ttl:          Cache TTL in seconds (default: 60)
        key_prefix:   Key namespace prefix (default: "ember:")
        key_fn:       Custom key function: (request) -> str
        vary_headers: Header names whose values are included in the cache key
        max_size:     Skip caching responses larger than this (bytes, default 1MB)
        client:       Inject a pre-existing redis.asyncio client (skips auto-connect)
    """

    def __init__(
        self,
        url: str = "redis://localhost:6379",
        ttl: int = 60,
        key_prefix: str = "ember:",
        key_fn: Callable | None = None,
        vary_headers: list[str] | None = None,
        max_size: int = 1_048_576,
        client: Any = None,
    ) -> None:
        super().__init__(
            ttl=ttl, key_prefix=key_prefix,
            key_fn=key_fn, vary_headers=vary_headers, max_size=max_size,
        )
        self._url    = url
        self._client = client

    async def connect(self) -> None:
        if self._client is not None:
            return
        if aioredis is None:
            raise ImportError(
                "RedisCache requires 'redis[asyncio]>=5.0'. "
                "Install it: pip install 'redis[asyncio]'"
            )
        self._client = aioredis.from_url(self._url, decode_responses=False)
        logger.info("RedisCache connected to %s", self._url)

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def get(self, request: "Request") -> "CachedResponse | None":
        if request.method != b"GET":
            return None
        try:
            data = await self._client.get(self._make_key(request))
        except Exception as exc:
            logger.warning("RedisCache.get error: %s", exc)
            return None
        if data:
            return CachedResponse(data)
        return None

    async def store(self, request: "Request", response: "Response") -> None:
        if not self._should_cache(request, response):
            return
        try:
            await self._client.setex(
                self._make_key(request), self.ttl, response.encode()
            )
        except Exception as exc:
            logger.warning("RedisCache.store error: %s", exc)

    async def invalidate(self, pattern: str | None = None, key: str | None = None) -> None:
        try:
            if key is not None:
                await self._client.delete(self.key_prefix + key)
            elif pattern is not None:
                keys = await self._client.keys(self.key_prefix + pattern)
                if keys:
                    await self._client.delete(*keys)
        except Exception as exc:
            logger.warning("RedisCache.invalidate error: %s", exc)


class MemcachedCache(DistributedCache):
    """Memcached-backed response cache using aiomcache.

    Install: pip install aiomcache>=0.8

    Args:
        host:         Memcached host (default: 127.0.0.1)
        port:         Memcached port (default: 11211)
        pool_size:    Connection pool size (default: 2)
        ttl:          Cache TTL in seconds (default: 60)
        key_prefix:   Key namespace prefix (default: "ember:")
        key_fn:       Custom key function: (request) -> str
        vary_headers: Header names whose values are included in the cache key
        max_size:     Skip caching responses larger than this (bytes, default 1MB)
        client:       Inject a pre-existing aiomcache.Client (skips auto-connect)
    """

    _KEY_LIMIT = 250  # Memcached max key length

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 11211,
        pool_size: int = 2,
        ttl: int = 60,
        key_prefix: str = "ember:",
        key_fn: Callable | None = None,
        vary_headers: list[str] | None = None,
        max_size: int = 1_048_576,
        client: Any = None,
    ) -> None:
        super().__init__(
            ttl=ttl, key_prefix=key_prefix,
            key_fn=key_fn, vary_headers=vary_headers, max_size=max_size,
        )
        self._host      = host
        self._port      = port
        self._pool_size = pool_size
        self._client    = client

    def _make_mc_key(self, request: "Request") -> bytes:
        return self._make_key(request).encode("utf-8")[:self._KEY_LIMIT]

    async def connect(self) -> None:
        if self._client is not None:
            return
        if aiomcache is None:
            raise ImportError(
                "MemcachedCache requires 'aiomcache>=0.8'. "
                "Install it: pip install aiomcache"
            )
        self._client = aiomcache.Client(
            self._host, self._port, pool_size=self._pool_size
        )
        logger.info("MemcachedCache connected to %s:%d", self._host, self._port)

    async def close(self) -> None:
        if self._client:
            await self._client.close()
            self._client = None

    async def get(self, request: "Request") -> "CachedResponse | None":
        if request.method != b"GET":
            return None
        try:
            data = await self._client.get(self._make_mc_key(request))
        except Exception as exc:
            logger.warning("MemcachedCache.get error: %s", exc)
            return None
        if data:
            return CachedResponse(data)
        return None

    async def store(self, request: "Request", response: "Response") -> None:
        if not self._should_cache(request, response):
            return
        try:
            await self._client.set(
                self._make_mc_key(request), response.encode(), exptime=self.ttl
            )
        except Exception as exc:
            logger.warning("MemcachedCache.store error: %s", exc)

    async def invalidate(self, pattern: str | None = None, key: str | None = None) -> None:
        if key is not None:
            try:
                await self._client.delete(
                    (self.key_prefix + key).encode("utf-8")[:self._KEY_LIMIT]
                )
            except Exception as exc:
                logger.warning("MemcachedCache.invalidate error: %s", exc)
        elif pattern is not None:
            warnings.warn(
                "MemcachedCache does not support pattern-based invalidation. "
                "Use key= to delete a specific key.",
                stacklevel=2,
            )
