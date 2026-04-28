import pytest
from ember.response.response import (
    Response, JSONResponse, CachedResponse, RedirectResponse,
    SSEResponse,
)


class TestResponse:
    def test_basic_encode(self):
        r = Response(b"hello", status_code=200)
        encoded = r.encode()
        assert b"HTTP/1.1 200 OK" in encoded
        assert b"hello" in encoded
        assert b"content-length: 5" in encoded

    def test_string_body(self):
        r = Response("hello", status_code=200)
        assert r.body == b"hello"

    def test_custom_headers(self):
        r = Response(b"", headers={"x-custom": "value"})
        encoded = r.encode()
        assert b"x-custom: value" in encoded

    def test_cached_encoding(self):
        r = Response(b"body")
        e1 = r.encode()
        e2 = r.encode()
        assert e1 is e2  # same object (cached)


class TestJSONResponse:
    def test_dict_serialization(self):
        r = JSONResponse({"key": "value", "num": 42})
        encoded = r.encode()
        assert b"application/json" in encoded
        assert b'"key"' in encoded

    def test_status_code(self):
        r = JSONResponse({}, status_code=201)
        encoded = r.encode()
        assert b"201 Created" in encoded

    def test_nested_data(self):
        r = JSONResponse({"nested": {"a": [1, 2, 3]}})
        assert b'"nested"' in r.encode()


class TestCachedResponse:
    def test_from_response(self):
        original = JSONResponse({"test": True})
        cached = CachedResponse.from_response(original)
        assert cached.encode() == original.encode()

    def test_cached_bytes_identity(self):
        original = Response(b"data")
        cached = CachedResponse.from_response(original)
        b1 = cached.encode()
        b2 = cached.encode()
        assert b1 is b2


class TestRedirectResponse:
    def test_302_redirect(self):
        r = RedirectResponse("/new-location")
        encoded = r.encode()
        assert b"302 Found" in encoded
        assert b"location: /new-location" in encoded

    def test_301_redirect(self):
        r = RedirectResponse("/permanent", status_code=301)
        assert b"301 Moved" in r.encode()


class TestSSEResponse:
    @pytest.mark.asyncio
    async def test_header_encoding(self):
        async def gen():
            yield "hello"
            yield " world"

        r = SSEResponse(stream=gen())
        # _encode_headers returns SSE headers
        headers = r._encode_headers()
        assert b"text/event-stream" in headers
        assert b"cache-control: no-cache" in headers
        assert b"transfer-encoding: chunked" in headers

    def test_format_event(self):
        async def gen():
            yield ""
        r = SSEResponse(stream=gen(), event_type="message")
        frame = r._format_event(b"hello world")
        assert b"event: message" in frame
        assert b"data: hello world" in frame
        assert b"id:" in frame

    def test_format_done(self):
        async def gen():
            yield ""
        r = SSEResponse(stream=gen())
        done = r._format_done()
        assert done == b"data: [DONE]\n\n"
