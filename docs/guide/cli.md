# CLI Reference

Ember ships a CLI accessible as `ember` after `pip install ember-api`.

```bash
ember --help
```

---

## `ember new`

Scaffold a new project directory.

```bash
ember new <name> [--port PORT]
```

| Flag | Default | Description |
|------|---------|-------------|
| `name` | required | Directory name and project name |
| `--port` | `8000` | Default port written into `main.py` |

**Example:**

```bash
ember new myapi --port 9000
cd myapi
ember dev
```

---

## `ember dev`

Run a development server — single worker, debug logging enabled.

```bash
ember dev [--host HOST] [--port PORT] [--app MODULE:ATTR]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--host` | `127.0.0.1` | Bind address |
| `--port` | `8000` | Bind port |
| `--app` | auto-detect | App location (`module:attr`) |

Auto-detection order: `main:app` → `app:app` → `application:app`.

**Example:**

```bash
ember dev --port 9000
ember dev --app src.main:app
```

---

## `ember build`

Compile Cython hot-path extensions in-place. Must be run from the repo root (where `setup.py` lives).

```bash
ember build [--clean] [--jobs N]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--clean` | off | Remove `.so`, `.c`, `build/` before compiling |
| `--jobs N` | cpu count | Parallel compiler processes |

**Example:**

```bash
# First-time build
ember build

# Clean rebuild (after upgrading Cython)
ember build --clean --jobs 4
```

What gets compiled:

| Module | File |
|--------|------|
| HTTP protocol (llhttp) | `ember/protocol/cprotocol.pyx` |
| Router + LRU cache | `ember/router/router.pyx` |
| Request + Stream | `ember/request/request.pyx` |
| Response | `ember/response/response.pyx` |
| Headers | `ember/headers/headers.pyx` |
| SSE writer | `ember/ai/sse/sse_writer.pyx` |
| Token bucket | `ember/ai/ratelimit/token_bucket.pyx` |

---

## `ember routes`

Inspect all registered routes for the app.

```bash
ember routes [--app MODULE:ATTR]
```

**Example output:**

```
METHOD     PATH                                          HANDLER
────────────────────────────────────────────────────────────────────────────────
DELETE     /tasks/{task_id}                              delete_task
GET        /                                             index
GET        /health                                       health
GET        /tasks                                        list_tasks
GET        /tasks/{task_id}                              get_task
POST       /tasks                                        create_task
POST       /v1/chat                                      chat   [AI/SSE]
PUT        /tasks/{task_id}                              update_task
```

Routes marked `[AI/SSE]` are `ai_route()` endpoints.

---

## `ember start`

Run the production server — multi-process, no debug output.

```bash
ember start [--host HOST] [--port PORT] [--workers N] [--app MODULE:ATTR]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--host` | `0.0.0.0` | Bind address |
| `--port` | `8000` | Bind port |
| `--workers` | `cpu_count + 2` | Worker processes |
| `--app` | auto-detect | App location |

**Example:**

```bash
ember start --workers 8 --port 80
ember start --app api.main:app --workers $(nproc)
```

---

## `ember version`

```bash
ember version
# Ember 0.1.0
```

---

## App Spec (`--app`)

All commands that accept `--app` use the `module:attr` format:

```bash
ember dev --app main:app           # from ./main.py, object named app
ember dev --app src.server:create  # from ./src/server.py, callable
ember start --app mypackage.main:application
```

The module is imported relative to the current working directory.
