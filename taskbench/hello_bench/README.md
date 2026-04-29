# Hello-World Cross-Framework Benchmark

Compares Ember against Fiber (Go), Express, NestJS, and FastAPI on the same
machine, under identical k6 load.

## Layout

```
hello_bench/
  apps/
    ember/server.py        # Ember
    fastapi/server.py      # FastAPI + uvicorn
    express/server.js      # Express (reuses ../express_app/node_modules)
    nestjs/main.js         # NestJS
    fiber/main.go          # Go Fiber
  k6_hello.js              # k6 scenario (200 VUs, 20s, GET /hello)
  bench_one.sh             # Run one framework + sample CPU/RSS during the run
  bench_all.sh             # Build deps + run all five back-to-back
  results/
    results.csv            # Machine-readable
    results.md             # Human-readable summary
    <name>-k6.txt          # Raw k6 output per framework
    <name>-samples.txt     # CPU% / RSS samples per framework
```

## Run

```bash
./bench_all.sh
```

This will:
1. `go build` the Fiber binary if missing.
2. `npm install` NestJS deps if missing.
3. Verify Express deps exist in `../express_app/node_modules`.
4. Bench all 5 frameworks back-to-back, single worker each.
5. Write `results/results.csv` and print a summary table.

To bench just one framework:

```bash
./bench_one.sh ember 9010 env EMBER_WORKERS=1 python3 apps/ember/server.py
```

## Knobs

- `VUS=400 DURATION=30s ./bench_all.sh` — adjust k6 load (passed via env).
- For multi-worker runs, set `EMBER_WORKERS=4`, `WORKERS=4` (Express/NestJS),
  `GOMAXPROCS=4` (Fiber), or `--workers 4` (uvicorn).

## Fairness notes

- All servers run **single worker** by default. Fiber is pinned to one CPU
  via `GOMAXPROCS=1` so it doesn't get a free 28-core advantage.
- All return `text/plain` body `Hello, World!` (13 bytes).
- k6 runs against `localhost`, so the network is not the bottleneck — this
  measures framework + runtime overhead.
- CPU/RSS sampling sums the parent process and all descendants (covers
  Ember workers, Node cluster children, uvicorn workers, Go threads).
