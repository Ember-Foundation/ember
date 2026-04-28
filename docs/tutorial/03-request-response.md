# 3 — Request & Response

---

## Reading the Request

### Method and URL

```python
@app.route("/items", methods=["GET", "POST"])
async def items(request):
    method = request.method          # b"GET" or b"POST"
    path   = request.path            # "/items"
    qs     = request.query_string    # "page=1&limit=10"
    url    = request.url             # b"/items?page=1&limit=10"
```

### Headers

```python
content_type = request.headers.get_str("content-type", "")
auth         = request.headers.get_str("authorization", "")
user_agent   = request.headers.get_str("user-agent", "")
```

### Body

```python
# JSON body
@app.post("/tasks")
async def create(request):
    data = await request.json()     # dict
    title = data.get("title", "")
    return {"title": title}

# Raw bytes
@app.post("/upload")
async def upload(request):
    raw = await request.body()      # bytes
    return {"size": len(raw)}

# Plain text
@app.post("/text")
async def text_in(request):
    text = await request.text()     # str
    return {"received": text}

# Form data
@app.post("/form")
async def form_in(request):
    form = await request.form()     # dict[str, str]
    name = form.get("name", "")
    return {"name": name}
```

### Client IP

```python
@app.get("/whoami")
async def whoami(request):
    return {"ip": request.client_ip}
```

Checks `X-Forwarded-For` first (for proxied deployments), then falls back to the socket address.

---

## Response Types

### Dict → JSON (shorthand)

```python
@app.get("/items")
async def items(request):
    return {"items": []}   # automatically JSONResponse 200
```

### JSONResponse

```python
from ember import JSONResponse

return JSONResponse({"id": 1, "name": "Task"})                   # 200
return JSONResponse({"error": "not found"}, status_code=404)     # 404
return JSONResponse({"id": 1}, status_code=201)                  # 201 Created
```

### Plain Response

```python
from ember import Response

return Response(b"Hello", content_type=b"text/plain; charset=utf-8")
return Response(b"", status_code=204)   # No Content
```

### Custom Headers

```python
return JSONResponse(
    {"token": "abc"},
    headers={"x-request-id": "req-123", "cache-control": "no-store"},
)
```

### Redirect

```python
from ember import RedirectResponse

return RedirectResponse("/new-path")             # 302
return RedirectResponse("/new-path", status_code=301)  # 301 Permanent
```

---

## Status Codes

```python
return JSONResponse({}, status_code=200)   # OK
return JSONResponse({}, status_code=201)   # Created
return JSONResponse({}, status_code=204)   # No Content
return JSONResponse({}, status_code=400)   # Bad Request
return JSONResponse({}, status_code=401)   # Unauthorized
return JSONResponse({}, status_code=403)   # Forbidden
return JSONResponse({}, status_code=404)   # Not Found
return JSONResponse({}, status_code=409)   # Conflict
return JSONResponse({}, status_code=422)   # Unprocessable Entity
return JSONResponse({}, status_code=429)   # Too Many Requests
return JSONResponse({}, status_code=500)   # Internal Server Error
```

---

## Path Params in Context

Path parameters can also be read from `request.path_params`:

```python
@app.get("/users/{user_id:int}/posts/{post_id:int}")
async def get_post(request):
    params = request.path_params   # {"user_id": 7, "post_id": 42}
    return params
```

Or injected directly — Ember matches handler argument names to the pattern:

```python
@app.get("/users/{user_id:int}/posts/{post_id:int}")
async def get_post(request, user_id: int, post_id: int):
    return {"user": user_id, "post": post_id}
```

---

## Full CRUD Example

```python
from ember import Ember, Request, JSONResponse
import uuid

app = Ember()
db: dict = {}

@app.get("/items")
async def list_items(request: Request) -> JSONResponse:
    page  = int(request.get_arg("page", "1"))
    limit = int(request.get_arg("limit", "10"))
    items = list(db.values())[(page - 1) * limit : page * limit]
    return JSONResponse({"items": items, "total": len(db)})

@app.get("/items/{item_id:str}")
async def get_item(request: Request, item_id: str) -> JSONResponse:
    item = db.get(item_id)
    if not item:
        return JSONResponse({"error": "not_found"}, status_code=404)
    return JSONResponse(item)

@app.post("/items")
async def create_item(request: Request) -> JSONResponse:
    data = await request.json()
    item_id = str(uuid.uuid4())
    db[item_id] = {"id": item_id, **data}
    return JSONResponse(db[item_id], status_code=201)

@app.put("/items/{item_id:str}")
async def update_item(request: Request, item_id: str) -> JSONResponse:
    if item_id not in db:
        return JSONResponse({"error": "not_found"}, status_code=404)
    data = await request.json()
    db[item_id].update(data)
    return JSONResponse(db[item_id])

@app.delete("/items/{item_id:str}")
async def delete_item(request: Request, item_id: str) -> JSONResponse:
    if item_id not in db:
        return JSONResponse({"error": "not_found"}, status_code=404)
    del db[item_id]
    return JSONResponse({"deleted": item_id})

if __name__ == "__main__":
    app.run(port=8000)
```

**Next:** [Middleware →](./04-middleware)
