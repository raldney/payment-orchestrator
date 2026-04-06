## 🛠️ Regras de Negócio

- **Automação de Lote**: 8 a 12 faturas a cada 3 horas.
- **Workflow Persistence**: Operação por 24 horas (`LIFECYCLE_HOURS`).
- **Liquidação**: Repasse automático do valor `credited` (limpo de taxas) para a conta centralizadora Stark Bank S.A.

---

## 🏁 Funcionalidades e Resiliência

- [x] **Idempotência**: Proteção via `event.id` e log de eventos.
- [x] **Orquestração**: Disparo de transferências via webhooks.
- [x] **Integridade**: PostgreSQL 18 + Locks Pessimistas.
- [x] **Observabilidade**: Tracing, Métricas e Logs Estruturados.
- [x] **Segurança**: Validação de assinaturas ECDSA Stark Bank.

---

## 🚀 Guia de Início Rápido

### 1. Requisitos
- Docker & Docker Compose
- Credenciais Stark Bank (Sandbox)

### 2. Configuração
Copie o arquivo de exemplo e configure suas chaves:
```bash
cp .env.example .env
```

| Variável | Exemplo |
| :--- | :--- |
| `STARK_PROJECT_ID` | `6256488727183360` |
| `STARK_PRIVATE_KEY` | `"-----BEGIN EC..."` |

### 3. Execução
```bash
docker compose up -d --build
docker compose exec api alembic upgrade head
```

---

## 📖 Links Úteis

- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Grafana Dashboard**: [http://localhost:3000](http://localhost:3000)
- **Detalhes de Observabilidade**: [docs/observability.md](observability.md)
- **Estratégia de Testes**: [docs/testing.md](testing.md)

---

## 🛠 Funcionalidades Detalhadas

- **Webhook ID Tracking:** Cada `event.id` recebido da StarkBank é registrado no banco local.
- **Outbound Idempotency:** O `external_id` de cada transferência é amarrado à Invoice original.
- **Native UUIDs (v7) & PostgreSQL 18:** Performance otimizada.
- **Automated Lifecycle:** O sistema se auto-gerencia e para automaticamente via `LIFECYCLE_HOURS`.
- **LGPD Compliance:** Mascaramento de PII nos logs enviado ao Loki.
