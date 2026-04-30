# Hello-World Benchmark — 5 Frameworks, Same Machine

## Setup

- **Hardware:** Intel i7-14700 (28 logical cores), 15 GB RAM
- **Load:** k6 — 200 VUs, 20 s, plaintext `GET /hello` returning `Hello, World!`
- **Workers:** 1 per framework (Fiber pinned to a single CPU via `GOMAXPROCS=1` for fairness)
- **Versions:** Ember v0.2 (this repo), FastAPI 0.135.3 + uvicorn 0.44.0, Express 4.x, NestJS 10.x, Fiber v2.52.13, Go 1.22.2, Node 22.14, Python 3.12 / 3.13
- **Date:** 2026-04-30

## Results

All five frameworks benched back-to-back via `./bench_all.sh` (single-worker, fresh process each, 0% errors). Ember runs with the v0.2.1 trivial-handler fast path enabled.

| Framework | RPS | avg (ms) | p50 (ms) | p95 (ms) | p99 (ms) | err | avg CPU | peak CPU | idle RSS | peak RSS |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **Fiber (Go)**     | **140,993** | 1.36  | 1.21  |  2.91 |  3.96 | 0.00% | 75.9% |  89.3% |  5.9 MB |   **8.8 MB** |
| **Ember (Python)** | **112,177** | 1.75  | 1.68  |  2.59 |  4.35 | 0.00% | 77.0% |  89.7% | 22.8 MB |  **25.2 MB** |
| Express (Node)     |    26,357   | 7.56  | 7.09  |  9.98 | 13.57 | 0.00% | 89.8% | 104.0% | 59.8 MB | 131.0 MB |
| NestJS (Node)      |    23,528   | 8.47  | 8.08  | 10.97 | 13.75 | 0.00% | 91.4% | 105.0% | 81.4 MB | 158.6 MB |
| FastAPI (Python)   |    17,517   | 11.36 | 9.45  | 20.67 | 30.86 | 0.00% | 76.3% |  89.4% | 47.6 MB |  49.1 MB |

CPU figures > 100% indicate the runtime spilled work to additional threads (Node libuv pool / V8 GC).

## What changed since v0.1.x

| Metric        | v0.1.x  | v0.2.1  | Δ        |
|---            |   ---:  | ---:    | ---:     |
| RPS           | 91,156  | 112,177 | **+23%** |
| p99 latency   | 5.95 ms | 4.35 ms | **−27%** |
| Idle RSS      | 42.5 MB | 22.8 MB | **−46%** |
| Peak RSS      | 48.1 MB | 25.2 MB | **−48%** |

Four changes:

1. **`workers=1` runs in-process** on Linux — no supervisor process, ~22 MB saved.
2. **io_uring buffer pool is runtime-tunable.** Default reduced from 1024 × 32 KB (32 MB) to 256 × 8 KB (2 MB). Set via `Ember.run(io_uring_num_bufs=, io_uring_buf_size=)`.
3. **`import ember` lazy-loads** the AI / cache / middleware namespaces — plain HTTP apps no longer import numpy / redis / memcached at startup.
4. **Trivial-handler fast path** (v0.2.1): when an `async def` handler has no `await` opcode in its bytecode (and the route has no per-route cache, no limits, no app-level before/after-endpoint hooks), the protocol drives the coroutine directly with `coro.send(None)` instead of wrapping in a Task. Saves 1 Task object + 1 coroutine wrapper + 1 await dispatch per request.

Plus `gc.freeze()` after worker init, a smaller default `ServerLimits.write_buffer` (419 KB → 64 KB), and stripped Cython `.so` files (-80% on disk).

## Throughput vs Fiber

| Framework | RPS     | % of Fiber |
|---|---:|---:|
| Fiber   | 140,993 | 100.0% |
| Ember   | 112,177 |  79.6% |
| Express |  26,357 |  18.7% |
| NestJS  |  23,528 |  16.7% |
| FastAPI |  17,517 |  12.4% |

(Run-to-run variance is ±10–15% on this 28-core box because k6 competes for the same cores. Use `bench_pinned.sh` for tighter numbers — see `Reproducing >100k RPS` in `docs/guide/performance.md`.)

## Key takeaways

- **Throughput:** Ember hits **112,177 RPS single-thread**, **80% of Go Fiber's** raw RPS — the closest a Python framework has come on a single core. Runs ~6.4× FastAPI, ~4.3× Express, ~4.8× NestJS.
- **Memory:** Ember is the lightest Python or Node framework in this benchmark at 25.2 MB peak RSS — half FastAPI's 49 MB, ~5× lighter than Express, ~6× lighter than NestJS. Only Fiber's static Go binary (no interpreter) sits lower at 8.8 MB.
- **CRUD parity with Node:** On real CRUD workloads against PostgreSQL (see `compare_all.js`), Ember averages 19.85 ms vs Express's 19.20 ms — within 3% — and has a **13× tighter tail than FastAPI** (59 ms vs 794 ms p99).
- **NestJS pays an overhead vs raw Express** — comparable RPS, ~28 MB more RSS.
- **CPU saturation pattern:** Fiber, Ember, FastAPI all sit ~90% peak on one core (single-threaded loop = CPU-bound). Node hits >100% because libuv / V8 GC use extra threads.

## Reproducing

```bash
cd taskbench/hello_bench
./bench_all.sh
```

Per-framework raw output is saved alongside this file as `<framework>-k6.txt` and `<framework>-samples.txt`.
