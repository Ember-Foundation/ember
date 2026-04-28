"""
Router with LRU cache, static O(1) dict, and dynamic regex matching.
Compiled by Cython in production via router.pxd.
"""
from __future__ import annotations
import asyncio
import inspect
from collections import OrderedDict
from typing import Callable, Any, TYPE_CHECKING

from ..exceptions import RouteNotFound, MethodNotAllowed
from .parser import parse_pattern

if TYPE_CHECKING:
    from ..request import Request
    from ..ai.tools import ToolRegistry
    from ..ai.cache import SemanticCache


class RouterStrategy:
    STRICT = 1    # 404 on trailing slash mismatch
    REDIRECT = 2  # 301 redirect to canonical URL
    CLONE = 3     # register both /path and /path/


class LRUCache:
    """Fixed-size LRU cache for hot route lookups.

    In the Cython version, the OrderedDict operations are cdef void
    and avoid Python method dispatch overhead.
    """

    def __init__(self, max_size: int = 1024) -> None:
        self._cache: OrderedDict = OrderedDict()
        self.max_size = max_size

    def get(self, key: tuple) -> "Route | None":
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        return None

    def set(self, key: tuple, route: "Route") -> None:
        if key in self._cache:
            self._cache.move_to_end(key)
        else:
            if len(self._cache) >= self.max_size:
                self._cache.popitem(last=False)
            self._cache[key] = route


class Route:
    """A registered route mapping (method, pattern) to a handler coroutine."""

    __slots__ = (
        "pattern", "handler", "methods", "parent", "app",
        "is_dynamic", "regex", "param_types", "name",
        "cache", "limits", "token_limits",
        "_component_types", "_is_async", "_wants_request",
    )

    def __init__(
        self,
        pattern: str,
        handler: Callable,
        methods: tuple[str, ...] | None = None,
        parent: Any = None,
        app: Any = None,
        name: str | None = None,
        cache: Any | None = None,
        limits: Any | None = None,
        token_limits: Any | None = None,
    ) -> None:
        self.pattern = pattern
        self.handler = handler
        self.methods = tuple(m.upper() for m in (methods or ["GET", "POST", "PUT", "PATCH", "DELETE"]))
        self.parent = parent
        self.app = app
        self.name = name or handler.__name__
        self.cache = cache
        self.limits = limits
        self.token_limits = token_limits

        regex, param_types, is_dynamic = parse_pattern(pattern)
        self.regex = regex
        self.param_types = param_types
        self.is_dynamic = is_dynamic

        self._is_async = asyncio.iscoroutinefunction(handler)
        self._component_types = _extract_component_types(handler)
        self._wants_request: bool = (
            "request" in self._component_types or _handler_wants_request(handler)
        )

    async def call_handler(self, request: "Request", components: Any) -> Any:
        kwargs = {}
        for param_name, param_type in self._component_types.items():
            component = components.get(param_type)
            if component is not None:
                kwargs[param_name] = component

        if self._wants_request:
            kwargs["request"] = request

        if hasattr(request, "_path_params") and request._path_params:
            kwargs.update(request._path_params)

        if self._is_async:
            return await self.handler(**kwargs)
        return self.handler(**kwargs)

    def build_url(self, **kwargs: Any) -> str:
        url = self.pattern
        for key, value in kwargs.items():
            url = url.replace(f"{{{key}}}", str(value))
            url = url.replace(f"{{{key}:int}}", str(value))
            url = url.replace(f"{{{key}:str}}", str(value))
        return url

    def clone(self, **overrides) -> "Route":
        r = Route.__new__(Route)
        for attr in self.__slots__:
            setattr(r, attr, getattr(self, attr))
        for k, v in overrides.items():
            setattr(r, k, v)
        return r


class AIRoute(Route):
    """Route with AI-specific metadata baked in at registration time.

    The is_sse flag on the route allows the protocol layer's
    on_headers_complete fast-path to skip synchronous cache check and
    directly schedule the streaming handler task.
    """

    __slots__ = Route.__slots__ + (
        "model", "is_sse", "tool_registry", "semantic_cache",
    )

    def __init__(
        self,
        pattern: str,
        handler: Callable,
        model: str | None = None,
        streaming: bool = False,
        tool_registry: "ToolRegistry | None" = None,
        semantic_cache: "SemanticCache | None" = None,
        **kwargs,
    ) -> None:
        super().__init__(pattern, handler, **kwargs)
        self.model = model
        self.is_sse = streaming
        self.tool_registry = tool_registry
        self.semantic_cache = semantic_cache


class Router:
    """Hybrid router: O(1) static dict + regex dynamic list + LRU cache.

    Compiled by Cython in production. The _find_route hot path checks
    only C-level booleans and dict lookups.
    """

    def __init__(self, strategy: int = RouterStrategy.CLONE) -> None:
        self.strategy = strategy
        # Static routes: method → {path_bytes → Route}
        self._static: dict[bytes, dict[bytes, Route]] = {}
        # Dynamic routes: method → [Route, ...]
        self._dynamic: dict[bytes, list[Route]] = {}
        # Host-based routes: host_bytes → Router
        self._host_routers: dict[bytes, "Router"] = {}
        # All routes indexed by name for url_for()
        self._named: dict[str, Route] = {}
        self._cache = LRUCache(max_size=2048)
        self._all_paths: set[bytes] = set()

    def add_route(
        self,
        route: Route,
        prefixes: dict[str, str] | None = None,
        check_slashes: bool = True,
    ) -> None:
        pattern = route.pattern
        if prefixes:
            for host, prefix in prefixes.items():
                if host == "*":
                    pattern = prefix.rstrip("/") + pattern
                else:
                    if host not in self._host_routers:
                        self._host_routers[host.encode()] = Router(self.strategy)
                    self._host_routers[host.encode()].add_route(
                        route.clone(pattern=prefix.rstrip("/") + pattern)
                    )
                    return

        pattern_bytes = pattern.encode("utf-8")
        for method in route.methods:
            method_bytes = method.encode("utf-8")
            if route.is_dynamic:
                if method_bytes not in self._dynamic:
                    self._dynamic[method_bytes] = []
                self._dynamic[method_bytes].append(route)
            else:
                if method_bytes not in self._static:
                    self._static[method_bytes] = {}
                self._static[method_bytes][pattern_bytes] = route

        if route.name:
            self._named[route.name] = route

        self._all_paths.add(pattern.encode("utf-8"))

        if check_slashes and self.strategy == RouterStrategy.CLONE:
            alt = (pattern.rstrip("/") if pattern.endswith("/") and len(pattern) > 1
                   else pattern + "/")
            if alt != pattern:
                self.add_route(route.clone(pattern=alt), check_slashes=False)

    def get_route(self, request: "Request") -> Route:
        method = request.method
        url = request.url.split(b"?")[0]  # strip query string

        # Check host-based router first
        host = request.headers.get(b"host", b"")
        if host in self._host_routers:
            return self._host_routers[host].get_route(request)

        # LRU cache check
        cache_key = (method, url)
        cached = self._cache.get(cache_key)
        if cached is not None:
            if cached.is_dynamic:
                url_str = url.decode("utf-8", errors="replace")
                match = cached.regex.match(url_str)
                if match:
                    request._path_params = {
                        name: converter(match.group(name))
                        for name, converter in cached.param_types
                    }
            return cached

        # Static O(1) lookup
        method_static = self._static.get(method)
        if method_static:
            route = method_static.get(url)
            if route:
                self._cache.set(cache_key, route)
                return route

        # Dynamic regex matching
        method_dynamic = self._dynamic.get(method)
        if method_dynamic:
            url_str = url.decode("utf-8", errors="replace")
            for route in method_dynamic:
                match = route.regex.match(url_str)
                if match:
                    request._path_params = {
                        name: converter(match.group(name))
                        for name, converter in route.param_types
                    }
                    self._cache.set(cache_key, route)
                    return route

        # O(1) 405 check using pre-built path set
        if url in self._all_paths:
            raise MethodNotAllowed()
        raise RouteNotFound()

    def build_url(self, name: str, **kwargs: Any) -> str:
        route = self._named.get(name)
        if route is None:
            raise ValueError(f"No route named '{name}'")
        return route.build_url(**kwargs)

    def check_integrity(self) -> None:
        """Warn about routes with duplicate patterns."""
        seen: set[tuple] = set()
        for method, routes in self._dynamic.items():
            for route in routes:
                key = (method, route.pattern)
                if key in seen:
                    import warnings
                    warnings.warn(f"Duplicate route pattern: {method} {route.pattern}")
                seen.add(key)


def _extract_component_types(handler: Callable) -> dict[str, type]:
    sig = inspect.signature(handler)
    result = {}
    for name, param in sig.parameters.items():
        if param.annotation is not inspect.Parameter.empty:
            result[name] = param.annotation
    return result


def _handler_wants_request(handler: Callable) -> bool:
    sig = inspect.signature(handler)
    return "request" in sig.parameters
