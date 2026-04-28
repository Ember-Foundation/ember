import pytest
from ember.router.router import Router, Route, AIRoute, RouterStrategy, LRUCache
from ember.router.parser import parse_pattern
from ember.request.request import Request, Stream
from ember.headers.headers import Headers


def make_request(path: str, method: str = "GET") -> Request:
    headers = Headers([(b"host", b"localhost")])
    stream = Stream()
    stream.end()
    return Request(
        url=path.encode(),
        method=method.encode(),
        headers=headers,
        stream=stream,
        protocol=None,
    )


async def dummy_handler(request: Request):
    return None


class TestPatternParser:
    def test_static_pattern(self):
        regex, params, is_dynamic = parse_pattern("/hello")
        assert not is_dynamic
        assert params == []
        assert regex.match("/hello")
        assert not regex.match("/world")

    def test_single_param(self):
        regex, params, is_dynamic = parse_pattern("/users/{id:int}")
        assert is_dynamic
        assert len(params) == 1
        assert params[0] == ("id", int)
        m = regex.match("/users/42")
        assert m
        assert m.group("id") == "42"

    def test_multiple_params(self):
        regex, params, is_dynamic = parse_pattern("/users/{user_id:int}/posts/{slug}")
        assert is_dynamic
        assert len(params) == 2
        m = regex.match("/users/1/posts/my-post")
        assert m
        assert m.group("user_id") == "1"
        assert m.group("slug") == "my-post"

    def test_uuid_param(self):
        regex, params, is_dynamic = parse_pattern("/items/{id:uuid}")
        m = regex.match("/items/550e8400-e29b-41d4-a716-446655440000")
        assert m

    def test_no_match_across_segments(self):
        regex, params, is_dynamic = parse_pattern("/users/{id:int}")
        assert not regex.match("/users/42/extra")


class TestLRUCache:
    def test_basic_get_set(self):
        cache = LRUCache(max_size=3)
        route = Route("/test", dummy_handler)
        cache.set((b"GET", b"/test"), route)
        assert cache.get((b"GET", b"/test")) is route

    def test_eviction(self):
        cache = LRUCache(max_size=2)
        r1 = Route("/a", dummy_handler)
        r2 = Route("/b", dummy_handler)
        r3 = Route("/c", dummy_handler)
        cache.set((b"GET", b"/a"), r1)
        cache.set((b"GET", b"/b"), r2)
        cache.set((b"GET", b"/c"), r3)
        # /a should be evicted
        assert cache.get((b"GET", b"/a")) is None
        assert cache.get((b"GET", b"/b")) is r2

    def test_miss_returns_none(self):
        cache = LRUCache()
        assert cache.get((b"GET", b"/missing")) is None


class TestRouter:
    def setup_method(self):
        self.router = Router(strategy=RouterStrategy.STRICT)

    def test_static_route(self):
        route = Route("/hello", dummy_handler, methods=("GET",))
        self.router.add_route(route, check_slashes=False)
        req = make_request("/hello")
        found = self.router.get_route(req)
        assert found is route

    def test_dynamic_route(self):
        route = Route("/users/{id:int}", dummy_handler, methods=("GET",))
        self.router.add_route(route, check_slashes=False)
        req = make_request("/users/42")
        found = self.router.get_route(req)
        assert found is route
        assert req._path_params == {"id": 42}

    def test_404_raises(self):
        from ember.exceptions import RouteNotFound
        req = make_request("/nonexistent")
        with pytest.raises(RouteNotFound):
            self.router.get_route(req)

    def test_405_raises(self):
        from ember.exceptions import MethodNotAllowed
        route = Route("/only-get", dummy_handler, methods=("GET",))
        self.router.add_route(route, check_slashes=False)
        req = make_request("/only-get", method="POST")
        with pytest.raises(MethodNotAllowed):
            self.router.get_route(req)

    def test_clone_strategy(self):
        router = Router(strategy=RouterStrategy.CLONE)
        route = Route("/path", dummy_handler, methods=("GET",))
        router.add_route(route)
        # Both /path and /path/ should resolve
        req1 = make_request("/path")
        req2 = make_request("/path/")
        assert router.get_route(req1) is not None
        assert router.get_route(req2) is not None

    def test_url_for(self):
        route = Route("/users/{id:int}", dummy_handler, methods=("GET",), name="get_user")
        self.router.add_route(route, check_slashes=False)
        url = self.router.build_url("get_user", id=99)
        assert "99" in url

    def test_ai_route(self):
        route = AIRoute("/v1/chat", dummy_handler, methods=("POST",), streaming=True)
        self.router.add_route(route, check_slashes=False)
        req = make_request("/v1/chat", method="POST")
        found = self.router.get_route(req)
        assert found.is_sse is True
