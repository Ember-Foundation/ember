# 1 — Hello World

This is the simplest possible Ember app. No database, no auth — just a running HTTP server.

---

## Create the file

```python
# main.py
from ember import Ember

app = Ember()

@app.get("/")
async def index(request):
    return {"hello": "world"}
```

## Run it

```bash
ember dev
```

```
  Ember dev server → http://127.0.0.1:8000
  Press Ctrl+C to stop
```

## Test it

```bash
curl http://127.0.0.1:8000/
# {"hello":"world"}
```

---

## What just happened?

- `Ember()` creates the application.
- `@app.get("/")` registers a `GET` route at the root path.
- Returning a `dict` automatically becomes a `JSONResponse` with `200 OK`.
- `ember dev` finds `app` in `main.py` automatically.

---

## Plain text response

```python
from ember import Ember, Response

app = Ember()

@app.get("/ping")
async def ping(request):
    return Response(b"pong", content_type=b"text/plain")
```

```bash
curl http://127.0.0.1:8000/ping
# pong
```

---

## Multiple routes

```python
from ember import Ember

app = Ember()

@app.get("/")
async def index(request):
    return {"name": "My API", "version": "1.0"}

@app.get("/health")
async def health(request):
    return {"status": "ok"}

@app.post("/echo")
async def echo(request):
    body = await request.json()
    return body
```

```bash
curl http://127.0.0.1:8000/health
# {"status":"ok"}

curl -X POST http://127.0.0.1:8000/echo \
  -H "Content-Type: application/json" \
  -d '{"message":"test"}'
# {"message":"test"}
```

---

## Inspect your routes

```bash
ember routes
```

```
METHOD     PATH          HANDLER
──────────────────────────────────────────
GET        /             index
GET        /health       health
POST       /echo         echo
```

**Next:** [Routing & Path Parameters →](./02-routing)
