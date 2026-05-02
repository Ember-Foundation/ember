# ember-cache

TTL + single-flight response cache for the [Ember](https://github.com/Ember-Foundation/ember) web framework. Drop-in cache primitives that work standalone on top of [`emberloop`](https://pypi.org/project/emberloop/).

## What's inside

- **`TTLCache`** — multi-key route cache with TTL, bounded size, and built-in single-flight coalescing. When N concurrent users miss the same key, only one runs the handler; the rest wait and receive the same bytes.
- **`StaticCache`** — single-entry cache for routes with no dynamic parameters; first response is stored as pre-encoded bytes.
- **`RedisCache`** — async Redis-backed response cache (`pip install ember-cache[redis]`).
- **`MemcachedCache`** — async Memcached-backed response cache (`pip install ember-cache[memcached]`).
- **`CachedResponse`** — pre-encoded `Response` subclass that returns stored bytes on `encode()` with no re-serialization.

## Install

```bash
pip install ember-cache                  # core: TTLCache, StaticCache
pip install "ember-cache[redis]"         # + Redis backend
pip install "ember-cache[memcached]"     # + Memcached backend
pip install "ember-cache[all]"           # all backends
```

## Use

```python
from ember.cache import TTLCache

cache = TTLCache(ttl=1.0, max_entries=1024)

@app.get("/tasks", cache=cache)
async def list_tasks(request):
    return JSONResponse(await fetch_tasks())
```

That single argument enables TTL caching **and** single-flight coalescing — N concurrent requests collapse to one handler invocation.

## License

MIT
