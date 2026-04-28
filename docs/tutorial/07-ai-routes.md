# 7 — AI Routes & Streaming

Ember's AI layer provides first-class primitives for LLM-backed APIs — streaming output, conversation memory, tool calling, and model routing.

---

## Basic SSE Streaming

Any async generator can stream Server-Sent Events:

```python
from ember import Ember, SSEResponse
import asyncio

app = Ember()

@app.get("/stream")
async def stream_numbers(request):
    async def events():
        for i in range(10):
            await asyncio.sleep(0.1)
            yield f"data: {i}\n\n"
    return SSEResponse(events())
```

```bash
curl -N http://127.0.0.1:8000/stream
# data: 0
# data: 1
# ...
```

---

## Token Streaming (LLM Output)

`TokenStreamResponse` wraps a string token generator in SSE frames automatically:

```python
from ember import TokenStreamResponse
import asyncio

@app.post("/generate")
async def generate(request):
    data = await request.json()
    prompt = data.get("prompt", "")

    async def tokens():
        words = f"You asked: {prompt}. Here is my answer.".split()
        for word in words:
            await asyncio.sleep(0.04)
            yield word + " "

    return TokenStreamResponse(tokens())
```

```bash
curl -N -X POST http://127.0.0.1:8000/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Hello"}'
# data: You
# data: asked:
# ...
```

---

## `ai_route()` — Full AI Endpoint

`ai_route()` enables auto-injection of `ConversationContext` and `ModelRouter` into the handler:

```python
from ember import (
    Ember, Request, SSEResponse,
    ConversationContext, MessageRole,
    sse_stream, TokenLimits,
)
import asyncio

app = Ember()

async def fake_llm(prompt: str):
    """Simulate a streaming LLM response."""
    for word in f"Sure! You asked about: {prompt}".split():
        await asyncio.sleep(0.05)
        yield word + " "

@app.ai_route(
    "/v1/chat",
    methods=["POST"],
    streaming=True,
    token_limits=TokenLimits(tokens_per_minute=60_000),
)
async def chat(
    request: Request,
    context: ConversationContext,   # auto-injected — per-session history
) -> SSEResponse:
    body = await request.json()
    user_msg = body.get("message", "")

    context.add_message(MessageRole.USER, user_msg)
    stream = fake_llm(user_msg)
    return sse_stream(stream)
```

```bash
curl -N -X POST http://127.0.0.1:8000/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"What is Python?"}'
```

---

## ConversationContext

Manages per-session message history. Auto-injected into `ai_route()` handlers.

```python
from ember import ConversationContext, MessageRole

context.add_message(MessageRole.USER,      "Hello")
context.add_message(MessageRole.ASSISTANT, "Hi there!")
context.add_message(MessageRole.SYSTEM,    "You are a helpful assistant.")

messages = context.get_messages()  # list[Message]
context.clear()                    # reset history
```

---

## ToolRegistry

Register Python functions as tools callable by LLMs:

```python
from ember import ToolRegistry
from ember.ai.tools import ToolCall, ParameterSchema

tools = ToolRegistry()

@tools.register(description="Get current weather for a city")
async def get_weather(city: str, units: str = "celsius") -> dict:
    return {"city": city, "temperature": 22, "units": units}

@tools.register(
    name="search",
    description="Search the web for information",
    parameters=[
        ParameterSchema("query", "string", "Search query"),
        ParameterSchema("limit", "integer", "Max results", required=False),
    ],
)
async def search_web(query: str, limit: int = 5) -> list:
    return [{"title": f"Result for {query}"}]
```

Execute a tool (from an LLM tool-use response):

```python
result = await tools.execute(ToolCall(
    id="call_01",
    name="get_weather",
    arguments={"city": "Paris", "units": "celsius"},
))
print(result.content)    # '{"city": "Paris", "temperature": 22, "units": "celsius"}'
print(result.is_error)   # False
```

Generate specs:

```python
tools.to_openai_specs()      # for OpenAI function calling
tools.to_anthropic_specs()   # for Anthropic tools
```

Use in a route:

```python
@app.ai_route("/v1/chat", methods=["POST"], streaming=True, tool_registry=tools)
async def chat(request, context):
    ...
```

---

## ModelRouter

Route requests to different LLM providers based on strategy:

```python
from ember import ModelRouter, ModelSpec, RoutingStrategy

router = ModelRouter(
    models=[
        ModelSpec(
            name="gpt-4o-mini",
            provider="openai",
            endpoint="https://api.openai.com/v1/chat/completions",
            api_key_env="OPENAI_API_KEY",
            max_tokens=4096,
            context_window=128_000,
            cost_per_input_token=0.00015,
            cost_per_output_token=0.0006,
            supports_tools=True,
        ),
        ModelSpec(
            name="claude-haiku",
            provider="anthropic",
            endpoint="https://api.anthropic.com/v1/messages",
            api_key_env="ANTHROPIC_API_KEY",
            max_tokens=4096,
            context_window=200_000,
            cost_per_input_token=0.0008,
            cost_per_output_token=0.004,
        ),
    ],
    strategy=RoutingStrategy.FALLBACK,   # try first, fall back on error
)

app = Ember(model_router=router)

@app.ai_route("/v1/chat", methods=["POST"])
async def chat(request, context, model_router: ModelRouter):
    model = await model_router.select(request, context)
    # model.name → "gpt-4o-mini" or "claude-haiku"
    ...
```

Strategies: `FALLBACK`, `CHEAPEST`, `FASTEST`, `ROUND_ROBIN`.

---

## Token Rate Limiting

Protect your LLM budget:

```python
from ember import TokenLimits, GlobalTokenBucket, RateLimitMiddleware

# Global bucket: 100k tokens/minute across all users
bucket = GlobalTokenBucket(
    capacity=100_000.0,
    refill_rate=100_000.0 / 60,  # per second
)
app.add_middleware(RateLimitMiddleware(
    global_bucket=bucket,
    estimate_from_body=True,  # deducts estimated tokens from request body
))

# Per-route limits
@app.ai_route(
    "/v1/premium",
    methods=["POST"],
    token_limits=TokenLimits(
        tokens_per_minute=10_000,
        max_prompt_tokens=4_096,
        max_completion_tokens=2_048,
    ),
)
async def premium_chat(request, context): ...
```

---

## OpenAI-Compatible Endpoint

Full streaming response in OpenAI chat format:

```python
import json, uuid, asyncio
from ember import Ember, Request, SSEResponse

app = Ember()

@app.post("/v1/chat/completions")
async def completions(request: Request) -> SSEResponse:
    body   = await request.json()
    stream = body.get("stream", False)
    model  = body.get("model", "ember-default")

    async def fake_tokens():
        for word in "Hello! I am Ember, your AI assistant.".split():
            await asyncio.sleep(0.05)
            yield word + " "

    if stream:
        async def openai_stream():
            chunk_id = f"chatcmpl-{uuid.uuid4().hex[:8]}"
            async for token in fake_tokens():
                chunk = {
                    "id": chunk_id,
                    "object": "chat.completion.chunk",
                    "model": model,
                    "choices": [{"delta": {"content": token}, "index": 0, "finish_reason": None}],
                }
                yield f"data: {json.dumps(chunk)}\n\n"
            yield "data: [DONE]\n\n"
        return SSEResponse(openai_stream())
    else:
        tokens = []
        async for t in fake_tokens():
            tokens.append(t)
        content = "".join(tokens)
        return {
            "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
            "object": "chat.completion",
            "model": model,
            "choices": [{"message": {"role": "assistant", "content": content}, "index": 0}],
            "usage": {"prompt_tokens": 20, "completion_tokens": len(tokens), "total_tokens": 20 + len(tokens)},
        }

if __name__ == "__main__":
    app.run(port=8000)
```

```bash
# Non-streaming
curl -X POST http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"ember-default","messages":[{"role":"user","content":"Hello"}]}'

# Streaming
curl -N -X POST http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"ember-default","stream":true,"messages":[{"role":"user","content":"Hello"}]}'
```
