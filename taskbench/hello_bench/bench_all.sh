#!/bin/bash
# Build/install dependencies, then bench all 5 frameworks back-to-back.
set -eu
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

# 1. Fiber: build binary if missing
if [ ! -x apps/fiber/fiberbench ]; then
  echo ">> building fiber..."
  (cd apps/fiber && go mod tidy && go build -o fiberbench .)
fi

# 2. NestJS: install deps if missing
if [ ! -d apps/nestjs/node_modules ]; then
  echo ">> installing nestjs deps..."
  (cd apps/nestjs && npm install --silent --no-audit --no-fund)
fi

# 3. Express: reuse existing taskbench/express_app/node_modules. Verify present.
if [ ! -d "$DIR/../express_app/node_modules/express" ]; then
  echo ">> express node_modules missing — installing in taskbench/express_app/"
  (cd "$DIR/../express_app" && npm install --silent --no-audit --no-fund)
fi

# Make sure all bench ports are free
for port in 9010 9011 9012 9013 9014; do
  if ss -ltn 2>/dev/null | grep -q ":${port} "; then
    echo "port ${port} already in use — aborting" >&2
    exit 1
  fi
done

CSV="$DIR/results/results.csv"
echo "framework,rps,avg_ms,p50,p95,p99,err_pct,avg_cpu_pct,peak_cpu_pct,idle_rss_mb,avg_rss_mb,peak_rss_mb" > "$CSV"

run() {
  local name="$1"; local port="$2"; shift 2
  echo ">> bench ${name}..."
  out=$("$DIR/bench_one.sh" "$name" "$port" "$@")
  echo "$out"
  echo "${out#RESULT,}" >> "$CSV"
  sleep 2
}

run ember   9010 env EMBER_WORKERS=1 python3 "$DIR/apps/ember/server.py"
run fastapi 9012 python3 -m uvicorn --app-dir "$DIR/apps/fastapi" server:app --host 0.0.0.0 --port 9012 --workers 1 --log-level warning
run express 9011 env PORT=9011 WORKERS=1 node "$DIR/apps/express/server.js"
run nestjs  9014 env PORT=9014 WORKERS=1 node "$DIR/apps/nestjs/main.js"
run fiber   9013 env PORT=9013 GOMAXPROCS=1 "$DIR/apps/fiber/fiberbench"

echo
echo "==== summary ===="
column -s, -t < "$CSV"
echo
echo "csv: $CSV"
