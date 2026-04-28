#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════════
# Benchmark runner: starts all three servers, runs k6, prints comparison table
# Usage: ./run_benchmarks.sh [--quick] [--only fastapi|ember|express]
# ═══════════════════════════════════════════════════════════════════════════════
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RESULTS_DIR="$SCRIPT_DIR/results"
mkdir -p "$RESULTS_DIR"

QUICK=0
ONLY=""
for arg in "$@"; do
  [[ "$arg" == "--quick"  ]] && QUICK=1
  [[ "$arg" == "--only"   ]] && ONLY="${2:-}"
done

# ── Dependency checks ──────────────────────────────────────────────────────────
check_cmd() { command -v "$1" &>/dev/null || { echo "ERROR: '$1' not found. Install it first."; exit 1; }; }
check_cmd k6
check_cmd python3
check_cmd node

echo ""
echo "  Checking Python deps..."
pip install -q fastapi uvicorn uvloop httptools 2>/dev/null || true

echo "  Checking Node deps..."
cd "$SCRIPT_DIR/express_app"
npm install --silent 2>/dev/null || npm install
cd "$SCRIPT_DIR"

# ── Start servers ──────────────────────────────────────────────────────────────
PIDS=()

cleanup() {
  echo ""
  echo "  Stopping servers..."
  for pid in "${PIDS[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
  echo "  Done."
}
trap cleanup EXIT INT TERM

start_server() {
  local name="$1"; local cmd="$2"; local port="$3"
  [[ -n "$ONLY" && "$ONLY" != "$name" ]] && return

  echo "  Starting $name on port $port..."
  eval "$cmd" &
  PIDS+=($!)

  # Wait for server to be ready
  for i in $(seq 1 30); do
    if curl -sf "http://localhost:$port/health" &>/dev/null; then
      echo "  ✓ $name ready (${i}s)"
      return
    fi
    sleep 1
  done
  echo "  ✗ $name failed to start on port $port"
  exit 1
}

start_server fastapi \
  "python3 $SCRIPT_DIR/fastapi_app/main.py" \
  8001

start_server ember \
  "python3 $SCRIPT_DIR/ember_app/main.py" \
  8002

start_server express \
  "node $SCRIPT_DIR/express_app/server.js" \
  8003

echo ""
echo "  All servers running. Starting benchmarks..."
echo ""

STAMP=$(date +%Y%m%d_%H%M%S)

# ── Individual benchmarks ──────────────────────────────────────────────────────
run_k6() {
  local name="$1"; local script="$2"; local port="$3"
  [[ -n "$ONLY" && "$ONLY" != "$name" ]] && return

  echo "══════════════════════════════════════════════════════════"
  echo "  Benchmarking: $name (port $port)"
  echo "══════════════════════════════════════════════════════════"

  k6 run \
    --out "json=$RESULTS_DIR/${name}_${STAMP}.json" \
    --summary-export "$RESULTS_DIR/${name}_summary_${STAMP}.json" \
    "$script" \
    2>&1 | tee "$RESULTS_DIR/${name}_output_${STAMP}.txt"

  echo ""
}

if [[ -z "$ONLY" || "$ONLY" == "fastapi" ]]; then
  run_k6 fastapi "$SCRIPT_DIR/k6/bench_fastapi.js" 8001
fi

if [[ -z "$ONLY" || "$ONLY" == "ember" ]]; then
  run_k6 ember "$SCRIPT_DIR/k6/bench_ember.js" 8002
fi

if [[ -z "$ONLY" || "$ONLY" == "express" ]]; then
  run_k6 express "$SCRIPT_DIR/k6/bench_express.js" 8003
fi

# ── Side-by-side comparison ────────────────────────────────────────────────────
if [[ -z "$ONLY" ]]; then
  echo "══════════════════════════════════════════════════════════"
  echo "  Side-by-side comparison (all three simultaneously)"
  echo "══════════════════════════════════════════════════════════"

  k6 run \
    --out "json=$RESULTS_DIR/compare_${STAMP}.json" \
    "$SCRIPT_DIR/k6/compare_all.js" \
    2>&1 | tee "$RESULTS_DIR/compare_output_${STAMP}.txt"
fi

echo ""
echo "  Results saved to: $RESULTS_DIR/"
echo ""
