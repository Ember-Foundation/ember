cdef class LRUCache:
    cdef object _cache
    cdef int max_size

    cpdef object get(self, tuple key)
    cpdef void set(self, tuple key, object route)

cdef class Route:
    cdef public str pattern
    cdef public object handler
    cdef public tuple methods
    cdef public object parent
    cdef public object app
    cdef public bint is_dynamic
    cdef public object regex
    cdef public list param_types
    cdef public str name
    cdef public object cache
    cdef public object limits
    cdef public object token_limits
    cdef dict _component_types
    cdef bint _is_async
    cdef bint _wants_request
    cdef bint _simple_call
    cdef public bint _trivial_path  # safe to bypass _handle_request coroutine entirely

cdef class AIRoute(Route):
    cdef public str model
    cdef public bint is_sse
    cdef public object tool_registry
    cdef public object semantic_cache

cdef class Router:
    cdef dict _static
    cdef dict _dynamic
    cdef dict _host_routers
    cdef dict _named
    cdef LRUCache _cache
    cdef int strategy
    cdef set _all_paths

    cpdef void add_route(self, Route route, dict prefixes=*, bint check_slashes=*)
    cpdef Route get_route(self, object request)
