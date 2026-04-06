import http from 'k6/http';
import { check, sleep } from 'k6';

// -----------------------------------------------------------------------------
// CONFIGURATION & SCENARIOS
// -----------------------------------------------------------------------------
export const options = {
  scenarios: {
    // 1. Ramp-up: Teste de carga progressivo
    ramp_up: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '30s', target: 50 }, // Sobe até 50 usuários
        { duration: '1m', target: 50 },  // Mantém
        { duration: '30s', target: 0 },  // Desce
      ],
      gracefulStop: '30s',
    },
    // 2. Stress/Idempotency: Múltiplos usuários tentando o MESMO recurso simultaneamente
    idempotency_conflict: {
      executor: 'constant-vus',
      vus: 20,
      duration: '30s',
      startTime: '2m', // Começa depois do ramp-up
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.01'], // Menos de 1% de erro
    http_req_duration: ['p(95)<500'], // 95% das requests < 500ms
  },
};

// -----------------------------------------------------------------------------
// TEST LOGIC
// -----------------------------------------------------------------------------
export default function () {
  const url = __ENV.API_URL || 'http://localhost:8000/v1/webhooks/starkbank';
  
  // No cenário de idempotência, usamos o mesmo ID para causar conflito proposital
  const isConflictScenario = __SCENARIO === 'idempotency_conflict';
  const eventId = isConflictScenario 
    ? 'evt_stress_conflict_001' 
    : `evt_load_${Math.floor(Math.random() * 1000000)}`;

  const payload = JSON.stringify({
    event: {
      id: eventId,
      subscription: 'invoice',
      created: new Date().toISOString(),
      log: {
        id: `log_${Math.floor(Math.random() * 1000000)}`,
        type: 'credited',
        created: new Date().toISOString(),
        invoice: {
          id: `ext_inv_${Math.floor(Math.random() * 1000)}`,
          amount: 10000,
          fee: 50,
          status: 'paid',
          tags: [`k6_vu_${__VU}`]
        }
      }
    }
  });

  const params = {
    headers: {
      'Content-Type': 'application/json',
      'Digital-Signature': 'mock-sig-load-test',
      'X-Test-Bypass': 'true',
    },
  };

  const res = http.post(url, payload, params);

  check(res, {
    'is status 200': (r) => r.status === 200,
    'latency OK': (r) => r.timings.duration < 500,
  });

  // Pensa um pouco entre as requests (simula comportamento real)
  sleep(Math.random() * 2 + 0.5);
}
