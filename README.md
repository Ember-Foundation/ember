# 🔥 Ember

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12%2B-blue)](https://python.org)
[![CI](https://github.com/Ember-Foundation/ember/actions/workflows/ci.yml/badge.svg)](https://github.com/Ember-Foundation/ember/actions)

**AI-API-first async HTTP framework for Python** — built for LLM workloads with Cython hot paths, multi-process workers, and first-class streaming.

📖 **[Documentation](https://ember-foundation.github.io/ember/)** · 🤝 **[Contributing](CONTRIBUTING.md)**

---

## Why Ember

| | Ember | FastAPI | Express | NestJS |
|---|---|---|---|---|
| **Protocol** | llhttp + Cython + io_uring | ASGI / uvicorn | Node.js http | Node.js http |
| **Workers** | Fork + SO_REUSEPORT | Single process | cluster | cluster |
| **SSE streaming** | Native, zero-copy | via starlette | manual | manual |
| **AI primitives** | Built-in | none | none | none |

### Hello-world benchmark (single worker, k6 200 VUs / 20 s)

`GET /hello → "Hello, World!"`, all running on the same Intel i7-14700 box,
0% error rate. Fiber pinned to one core (`GOMAXPROCS=1`) for fairness.

| Framework         |       RPS |  p50 (ms) | p99 (ms) | peak RSS |
| ----------------- | --------: | --------: | -------: | -------: |
| **Fiber (Go)**    | **140,993** |  1.21 |  3.96 |   **9 MB** |
| **Ember**         | **112,177** |  1.68 |  4.35 |  **25 MB** |
| Express (Node)    |    26,357 |  7.09 | 13.57 |  131 MB |
| NestJS (Node)     |    23,528 |  8.08 | 13.75 |  158 MB |
| FastAPI (Python)  |    17,517 |  9.45 | 30.86 |   49 MB |

Ember runs **6.4× FastAPI**, **4.3× Express**, and **4.8× NestJS** on the same
hardware — and at **112k RPS / 25 MB RSS / 80% of Go Fiber's throughput**, it
is the only Python framework in this league.

### CRUD benchmark (PostgreSQL, mixed reads + writes)

300-VU ramp, 196k-row table, 70k requests, 0% errors:

| Framework | avg latency | p95   | p99   |
|---|---:|---:|---:|
| **Ember** | **19.85 ms** | **44 ms** | **59 ms** |
| Express   |     19.20 ms |    43 ms |    56 ms |
| FastAPI   |    153.72 ms |   549 ms |   794 ms |

**Ember matches Node on real CRUD** — within 3% of Express on average, within
6% on p99 — and has a **13× tighter tail than FastAPI**.

**Memory:** Peak RSS dropped from 48 MB → 25 MB (-48%) in v0.2 — see
[Performance § Tuning the buffer pool](docs/guide/performance.md). Idle RSS is
~22 MB, well under FastAPI (47 MB) and 5× lighter than Node frameworks.

Reproducible: see [`taskbench/hello_bench/`](taskbench/hello_bench/) — run
`./bench_all.sh`.

---

## Features

- **Cython hot paths** — headers, router, request, response, protocol all compiled to C
- **Multi-process workers** — fork-based with `SO_REUSEPORT`, kernel load-balancing
- **`workers=1` in-process** — no supervisor overhead when you don't need it (~22 MB saved)
- **Tunable io_uring buffer pool** — `Ember.run(io_uring_num_bufs=, io_uring_buf_size=)` to scale RAM down to **2 MB pool** (default) or up to 32 MB for high-concurrency workloads
- **Lazy AI / cache / middleware imports** — `import ember` no longer pulls numpy/redis/memcached for plain HTTP apps
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
