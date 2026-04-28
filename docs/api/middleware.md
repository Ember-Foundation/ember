# Middleware

Middleware is registered via `app.add_middleware()` and runs as a `BEFORE_ENDPOINT` hook on every request.

---

## CORS

```python
from ember import CORSMiddleware

app.add_middleware(CORSMiddleware(
    allow_origins=["https://myapp.com", "http://localhost:3000"],
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["content-type", "authorization"],
    allow_credentials=False,
    max_age=86400,
))
```

Pass `allow_origins=["*"]` to allow all origins. When `allow_credentials=True`, the specific request origin is reflected instead of `*`.

---

## Bearer Auth

```python
from ember import BearerAuthMiddleware

app.add_middleware(BearerAuthMiddleware(
    verify_fn=lambda token: token == "my-secret-token",
    exclude_paths=["/health", "/docs"],
))
```

`verify_fn` may be sync or async. Returns `True` to allow, `False` to respond with `401`.

---

## API Key

```python
from ember import APIKeyMiddleware

app.add_middleware(APIKeyMiddleware(
    api_keys=["key-abc", "key-xyz"],
    header="x-api-key",
    exclude_paths=["/health"],
))
```

---

## Rate Limiting (Token Bucket)

```python
from ember import RateLimitMiddleware, GlobalTokenBucket

bucket = GlobalTokenBucket(
    capacity=100_000.0,          # max tokens in bucket
    refill_rate=100_000.0 / 60,  # tokens per second
)

app.add_middleware(RateLimitMiddleware(
    global_bucket=bucket,
    estimate_from_body=True,   # deduct estimated tokens from request body
))
```

Returns `429 Too Many Requests` when the bucket is empty.

---

## Custom Middleware

Any callable that matches the hook signature works:

```python
async def logging_middleware(request, response):
    import time
    start = time.monotonic()
    # (response is None at BEFORE_ENDPOINT)
    yield  # control passes to handler
    elapsed = time.monotonic() - start
    print(f"{request.method.decode()} {request.path} {elapsed*1000:.1f}ms")

@app.hook(Events.BEFORE_ENDPOINT)
async def log(request, response):
    ...
```

Or as a class with `__call__`:

```python
class TimingMiddleware:
    async def __call__(self, request, response):
        ...

app.add_middleware(TimingMiddleware())
```
