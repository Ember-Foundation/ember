# 4 — Middleware & Hooks

---

## What Is Middleware?

Middleware is code that runs before (or after) every request handler. Ember implements middleware as **lifecycle hooks** — async functions registered on the `BEFORE_ENDPOINT` or `AFTER_ENDPOINT` events.

`app.add_middleware()` is shorthand for registering a `BEFORE_ENDPOINT` hook.

---

## Built-in Middleware

### CORS

```python
from ember import CORSMiddleware

app.add_middleware(CORSMiddleware(
    allow_origins=["https://myapp.com"],
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["content-type", "authorization"],
    allow_credentials=False,
))
```

Pass `allow_origins=["*"]` for open APIs.

### Bearer Auth

```python
from ember import BearerAuthMiddleware

def verify_token(token: str) -> bool:
    return token == "super-secret"

app.add_middleware(BearerAuthMiddleware(
    verify_fn=verify_token,
    exclude_paths=["/health", "/"],
))
```

`verify_fn` can also return a `dict` — it will be stored in `request.context["auth"]`:

```python
def verify_token(token: str) -> dict | bool:
    user = lookup_token(token)
    if not user:
        return False
    return {"user_id": user.id, "roles": user.roles}

@app.get("/profile")
async def profile(request):
    user = request.context["auth"]   # {"user_id": 42, "roles": ["admin"]}
    return user
```

### API Key

```python
from ember import APIKeyMiddleware

app.add_middleware(APIKeyMiddleware(
    valid_keys={"key-abc-123", "key-xyz-456"},
    header="x-api-key",
    exclude_paths=["/health"],
))
```

Or validate with a function:

```python
app.add_middleware(APIKeyMiddleware(
    valid_keys=lambda key: key.startswith("live_"),
    header="x-api-key",
))
```

---

## Custom Middleware

Any async callable works. Return `None` to continue, return a `Response` to short-circuit:

```python
from ember import Events
import time

@app.hook(Events.BEFORE_ENDPOINT)
async def log_requests(request, response):
    request.context["_start"] = time.monotonic()

@app.hook(Events.AFTER_ENDPOINT)
async def log_responses(request, response):
    elapsed = (time.monotonic() - request.context.get("_start", 0)) * 1000
    print(f"{request.method.decode()} {request.path} → {response.status_code} ({elapsed:.1f}ms)")
```

As a class:

```python
class RequireJSONMiddleware:
    async def __call__(self, request):
        from ember import JSONResponse
        if request.method in (b"POST", b"PUT", b"PATCH"):
            ct = request.headers.get_str("content-type", "")
            if "application/json" not in ct:
                return JSONResponse({"error": "content_type_must_be_json"}, status_code=415)
        return None

app.add_middleware(RequireJSONMiddleware())
```

---

## Lifecycle Hooks

Hooks run at defined points in the server and request lifecycle.

```python
from ember import Events

@app.hook(Events.BEFORE_SERVER_START)
async def startup(components):
    # Connect DB, warm caches, load models
    print("Server starting...")

@app.hook(Events.AFTER_SERVER_START)
async def after_start(components):
    print("Server ready.")

@app.hook(Events.BEFORE_SERVER_STOP)
async def shutdown(components):
    # Close DB pool, flush buffers
    print("Shutting down...")

@app.hook(Events.AFTER_SERVER_STOP)
async def after_stop(components):
    print("Server stopped.")

@app.hook(Events.BEFORE_ENDPOINT)
async def before_each(request, response):
    # Runs before every handler (same as middleware)
    pass

@app.hook(Events.AFTER_ENDPOINT)
async def after_each(request, response):
    # Runs after every handler
    pass
```

---

## Middleware Execution Order

Middleware runs in registration order. Register less-specific middleware first:

```python
app.add_middleware(CORSMiddleware(...))       # 1st — handles preflight
app.add_middleware(BearerAuthMiddleware(...)) # 2nd — checks token
app.add_middleware(RateLimitMiddleware(...))  # 3rd — checks quota
```

---

## Per-Route Auth with `request.context`

Middleware can gate specific routes by checking `request.path`:

```python
PROTECTED = {"/admin", "/admin/users"}

class AdminOnly:
    async def __call__(self, request):
        from ember import JSONResponse
        if request.path not in PROTECTED:
            return None
        user = request.context.get("auth", {})
        if "admin" not in user.get("roles", []):
            return JSONResponse({"error": "forbidden"}, status_code=403)
        return None

app.add_middleware(BearerAuthMiddleware(verify_fn=verify))
app.add_middleware(AdminOnly())
```

**Next:** [Blueprints →](./05-blueprints)
