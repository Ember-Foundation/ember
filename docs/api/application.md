# Application

## `Ember`

The top-level entry point. Inherits from `EmberApplication` → `Blueprint`.

```python
from ember import Ember, ServerLimits, TokenLimits
from ember.ai.routing import ModelRouter

app = Ember(
    server_limits=ServerLimits(keep_alive_timeout=30),
    model_router=model_router,        # optional — enables ai_route()
    token_limits=TokenLimits(...),    # optional — global token limits
)
```

### `app.run()`

```python
app.run(
    host="127.0.0.1",
    port=8000,
    workers=None,           # default: os.cpu_count() + 2
    debug=False,
    block=True,
    necromancer=True,       # auto-revive dead workers
    startup_message=True,
    thread_pool_workers=None,  # default: min(32, cpu_count + 4)
)
```

**Windows**: `workers` is ignored; always runs single-process.

### `app.add_blueprint()`

```python
app.add_blueprint(blueprint, prefixes={"*": "/api/v1"})
# prefix key is a hostname or "*" (all hosts)
```

### `app.add_middleware()`

```python
from ember import CORSMiddleware
app.add_middleware(CORSMiddleware(allow_origins=["*"]))
```

Middleware is registered as a `BEFORE_ENDPOINT` hook.

---

## `Blueprint`

A modular route group. Routes, hooks, and exception handlers defined on a blueprint are merged into the application at startup.

```python
from ember import Blueprint

bp = Blueprint(
    hosts=["api.example.com"],   # optional host binding
    limits=RouteLimits(...),      # default limits for all routes
    token_limits=TokenLimits(...),
)
```

---

## Lifecycle Hooks

```python
from ember import Events

@app.hook(Events.BEFORE_SERVER_START)
async def startup(components) -> None:
    # connect DB, warm caches
    ...

@app.hook(Events.AFTER_SERVER_START)
async def after_start(components) -> None: ...

@app.hook(Events.BEFORE_SERVER_STOP)
async def shutdown(components) -> None:
    # close DB pool
    ...

@app.hook(Events.AFTER_SERVER_STOP)
async def after_stop(components) -> None: ...

@app.hook(Events.BEFORE_ENDPOINT)
async def before_each(request, response) -> None: ...

@app.hook(Events.AFTER_ENDPOINT)
async def after_each(request, response) -> None: ...
```

---

## Exception Handlers

```python
@app.handle(404)
async def not_found(exc) -> JSONResponse:
    return JSONResponse({"error": "not_found"}, status_code=404)

@app.handle(500)
async def server_error(exc) -> JSONResponse:
    return JSONResponse({"error": "internal_server_error"}, status_code=500)
```

---

## Component Injection

Components are shared objects (DB pool, model clients) injected into route handlers:

```python
app.add_component(db_pool)  # registers by type

@app.get("/users")
async def list_users(request, pool: asyncpg.Pool) -> JSONResponse:
    rows = await pool.fetch("SELECT id, name FROM users")
    return JSONResponse({"users": [dict(r) for r in rows]})
```
