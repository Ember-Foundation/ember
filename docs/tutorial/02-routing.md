# 2 — Routing & Path Parameters

---

## HTTP Methods

```python
@app.get("/items")          # GET
@app.post("/items")         # POST
@app.put("/items/{id:int}") # PUT
@app.patch("/items/{id:int}")   # PATCH
@app.delete("/items/{id:int}")  # DELETE

# Multiple methods on one handler
@app.route("/items", methods=["GET", "POST"])
async def items(request):
    if request.method == b"POST":
        ...
```

---

## Path Parameters

Declare typed parameters in the URL pattern — they are extracted and injected directly into your handler.

```python
@app.get("/users/{user_id:int}")
async def get_user(request, user_id: int):
    return {"user_id": user_id}   # user_id is already an int
```

```bash
curl http://127.0.0.1:8000/users/42
# {"user_id": 42}
```

### Converters

| Converter | Pattern | Example |
|-----------|---------|---------|
| `:int` | `[0-9]+` | `/users/42` |
| `:float` | `[0-9.]+` | `/prices/9.99` |
| `:str` | `[^/]+` | `/posts/my-slug` |
| `:uuid` | UUID format | `/tasks/550e8400-...` |
| `:path` | `.*` (matches `/`) | `/files/a/b/c.txt` |

```python
@app.get("/posts/{slug:str}")
async def get_post(request, slug: str):
    return {"slug": slug}

@app.get("/tasks/{task_id:uuid}")
async def get_task(request, task_id: str):
    return {"task_id": task_id}

@app.get("/files/{filepath:path}")
async def get_file(request, filepath: str):
    return {"path": filepath}
```

---

## Query Parameters

`request.args` is a `dict[str, list[str]]`. Use `get_arg()` for a single value.

```python
@app.get("/tasks")
async def list_tasks(request):
    page    = int(request.get_arg("page", "1"))
    limit   = int(request.get_arg("limit", "10"))
    status  = request.get_arg("status")           # None if missing

    return {
        "page": page,
        "limit": limit,
        "filter": status,
    }
```

```bash
curl "http://127.0.0.1:8000/tasks?page=2&limit=5&status=done"
# {"page":2,"limit":5,"filter":"done"}
```

---

## Named Routes

Give a route a name to reference it programmatically:

```python
@app.get("/users/{user_id:int}", name="user_detail")
async def get_user(request, user_id: int):
    return {"user_id": user_id}
```

---

## Route Priorities

Static routes always match before dynamic ones. `/users/me` will always win over `/users/{user_id:int}`:

```python
@app.get("/users/me")           # static — matches first
async def get_me(request): ...

@app.get("/users/{user_id:int}")  # dynamic — fallback
async def get_user(request, user_id: int): ...
```

---

## 404 and 405 Handlers

```python
@app.handle(404)
async def not_found(exc):
    from ember import JSONResponse
    return JSONResponse({"error": "not_found"}, status_code=404)

@app.handle(405)
async def method_not_allowed(exc):
    from ember import JSONResponse
    return JSONResponse({"error": "method_not_allowed"}, status_code=405)
```

**Next:** [Request & Response →](./03-request-response)
