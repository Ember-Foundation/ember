/**
 * k6 hello-world benchmark — pure framework throughput, no DB.
 * Runs both Ember (9010) and Express (9011) back-to-back.
 */
import http from "k6/http";
import { check } from "k6";
import { Rate, Trend } from "k6/metrics";

const EMBER_BASE   = "http://localhost:9010";
const EXPRESS_BASE = "http://localhost:9011";

const emberErr    = new Rate("ember_error_rate");
const expressErr  = new Rate("express_error_rate");
const emberDur    = new Trend("ember_duration",   true);
const expressDur  = new Trend("express_duration", true);

export const options = {
  summaryTrendStats: ["avg", "min", "p(50)", "p(90)", "p(95)", "p(99)", "max"],
  scenarios: {
    ember_warmup: {
      executor: "constant-vus", vus: 50,  duration: "10s",
      env: { TARGET: "ember" },
    },
    ember_load: {
      executor: "constant-vus", vus: 200, duration: "20s", startTime: "15s",
      env: { TARGET: "ember" },
    },
    express_warmup: {
      executor: "constant-vus", vus: 50,  duration: "10s", startTime: "45s",
      env: { TARGET: "express" },
    },
    express_load: {
      executor: "constant-vus", vus: 200, duration: "20s", startTime: "60s",
      env: { TARGET: "express" },
    },
  },
  thresholds: {
    ember_error_rate:   ["rate<0.01"],
    express_error_rate: ["rate<0.01"],
  },
};

export default function () {
  const isEmber = __ENV.TARGET === "ember";
  const url     = (isEmber ? EMBER_BASE : EXPRESS_BASE) + "/hello";
  const t       = Date.now();
  const res     = http.get(url);
  const dur     = Date.now() - t;
  const ok      = check(res, {
    "status 200":       (r) => r.status === 200,
    "body correct":     (r) => r.body === "Hello, World!",
  });
  if (isEmber) { emberDur.add(dur);   emberErr.add(!ok); }
  else         { expressDur.add(dur); expressErr.add(!ok); }
}
