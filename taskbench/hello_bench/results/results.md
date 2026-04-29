# Hello-World Benchmark — 5 Frameworks, Same Machine

## Setup

- **Hardware:** Intel i7-14700 (28 logical cores), 15 GB RAM
- **Load:** k6 — 200 VUs, 20 s, plaintext `GET /hello` returning `Hello, World!`
- **Workers:** 1 per framework (Fiber pinned to a single CPU via `GOMAXPROCS=1` for fairness)
- **Versions:** Ember (this repo), FastAPI 0.135.3 + uvicorn 0.44.0, Express 4.x, NestJS 10.x, Fiber v2.52.13, Go 1.22.2, Node 22.14, Python 3.13
- **Date:** 2026-04-29

## Results

| Framework | RPS | avg (ms) | p50 (ms) | p95 (ms) | p99 (ms) | err | avg CPU | peak CPU | idle RSS | peak RSS |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **Fiber (Go)**     | **120,912** | 1.59  | 1.43  | 3.35  | 4.54  | 0.00% | 77.5% |  90.2% |  6.3 MB |   9.4 MB |
| **Ember (Python)** |  **91,156** | 2.16  | 1.99  | 3.77  | 5.95  | 0.00% | 76.7% |  89.6% | 42.5 MB |  48.1 MB |
| Express (Node)     |   22,695    | 8.77  | 8.08  | 12.26 | 17.32 | 0.00% | 92.0% | 106.0% | 59.7 MB | 130.2 MB |
| NestJS (Node)      |   20,091    | 9.91  | 9.39  | 13.48 | 17.51 | 0.00% | 94.8% | 109.0% | 81.6 MB | 156.5 MB |
| FastAPI (Python)   |   15,697    | 12.67 | 11.24 | 20.58 | 26.17 | 0.00% | 76.4% |  89.5% | 46.8 MB |  48.7 MB |

CPU figures > 100% indicate the runtime spilled work to additional threads (Node libuv pool / V8 GC).

## Throughput vs Fiber

| Framework | RPS  | % of Fiber |
|---|---:|---:|
| Fiber   | 120,912 | 100.0% |
| Ember   |  91,156 |  75.4% |
| Express |  22,695 |  18.8% |
| NestJS  |  20,091 |  16.6% |
| FastAPI |  15,697 |  13.0% |

## Key takeaways

- **Fiber wins on raw throughput**, as expected for a Go fasthttp framework — but only by ~33% over Ember single-worker on this hardware.
- **Ember is the only Python framework in the same league as Go.** It does ~5.8× FastAPI's RPS and ~4× Express's RPS.
- **NestJS pays an overhead vs raw Express** (~11% slower, ~25 MB more RSS).
- **Memory:** Fiber is in a different class (~9 MB RSS) — Go binaries vs interpreted runtimes. Ember and FastAPI are the Python baseline (~48 MB). Node cluster heap is the heaviest (130–157 MB).
- **CPU saturation pattern:** Fiber, Ember, FastAPI all sit ~90% peak on one core (single-threaded loop = CPU-bound). Node hits >100% because libuv / V8 GC use extra threads.

## Reproducing

```bash
cd taskbench/hello_bench
./bench_all.sh
```

Per-framework raw output is saved alongside this file as `<framework>-k6.txt` and `<framework>-samples.txt`.
