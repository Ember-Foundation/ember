#!/bin/bash
# Usage: bench_pinned.sh <name> <port> <cmd...>
# Same as bench_one.sh but pins server and k6 to disjoint core sets.
# Eliminates the k6-vs-server contention that causes large RPS variance
# on multi-core dev boxes.
#
# Override pinning:
#   SERVER_CORES=14 K6_CORES=0-13,15-27 ./bench_pinned.sh ember 9010 ...
#
# Defaults: server → P-cores 0-3 (4 logical cores, lets the scheduler pick
# the freshest one and lets the CPU turbo-boost); k6 → cores 4-27.
# Pinning the server to a single core kills turbo on that core and capped
# our throughput; giving it a small pool keeps turbo headroom while still
# isolating it from the load generator.
set -u
NAME="$1"; PORT="$2"; shift 2

DIR="$(cd "$(dirname "$0")" && pwd)"

SERVER_CORES="${SERVER_CORES:-0-3}"
K6_CORES="${K6_CORES:-4-27}"

if ! command -v taskset >/dev/null 2>&1; then
  echo "bench_pinned.sh: taskset not found — install util-linux or use bench_one.sh" >&2
  exit 1
fi

echo ">> bench_pinned: server=core(s) ${SERVER_CORES}, k6=core(s) ${K6_CORES}"

# bench_one.sh reads $K6_TASKSET to wrap k6; we wrap the server here directly.
exec env K6_TASKSET="taskset -c ${K6_CORES}" \
  "$DIR/bench_one.sh" "$NAME" "$PORT" \
  taskset -c "${SERVER_CORES}" "$@"
