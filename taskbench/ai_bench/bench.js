// AI inference bench — POST /predict with varied inputs.
// VUs is parametrized via env var so we can sweep concurrency: 1, 4, 16, 50.
import http from 'k6/http';
import { check } from 'k6';
import { Trend, Counter, Rate } from 'k6/metrics';

const BASE = __ENV.BASE || 'http://localhost:9101';
const VUS  = parseInt(__ENV.VUS || '50', 10);
const DUR  = __ENV.DUR || '20s';
const lat  = new Trend('latency_ms', true);
const reqs = new Counter('total_reqs');
const errs = new Rate('error_rate');

const SAMPLES = [
  'This movie is fantastic! Best film of the year.',
  'Absolute trash, would not recommend to my worst enemy.',
  'I had mixed feelings about it but ended up liking the third act.',
  'The acting was wooden and the plot made no sense.',
  'A masterpiece of modern cinema with breathtaking visuals.',
  'Boring, predictable, and way too long. I fell asleep.',
  'Loved every second of it, the soundtrack was incredible.',
  'Mediocre at best. The trailer made it look better than it was.',
];

export const options = {
  summaryTrendStats: ['avg','min','med','max','p(50)','p(90)','p(95)','p(99)'],
  scenarios: { main: {
    executor: 'constant-vus', vus: VUS, duration: DUR,
  }},
};

export default function () {
  const text = SAMPLES[Math.floor(Math.random() * SAMPLES.length)];
  const t = Date.now();
  const res = http.post(`${BASE}/predict`,
    JSON.stringify({ text }),
    { headers: { 'Content-Type': 'application/json' } });
  lat.add(Date.now() - t);
  reqs.add(1);
  const ok = check(res, { '200': r => r.status === 200 });
  errs.add(!ok);
}

export function handleSummary(data) {
  const m = data.metrics;
  const p = (k, s) => (m[k] && m[k].values[s]) ? m[k].values[s].toFixed(2) : 'N/A';
  const dur = data.state.testRunDurationMs / 1000;
  const total = m.total_reqs ? m.total_reqs.values.count : 0;
  const out = [
    `vus           ${VUS}`,
    `total_reqs    ${total}`,
    `duration_s    ${dur.toFixed(2)}`,
    `rps           ${(total/dur).toFixed(0)}`,
    `latency_avg   ${p('latency_ms','avg')}`,
    `latency_p50   ${p('latency_ms','p(50)')}`,
    `latency_p95   ${p('latency_ms','p(95)')}`,
    `latency_p99   ${p('latency_ms','p(99)')}`,
    `latency_max   ${p('latency_ms','max')}`,
    `error_rate    ${m.error_rate ? (m.error_rate.values.rate*100).toFixed(3)+'%' : 'N/A'}`,
  ].join('\n');
  return { stdout: '\n' + out + '\n', '/tmp/ai_bench_result.txt': out };
}
