/**
 * k6 benchmark — Ember (port 8002)
 * Identical scenarios to bench_fastapi.js — only BASE URL differs.
 */
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';
import { randomIntBetween } from 'https://jslib.k6.io/k6-utils/1.4.0/index.js';

const BASE = 'http://localhost:9002';

const errorRate      = new Rate('error_rate');
const listDuration   = new Trend('list_duration',   true);
const getDuration    = new Trend('get_duration',    true);
const createDuration = new Trend('create_duration', true);
const allDuration    = new Trend('all_duration',    true);

let taskIds = [];

export function setup() {
  const res = http.get(`${BASE}/tasks/all`);
  if (res.status === 200) {
    taskIds = JSON.parse(res.body).tasks.map(t => t.id);
    console.log(`Ember: loaded ${taskIds.length} task IDs`);
  }
  return { taskIds };
}

export const options = {
  summaryTrendStats: ['avg', 'min', 'p(50)', 'p(90)', 'p(95)', 'p(99)', 'max'],
  scenarios: {
    warmup: {
      executor: 'constant-vus', vus: 20, duration: '15s',
      tags: { scenario: 'warmup' },
    },
    load: {
      executor: 'constant-vus', vus: 100, duration: '30s', startTime: '20s',
      tags: { scenario: 'load' },
    },
    spike: {
      executor: 'constant-vus', vus: 200, duration: '15s', startTime: '55s',
      tags: { scenario: 'spike' },
    },
  },
  thresholds: {
    http_req_duration: ['p(95)<500'],
    http_req_failed:   ['rate<0.02'],
    error_rate:        ['rate<0.02'],
  },
};

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
  const id  = ids[randomIntBetween(0, ids.length - 1)];
  const t   = Date.now();
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
    'all status 200': r => r.status === 200,
    'all has 1000+':  r => JSON.parse(r.body).total >= 1000,
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
  if      (roll < 0.70) list_paginated(data);
  else if (roll < 0.90) get_single(data);
  else                  create_task(data);
  sleep(0.01);
}

export function stress_ramp(data) { mixed_workload(data); }

export default function(data) { mixed_workload(data); }
