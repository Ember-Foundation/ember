# Core Concepts

## Architecture

```
  ┌─────────────────────────────────────────┐
  │             Ember (server.py)           │
  │   spawns N fork workers, shared socket  │
  └──────────────┬──────────────────────────┘
                 │  SO_REUSEPORT
     ┌───────────┼───────────┐
     ▼           ▼           ▼
  Worker      Worker      Worker
  (uvloop)    (uvloop)    (uvloop)
     │
     ▼
  cprotocol (Cython llhttp)
     │ on_headers_complete → StaticCache fast path
     │ _handle_request     → async caches, hooks, handler
     ▼
  Router (Cython LRU + regex)
     ▼
  Route handler (async def)
     ▼
  Response (Cython encode)
```

## Request Lifecycle

1. **TCP connection** — kernel delivers to one worker via `SO_REUSEPORT`
2. **llhttp parsing** — Cython protocol parses headers; fires `on_headers_complete`
3. **Static cache check** — `StaticCache` hits return bytes immediately, bypassing the event loop task entirely
4. **Route lookup** — Cython router checks LRU cache, then static dict, then dynamic regex tree
5. **Async cache check** — `RedisCache` / `MemcachedCache` checked before hooks
6. **BEFORE_ENDPOINT hooks** — middleware (auth, CORS, rate limiting) runs
7. **Handler** — your `async def` function runs
8. **AFTER_ENDPOINT hooks** — post-processing
9. **Response encode** — Cython `response.encode()` builds HTTP/1.1 bytes
10. **Write** — bytes written directly to transport

## Blueprint

A `Blueprint` is a route group. It holds routes, hooks, and exception handlers that are merged into the application at startup.

```python
from ember import Blueprint, JSONResponse

api = Blueprint()

@api.get("/users")
async def list_users():
    return JSONResponse({"users": []})
```

Add to the app with an optional URL prefix:

```python
app.add_blueprint(api, prefixes={"*": "/v1"})
# GET /v1/users
```

`Ember` itself inherits from `Blueprint` — `@app.get()` is just shorthand for a root-level blueprint.

## Cython Hot Paths

Every performance-critical module ships both a `.pyx` (Cython) and a `.py` (pure Python) file. Python's import system loads the `.so` compiled extension when available, falling back to `.py` otherwise.

| Module | Benefit |
|--------|---------|
| `ember.headers` | Zero-copy header parsing |
| `ember.request` | Direct C struct access for URL, method, body |
| `ember.response` | Inline HTTP/1.1 encoding, no string concat |
| `ember.router` | O(1) LRU cache + compiled regex dispatch |
| `ember.protocol` | llhttp C parser, `cdef` callbacks |
| `ember.ai.sse` | Zero-copy SSE frame encoding |
| `ember.ai.ratelimit` | Lock-free token bucket |

## Workers and the Thread Pool

Each worker runs one `uvloop` event loop. A `ThreadPoolExecutor` is attached for CPU-bound work (model inference, tokenization, embedding) that must not block the loop. The default pool size is `min(32, cpu_count + 4)`.

## Keep-Alive and the Reaper

The `Reaper` background task scans open connections every second and closes ones that have exceeded `keep_alive_timeout` (default 30s) without a new request. This prevents connection exhaustion under slow clients.
