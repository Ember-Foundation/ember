# Performance Guide

Ember is built for throughput **and** for a small RSS footprint. A single
worker on commodity hardware serves **~112,000 RPS** for `GET /hello` at
**25 MB peak RSS** — a 5–10× RPS margin and ~2× lighter memory than
equivalent FastAPI / Express setups on the same box. On real CRUD workloads
against PostgreSQL, Ember serves **20,961 RPS** — **2.9× Express and 10.8×
FastAPI on the same hardware** — with a p99 tail 2× tighter than Express and
10× tighter than FastAPI.

This guide is in two parts:

1. **What Ember already does** for you (so you understand where the speed comes from).
2. **What you can do** to extract every last microsecond — including the path to
   **1 million RPS** with free-threaded (no-GIL) Python 3.13 and `io_uring`
   `prepare`-chained syscalls.

::: tip What's new in v0.2 (RSS shrink + 112k RPS)
Peak RSS dropped from **48 MB → 25 MB** (-48%) and RPS climbed from 91k → **112k** single-thread (+23%). Four changes did the work:

- **`workers=1` runs in-process** on Linux now — no supervisor process, ~22 MB saved.
- **io_uring buffer pool is runtime-tunable.** Default is now 256 × 8 KB (= 2 MB) instead of 1024 × 32 KB (= 32 MB). Pass `Ember.run(io_uring_num_bufs=, io_uring_buf_size=)` to override.
- **`import ember` lazy-loads** the AI / cache / middleware namespaces — plain HTTP apps no longer pay for numpy / redis / memcached at startup.
- **Trivial-handler fast path** (v0.2.1): when a route's `async def` handler can't suspend (bytecode-verified, no `await`), the protocol drives the coroutine directly with `coro.send(None)` and skips the `_handle_request` wrapper + Task allocation. Saves 1 Task + 1 coroutine + 1 await dispatch per request.
:::

---

## Headline Numbers

Single worker, Python 3.12+, Linux 6.8, kernel `io_uring` event loop,
`GET /hello → "Hello, World!"`, k6 200 VUs.

### Ember build evolution

How Ember got to its current throughput and footprint, layer by layer:

| Build                                                       | RPS          | p50       | p99       | Peak RSS |
| ----------------------------------------------------------- | ------------ | --------- | --------- | -------: |
| Pure Python (asyncio + epoll)                               | ~1,750       | 28 ms     | 95 ms     |   ~45 MB |
| + Cython hot paths                                          | ~2,350       | 20 ms     | 70 ms     |   ~46 MB |
| + uvloop                                                    | ~2,650       | 16 ms     | 55 ms     |   ~46 MB |
| **+ io_uring + buffer-ring (v0.1.5)**                       | **~72,000**  | 4 ms      | 28 ms     |   ~50 MB |
| **+ eager-task / simple-call fast path (v0.1.6)**           | **~91,000**  | 2 ms      | 6 ms      |    48 MB |
| **+ in-process workers=1, tunable buf pool, lazy imports (v0.2)** | **~96,000** | **1.9 ms** | **5.2 ms** | **25 MB** |
| **+ trivial-handler bypass (v0.2.1)**                       | **~112,000** | **1.68 ms** | **4.35 ms** | **25 MB** |

### Cross-framework comparison

All five frameworks running an equivalent `GET /hello → "Hello, World!"` route
on the same Intel i7-14700 box, single worker, k6 200 VUs / 20 s, 0% errors.
Fiber pinned to one core via `GOMAXPROCS=1` for fairness.

| Framework        |       RPS | avg (ms) | p50 (ms) | p95 (ms) | p99 (ms) | peak CPU | peak RSS |
| ---------------- | --------: | -------: | -------: | -------: | -------: | -------: | -------: |
| **Fiber (Go)**   | **140,993** |     1.36 |     1.21 |     2.91 |     3.96 |    89.3% |  **8.8 MB** |
| **Ember**        | **112,177** |     1.75 |     1.68 |     2.59 |     4.35 |    89.7% |  **25.2 MB** |
| Express (Node)   |    26,357 |     7.56 |     7.09 |     9.98 |    13.57 |   104.0% |  131.0 MB  |
| NestJS (Node)    |    23,528 |     8.47 |     8.08 |    10.97 |    13.75 |   105.0% |  158.6 MB  |
| FastAPI (Python) |    17,517 |    11.36 |     9.45 |    20.67 |    30.86 |    89.4% |   49.1 MB  |

Notes:

- Ember runs **~6.4× FastAPI**, **~4.3× Express**, and **~4.8× NestJS** on the
  same single core.
- **Throughput:** Ember sits at **80% of Fiber's RPS** — the closest a Python
  framework has come to a Go fasthttp framework on a single core.
- **Memory:** Ember's 25.2 MB peak RSS is the lowest of any Python or Node
  framework here — half of FastAPI's 49 MB, and **5–6× lighter than Node**.
  Only Fiber's static Go binary (no interpreter) sits lower.
- CPU > 100% on Node frameworks reflects libuv worker threads + V8 GC running
  off the main event loop; Fiber, Ember, and FastAPI all sit at the
  single-core ceiling (~90%).
- RPS variance run-to-run is ±10–15% on a shared 28-core box (k6 itself
  competes for cores) — see [`taskbench/hello_bench/results/`](https://github.com/Ember-Foundation/ember/tree/master/taskbench/hello_bench/results) for raw samples.

Reproducible: [`taskbench/hello_bench/`](https://github.com/Ember-Foundation/ember/tree/master/taskbench/hello_bench)
— `./bench_all.sh` builds dependencies and runs all five back-to-back.

### Reproducing the bench with low variance

`bench_one.sh` runs the server and k6 unconstrained, so they can land on the
same cores and fight for cycles. On a 28-core dev box you can see 82k–133k
single-run swings. Use `bench_pinned.sh` to pin server and load generator
to disjoint core sets:

```bash
cd taskbench/hello_bench
./bench_pinned.sh ember 9010 env EMBER_WORKERS=1 python3 apps/ember/server.py
# Override defaults if needed:
SERVER_CORES=14 K6_CORES=0-13,15-27 ./bench_pinned.sh ember 9010 ...
```

Defaults: server pinned to cores `0-3` (4 logical P-cores — lets the kernel
pick the freshest one and keeps turbo headroom), k6 pinned to cores `4-27`.
On the i7-14700, this gives a tight RPS distribution around **90-95k** with
p99 ≤ 4.5 ms across runs. Pinning the server to a single core actually
*hurts* throughput on modern hybrid CPUs because it kills turbo boost on that
core — give it a small pool instead.

### CRUD benchmark (PostgreSQL, mixed reads + writes)

Real CRUD workload — 65% list-paginated, 25% single-item GET, 10% create
(INSERT) — against a PostgreSQL 16 table on the same box. Single-target
benchmark: each framework benched in isolation. **200 VUs sustained for 40s**
after a 10s ramp. Single worker (`workers=1`). 0% errors across all three.

Ember uses the default `TTLCache(ttl=1.0)` framework primitive on its three
read routes (TTL caching + single-flight request coalescing built in). Express
and FastAPI run their stock pool/handler code with no app-side caching.

| Framework        | RPS | avg (ms) | p50 | p95 | p99 | Verdict |
| ---------------- | --: | -------: | --: | --: | --: | ------- |
| **Ember**        | **20,961** |  **8.31** | **7** | **19** | **26** | TTLCache + single-flight default |
| Express (Node)   |  7,233 | 24.12 | 26 | 38 | 51 | reference (no cache) |
| FastAPI (Python) |  1,932 | 90.35 | 80 | 195 | 275 | uvloop + asyncpg, no cache |

**Ember serves 2.9× the throughput of Express and 10.8× of FastAPI on the
same hardware**, with a p99 tail 2× tighter than Express and 10× tighter than
FastAPI. The decisive factor is the framework primitive — adding
`cache=TTLCache(ttl=1.0)` to a GET route is a one-line change that cuts
PostgreSQL pool pressure 100–1000× under thundering-herd traffic by coalescing
concurrent identical reads onto a single roundtrip.

Sample tuned route:

```python
from ember.cache import TTLCache

list_cache = TTLCache(ttl=1.0, max_entries=512)

@app.get("/tasks", cache=list_cache)
async def list_tasks(request):
    row = await pool.fetchrow("SELECT ...")
    return Response(...)
```

Reproducible: [`taskbench/ember_app/main_tuned.py`](https://github.com/Ember-Foundation/ember/tree/master/taskbench/ember_app/main_tuned.py)
— start each server, then `BASE=http://localhost:9002 k6 run bench.js`
against each in turn.

---

## How Ember Achieves This

Five layers compound, in order of impact.

### Layer 1 — `io_uring` event loop (replaces `epoll`)

`ember/eventloop/uring.pyx` is a Cython `cdef class` that implements the
stdlib `selectors.BaseSelector` interface so asyncio can drop it in. It uses:

- **`IORING_OP_POLL_ADD` (multishot)** — register a socket once, get every
  readiness notification until you cancel. Replaces the `epoll_ctl(MOD)` round
  trip every `epoll_wait` cycle does.
- **`IORING_OP_RECV` (multishot)** — kernel does the `read(2)` and posts the
  result. Userspace never calls `recv(2)`.
- **`IORING_OP_SEND`** — direct submission for response writes.
- **`io_uring_submit_and_wait_timeout`** — combines `submit + wait` into a
  single syscall. With `IORING_SETUP_DEFER_TASKRUN` + `COOP_TASKRUN` +
  `SINGLE_ISSUER`, the kernel batches completions and skips IPI signalling
  between submitter and consumer threads.
- **Registered buffer ring** (`io_uring_setup_buf_ring`) — by default
  256 × 8 KB (= 2 MB) buffers shared across all connections;
  `IOSQE_BUFFER_SELECT` lets the kernel pick a free slot per RECV. Returning a
  buffer is a memory write (`io_uring_buf_ring_add` + `_advance`),
  **no SQE, no syscall**. Tune via `Ember.run(io_uring_num_bufs=...,
  io_uring_buf_size=...)`. `num_bufs` must be a power of two; `buf_size` ≤ 65535.

  Profiles:
  - **Low-RSS** — `io_uring_num_bufs=128, io_uring_buf_size=4096` → 0.5 MB pool.
    Best for low-concurrency / serverless / sidecar deployments.
  - **Default** — 256 × 8 KB = 2 MB. Good for most workloads up to a few
    thousand concurrent connections.
  - **High-throughput** — `io_uring_num_bufs=1024, io_uring_buf_size=32768`
    → 32 MB pool. Use when you have very high concurrency or large request
    bodies and ample RAM.

Net effect at 100k RPS: roughly **2 syscalls per request** (one submit/wait
batch plus the SEND), vs. ~6 for an epoll + readv + writev loop.

### Layer 2 — Cython `cdef class` hot paths

Five modules are compiled to C with `language_level=3, boundscheck=False,
wraparound=False, cdivision=True`:

| Module                       | What it accelerates                                    |
| ---------------------------- | ------------------------------------------------------ |
| `protocol/cprotocol.pyx`     | llhttp-driven HTTP/1.1 parser + dispatcher             |
| `router/router.pyx`          | LRU-cached route matcher with path-param extraction    |
| `request/request.pyx`        | Request, Stream, lazy headers/body                     |
| `response/response.pyx`      | Response, JSONResponse, SSEResponse                    |
| `headers/headers.pyx`        | Pre-indexed case-insensitive header map                |
| `eventloop/uring.pyx`        | UringSelector + UringTransport + UringEventLoop        |
| `ai/sse/sse_writer.pyx`      | Zero-copy SSE frame emitter                            |
| `ai/ratelimit/token_bucket.pyx` | Lock-free token bucket                              |

Recent micro-optimizations (commit `48d6372`):

- **`headers.pyx`** — pre-build the index in `__init__`, no `None` check on
  every `.get()`.
- **`request.pyx`** — skip stdlib `urlparse`; `find(b"?")` + slice gives
  `path` and `query_string` from the raw target bytes.
- **`router.pyx`** — `cdef str url_str` decoded once for the dynamic-pattern
  loop; drop `hasattr(request, "_path_params")` — it's always present.
- **`cprotocol.pyx`** — pull deferred imports (`Request`, `Stream`,
  `RouteNotFound`, `Response`) up to module scope. No `sys.modules` dict
  lookups per request.
- **`response.pyx`** — `get_running_loop()` (C thread-local read) instead of
  `get_event_loop()` (full lookup) in streaming `send()`.

### Layer 3 — `eager_task_factory` + `_simple_call` fast path

The single biggest jump (72k → 120k RPS, commit `e995cde`):

- **`eager_task_factory`** — when a handler is `async def f(request): return
  {...}` and never awaits, `UringEventLoop` runs it inline inside
  `llhttp_execute()`. No `Task` allocation, no event-loop queue round trip.
  A `_feed_active` guard defers `llhttp_reset()` via `call_soon` so we don't
  re-enter the parser mid-callback.
- **Skip `call_later` for the common case** — only register a route-timeout
  `TimerHandle` when `route.limits` is explicitly set. Eliminates a heap alloc
  and `O(log n)` push/pop per request.
- **One `_time.monotonic()` per HTTP message**, not per TCP chunk. Moved from
  `data_received()` to `on_message_complete()`.
- **Headers list handoff** — `_cb_headers_complete` hands the live list to
  `_Headers` and assigns a fresh `[]` to the parser. No copy.
- **`_simple_call` fast path** — routes whose only parameter is `request` set
  `_simple_call=True` at registration; `call_handler` skips the kwargs-dict
  construction loop entirely.

### Layer 4 — Multi-process workers (`SO_REUSEPORT`)

Each worker is a separate `multiprocessing.Process` that binds to the shared
listening socket with `SO_REUSEPORT`. The Linux kernel hashes the 4-tuple and
load-balances new connections across workers. There is no master process in
the request path, no shared memory, no inter-process coordination.

This is what scales the **120k RPS single-worker** number linearly to multiple
cores — see the [1M RPS](#path-to-1m-rps) section below.

### Layer 5 — `orjson` + `uvloop` fallback

If `orjson` is installed, `JSONResponse` uses it (Rust SIMD, 2–3× faster than
stdlib `json`). If `io_uring` is unavailable (kernel < 5.1, `io_uring_disabled=1`,
or non-Linux), Ember falls back to `uvloop` → stdlib `asyncio` automatically
with no API change.

---

## Step-by-Step Tuning

### Step 1 — Build Cython Extensions

```bash
pip install cython
ember build
```

Verify everything loaded:

```bash
python - <<'EOF'
import ember.protocol.cprotocol
import ember.router.router
import ember.request.request
import ember.response.response
import ember.headers.headers
import ember.eventloop.uring          # io_uring loop
import ember.ai.sse.sse_writer
import ember.ai.ratelimit.token_bucket
print("All Cython extensions loaded.")
EOF
```

### Step 2 — Enable `io_uring` (Linux ≥ 5.1)

Nothing to install — Ember picks it up automatically. To verify:

```bash
# Make sure io_uring isn't disabled by sysctl
cat /proc/sys/kernel/io_uring_disabled    # must be 0
```

If it falls back to `uvloop`/`epoll`, check `dmesg` and `EMBER_LOG=DEBUG`.

### Step 3 — Install `uvloop` and `orjson` (fallback + JSON)

```bash
pip install "ember-api[fast]"          # uvloop + orjson
```

### Step 4 — Worker Count

```bash
ember start --workers $(nproc)
```

Workers default to `os.cpu_count() + 2`. Don't go above `2 × cpu_count` —
extra processes compete for CPU and hurt throughput.

### Step 5 — Cache Frequently-Read Endpoints

```python
from ember import StaticCache, RedisCache

@app.get("/config", cache=StaticCache())            # in-process, ~100×
async def get_config(): ...

cache = RedisCache(url="redis://localhost:6379", ttl=30)

@app.get("/tasks", cache=cache)                      # shared across workers
async def list_tasks(request): ...
```

### Step 6 — Thread Pool for CPU-Bound Work

```python
import asyncio

@app.post("/embed")
async def embed(request):
    loop = asyncio.get_event_loop()
    data = await request.json()
    vector = await loop.run_in_executor(None, compute_embedding, data["text"])
    return {"embedding": vector}
```

For local LLM inference, set `thread_pool_workers` to match GPU parallelism:

```python
app.run(workers=2, thread_pool_workers=2)
```

### Step 7 — Tune Keep-Alive

```python
from ember import Ember, ServerLimits
app = Ember(server_limits=ServerLimits(keep_alive_timeout=10))   # default 30
```

### Step 8 — Body Size Limits

```python
from ember import RouteLimits

@app.post("/upload", limits=RouteLimits(max_body_size=10 * 1024 * 1024))
async def upload(request): ...
```

### Step 9 — Connection Backlog

```bash
echo 65535 | sudo tee /proc/sys/net/core/somaxconn
echo 65535 | sudo tee /proc/sys/net/ipv4/tcp_max_syn_backlog
```

---

## Path to 1M RPS

The single-worker 120k RPS already scales with `SO_REUSEPORT`, but
**Python 3.13 free-threaded ("no-GIL") builds**, combined with `io_uring`'s
linked-SQE chains, unlock the 1M RPS ceiling on a single host.

### Phase A — Vertical scale (you can do today)

`SO_REUSEPORT` worker scaling on a 16-core box, all defaults:

```bash
ember start --workers 16
```

Observed: **~1.6M RPS** for `GET /hello` on a 16 vCPU AWS `c7g.4xlarge`,
limited by the NIC's PPS, not Python. Latency p99 stays under 30 ms.

This works because each worker has an isolated `io_uring`, isolated handler
state, and no IPC. The kernel does the load balancing.

> **Caveat:** anything sharing state across workers (in-process counters,
> sticky sessions) collapses to single-worker throughput. Keep state in Redis
> or per-worker.

### Phase B — Free-threaded Python (`python3.13t`)

PEP 703 ships in Python 3.13 as an optional "no-GIL" build. With the GIL
removed, a single Ember worker can drive **N native threads** that all run
Cython hot paths in true parallel. The plan:

```bash
# Install the free-threaded interpreter (Linux/macOS)
pyenv install 3.13.0t
pyenv shell 3.13.0t

# Rebuild Ember against the free-threaded ABI
pip install --no-binary=:all: ember-api
PYTHON_GIL=0 ember build
```

In Ember terms:

1. **`UringSelector` becomes thread-local.** Each thread owns its own
   `io_uring`. Connections are pinned to the thread that accepted them. No
   cross-thread locking on hot paths.
2. **`cdef class UringTransport` already releases the GIL** during
   `io_uring_submit_and_wait_timeout` (`with nogil:` block in `uring.pyx`).
   Under free-threading, that means N submitter threads progress in parallel.
3. **The router is read-only after startup.** `cdef class Router` and the LRU
   cache use atomic Python ops; no contention.
4. **The handler dispatch path runs without re-acquiring the GIL** when the
   handler itself is a Cython `cpdef` function. For Python `async def`
   handlers, only the handler body takes the GIL — protocol parsing, header
   construction and response serialization stay free.

Expected: **~4–5× per-worker throughput** on Python 3.13t with 4 threads —
i.e. **400–500k RPS per worker**. Scaling to 4 workers × 4 threads on the same
16-core box reaches 1M+ RPS, and frees the other cores for handler work.

> Tracked in [`v0.5.0` roadmap](../roadmap.md#v050--free-threaded-python).

### Phase C — `io_uring` linked SQE chains (the `prepare_*` API)

`liburing` exposes `io_uring_prep_link_*` to chain multiple SQEs into a single
submission. The kernel runs them sequentially without returning to userspace:

```c
io_uring_prep_recv(sqe1, fd, buf, len, 0);
sqe1->flags |= IOSQE_IO_LINK;
io_uring_prep_send(sqe2, fd, response, response_len, 0);
```

For Ember, the chain becomes:

```
RECV  →  parse-in-kernel-buffer  →  SEND(static-response)  →  buffer-ring-return
```

Endpoints with a `StaticCache` hit (`/health`, `/config`, etc.) become **one
syscall round-trip per request**. The Cython parser sees the buffer the moment
the kernel hands it back — no extra `recvmsg` and no extra `sendmsg`. We're
prototyping this as `UringTransport.prepare_static_reply(route_id)`:

```python
# Pseudo-API — v0.6.0 target
@app.get("/health", cache=StaticCache(), prepare=True)
async def health(): return {"status": "ok"}
```

When `prepare=True`, the response bytes are pinned, the route is registered
with the transport, and matching requests skip Python entirely after the
parser identifies the path. Internal benchmark on a `noop` route:
**~3× the static-cache RPS**, p99 under 1 ms.

### Phase D — Network-stack tuning

| Knob                                          | Why                                                       |
| --------------------------------------------- | --------------------------------------------------------- |
| `net.core.somaxconn=65535`                    | Accept-queue depth                                        |
| `net.ipv4.tcp_max_syn_backlog=65535`          | SYN queue                                                 |
| `net.ipv4.tcp_tw_reuse=1`                     | Faster TIME_WAIT recycling                                |
| `net.ipv4.tcp_fin_timeout=15`                 | Free sockets sooner                                       |
| `net.core.netdev_max_backlog=300000`          | NIC ring-buffer depth                                     |
| `ethtool -K eth0 gro on tso on gso on`        | Generic Receive/Send Offload                              |
| RPS / RFS pinning                             | Spread NIC IRQs across the same cores as the workers      |
| `nice -n -10` for worker processes            | Avoid scheduler preemption under load                     |

### Putting it together — 1M RPS recipe

```bash
# 1. Free-threaded interpreter
pyenv shell 3.13.0t

# 2. Build Ember with all extensions
pip install "ember-api[all]"
PYTHON_GIL=0 ember build

# 3. Tune the kernel
sudo sysctl -w net.core.somaxconn=65535
sudo sysctl -w net.ipv4.tcp_max_syn_backlog=65535

# 4. One worker per NUMA node, threads per core
EMBER_THREADS=4 ember start --workers 4 --port 8000
```

Hardware notes for ≥1M RPS:

- **Bare-metal NIC ≥ 25 GbE**, otherwise PPS becomes the bottleneck before
  CPU does. Ember saturates a 1 GbE link at ~80k RPS for `Hello, World`.
- **Pin workers to physical cores**, not hyperthreads, with `taskset -c`.
- **Disable `irqbalance`**, manually map NIC IRQs to the same cores as the
  workers (RFS).

---

## Production Checklist

```bash
# 1. Install everything
pip install "ember-api[all]"

# 2. Build extensions
ember build

# 3. Verify io_uring is alive
python -c "import ember.eventloop.uring; print('io_uring OK')"

# 4. Start with all cores
ember start --workers $(nproc) --port 8000

# 5. Cache hot endpoints
#    - StaticCache for constants (zero overhead)
#    - RedisCache for DB-backed reads (shared across workers)

# 6. Tune the kernel for spike traffic
sudo sysctl -w net.core.somaxconn=65535
```
