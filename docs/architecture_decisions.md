# Architecture Decision Records (ADRs)

## Context
O StarkBank Payment Orchestrator exige alta disponibilidade e consistência para gerenciar fluxos financeiros (faturas e transferências automáticas). Para garantir a integridade, foram adotadas as seguintes diretrizes arquiteturais.

---

## ADR-001: Modular Monolith with Hexagonal Architecture (Ports and Adapters)
**Status:** ✅ Approved
**Date:** 2026-04-04

**Decision:** We adopt a Hexagonal Architecture. 
- **Domain:** Pure Pydantic models with no ORM or infrastructure logic (inside `app/domain`).
- **Application:** Use Cases orchestrating business logic and Ports (abstract interfaces) for external integrations (inside `app/application`).
- **Infrastructure:** Concrete implementations (SQLAlchemy, Celery, FastAPI, StarkBank SDK) implementing the Ports (inside `app/infra`).

---

## ADR-002: Asynchronous Event-Driven Execution (Celery + RabbitMQ)
**Status:** ✅ Approved
**Date:** 2026-04-05

**Decision:** We adopt **RabbitMQ** as the message broker for Celery. 
- Use **AMQP** protocol.
- Separate queues for `webhooks` and `billing`.
- Redis is kept only as a temporary **Result Backend**.

---

## ADR-003: Double-Layer Idempotency 
**Status:** ✅ Approved

**Decision:** We implement a double-layer idempotency mechanism:
1. **Event Logs (Infrastructure Level):** We store the StarkBank `event_id` in a `webhook_events` table.
2. **Domain State (Application Level):** We check `Invoice.status` before creating transfers.

---

## ADR-004: ORM and Asynchronous Database Driver
**Status:** ✅ Approved

**Decision:** We utilize `asyncpg` combined with SQLAlchemy's `AsyncSession` and `create_async_engine`. 

---

## ADR-005: Observability Baseline (OpenTelemetry)
**Status:** ✅ Approved

**Decision:** Instrument FastAPI and Celery with OpenTelemetry and centralize generic logs using Structured JSON formatting for the LGTM Stack.

---

## ADR-006: Dedicated Dead Letter Queues (DLQ)
**Status:** ✅ Approved
**Date:** 2026-04-05

**Decision:** Implement dedicated DLQs (`webhooks_dlq` and `billing_dlq`) using RabbitMQ's `x-dead-letter-exchange`.

---

## ADR-007: Native PostgreSQL UUIDs for Primary Keys
**Status:** ✅ Approved
**Date:** 2026-04-05

**Decision:** Migrate all ID columns to native **`UUID`** type in PostgreSQL using `uuidv7` for time-ordered properties.

---

## ADR-008: PostgreSQL 18 and Storage Optimization
**Status:** ✅ Approved
**Date:** 2026-04-06

**Context:** We need the latest performance features. Version 18 introduced changes in data volume structure.

**Decision:** Upgrade to **PostgreSQL 18-alpine**.
- Adjusted Docker volumes to mount `/var/lib/postgresql` to support major version specific directory names.
- Unified all previous migrations into a single **`initial_schema`**.

---

## ADR-009: Observability Isolation in Multi-Process Workers
**Status:** ✅ Approved
**Date:** 2026-04-06

**Decision:** 
1. Delayed OTel initialization until after the worker fork (`@worker_process_init`).
2. Generate a **Unique Instance ID** per child process.
3. Use `ObservableGauge` for scheduling metrics.
4. Dashboard queries use `max_over_time` to prevent counter drops in multi-process environments.
