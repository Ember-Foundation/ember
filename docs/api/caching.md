# Caching

Ember has two cache tiers:

| Tier | Class | Async | Hooks run? | When checked |
|------|-------|-------|-----------|--------------|
| Static | `StaticCache` | No | No | Before event loop task (fastest) |
| Distributed | `RedisCache`, `MemcachedCache` | Yes | Yes | After auth/rate-limit hooks |

---

## StaticCache

In-process LRU cache. The response is stored on first hit and served from C memory on every subsequent request — the async event loop is not involved at all.

```python
from ember import StaticCache

@app.get("/health", cache=StaticCache())
async def health():
    return {"status": "ok"}
```

Use for endpoints whose response never changes (health checks, static config).

---

## RedisCache

```python
from ember import RedisCache

task_cache = RedisCache(
    url="redis://localhost:6379",
    ttl=30,                         # seconds
    key_prefix="ember:",            # namespace prefix
    vary_headers=["x-tenant-id"],   # vary cache key by header value
    max_size=1_048_576,             # skip caching bodies larger than 1 MB
)

@app.get("/tasks", cache=task_cache)
async def list_tasks(request): ...

@app.get("/tasks/{task_id:str}", cache=task_cache)
async def get_task(request, task_id: str): ...
```

**Cache key**: `"{method}:{path}?{query_string}"` — pagination gets separate keys.

Only `GET` requests with `2xx` responses are cached. Non-GET and non-2xx bypass the cache.

### Custom key function

```python
def per_user_key(request) -> str:
    user_id = request.headers.get(b"x-user-id", b"anon").decode()
    return f"GET:{request.path}:{user_id}"

@app.get("/profile", cache=RedisCache(ttl=60, key_fn=per_user_key))
async def profile(request): ...
```

### Invalidation

```python
await task_cache.invalidate(key="GET:/tasks")
await task_cache.invalidate(pattern="GET:/tasks*")
```

---

## MemcachedCache

```python
from ember import MemcachedCache

@app.get("/posts", cache=MemcachedCache(
    host="localhost",
    port=11211,
    ttl=60,
    pool_size=2,
))
async def list_posts(request): ...
```

Pattern invalidation is not supported by memcached — a warning is logged if attempted.

---

## Auto-Connect Lifecycle

Ember scans all routes during `initialize()` and automatically calls `connect()` on every distributed cache. On shutdown, `close()` is called on each. No lifecycle code is needed from the user:

```python
# This is all you need — no startup/shutdown hooks for the cache
task_cache = RedisCache(url="redis://localhost:6379", ttl=30)

@app.get("/tasks", cache=task_cache)
async def list_tasks(request): ...
```

---

## Shared Cache Across Routes

One cache instance can be shared:

```python
cache = RedisCache(url="redis://localhost:6379", ttl=60)

@app.get("/tasks",            cache=cache)
@app.get("/tasks/{id:str}",   cache=cache)
@app.get("/users",            cache=cache)
```

Ember deduplicates by `id()` — `connect()` and `close()` are called once.
