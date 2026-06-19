import http from 'k6/http';
import { check, sleep } from 'k6';
import { Trend, Rate, Counter } from 'k6/metrics';

const BASE_URL = __ENV.BASE_URL || 'http://127.0.0.1:8000';
const VUS = Number(__ENV.VUS || 10);
const RAMP_UP = __ENV.RAMP_UP || '60s';
const STEADY = __ENV.DURATION || '5m';
const USER_COUNT = Number(__ENV.USER_COUNT || 120);
const PASSWORD = __ENV.PASSWORD || 'LoadTestAuth123!';
const USER_PREFIX = __ENV.USER_PREFIX || 'loadtest.user';

export const loginDuration = new Trend('login_duration', true);
export const loginSuccessRate = new Rate('login_success_rate');
export const loginFailureCount = new Counter('login_failure_count');

export const options = {
  scenarios: {
    auth_burst: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: RAMP_UP, target: VUS },
        { duration: STEADY, target: VUS },
        { duration: '30s', target: 0 },
      ],
      gracefulRampDown: '10s',
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.05'],
    http_req_duration: ['p(95)<1500', 'p(99)<3000'],
    login_success_rate: ['rate>0.95'],
  },
};

function userEmailForVu() {
  const userNumber = ((__VU - 1) % USER_COUNT) + 1;
  return `${USER_PREFIX}.${String(userNumber).padStart(3, '0')}@example.com`;
}

function randomTraceId() {
  return `${Date.now()}-${__VU}-${__ITER}-${Math.floor(Math.random() * 100000)}`;
}

export default function () {
  const email = userEmailForVu();
  const payload = JSON.stringify({
    email,
    password: PASSWORD,
  });

  const res = http.post(`${BASE_URL}/api/auth/login/`, payload, {
    headers: {
      'Content-Type': 'application/json',
      'X-Loadtest-Trace': randomTraceId(),
    },
    tags: {
      endpoint: 'auth_login',
      scenario: 'auth_only',
    },
    timeout: '10s',
  });

  loginDuration.add(res.timings.duration);

  const ok = check(res, {
    'status is 200': (r) => r.status === 200,
    'has access token': (r) => {
      if (r.status !== 200) {
        return false;
      }
      try {
        const body = JSON.parse(r.body || '{}');
        return Boolean(body.access && body.refresh);
      } catch (_) {
        return false;
      }
    },
  });

  loginSuccessRate.add(ok);
  if (!ok) {
    loginFailureCount.add(1);
    console.error(`login failed: status=${res.status} body=${res.body}`);
  }

  sleep(1 + Math.random() * 2);
}

export function handleSummary(data) {
  const metrics = data.metrics;
  const httpDuration = metrics.http_req_duration?.values || {};
  const loginMetric = metrics.login_duration?.values || {};
  const requests = metrics.http_reqs?.values?.count || 0;
  const durationSeconds = (data.state?.testRunDurationMs || 0) / 1000;
  const rps = durationSeconds > 0 ? (requests / durationSeconds).toFixed(2) : '0.00';

  const summary = {
    vus: VUS,
    baseUrl: BASE_URL,
    userCount: USER_COUNT,
    requests,
    rps,
    successRate: metrics.login_success_rate?.values?.rate ?? null,
    failedRate: metrics.http_req_failed?.values?.rate ?? null,
    httpReqDuration: httpDuration,
    loginDuration: loginMetric,
  };

  const text = [
    'k6 auth login summary',
    `base_url=${BASE_URL}`,
    `vus=${VUS}`,
    `user_count=${USER_COUNT}`,
    `requests=${requests}`,
    `rps=${rps}`,
    `success_rate=${metrics.login_success_rate?.values?.rate ?? 'n/a'}`,
    `failed_rate=${metrics.http_req_failed?.values?.rate ?? 'n/a'}`,
    `http_req_duration_ms min=${httpDuration.min ?? 'n/a'} p50=${httpDuration.med ?? 'n/a'} p95=${httpDuration['p(95)'] ?? 'n/a'} p99=${httpDuration['p(99)'] ?? 'n/a'} max=${httpDuration.max ?? 'n/a'}`,
    `login_duration_ms min=${loginMetric.min ?? 'n/a'} p50=${loginMetric.med ?? 'n/a'} p95=${loginMetric['p(95)'] ?? 'n/a'} p99=${loginMetric['p(99)'] ?? 'n/a'} max=${loginMetric.max ?? 'n/a'}`,
  ].join('\n');

  return {
    stdout: `${text}\n`,
    'simple/loadtests/results/auth-login-summary.json': JSON.stringify(summary, null, 2),
  };
}
