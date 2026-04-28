# Request & Response

## Request

```python
request.method          # bytes: b"GET"
request.url             # bytes: b"/tasks?page=1"
request.path            # str:   "/tasks"
request.query_string    # str:   "page=1"
request.args            # dict[str, str] — query params
request.headers         # Headers object
request.path_params     # dict — path param values (e.g. {"task_id": "abc"})
request.client_ip       # str — remote address
request.stream_requested # bool — client sent Accept: text/event-stream
```

### Reading the Body

```python
body  = await request.body()          # bytes
text  = await request.text()          # str
data  = await request.json()          # dict (uses orjson if available)
form  = await request.form()          # dict[str, str]
```

### AI Body

```python
body = await request.ai_body()
# body.messages — list of message dicts
# body.stream   — bool
# body.model    — str | None
```

### Token Counting

```python
count = request.estimate_tokens()   # fast heuristic (chars / 4)
```

### Streaming Upload

```python
@app.post("/upload")
async def upload(request):
    async for chunk in request.stream:
        process(chunk)
```

---

## Response

### Plain

```python
from ember import Response

return Response(
    content=b"Hello",
    status_code=200,
    headers={"content-type": "text/plain"},
)
```

### JSON

```python
from ember import JSONResponse

return JSONResponse({"key": "value"}, status_code=200)
return JSONResponse({"error": "not found"}, status_code=404)
```

Uses `orjson` if installed (2–3× faster than `json`).

### Redirect

```python
from ember import RedirectResponse

return RedirectResponse("/new-path", status_code=301)
```

### SSE (Server-Sent Events)

```python
from ember import SSEResponse

async def generator():
    for i in range(10):
        yield f"data: chunk {i}\n\n"

return SSEResponse(generator())
```

### Token Stream

```python
from ember import TokenStreamResponse

async def tokens():
    for word in "Hello world".split():
        yield word + " "

return TokenStreamResponse(tokens())
```

Each token is automatically wrapped in SSE `data:` frames.

### `sse_stream()` Helper

```python
from ember import sse_stream, GlobalTokenBucket

bucket = GlobalTokenBucket(capacity=100_000, refill_rate=1_000)

return sse_stream(token_generator(), token_bucket=bucket)
```

Applies back-pressure via the token bucket when provided.

---

## Status Codes

```python
return JSONResponse({}, status_code=201)  # Created
return JSONResponse({}, status_code=204)  # No Content
return JSONResponse({}, status_code=400)  # Bad Request
return JSONResponse({}, status_code=401)  # Unauthorized
return JSONResponse({}, status_code=403)  # Forbidden
return JSONResponse({}, status_code=404)  # Not Found
return JSONResponse({}, status_code=422)  # Unprocessable Entity
return JSONResponse({}, status_code=500)  # Internal Server Error
```
