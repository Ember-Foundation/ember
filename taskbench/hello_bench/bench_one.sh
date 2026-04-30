#!/bin/bash
# Usage: bench_one.sh <name> <port> <cmd...>
# Starts a hello-world server, waits for /hello, runs k6 (200 VUs / 20s),
# samples CPU/RAM every 1s for the parent + descendants, kills the server,
# prints a CSV row to stdout.
set -u
NAME="$1"; PORT="$2"; shift 2

DIR="$(cd "$(dirname "$0")" && pwd)"
RESULTS="$DIR/results"
mkdir -p "$RESULTS"

LOG="$RESULTS/${NAME}.log"
SAMPLES="$RESULTS/${NAME}-samples.txt"
K6_OUT="$RESULTS/${NAME}-k6.txt"

# Start server
"$@" > "$LOG" 2>&1 &
SERVER_PID=$!

# Wait for /hello
ok=0
for _ in $(seq 1 50); do
  if curl -s -o /dev/null -w "%{http_code}" "http://localhost:${PORT}/hello" 2>/dev/null | grep -q 200; then
    ok=1; break
  fi
  sleep 0.2
done
if [ "$ok" != "1" ]; then
  echo "${NAME}: failed to start (see $LOG)" >&2
  kill -9 $SERVER_PID 2>/dev/null
  exit 1
fi

# Helpers — sum CPU% / RSS for SERVER_PID and descendants
descendants_awk='
  { ppid_of[$1] = $2; val_of[$1] = $3 }
  END {
    inc[root] = 1; changed = 1
    while (changed) {
      changed = 0
      for (p in val_of) if (!(p in inc) && (ppid_of[p] in inc)) { inc[p] = 1; changed = 1 }
    }
    total = 0
    for (p in inc) total += val_of[p]
    print total
  }'
get_rss_kb() { ps -e -o pid,ppid,rss --no-headers 2>/dev/null | awk -v root=$SERVER_PID "$descendants_awk"; }
get_cpu_pct() { ps -e -o pid,ppid,pcpu --no-headers 2>/dev/null | awk -v root=$SERVER_PID "$descendants_awk"; }

# Idle baseline
sleep 2
IDLE_RSS_KB=$(get_rss_kb)

# Sampler
> "$SAMPLES"
( while true; do echo "$(get_cpu_pct) $(get_rss_kb)" >> "$SAMPLES"; sleep 1; done ) &
SAMPLER_PID=$!

# Run k6 — optionally pinned to specific cores via $K6_TASKSET
# (e.g. K6_TASKSET="taskset -c 4-27"). Empty by default → no pinning.
URL="http://localhost:${PORT}/hello" ${K6_TASKSET:-} k6 run --quiet \
  --summary-trend-stats="avg,min,med,p(50),p(90),p(95),p(99),max" \
  "$DIR/k6_hello.js" > "$K6_OUT" 2>&1
K6_RC=$?

# Stop sampler
kill -9 $SAMPLER_PID 2>/dev/null
wait $SAMPLER_PID 2>/dev/null

# Stop server tree
DESCS=$(ps -e -o pid,ppid --no-headers | awk -v root=$SERVER_PID '
  { p[$1]=$2 } END { inc[root]=1; ch=1
    while (ch) { ch=0; for (q in p) if (!(q in inc) && (p[q] in inc)) { inc[q]=1; ch=1 } }
    for (q in inc) print q
  }')
for p in $DESCS; do kill -9 $p 2>/dev/null; done
sleep 1

# Parse k6
RPS=$(awk '/http_reqs/{ for(i=1;i<=NF;i++) if($i ~ /\/s$/) { gsub("/s","",$i); print $i; exit }}' "$K6_OUT")
DUR=$(grep 'http_req_duration' "$K6_OUT" | head -1)
P50=$(echo "$DUR" | grep -oP 'med=\K[^ ]+')
P95=$(echo "$DUR" | grep -oP 'p\(95\)=\K[^ ]+')
P99=$(echo "$DUR" | grep -oP 'p\(99\)=\K[^ ]+')
AVG=$(echo "$DUR" | grep -oP 'avg=\K[^ ]+')
ERR_PCT=$(grep 'http_req_failed' "$K6_OUT" | grep -oP '\K[0-9.]+(?=%)' | head -1)

# Parse samples (skip first line as warmup)
read AVG_CPU PEAK_CPU AVG_RSS PEAK_RSS <<<"$(awk 'NR>1 { c+=$1; if($1>mc) mc=$1; r+=$2; if($2>mr) mr=$2; n++ }
  END { if (n==0) print "0 0 0 0"; else printf "%.1f %.1f %.1f %.1f\n", c/n, mc, (r/n)/1024, mr/1024 }' "$SAMPLES")"

IDLE_RSS_MB=$(awk "BEGIN { printf \"%.1f\", $IDLE_RSS_KB / 1024 }")

echo "RESULT,${NAME},${RPS:-NA},${AVG:-NA},${P50:-NA},${P95:-NA},${P99:-NA},${ERR_PCT:-NA}%,${AVG_CPU},${PEAK_CPU},${IDLE_RSS_MB},${AVG_RSS},${PEAK_RSS}"
exit $K6_RC
