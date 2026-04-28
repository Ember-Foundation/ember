# Routing

## Route Decorators

```python
@app.get("/path")
@app.post("/path")
@app.put("/path")
@app.patch("/path")
@app.delete("/path")
@app.route("/path", methods=["GET", "POST"])
```

All accept the same keyword arguments:

```python
@app.get(
    "/path",
    cache=RedisCache(ttl=30),        # optional cache backend
    name="route_name",               # optional named route
    limits=RouteLimits(...),         # per-route body/timeout limits
    token_limits=TokenLimits(...),   # per-route token limits (AI routes)
)
```

---

## Path Parameters

```python
@app.get("/users/{user_id:int}")
async def get_user(request, user_id: int):
    # user_id is already an int
    ...

@app.get("/posts/{slug:str}")
async def get_post(request, slug: str): ...

@app.get("/files/{path:path}")   # matches slashes
async def get_file(request, path: str): ...
```

Supported converters: `int`, `float`, `str`, `uuid`, `path`.

Path params are available on `request.path_params` or injected directly as function arguments.

---

## Query Parameters

```python
@app.get("/tasks")
async def list_tasks(request):
    page  = int(request.args.get("page", 1))
    limit = int(request.args.get("limit", 10))
    q     = request.args.get("q", "")
    ...
```

`request.args` is a `dict[str, str]`.

---

## AI Routes

```python
from ember import ConversationContext, SSEResponse, ModelRouter

@app.ai_route(
    "/v1/chat",
    methods=["POST"],
    streaming=True,
    tool_registry=tools,
    token_limits=TokenLimits(tokens_per_minute=60_000),
)
async def chat(
    request: Request,
    context: ConversationContext,  # auto-injected per-session context
    model_router: ModelRouter,     # auto-injected from app
) -> SSEResponse:
    ...
```

`ai_route()` injects `ConversationContext` and `ModelRouter` into the handler signature automatically.

---

## Limits

```python
from ember import RouteLimits

@app.post("/upload", limits=RouteLimits(max_body_size=100 * 1024 * 1024))
async def upload(request): ...
```

`RouteLimits` fields:
- `max_body_size` — bytes, default 4 MB
- `timeout` — seconds, default 300
- `in_memory_threshold` — bytes before spilling to disk, default 1 MB
