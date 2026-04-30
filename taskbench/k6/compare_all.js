/**
 * Side-by-side comparison benchmark — hits all three servers simultaneously.
 *
 * Run: k6 run k6/compare_all.js --out json=results/compare_all.json
 *
 * Metrics are tagged by `server` so you can filter in the summary:
 *   fastapi | ember | express
 */
import http from 'k6/http';
import { check, sleep, group } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';
import { randomIntBetween } from 'https://jslib.k6.io/k6-utils/1.4.0/index.js';

const SERVERS = {
  fastapi: 'http://localhost:9001',
  ember:   'http://localhost:9002',
  express: 'http://localhost:9003',
};

// Per-server metrics
const reqs    = {};
const latency = {};
const errors  = {};

for (const name of Object.keys(SERVERS)) {
  reqs[name]    = new Counter(`${name}_requests`);
  latency[name] = new Trend(`${name}_latency_ms`, true);
  errors[name]  = new Rate(`${name}_error_rate`);
}

// Shared task IDs cache per server
const cache = { fastapi: [], ember: [], express: [] };

export function setup() {
  const result = {};
  for (const [name, base] of Object.entries(SERVERS)) {
    const res = http.get(`${base}/tasks?page=1&limit=500`);
    if (res.status === 200) {
      result[name] = JSON.parse(res.body).tasks.map(t => t.id);
      console.log(`${name}: ${result[name].length} tasks`);
    } else {
      console.error(`${name}: failed to load tasks (${res.status})`);
      result[name] = [];
    }
  }
  return result;
}

export const options = {
  setupTimeout: '120s',
  summaryTrendStats: ['avg', 'min', 'med', 'max', 'p(50)', 'p(90)', 'p(95)', 'p(99)'],
  scenarios: {
    // ── Phase 1: Warm up all three at low concurrency ─────────────────────
    warmup: {
      executor: 'constant-vus',
      vus: 10,
      duration: '15s',
      tags: { phase: 'warmup' },
    },
    // ── Phase 2: Medium load — 50 VUs per server ──────────────────────────
    medium_load: {
      executor: 'constant-vus',
      vus: 50,
      duration: '30s',
      startTime: '20s',
      tags: { phase: 'medium' },
    },
    // ── Phase 3: Heavy load — 150 VUs ────────────────────────────────────
    heavy_load: {
      executor: 'constant-vus',
      vus: 150,
      duration: '30s',
      startTime: '55s',
      tags: { phase: 'heavy' },
    },
    // ── Phase 4: Spike — ramp to 300 VUs ─────────────────────────────────
    spike: {
      executor: 'ramping-vus',
      startVUs: 10,
      stages: [
        { duration: '10s', target: 300 },
        { duration: '20s', target: 300 },
        { duration: '10s', target: 0   },
      ],
      startTime: '90s',
      tags: { phase: 'spike' },
    },
  },
  thresholds: {
    fastapi_error_rate: ['rate<0.02'],
    ember_error_rate:   ['rate<0.02'],
    express_error_rate: ['rate<0.02'],
    fastapi_latency_ms: ['p(95)<500'],
    ember_latency_ms:   ['p(95)<500'],
    express_latency_ms: ['p(95)<500'],
  },
};

function runScenario(name, base, ids) {
  const roll = Math.random();

  if (roll < 0.65) {
    // List paginated (most common read)
    const page = randomIntBetween(1, 50);
    const t    = Date.now();
    const res  = http.get(`${base}/tasks?page=${page}&limit=20`, {
      tags: { server: name, op: 'list' },
    });
    latency[name].add(Date.now() - t);
    reqs[name].add(1);
    const ok = check(res, { [`${name} list 200`]: r => r.status === 200 });
    errors[name].add(!ok);

  } else if (roll < 0.90) {
    // Single item GET
    if (!ids.length) return;
    const id  = ids[randomIntBetween(0, ids.length - 1)];
    const t   = Date.now();
    const res = http.get(`${base}/tasks/${id}`, {
      tags: { server: name, op: 'get' },
    });
    latency[name].add(Date.now() - t);
    reqs[name].add(1);
    const ok = check(res, { [`${name} get 200`]: r => r.status === 200 });
    errors[name].add(!ok);

  } else {
    // Create (write)
    const t   = Date.now();
    const res = http.post(`${base}/tasks`,
      JSON.stringify({ title: `k6 task ${Date.now()}`, priority: 'low' }),
      { headers: { 'Content-Type': 'application/json' }, tags: { server: name, op: 'create' } },
    );
    latency[name].add(Date.now() - t);
    reqs[name].add(1);
    const ok = check(res, { [`${name} create 201`]: r => r.status === 201 });
    errors[name].add(!ok);
  }
}

export default function(data) {
  // Hit all three servers in each VU iteration for a true side-by-side comparison
  for (const [name, base] of Object.entries(SERVERS)) {
    runScenario(name, base, data[name] || []);
  }
  sleep(0.005);
}

export function warmup(data)     { return exports.default(data); }
export function medium_load(data){ return exports.default(data); }
export function heavy_load(data) { return exports.default(data); }
export function spike(data)      { return exports.default(data); }

export function handleSummary(data) {
  const fmt = (v) => v !== undefined ? v.toFixed(2) : 'N/A';

  const table = ['', '═══════════════════════════════════════════════════════════════════',
    '  EMBER vs FastAPI vs Express — k6 Benchmark Summary',
    '═══════════════════════════════════════════════════════════════════',
    `  ${'Metric'.padEnd(28)} ${'FastAPI'.padEnd(14)} ${'Ember'.padEnd(14)} ${'Express'.padEnd(14)}`,
    '  ' + '─'.repeat(65),
  ];

  const metrics = [
    ['Requests total',      'fastapi_requests',    'ember_requests',    'express_requests',    'count'],
    ['Latency p50 (ms)',    'fastapi_latency_ms',  'ember_latency_ms',  'express_latency_ms',  'p(50)'],
    ['Latency p95 (ms)',    'fastapi_latency_ms',  'ember_latency_ms',  'express_latency_ms',  'p(95)'],
    ['Latency p99 (ms)',    'fastapi_latency_ms',  'ember_latency_ms',  'express_latency_ms',  'p(99)'],
    ['Latency avg (ms)',    'fastapi_latency_ms',  'ember_latency_ms',  'express_latency_ms',  'avg'],
    ['Error rate',          'fastapi_error_rate',  'ember_error_rate',  'express_error_rate',  'rate'],
  ];

  for (const [label, fa, em, ex, stat] of metrics) {
    const get = (key) => {
      const m = data.metrics[key];
      if (!m) return 'N/A';
      const v = stat === 'count' ? m.values['count']
              : stat === 'rate'  ? (m.values['rate'] * 100).toFixed(3) + '%'
              : m.values[stat];
      return typeof v === 'number' ? fmt(v) : String(v);
    };
    table.push(`  ${label.padEnd(28)} ${get(fa).padEnd(14)} ${get(em).padEnd(14)} ${get(ex).padEnd(14)}`);
  }

  table.push('═══════════════════════════════════════════════════════════════════', '');

  return {
    stdout: table.join('\n'),
    'results/compare_all_summary.txt': table.join('\n'),
  };
}
