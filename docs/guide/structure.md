# Project Structure

```
ember/                    # Python package
  ai/
    cache.py              # SemanticCache (vector search)
    context.py            # ConversationContext, Message, MessageRole
    prompt.py             # PromptTemplate, TemplateVar
    routing.py            # ModelRouter, ModelSpec, RoutingStrategy
    tools.py              # ToolRegistry, ToolCall, ToolResult, ParameterSchema
    ratelimit/
      token_bucket.py/.pyx  # TokenBucket, GlobalTokenBucket
      middleware.py          # RateLimitMiddleware
    sse/
      response.py            # SSEResponse, TokenStreamResponse, sse_stream()
      sse_writer.py/.pyx     # SSEWriter (Cython frame encoder)
  cache/
    lru.py                # CacheEngine, StaticCache
    backends.py           # DistributedCache, RedisCache, MemcachedCache
  headers/
    headers.py/.pyx       # Headers (Cython)
  middleware/
    cors.py               # CORSMiddleware
    auth.py               # BearerAuthMiddleware, APIKeyMiddleware
  protocol/
    cprotocol.pyx         # Cython HTTP/1.1 protocol (llhttp)
    protocol.py           # Pure-Python fallback
  request/
    request.py/.pyx       # Request, Stream (Cython)
  response/
    response.py/.pyx      # Response, JSONResponse, RedirectResponse … (Cython)
  router/
    router.py/.pyx        # Router, Route, AIRoute (Cython)
    parser.py             # URL pattern parser
  sessions/
    base.py               # SessionEngine ABC
    memory.py             # MemorySession
  workers/
    handler.py            # RequestHandler (Process subclass)
    reaper.py             # Reaper (keep-alive watchdog)
  components/
    container.py          # ComponentsEngine (DI)
  application.py          # Blueprint, EmberApplication
  server.py               # Ember (entry point, worker spawning)
  limits.py               # ServerLimits, RouteLimits, TokenLimits
  hooks.py                # Hook, Events
  constants.py            # Events enum
  exceptions.py           # RouteNotFound, RateLimitExceeded …
  __init__.py             # Public API surface
  __version__.py

examples/
  basic_api.py            # Routes, blueprints, middleware, caching
  streaming_chat.py       # SSE, ConversationContext, ModelRouter, tools
  tool_calling.py         # ToolRegistry, ParameterSchema, execute()

tests/
  test_router.py
  test_request.py
  test_responses.py
  test_ai.py

setup.py                  # Cython build config
pyproject.toml
requirements.txt
```

## Typical App Layout

```
myapp/
  app.py          # Ember() instance, top-level routes
  routes/
    tasks.py      # Blueprint for /tasks
    users.py      # Blueprint for /users
  services/
    db.py         # asyncpg pool helper
  models/
    task.py       # dataclass / TypedDict
  migrations/
    001_create_tasks.sql
```

```python
# app.py
from ember import Ember
from routes.tasks import tasks_bp
from routes.users import users_bp

app = Ember()
app.add_blueprint(tasks_bp, prefixes={"*": "/tasks"})
app.add_blueprint(users_bp, prefixes={"*": "/users"})

if __name__ == "__main__":
    app.run(workers=4)
```
