# cython: language_level=3, boundscheck=False, wraparound=False, cdivision=True
"""
Cython router — LRU cache + O(1) static dict + regex dynamic matching.

Hot-path gains vs pure-Python version:
- LRUCache.get/set: C-speed OrderedDict ops, no Python method dispatch
- Route fields: direct C struct access, no __dict__ indirection
- Router.get_route: cpdef cpdef — C return type, no boxing
- _wants_request: cdef bint — zero-cost C boolean per call_handler
- _all_paths: cdef set — O(1) 405 check, no O(n) route rescan
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
    STRICT   = 1
    REDIRECT = 2
    CLONE    = 3


cdef class LRUCache:

    def __init__(self, int max_size=1024):
        self._cache    = OrderedDict()
        self.max_size  = max_size

    cpdef object get(self, tuple key):
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        return None

    cpdef void set(self, tuple key, object route):
        if key in self._cache:
            self._cache.move_to_end(key)
        else:
            if len(self._cache) >= self.max_size:
                self._cache.popitem(last=False)
            self._cache[key] = route


cdef class Route:

    def __init__(
        self,
        pattern,
        handler,
        methods=None,
        parent=None,
        app=None,
        name=None,
        cache=None,
        limits=None,
        token_limits=None,
    ):
        self.pattern      = pattern
        self.handler      = handler
        self.methods      = tuple(m.upper() for m in (methods or ["GET", "POST", "PUT", "PATCH", "DELETE"]))
        self.parent       = parent
        self.app          = app
        self.name         = name or handler.__name__
        self.cache        = cache
        self.limits       = limits
        self.token_limits = token_limits

        regex, param_types, is_dynamic = parse_pattern(pattern)
        self.regex        = regex
        self.param_types  = param_types
        self.is_dynamic   = is_dynamic

        self._is_async       = asyncio.iscoroutinefunction(handler)
        self._component_types = _extract_component_types(handler)
        self._wants_request  = (
            "request" in self._component_types or _handler_wants_request(handler)
        )
        self._simple_call    = (self._wants_request and
                                len(self._component_types) <= 1 and
                                not is_dynamic)

    async def call_handler(self, request, components):
        if self._simple_call:
            if self._is_async:
                return await self.handler(request=request)
            return self.handler(request=request)

        cdef dict kwargs = {}
        for param_name, param_type in self._component_types.items():
            component = components.get(param_type)
            if component is not None:
                kwargs[param_name] = component

        if self._wants_request:
            kwargs["request"] = request

        if request._path_params:
            kwargs.update(request._path_params)

        if self._is_async:
            return await self.handler(**kwargs)
        return self.handler(**kwargs)

    def build_url(self, **kwargs):
        url = self.pattern
        for key, value in kwargs.items():
            url = url.replace(f"{{{key}}}", str(value))
            url = url.replace(f"{{{key}:int}}", str(value))
            url = url.replace(f"{{{key}:str}}", str(value))
        return url

    def clone(self, **overrides):
        cdef Route r = Route.__new__(Route)
        r.pattern          = self.pattern
        r.handler          = self.handler
        r.methods          = self.methods
        r.parent           = self.parent
        r.app              = self.app
        r.is_dynamic       = self.is_dynamic
        r.regex            = self.regex
        r.param_types      = self.param_types
        r.name             = self.name
        r.cache            = self.cache
        r.limits           = self.limits
        r.token_limits     = self.token_limits
        r._component_types = self._component_types
        r._is_async        = self._is_async
        r._wants_request   = self._wants_request
        r._simple_call     = self._simple_call
        for k, v in overrides.items():
            setattr(r, k, v)
        return r


cdef class AIRoute(Route):

    def __init__(
        self,
        pattern,
        handler,
        model=None,
        streaming=False,
        tool_registry=None,
        semantic_cache=None,
        **kwargs,
    ):
        super().__init__(pattern, handler, **kwargs)
        self.model          = model
        self.is_sse         = streaming
        self.tool_registry  = tool_registry
        self.semantic_cache = semantic_cache


cdef class Router:

    def __init__(self, int strategy=3):   # 3 = RouterStrategy.CLONE
        self.strategy       = strategy
        self._static        = {}
        self._dynamic       = {}
        self._host_routers  = {}
        self._named         = {}
        self._cache         = LRUCache(max_size=2048)
        self._all_paths     = set()

    cpdef void add_route(self, Route route, dict prefixes=None, bint check_slashes=True):
        cdef str pattern = route.pattern
        cdef bytes pattern_bytes, method_bytes

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

        self._all_paths.add(pattern_bytes)

        if check_slashes and self.strategy == 3:   # CLONE
            alt = (pattern.rstrip("/") if pattern.endswith("/") and len(pattern) > 1
                   else pattern + "/")
            if alt != pattern:
                self.add_route(route.clone(pattern=alt), check_slashes=False)

    cpdef Route get_route(self, object request):
        cdef bytes method   = request.method
        cdef bytes url      = request.url.split(b"?")[0]
        cdef tuple cache_key
        cdef str url_str
        cdef object cached, method_static, method_dynamic, route, match

        # Host-based router
        host = request.headers.get(b"host", b"")
        if host in self._host_routers:
            return self._host_routers[host].get_route(request)

        # LRU cache
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

        # Static O(1)
        method_static = self._static.get(method)
        if method_static:
            route = method_static.get(url)
            if route:
                self._cache.set(cache_key, route)
                return route

        # Dynamic regex — decode once for all pattern attempts
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

        # O(1) 405 vs 404
        if url in self._all_paths:
            raise MethodNotAllowed()
        raise RouteNotFound()

    def build_url(self, name, **kwargs):
        route = self._named.get(name)
        if route is None:
            raise ValueError(f"No route named '{name}'")
        return route.build_url(**kwargs)

    def check_integrity(self):
        seen = set()
        for method, routes in self._dynamic.items():
            for route in routes:
                key = (method, route.pattern)
                if key in seen:
                    import warnings
                    warnings.warn(f"Duplicate route pattern: {method} {route.pattern}")
                seen.add(key)


def _extract_component_types(handler):
    sig = inspect.signature(handler)
    result = {}
    for name, param in sig.parameters.items():
        if param.annotation is not inspect.Parameter.empty:
            result[name] = param.annotation
    return result


def _handler_wants_request(handler):
    sig = inspect.signature(handler)
    return "request" in sig.parameters
