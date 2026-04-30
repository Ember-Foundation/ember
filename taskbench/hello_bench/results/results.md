# Hello-World Benchmark — 5 Frameworks, Same Machine

## Setup

- **Hardware:** Intel i7-14700 (28 logical cores), 15 GB RAM
- **Load:** k6 — 200 VUs, 20 s, plaintext `GET /hello` returning `Hello, World!`
- **Workers:** 1 per framework (Fiber pinned to a single CPU via `GOMAXPROCS=1` for fairness)
- **Versions:** Ember v0.2 (this repo), FastAPI 0.135.3 + uvicorn 0.44.0, Express 4.x, NestJS 10.x, Fiber v2.52.13, Go 1.22.2, Node 22.14, Python 3.12 / 3.13
- **Date:** 2026-04-30

## Results

Ember row reports the median of 5 solo runs (range: 81.9k – 107.5k RPS). Other rows are from a single full-suite `bench_all.sh` pass on the same machine immediately after.

| Framework | RPS | avg (ms) | p50 (ms) | p95 (ms) | p99 (ms) | err | avg CPU | peak CPU | idle RSS | peak RSS |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **Fiber (Go)**     | **149,007** | 1.29  | 1.16  |  2.75 |  3.89 | 0.00% | 75.6% |  89.1% |  5.9 MB |   **9.0 MB** |
| **Ember (Python)** | **101,411** | 1.94  | 1.79  |  2.97 |  4.98 | 0.00% | 76.8% |  89.7% | 22.5 MB |  **25.2 MB** |
| Express (Node)     |   23,516    | 8.47  | 8.00  | 11.26 | 13.79 | 0.00% | 91.6% | 106.0% | 59.6 MB | 129.9 MB |
| NestJS (Node)      |   22,317    | 8.93  | 8.50  | 11.77 | 14.29 | 0.00% | 92.6% | 107.0% | 81.8 MB | 158.1 MB |
| FastAPI (Python)   |   16,879    | 11.79 | 10.20 | 20.42 | 27.63 | 0.00% | 76.7% |  89.7% | 47.0 MB |  48.1 MB |

CPU figures > 100% indicate the runtime spilled work to additional threads (Node libuv pool / V8 GC).

## What changed since v0.1.x

| Metric        | v0.1.x  | v0.2.1  | Δ        |
|---            |   ---:  | ---:    | ---:     |
| RPS (median)  | 91,156  | 101,411 | **+11%** |
| p99 latency   | 5.95 ms | 4.98 ms | **−16%** |
| Idle RSS      | 42.5 MB | 22.5 MB | **−47%** |
| Peak RSS      | 48.1 MB | 25.2 MB | **−48%** |

Four changes:

1. **`workers=1` runs in-process** on Linux — no supervisor process, ~22 MB saved.
2. **io_uring buffer pool is runtime-tunable.** Default reduced from 1024 × 32 KB (32 MB) to 256 × 8 KB (2 MB). Set via `Ember.run(io_uring_num_bufs=, io_uring_buf_size=)`.
3. **`import ember` lazy-loads** the AI / cache / middleware namespaces — plain HTTP apps no longer import numpy / redis / memcached at startup.
4. **Trivial-handler fast path** (v0.2.1): when an `async def` handler has no `await` opcode in its bytecode (and the route has no per-route cache, no limits, no app-level before/after-endpoint hooks), the protocol drives the coroutine directly with `coro.send(None)` instead of wrapping in a Task. Saves 1 Task object + 1 coroutine wrapper + 1 await dispatch per request.

Plus `gc.freeze()` after worker init, a smaller default `ServerLimits.write_buffer` (419 KB → 64 KB), and stripped Cython `.so` files (-80% on disk).

## Throughput vs Fiber

| Framework | RPS  | % of Fiber |
|---|---:|---:|
| Fiber   | 149,007 | 100.0% |
| Ember   | 101,411 |  68.1% |
| Express |  23,516 |  15.8% |
| NestJS  |  22,317 |  15.0% |
| FastAPI |  16,879 |  11.3% |

(Run-to-run variance is ±10–15% on this 28-core box because k6 competes for the same cores. Use `bench_pinned.sh` for tighter numbers — see `Reproducing >100k RPS` in `docs/guide/performance.md`.)

## Key takeaways

- **Throughput:** Ember now **breaks 100k RPS single-thread** with the v0.2.1 trivial-handler fast path. Median 101k, peak 105.7k unpinned, p99 4.98 ms. Runs ~6.0× FastAPI, ~4.3× Express, ~4.5× NestJS. Fiber stays ahead at 149k but the gap is now ~32% rather than the 75-cent original.
- **Memory:** Ember is the lightest Python or Node framework in this benchmark at 25.2 MB peak RSS — half FastAPI's 48 MB, ~5× lighter than Express, ~6× lighter than NestJS. Only Fiber's static Go binary (no interpreter) sits lower at 9 MB.
- **NestJS pays an overhead vs raw Express** — comparable RPS, ~28 MB more RSS.
- **CPU saturation pattern:** Fiber, Ember, FastAPI all sit ~90% peak on one core (single-threaded loop = CPU-bound). Node hits >100% because libuv / V8 GC use extra threads.

## Reproducing

```bash
cd taskbench/hello_bench
./bench_all.sh
```

Per-framework raw output is saved alongside this file as `<framework>-k6.txt` and `<framework>-samples.txt`.
