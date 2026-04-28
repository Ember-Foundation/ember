# 6 — Caching

Ember has three caching backends. Pick based on what you're caching and how it changes.

---

## StaticCache — In-Process, No TTL

The fastest option. The response is stored on the first request and served directly from C memory on every subsequent one. The event loop is not involved at all after the first hit.

**Use for:** endpoints whose response never changes (health checks, build info, static config).

```python
from ember import StaticCache

@app.get("/health", cache=StaticCache())
async def health():
    return {"status": "ok"}

@app.get("/version", cache=StaticCache())
async def version():
    return {"version": "1.0.0", "build": "2026-04-27"}
```

---

## RedisCache — Distributed, TTL-Based

Stores full HTTP responses in Redis. Shared across all worker processes. GET requests with 2xx responses are cached; other methods and non-2xx responses are never cached.

**Use for:** expensive DB queries, paginated lists, user-agnostic data.

```python
from ember import RedisCache

# One shared client — Ember auto-connects on startup
task_cache = RedisCache(
    url="redis://localhost:6379",
    ttl=30,           # seconds
    key_prefix="api:",
)

@app.get("/tasks", cache=task_cache)
async def list_tasks(request):
    page  = int(request.get_arg("page", "1"))
    limit = int(request.get_arg("limit", "10"))
    # ... fetch from DB ...
    return {"tasks": [...], "page": page}
```

**Cache key** includes the query string: `GET:/tasks?page=1&limit=10` and `GET:/tasks?page=2&limit=10` are separate keys.

### Vary by header

Cache different responses per tenant or user:

```python
task_cache = RedisCache(
    url="redis://localhost:6379",
    ttl=60,
    vary_headers=["x-tenant-id"],
)
```

### Custom key function

```python
def user_key(request) -> str:
    user_id = request.context.get("auth", {}).get("user_id", "anon")
    return f"GET:{request.path}:{user_id}"

@app.get("/me/tasks", cache=RedisCache(ttl=30, key_fn=user_key))
async def my_tasks(request):
    ...
```

### Invalidate cache

```python
# In a POST/PUT/DELETE handler, after updating data:
await task_cache.invalidate(key="GET:/tasks")
await task_cache.invalidate(pattern="GET:/tasks*")  # all task keys
```

---

## MemcachedCache — Distributed, TTL-Based

Same as RedisCache but uses Memcached. Pattern invalidation is not supported.

```python
from ember import MemcachedCache

@app.get("/posts", cache=MemcachedCache(
    host="localhost",
    port=11211,
    ttl=60,
    pool_size=2,
))
async def list_posts(request):
    ...
```

---

## No Setup Required

Ember scans your routes during startup, calls `connect()` on each cache automatically, and calls `close()` on shutdown. You never write lifecycle code:

```python
cache = RedisCache(url="redis://localhost:6379", ttl=30)

@app.get("/a", cache=cache)
async def route_a(request): ...

@app.get("/b", cache=cache)
async def route_b(request): ...

# One shared client, connected once, closed once — automatically.
app.run()
```

---

## Choosing a Backend

| | StaticCache | RedisCache | MemcachedCache |
|-|-------------|------------|----------------|
| Speed | Fastest (C memory) | Fast (1 network RTT) | Fast (1 network RTT) |
| Shared across workers | No | Yes | Yes |
| TTL | No | Yes | Yes |
| Invalidation | No | Yes (key + pattern) | Yes (key only) |
| Depends on | Nothing | Redis server | Memcached server |
| Best for | Immutable responses | DB-backed endpoints | DB-backed endpoints |

---

## Cache + Auth Together

Distributed caches run **after** `BEFORE_ENDPOINT` hooks (auth, rate-limiting), so cached responses are only served to authenticated users:

```python
app.add_middleware(BearerAuthMiddleware(verify_fn=verify))  # runs 1st

cache = RedisCache(url="redis://localhost:6379", ttl=60)

@app.get("/protected", cache=cache)
async def protected(request):
    # Only reached after auth passes
    return {"data": "..."}
```

**Next:** [AI Routes & Streaming →](./07-ai-routes)
