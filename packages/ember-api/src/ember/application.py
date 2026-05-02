"""EmberApplication: Blueprint → Application → Ember inheritance layer.

Application holds the router, component registry, hook dispatch, and
exception handling. It extends Blueprint so the same @app.route() and
@app.ai_route() decorators work at both levels.
"""
from __future__ import annotations
import asyncio
import logging
from typing import Any, Callable, TYPE_CHECKING

from .constants import Events
from .hooks import Hook
from .router.router import Router, Route, AIRoute, RouterStrategy
from .components.container import ComponentsEngine
from .limits import ServerLimits, RouteLimits, TokenLimits

if TYPE_CHECKING:
    from .request import Request
    from .response import Response
    from .ai.routing import ModelRouter
    from .sessions.base import SessionEngine

logger = logging.getLogger("ember.app")


class Blueprint:
    """Modular route group with optional URL prefix and host binding.

    Blueprints are composed into the application at startup via add_blueprint().
    Routes, hooks, and exception handlers are all defined on blueprints and
    merged into the application router during initialize().
    """

    def __init__(
        self,
        hosts: list[str] | None = None,
        limits: RouteLimits | None = None,
        token_limits: TokenLimits | None = None,
    ) -> None:
        self.hosts = hosts
        self.limits = limits
        self.token_limits = token_limits
        self._routes: list[Route] = []
        self._blueprints: list[tuple["Blueprint", dict | None]] = []
        self._hooks: list[Hook] = []
        self._exception_handlers: dict[type, Callable] = {}

    # ── Route registration decorators ───────────────────────────────────

    def route(
        self,
        pattern: str,
        methods: list[str] | None = None,
        cache: Any = None,
        name: str | None = None,
        limits: RouteLimits | None = None,
        token_limits: TokenLimits | None = None,
    ) -> Callable:
        def decorator(fn: Callable) -> Callable:
            route = Route(
                pattern=pattern,
                handler=fn,
                methods=tuple(methods or ["GET"]),
                parent=self,
                name=name,
                cache=cache,
                limits=limits or self.limits,
                token_limits=token_limits or self.token_limits,
            )
            self._routes.append(route)
            return fn
        return decorator

    def get(self, pattern: str, **kwargs) -> Callable:
        return self.route(pattern, methods=["GET"], **kwargs)

    def post(self, pattern: str, **kwargs) -> Callable:
        return self.route(pattern, methods=["POST"], **kwargs)

    def put(self, pattern: str, **kwargs) -> Callable:
        return self.route(pattern, methods=["PUT"], **kwargs)

    def patch(self, pattern: str, **kwargs) -> Callable:
        return self.route(pattern, methods=["PATCH"], **kwargs)

    def delete(self, pattern: str, **kwargs) -> Callable:
        return self.route(pattern, methods=["DELETE"], **kwargs)

    def ai_route(
        self,
        pattern: str,
        methods: list[str] | None = None,
        model: str | None = None,
        streaming: bool = False,
        tool_registry: Any = None,
        semantic_cache: Any = None,
        name: str | None = None,
        limits: RouteLimits | None = None,
        token_limits: TokenLimits | None = None,
    ) -> Callable:
        def decorator(fn: Callable) -> Callable:
            route = AIRoute(
                pattern=pattern,
                handler=fn,
                methods=tuple(methods or ["POST"]),
                parent=self,
                model=model,
                streaming=streaming,
                tool_registry=tool_registry,
                semantic_cache=semantic_cache,
                name=name,
                limits=limits or self.limits,
                token_limits=token_limits or self.token_limits,
            )
            self._routes.append(route)
            return fn
        return decorator

    # ── Hooks ────────────────────────────────────────────────────────────

    def add_hook(self, hook: Hook) -> None:
        self._hooks.append(hook)

    def hook(self, event: int) -> Callable:
        def decorator(fn: Callable) -> Callable:
            self.add_hook(Hook(type_id=event, handler=fn))
            return fn
        return decorator

    # ── Exception handlers ────────────────────────────────────────────────

    def handle(self, exc_type: type | int) -> Callable:
        def decorator(fn: Callable) -> Callable:
            self._exception_handlers[exc_type] = fn
            return fn
        return decorator

    async def process_exception(self, exc: Exception, components: "ComponentsEngine") -> "Response":
        from .response import JSONResponse

        handler = self._exception_handlers.get(type(exc))
        if handler is None:
            for exc_class in type(exc).__mro__:
                handler = self._exception_handlers.get(exc_class)
                if handler:
                    break

        if handler:
            if asyncio.iscoroutinefunction(handler):
                return await handler(exc)
            return handler(exc)

        status = getattr(exc, "status_code", 500)
        return JSONResponse({"error": str(exc)}, status_code=status)

    # ── Nested blueprints ─────────────────────────────────────────────────

    def add_blueprint(self, blueprint: "Blueprint", prefixes: dict | None = None) -> None:
        self._blueprints.append((blueprint, prefixes))


class EmberApplication(Blueprint):
    """Application layer: owns the router, DI container, and hook dispatch."""

    def __init__(
        self,
        router_strategy: int = RouterStrategy.CLONE,
        session_engine: "SessionEngine | None" = None,
        server_name: str | None = None,
        url_scheme: str = "https",
        server_limits: "ServerLimits | None" = None,
        route_limits: "RouteLimits | None" = None,
        token_limits: "TokenLimits | None" = None,
        model_router: "ModelRouter | None" = None,
        debug: bool = False,
    ) -> None:
        super().__init__()
        self.router = Router(strategy=router_strategy)
        self.components = ComponentsEngine()
        self.session_engine = session_engine
        self.server_name = server_name
        self.url_scheme = url_scheme
        self._server_limits = server_limits or ServerLimits()
        self.route_limits = route_limits
        self.token_limits = token_limits
        self.model_router = model_router
        self.debug = debug
        self._initialized = False
        self._route_caches: list = []  # DistributedCache instances found on routes

        self._hooks_by_event: dict[int, list[Hook]] = {e: [] for e in Events}
        self._has_before_endpoint = False
        self._has_after_endpoint = False

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._register_all_routes(self, prefixes=None)
        self._compile_hooks()
        self._register_ai_components()
        await self._connect_route_caches()
        self.router.check_integrity()

    def _register_all_routes(self, blueprint: "Blueprint", prefixes: dict | None) -> None:
        from .cache.backends import DistributedCache
        seen_cache_ids: set[int] = getattr(self, "_seen_cache_ids", None)
        if seen_cache_ids is None:
            self._seen_cache_ids: set[int] = set()
            seen_cache_ids = self._seen_cache_ids
        for route in blueprint._routes:
            self.router.add_route(route, prefixes=prefixes)
            cache = getattr(route, "cache", None)
            if isinstance(cache, DistributedCache) and id(cache) not in seen_cache_ids:
                seen_cache_ids.add(id(cache))
                self._route_caches.append(cache)
        for nested, nested_prefixes in blueprint._blueprints:
            merged = {}
            if prefixes:
                merged.update(prefixes)
            if nested_prefixes:
                merged.update(nested_prefixes)
            self._register_all_routes(nested, merged or None)
            # Merge hooks and exception handlers
            self._hooks.extend(nested._hooks)
            self._exception_handlers.update(nested._exception_handlers)

    def _compile_hooks(self) -> None:
        for hook in self._hooks:
            if hook.type_id in self._hooks_by_event:
                self._hooks_by_event[hook.type_id].append(hook)
        self._has_before_endpoint = bool(self._hooks_by_event[Events.BEFORE_ENDPOINT])
        self._has_after_endpoint = bool(self._hooks_by_event[Events.AFTER_ENDPOINT])

    async def _connect_route_caches(self) -> None:
        for cache in self._route_caches:
            await cache.connect()

    def _register_ai_components(self) -> None:
        if self.model_router:
            self.components.add(self.model_router)
        if self.token_limits:
            from .ai.ratelimit.token_bucket import GlobalTokenBucket
            bucket = GlobalTokenBucket(
                capacity=float(self.token_limits.tokens_per_minute),
                refill_rate=self.token_limits.tokens_per_minute / 60.0,
            )
            self.components.add(bucket)

    async def call_hooks_by_event(self, event: int, components: "ComponentsEngine") -> None:
        for hook in self._hooks_by_event.get(event, []):
            await hook.call(components)

    async def call_hooks_before_endpoint(
        self, request: "Request", components: "ComponentsEngine"
    ) -> "Response | None":
        for hook in self._hooks_by_event[Events.BEFORE_ENDPOINT]:
            result = await hook.call(request)
            if result is not None:
                return result
        return None

    async def call_hooks_after_endpoint(
        self, request: "Request", response: "Response", components: "ComponentsEngine"
    ) -> None:
        for hook in self._hooks_by_event[Events.AFTER_ENDPOINT]:
            await hook.call(request, response)

    def url_for(self, name: str, external: bool = False, **kwargs) -> str:
        path = self.router.build_url(name, **kwargs)
        if external and self.server_name:
            return f"{self.url_scheme}://{self.server_name}{path}"
        return path

    def add_middleware(self, middleware: Any, event: int = Events.BEFORE_ENDPOINT) -> None:
        """Register any callable as a middleware hook."""
        self.add_hook(Hook(type_id=event, handler=middleware))
