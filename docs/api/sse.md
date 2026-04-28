# Server-Sent Events (SSE)

Ember has first-class SSE support designed for LLM token streaming.

---

## SSEResponse

Return an async generator from any route:

```python
from ember import SSEResponse
import asyncio

@app.get("/stream")
async def stream_data():
    async def events():
        for i in range(10):
            await asyncio.sleep(0.1)
            yield f"data: event {i}\n\n"
    return SSEResponse(events())
```

---

## TokenStreamResponse

Wraps a generator of string tokens in SSE frames automatically:

```python
from ember import TokenStreamResponse
import asyncio

@app.post("/generate")
async def generate(request):
    async def tokens():
        for word in "The quick brown fox".split():
            await asyncio.sleep(0.05)
            yield word + " "
    return TokenStreamResponse(tokens())
```

Each yielded string is sent as `data: <token>\n\n`.

---

## `sse_stream()` Helper

Combines a token generator with an optional token bucket for back-pressure:

```python
from ember import sse_stream, GlobalTokenBucket

bucket = GlobalTokenBucket(capacity=100_000, refill_rate=1_666.7)

@app.ai_route("/v1/chat", methods=["POST"], streaming=True)
async def chat(request, context):
    async def tokens():
        async for token in my_model_stream(request):
            yield token
    return sse_stream(tokens(), token_bucket=bucket)
```

---

## SSEWriter (Cython)

The `SSEWriter` Cython class encodes frames with zero Python string allocation. It is used internally by `SSEResponse` and `TokenStreamResponse`. You can use it directly for custom frame formats:

```python
from ember.ai.sse import SSEWriter

writer = SSEWriter()
frame  = writer.encode_token("Hello ")   # → b"data: Hello \n\n"
frame  = writer.encode_event("update", '{"id":1}')  # → b"event: update\ndata: {\"id\":1}\n\n"
frame  = writer.encode_done()            # → b"data: [DONE]\n\n"
```

---

## OpenAI-Compatible Streaming

```python
import json, uuid, time

@app.ai_route("/v1/chat/completions", methods=["POST"], streaming=True)
async def completions(request, context):
    body  = await request.ai_body()
    model = body.model or "ember-default"

    async def openai_stream():
        chunk_id = f"chatcmpl-{uuid.uuid4().hex[:8]}"
        async for token in my_llm(body.messages):
            chunk = {
                "id": chunk_id,
                "object": "chat.completion.chunk",
                "model": model,
                "choices": [{"delta": {"content": token}, "index": 0}],
            }
            yield f"data: {json.dumps(chunk)}\n\n"
        yield "data: [DONE]\n\n"

    return SSEResponse(openai_stream())
```
