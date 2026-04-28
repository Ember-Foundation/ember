# Getting Started

## Requirements

- Python 3.11 or higher
- pip

---

## 1. Install Ember

```bash
pip install ember-api
```

Install all performance extras (recommended for production):

```bash
pip install "ember-api[all]"
```

| Extra | Installs | Benefit |
|-------|----------|---------|
| `[fast]` | uvloop, orjson | ~30% RPS gain on Linux/macOS |
| `[cache]` | redis, aiomcache | Redis + Memcached backends |
| `[dev]` | pytest, httpx | testing |
| `[all]` | everything above | |

---

## 2. Create a New Project

```bash
ember new myapp
cd myapp
```

This scaffolds:

```
myapp/
  main.py           # app entry point
  requirements.txt  # ember-api
```

`main.py` starts with:

```python
from ember import Ember

app = Ember()

@app.get("/")
async def index(request):
    return {"message": "Hello from Ember!"}

@app.get("/health")
async def health(request):
    return {"status": "ok"}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
```

Options:

```bash
ember new myapp --port 9000      # set default port
```

---

## 3. Run the Dev Server

```bash
ember dev
```

The dev server starts on `http://127.0.0.1:8000` with a single worker and debug mode on. It auto-detects `main:app` — override with `--app`:

```bash
ember dev --app mymodule:my_app --port 9000
```

Test it:

```bash
curl http://127.0.0.1:8000/
# {"message":"Hello from Ember!"}
```

---

## 4. Build Cython Extensions

Cython compilation turns the HTTP parser, router, request, response, SSE writer, and token bucket into native C extensions — typically adding **30–50% RPS** over the pure-Python fallback.

```bash
ember build
```

First run installs Cython if needed, then compiles all `.pyx` files in-place. Subsequent builds only recompile changed files.

```bash
ember build --clean         # wipe build artifacts first
ember build --jobs 4        # parallel compile on 4 cores
```

Verify extensions loaded:

```bash
python -c "import ember.protocol.cprotocol; print('Cython OK')"
# Cython OK
```

---

## 5. List Routes

```bash
ember routes
```

```
METHOD     PATH                                          HANDLER
────────────────────────────────────────────────────────────────────────────────
GET        /                                             index
GET        /health                                       health
```

Override app location:

```bash
ember routes --app mymodule:app
```

---

## 6. Start Production Server

```bash
ember start
```

Starts with `os.cpu_count() + 2` workers bound to `0.0.0.0:8000`.

```bash
ember start --workers 8 --port 80
ember start --app mymodule:app --workers 4
```

Full production checklist:

```bash
# 1. Build Cython extensions
ember build

# 2. Start with explicit worker count
ember start --workers $(nproc) --port 8000
```

---

## Quick Reference

| Command | What it does |
|---------|-------------|
| `ember new <name>` | Scaffold a new project |
| `ember dev` | Dev server — single worker, debug on |
| `ember build` | Compile Cython hot paths |
| `ember build --clean` | Clean rebuild |
| `ember routes` | List all registered routes |
| `ember start` | Production server — multi-process |
| `ember start --workers N` | Production with N workers |
| `ember version` | Show version |
