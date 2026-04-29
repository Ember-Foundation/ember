import http from "k6/http";
import { check } from "k6";

const URL = __ENV.URL;

export const options = {
  vus: parseInt(__ENV.VUS || "200", 10),
  duration: __ENV.DURATION || "20s",
  summaryTrendStats: ["avg", "min", "med", "p(50)", "p(90)", "p(95)", "p(99)", "max"],
};

export default function () {
  const r = http.get(URL);
  check(r, { ok: (x) => x.status === 200 });
}
