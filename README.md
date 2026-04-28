# 🔥 Ember

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11%2B-blue)](https://python.org)
[![CI](https://github.com/Ember-Foundation/ember/actions/workflows/ci.yml/badge.svg)](https://github.com/Ember-Foundation/ember/actions)

**AI-API-first async HTTP framework for Python** — built for LLM workloads with Cython hot paths, multi-process workers, and first-class streaming.

📖 **[Documentation](https://ember-foundation.github.io/ember/)** · 🤝 **[Contributing](CONTRIBUTING.md)**

---

## Why Ember

| | Ember | FastAPI | Express |
|---|---|---|---|
| **Protocol** | Custom llhttp + Cython | ASGI / uvicorn | Node.js http |
| **Workers** | Fork + SO_REUSEPORT | Single process | cluster |
| **SSE streaming** | Native, zero-copy | via starlette | manual |
| **AI primitives** | Built-in | none | none |
| **Hello-world RPS** | **~2,650** | ~1,800 | ~2,340 |
| **p50 latency** | **~16 ms** | ~28 ms | ~22 ms |

_Benchmarked at 200 VUs on a single machine. See [`benchmarks/`](benchmarks/)._

---

## Features

- **Cython hot paths** — headers, router, request, response, protocol all compiled to C
- **Multi-process workers** — fork-based with `SO_REUSEPORT`, kernel load-balancing
- **AI-first routing** — `@app.ai_route()` with streaming, tool calling, conversation context
- **SSE streaming** — `SSEResponse`, `sse_stream()`, `TokenStreamResponse` for LLM token output
- **Pluggable caching** — `StaticCache`, `RedisCache`, `MemcachedCache` via single decorator arg
- **Token rate limiting** — `TokenBucket`, `GlobalTokenBucket`, `RateLimitMiddleware`
- **Model routing** — `ModelRouter` with fallback, cost, and latency strategies
- **Semantic cache** — vector-search cache for AI responses
- **Built-in middleware** — CORS, Bearer auth, API key
- **Blueprints** — modular route groups with URL prefixes
- **Cross-platform** — Linux/macOS multi-process, Windows single-process fallback

---

## Install

```bash
pip install ember-api
# With all performance extras:
pip install "ember-api[fast]"       # uvloop + orjson
pip install "ember-api[cache]"      # Redis + Memcached backends
pip install "ember-api[all]"        # everything
```

Build Cython extensions from source (optional, for maximum speed):

```bash
pip install cython
python setup.py build_ext --inplace
```

---

## Hello World

```python
from ember import Ember

app = Ember()

@app.get("/")
async def index():
    return {"hello": "world"}

app.run(host="0.0.0.0", port=8000, workers=4)
```

---

## Full CRUD Example

```python
from ember import Ember, Blueprint, Request, JSONResponse, StaticCache, RedisCache

app = Ember()

tasks: dict = {}

@app.get("/tasks", cache=RedisCache(ttl=30))
async def list_tasks(request: Request) -> JSONResponse:
    page  = int(request.args.get("page", 1))
    limit = int(request.args.get("limit", 10))
    items = list(tasks.values())[(page - 1) * limit : page * limit]
    return JSONResponse({"tasks": items, "total": len(tasks)})

@app.get("/tasks/{task_id:str}")
async def get_task(request: Request, task_id: str) -> JSONResponse:
    task = tasks.get(task_id)
    if not task:
        return JSONResponse({"error": "not found"}, status_code=404)
    return JSONResponse(task)

@app.post("/tasks")
async def create_task(request: Request) -> JSONResponse:
    data = await request.json()
    import uuid
    task_id = str(uuid.uuid4())
    tasks[task_id] = {"id": task_id, **data}
    return JSONResponse(tasks[task_id], status_code=201)

app.run(host="0.0.0.0", port=8000, workers=4)
```

---

## AI / LLM Routes

```python
from ember import Ember, Request, SSEResponse, ConversationContext, sse_stream
import asyncio

app = Ember()

async def token_stream(prompt: str):
    for word in f"You asked: {prompt}".split():
        await asyncio.sleep(0.05)
        yield word + " "

@app.ai_route("/v1/chat", methods=["POST"], streaming=True)
async def chat(request: Request, context: ConversationContext) -> SSEResponse:
    body = await request.json()
    prompt = body.get("message", "")
    context.add_message("user", prompt)
    return sse_stream(token_stream(prompt))

app.run(host="0.0.0.0", port=8000)
```

---

## Caching

```python
from ember import Ember, RedisCache, MemcachedCache, StaticCache

app = Ember()

# Static in-memory cache (no TTL, perfect for health checks)
@app.get("/health", cache=StaticCache())
async def health():
    return {"status": "ok"}

# Redis cache — shared across all workers
task_cache = RedisCache(url="redis://localhost:6379", ttl=30)

@app.get("/tasks", cache=task_cache)
async def list_tasks(request):
    ...

# Memcached cache
@app.get("/posts", cache=MemcachedCache(host="localhost", port=11211, ttl=60))
async def list_posts(request):
    ...
```

Ember auto-connects on server start and auto-disconnects on stop — no lifecycle code needed.

---

## Middleware

```python
from ember import Ember, CORSMiddleware, BearerAuthMiddleware, APIKeyMiddleware

app = Ember()

app.add_middleware(CORSMiddleware(allow_origins=["https://myapp.com"]))
app.add_middleware(BearerAuthMiddleware(verify_fn=lambda token: token == "secret"))
app.add_middleware(APIKeyMiddleware(api_keys=["key-1", "key-2"], header="x-api-key"))
```

---

## Blueprints

```python
from ember import Ember, Blueprint, JSONResponse

app   = Ember()
admin = Blueprint()

@admin.get("/users")
async def list_users():
    return JSONResponse({"users": []})

@admin.post("/users")
async def create_user(request):
    data = await request.json()
    return JSONResponse(data, status_code=201)

app.add_blueprint(admin, prefixes={"*": "/admin"})
app.run(port=8000)
```

---

## Limits & Rate Limiting

```python
from ember import Ember, RouteLimits, TokenLimits, ServerLimits

app = Ember(
    server_limits=ServerLimits(keep_alive_timeout=30),
)

@app.post(
    "/upload",
    limits=RouteLimits(max_body_size=50 * 1024 * 1024),  # 50 MB
)
async def upload(request):
    body = await request.body()
    return {"size": len(body)}

@app.ai_route(
    "/v1/chat",
    methods=["POST"],
    token_limits=TokenLimits(tokens_per_minute=10_000, max_prompt_tokens=4_096),
)
async def chat(request, context):
    ...
```

---

## Project Layout

```
ember/
  ai/           # ConversationContext, PromptTemplate, ToolRegistry, ModelRouter, SemanticCache
  cache/        # StaticCache, RedisCache, MemcachedCache
  headers/      # Cython headers parser
  middleware/   # CORS, BearerAuth, APIKey
  protocol/     # Cython llhttp HTTP/1.1 protocol
  request/      # Cython Request + Stream
  response/     # Cython Response, JSONResponse, SSEResponse …
  router/       # Cython router with LRU cache, path params, regex
  sessions/     # Session engine (in-memory, extensible)
  workers/      # Fork worker, Reaper, graceful shutdown
  application.py
  server.py
examples/
  basic_api.py
  streaming_chat.py
  tool_calling.py
tests/
setup.py
```

---

## Running Tests

```bash
pip install "ember-api[dev]"
pytest
```

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).  
Issues: [bug reports](https://github.com/Ember-Foundation/ember/issues/new?template=bug_report.md) · [feature requests](https://github.com/Ember-Foundation/ember/issues/new?template=feature_request.md)

## License

MIT — see [LICENSE](LICENSE).
