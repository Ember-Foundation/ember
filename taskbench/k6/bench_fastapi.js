/**
 * k6 benchmark — FastAPI (port 8001)
 *
 * Scenarios:
 *   1. list_paginated  — GET /tasks?page=N  (hot read path)
 *   2. get_single      — GET /tasks/:id     (single-item lookup)
 *   3. list_all        — GET /tasks/all     (full 1000-task payload)
 *   4. create_task     — POST /tasks        (write throughput)
 *   5. mixed_workload  — 70% list, 20% get, 10% create
 *   6. stress_ramp     — ramp 1→200 VUs, find breaking point
 */
import http    from 'k6/http';
import { check, sleep } from 'k6';
import { Counter, Rate, Trend } from 'k6/metrics';
import { randomIntBetween } from 'https://jslib.k6.io/k6-utils/1.4.0/index.js';

const BASE = 'http://localhost:8001';

// Custom metrics
const errorRate     = new Rate('error_rate');
const listDuration  = new Trend('list_duration',   true);
const getDuration   = new Trend('get_duration',    true);
const createDuration= new Trend('create_duration', true);
const allDuration   = new Trend('all_duration',    true);

// Pre-seed task IDs — fetched once during setup
let taskIds = [];

export function setup() {
  const res = http.get(`${BASE}/tasks/all`);
  if (res.status === 200) {
    const body = JSON.parse(res.body);
    taskIds = body.tasks.map(t => t.id);
    console.log(`FastAPI: loaded ${taskIds.length} task IDs`);
  }
  return { taskIds };
}

export const options = {
  scenarios: {
    // ── 1. Paginated list ────────────────────────────────────────────────────
    list_paginated: {
      executor: 'constant-vus',
      vus: 50,
      duration: '30s',
      tags: { scenario: 'list_paginated' },
    },
    // ── 2. Single-item GET ───────────────────────────────────────────────────
    get_single: {
      executor: 'constant-vus',
      vus: 50,
      duration: '30s',
      startTime: '35s',
      tags: { scenario: 'get_single' },
    },
    // ── 3. Full list (1000 tasks) ────────────────────────────────────────────
    list_all: {
      executor: 'constant-vus',
      vus: 20,
      duration: '30s',
      startTime: '70s',
      tags: { scenario: 'list_all' },
    },
    // ── 4. Write throughput ──────────────────────────────────────────────────
    create_task: {
      executor: 'constant-vus',
      vus: 30,
      duration: '30s',
      startTime: '105s',
      tags: { scenario: 'create_task' },
    },
    // ── 5. Mixed workload ────────────────────────────────────────────────────
    mixed_workload: {
      executor: 'constant-vus',
      vus: 100,
      duration: '60s',
      startTime: '140s',
      tags: { scenario: 'mixed' },
    },
    // ── 6. Stress ramp ───────────────────────────────────────────────────────
    stress_ramp: {
      executor: 'ramping-vus',
      startVUs: 1,
      stages: [
        { duration: '20s', target: 50  },
        { duration: '20s', target: 100 },
        { duration: '20s', target: 200 },
        { duration: '10s', target: 0   },
      ],
      startTime: '205s',
      tags: { scenario: 'stress' },
    },
  },
  thresholds: {
    http_req_duration:    ['p(95)<500', 'p(99)<1000'],
    http_req_failed:      ['rate<0.01'],
    error_rate:           ['rate<0.01'],
    list_duration:        ['p(95)<200'],
    get_duration:         ['p(95)<50'],
    create_duration:      ['p(95)<200'],
  },
};

// ── Scenario handlers ──────────────────────────────────────────────────────────

export function list_paginated(data) {
  const page = randomIntBetween(1, 50);
  const t    = Date.now();
  const res  = http.get(`${BASE}/tasks?page=${page}&limit=20`);
  listDuration.add(Date.now() - t);
  const ok = check(res, {
    'list status 200': r => r.status === 200,
    'list has tasks':  r => JSON.parse(r.body).tasks.length > 0,
  });
  errorRate.add(!ok);
}

export function get_single(data) {
  const ids = data.taskIds;
  if (!ids.length) return;
  const id = ids[randomIntBetween(0, ids.length - 1)];
  const t  = Date.now();
  const res = http.get(`${BASE}/tasks/${id}`);
  getDuration.add(Date.now() - t);
  const ok = check(res, {
    'get status 200': r => r.status === 200,
    'get has id':     r => JSON.parse(r.body).id === id,
  });
  errorRate.add(!ok);
}

export function list_all(data) {
  const t   = Date.now();
  const res = http.get(`${BASE}/tasks/all`);
  allDuration.add(Date.now() - t);
  const ok = check(res, {
    'all status 200':  r => r.status === 200,
    'all has 1000+':   r => JSON.parse(r.body).total >= 1000,
  });
  errorRate.add(!ok);
}

export function create_task(data) {
  const payload = JSON.stringify({
    title:       `Bench task ${Date.now()}`,
    description: 'Created by k6 benchmark',
    priority:    ['low','medium','high'][randomIntBetween(0, 2)],
  });
  const t   = Date.now();
  const res = http.post(`${BASE}/tasks`, payload, {
    headers: { 'Content-Type': 'application/json' },
  });
  createDuration.add(Date.now() - t);
  const ok = check(res, {
    'create status 201': r => r.status === 201,
    'create has id':     r => JSON.parse(r.body).id !== undefined,
  });
  errorRate.add(!ok);
}

export function mixed_workload(data) {
  const roll = Math.random();
  if (roll < 0.70) {
    list_paginated(data);
  } else if (roll < 0.90) {
    get_single(data);
  } else {
    create_task(data);
  }
  sleep(0.01);
}

export function stress_ramp(data) {
  mixed_workload(data);
}

// Default export used when no --env SCENARIO is set
export default function(data) {
  mixed_workload(data);
}
