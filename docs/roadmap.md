# Roadmap

---

## v0.1.0 — Current Release ✅

**Core framework complete.**

- [x] Custom llhttp C parser compiled via Cython
- [x] Multi-process fork workers with `SO_REUSEPORT` kernel load balancing
- [x] Cython hot paths: headers, request, response, router, protocol, SSE writer, token bucket
- [x] LRU route cache with correct path-param extraction on cache hit
- [x] Pure-Python fallback for every compiled module
- [x] `StaticCache` — pre-event-loop, zero-overhead in-process cache
- [x] `RedisCache` + `MemcachedCache` — distributed TTL cache with auto-connect lifecycle
- [x] `SSEResponse`, `TokenStreamResponse`, `sse_stream()` — first-class LLM streaming
- [x] AI primitives: `ConversationContext`, `PromptTemplate`, `ToolRegistry`, `ModelRouter`, `SemanticCache`
- [x] Token-aware rate limiting: `TokenBucket`, `GlobalTokenBucket`, `RateLimitMiddleware`
- [x] Built-in middleware: CORS, Bearer auth, API key
- [x] Blueprints with URL prefixes and per-blueprint limits/hooks
- [x] Cross-platform: Linux/macOS multi-process, Windows single-process fallback
- [x] CLI: `ember new`, `ember dev`, `ember build`, `ember start`, `ember routes`

---

## v0.1.5 — `io_uring` Event Loop ✅

**Shipped Q2 2026.** Replaces `epoll` on Linux ≥ 5.1.

- [x] `UringSelector` `cdef class` exposing the stdlib `selectors` interface
- [x] Multishot `IORING_OP_POLL_ADD`, `IORING_OP_RECV`, `IORING_OP_SEND`
- [x] Registered buffer ring (1024 × 32 KB) — kernel-side buffer selection
- [x] `IORING_SETUP_DEFER_TASKRUN` / `COOP_TASKRUN` / `SINGLE_ISSUER`
- [x] Eager-task fast path + `_simple_call` route registration
- [x] **120k RPS** on a single worker for `GET /hello`

See [`docs/guide/performance.md`](./guide/performance) for the full story.

---

## v0.2.0 — Observability & Real-Time

**Target: Q3 2026**

- [ ] **WebSocket support** — `Upgrade: websocket` handshake + async frame parser, room management
- [ ] **Prometheus metrics middleware** — per-route counters, latency histograms, error rates
- [ ] **Structured access log middleware** — JSON logs: method, path, status, duration, client IP
- [ ] **Response gzip/brotli compression** — `Accept-Encoding` negotiation, configurable threshold
- [ ] **`ember dev --reload`** — watch `.py` files, restart worker on change

---

## v0.3.0 — Developer Experience

**Target: Q4 2026**

- [ ] **OpenAPI / Swagger auto-generation** — derive spec from type annotations, serve at `/docs`
- [ ] **Pydantic v2 request body validation** — `@app.post("/", body=MyModel)` with auto 422
- [ ] **Static file serving** — `app.static("/assets", "./public")` using `sendfile()` zero-copy
- [ ] **Session backends** — Redis session store, signed cookie sessions
- [ ] **`ember test`** — built-in async test client, no httpx setup required

---

## v0.4.0 — Advanced Networking

**Target: Q1 2027**

- [ ] **HTTP/2** — multiplexed streams via the `h2` library
- [ ] **Request streaming** — chunked upload progress hooks
- [ ] **Connection pooling** — outbound HTTP pool for downstream service calls
- [ ] **Circuit breaker** — automatic fallback when downstream is unhealthy

---

## v0.5.0 — Free-Threaded Python

**Target: Q2 2027** — depends on Python 3.13t adoption

PEP 703 ships in CPython 3.13 as the optional "no-GIL" build. Ember's
Cython hot paths already release the GIL during `io_uring` syscalls, so the
groundwork is mostly there. The work:

- [ ] **Per-thread `UringSelector`** — each native thread owns its ring, no
      cross-thread submission contention.
- [ ] **`UringEventLoop` thread-affinity scheduler** — connections pinned to
      the thread that accepted them; no migration mid-request.
- [ ] **Audit Cython hot paths for `nogil` correctness** under
      `--enable-experimental-jit` and `PYTHON_GIL=0`.
- [ ] **`cdef class` mutex** added to `Router._lru` and `_Headers._index`
      (currently relies on GIL atomicity).
- [ ] **`EMBER_THREADS=N`** env var — spawn N event-loop threads inside each
      worker process.
- [ ] CI matrix: `cp313t-linux`, `cp313t-macos`, falling back to GIL build
      with no API change.

**Target throughput:** ~500k RPS per worker (4 threads × 120k), 1M+ RPS on
modest hardware.

See [Path to 1M RPS](./guide/performance#path-to-1m-rps) for the full plan.

---

## v0.6.0 — `prepare`-Chained `io_uring` Fast Path

**Target: Q3 2027**

Use `liburing`'s `prepare_*` API + `IOSQE_IO_LINK` to chain RECV → parse →
SEND → buffer-return into a single submission. Eliminates the userspace round
trip for cache-hit endpoints.

- [ ] **`UringTransport.prepare_static_reply(route_id, payload)`** — pin a
      route + response in registered memory.
- [ ] **`@app.get("/health", cache=StaticCache(), prepare=True)`** — opt-in
      decorator flag; the parser dispatches matching requests directly to
      the prepared SQE chain without reaching Python.
- [ ] **`prepare_streaming(generator)`** — chain SEND SQEs for SSE bursts;
      the kernel emits frames back-to-back.
- [ ] Benchmark target: **3× the current `StaticCache` RPS**, p99 < 1 ms.

---

## v0.7.0 — High-Performance Cython ORM

**Target: Q4 2027**

A first-party ORM that lives at the same performance tier as the framework.
Rationale: `asyncpg`, `aiomysql`, `aiosqlite` and SQLAlchemy each impose 30–60%
of the per-request budget at 100k RPS — protocol parsing in Python, ORM
overhead, and worst of all, **TCP connect / handshake overhead** for short
sessions. We can do much better.

### Design pillars

1. **Cython protocol parsers, not Python.** Each driver is a `cdef class`
   that speaks the wire protocol natively — no per-row tuple boxing for
   metadata, no Python-level state machine.
2. **Connection pool lives in the same `io_uring` as the HTTP transport.**
   No second event loop, no socket handoff, no thread hop. Submitting a
   query is one SQE on the same ring as the inbound HTTP RECV.
3. **`prepare`-chained queries** — a request that translates to a single
   `SELECT` becomes a kernel-side `RECV(http) → SEND(query) → RECV(rows) →
   SEND(http_response)` chain. The application thread wakes up once.
4. **Zero-copy row decoding** — rows are returned as views into the network
   buffer ring. Materialization to Python objects is opt-in
   (`row.as_dict()`, `row.as_pydantic(Model)`).
5. **Pre-warmed, pinned connections** — `pool.warm()` opens N connections
   before traffic starts; `SO_INCOMING_CPU` pins them to the same core as
   the worker. Eliminates connect latency from the request critical path.
6. **TLS via `kTLS`** — kernel TLS offload for `pgsslmode=require`. After
   the handshake, app/server data path is plain `recv/send` again, so the
   `io_uring` chain keeps working.

### TCP / connection-overhead improvements

| Technique | Win |
| --- | --- |
| `TCP_FASTOPEN` (client) | Skip SYN-ACK round trip on first query |
| `SO_KEEPALIVE` + `TCP_KEEPIDLE=30` | Detect dead pool conns without app-level pings |
| `TCP_NODELAY` + `TCP_QUICKACK` | No 40 ms Nagle delay on small queries |
| Pre-opened connections (`pool.warm()`) | First-request latency drops from ~3 ms (DNS+TCP+TLS) to ~0.1 ms |
| Linger=0 on shutdown | Free up TIME_WAIT slots faster under churn |
| Connection multiplexing (Postgres pipelining, MySQL COM_STMT batches) | N queries in one round trip |
| Pinned worker affinity (`SO_INCOMING_CPU`) | DB connection lives on same core as handler — no LLC miss |
| Unix-domain socket auto-detect | If the DB is local, use `/var/run/postgresql/.s.PGSQL.5432` instead of TCP |

### Roadmap by driver

- [ ] **`ember.orm.pg`** — PostgreSQL wire protocol v3 in Cython.
      Binary format only; `prepare`/`execute` cached per-connection.
      Targets: `asyncpg` parity within 5% then beats it via `io_uring`.
- [ ] **`ember.orm.mysql`** — MySQL/MariaDB native protocol; `caching_sha2_password` only.
- [ ] **`ember.orm.sqlite`** — `apsw` bindings via the loop's thread executor;
      `sqlite3` WAL mode tuning.
- [ ] **`ember.orm.mssql`** — TDS 7.4 in Cython for SQL Server.
- [ ] **`ember.orm.oracle`** — wraps `python-oracledb` thin mode initially,
      moves to native TNS protocol in v0.8.
- [ ] **`ember.orm.cockroach`** — Postgres wire-compatible; tested separately
      for retry semantics.
- [ ] **`ember.orm.redis`** — RESP3 parser (already partly written for
      `RedisCache`); promoted to a full client.

### Query layer

- [ ] **Typed model classes** — `class User(Model): id: int; email: str`
      compiles to a Cython `cdef class` at import time via a metaclass; field
      access is C-speed.
- [ ] **Async-iterator cursors** — `async for row in db.query(...):` streams
      from the buffer ring; `LIMIT`-less queries don't blow up RAM.
- [ ] **`select`/`insert`/`update`/`delete` builder** — composable, no string
      concatenation; statements are cached and re-bound by hash.
- [ ] **Transparent pipelining** — within an `async with db.transaction():`
      block, individual `await`s are buffered and flushed at `commit`/`yield
      to event loop`, like `asyncpg`'s `pipeline()`.
- [ ] **Migrations** — `ember orm makemigrations` and `ember orm migrate`,
      stored as Cython-importable modules so they run during deploy at C speed.

### Integration with the framework

```python
from ember import Ember
from ember.orm import Database, Model

db = Database("postgres://localhost/app", pool=20, warm=True)

class Task(Model):
    id: int
    title: str
    done: bool

app = Ember()
app.use(db)                                # joins the worker's io_uring

@app.get("/tasks/{task_id:int}")
async def get_task(request, task_id: int):
    task = await Task.get(task_id)         # one SQE; rows zero-copied
    return task.as_dict()
```

**Throughput target:** 80k RPS on a `SELECT … WHERE id = $1` against local
Postgres, single Ember worker. Today, the same handler with `asyncpg` ceilings
around 25k.

---

## v1.0.0 — Stable Release

**Target: Q1 2028**

- [ ] Stable public API, semantic versioning commitment
- [ ] Comprehensive test suite with 95%+ coverage
- [ ] Benchmarked and documented performance regression CI gate
- [ ] Official PyPI `ember-api` wheel with pre-built Cython binaries for
      Linux x86_64, ARM64, macOS (both GIL and `t` ABIs)
- [ ] `ember.orm` 1.0 with Postgres, MySQL, SQLite, Redis stable

---

## Long-term Ideas

| Idea | Notes |
|------|-------|
| HTTP/3 (QUIC) | via `aioquic` or native `io_uring` UDP support |
| GraphQL over SSE/WebSocket | subscription support |
| Distributed tracing | OpenTelemetry integration |
| Edge/worker deployment | WASM-compatible pure-Python mode |
| gRPC gateway | transcode REST → gRPC |
| AF_XDP fast path | bypass the kernel network stack for the busiest routes |

---

## How to Contribute

See [Contributing](./contributing) for dev setup and PR process.
Feature requests: [GitHub Issues](https://github.com/Ember-Foundation/ember/issues/new?template=feature_request.md)
