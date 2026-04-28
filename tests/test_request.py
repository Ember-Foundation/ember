import pytest
import json
from ember.request.request import Request, Stream, AIRequestBody
from ember.headers.headers import Headers


def make_request(
    path: str = "/",
    method: str = "GET",
    body: bytes = b"",
    headers: list | None = None,
) -> Request:
    raw_headers = headers or [(b"host", b"localhost")]
    h = Headers(raw_headers)
    stream = Stream()
    if body:
        stream.feed(body)
    stream.end()
    return Request(url=path.encode(), method=method.encode(), headers=h, stream=stream, protocol=None)


class TestStream:
    @pytest.mark.asyncio
    async def test_read_all(self):
        s = Stream()
        s.feed(b"hello ")
        s.feed(b"world")
        s.end()
        result = await s.read()
        assert result == b"hello world"

    @pytest.mark.asyncio
    async def test_empty_stream(self):
        s = Stream()
        s.end()
        result = await s.read()
        assert result == b""

    def test_clear(self):
        s = Stream()
        s.feed(b"data")
        s.clear()
        assert s._done is False


class TestRequest:
    def test_path_parsing(self):
        req = make_request("/api/v1/users?page=1&limit=10")
        assert req.path == "/api/v1/users"

    def test_query_args(self):
        req = make_request("/search?q=python&page=2")
        assert req.get_arg("q") == "python"
        assert req.get_arg("page") == "2"
        assert req.get_arg("missing") is None

    def test_missing_arg_default(self):
        req = make_request("/")
        assert req.get_arg("key", "default") == "default"

    @pytest.mark.asyncio
    async def test_body_read(self):
        req = make_request("/", body=b"hello body")
        body = await req.body()
        assert body == b"hello body"

    @pytest.mark.asyncio
    async def test_json_parse(self):
        data = {"key": "value", "number": 42}
        req = make_request("/", method="POST", body=json.dumps(data).encode())
        parsed = await req.json()
        assert parsed["key"] == "value"
        assert parsed["number"] == 42

    @pytest.mark.asyncio
    async def test_form_parse(self):
        req = make_request(
            "/",
            method="POST",
            body=b"name=Alice&age=30",
            headers=[(b"content-type", b"application/x-www-form-urlencoded")],
        )
        form = await req.form()
        assert form["name"] == "Alice"
        assert form["age"] == "30"

    def test_stream_requested_via_accept(self):
        req = make_request("/", headers=[(b"accept", b"text/event-stream")])
        assert req.stream_requested is True

    def test_stream_not_requested(self):
        req = make_request("/", headers=[(b"accept", b"application/json")])
        assert req.stream_requested is False

    def test_estimate_tokens(self):
        body = b"A" * 100
        req = make_request("/", body=body)
        req._body_cache = body
        tokens = req.estimate_tokens()
        assert tokens == 25  # 100 / 4

    @pytest.mark.asyncio
    async def test_ai_body(self):
        data = {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": "Hello"}],
            "stream": True,
            "temperature": 0.7,
        }
        req = make_request("/", method="POST", body=json.dumps(data).encode())
        ai_body = await req.ai_body()
        assert ai_body.model == "gpt-4o"
        assert ai_body.stream is True
        assert ai_body.temperature == 0.7
        assert len(ai_body.messages) == 1


class TestAIRequestBody:
    def test_from_dict_minimal(self):
        body = AIRequestBody.from_dict({"messages": []})
        assert body.model is None
        assert body.stream is False
        assert body.temperature == 1.0

    def test_from_dict_full(self):
        body = AIRequestBody.from_dict({
            "model": "claude-3-5-sonnet-20241022",
            "messages": [{"role": "user", "content": "Hi"}],
            "stream": True,
            "tools": [{"type": "function"}],
            "temperature": 0.5,
            "max_tokens": 1000,
        })
        assert body.model == "claude-3-5-sonnet-20241022"
        assert body.stream is True
        assert body.max_tokens == 1000
        assert len(body.tools) == 1

    def test_extra_fields_captured(self):
        body = AIRequestBody.from_dict({"custom_field": "value"})
        assert body.extra == {"custom_field": "value"}
