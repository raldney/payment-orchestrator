# 🏗️ Arquitetura Detalhada e Ciclo de Vida

Este documento descreve o funcionamento interno do **Payment Orchestrator**, detalhando as camadas, a máquina de estados e o ciclo de automação.

---

## 1. Diagrama de Arquitetura (Hexagonal)

O sistema segue os princípios de *Clean Architecture*, isolando a inteligência de negócio das ferramentas de infraestrutura.

```mermaid
graph TD
    subgraph Infra ["Camada de Infraestrutura (Adapters)"]
        API[FastAPI Controller]
        WRK[Celery Worker Processes]
        DB[(PostgreSQL 18)]
        MQ[RabbitMQ Broker]
        OTEL[OpenTelemetry Collector]
        SB[StarkBank SDK]
    end

    subgraph App ["Camada de Aplicação (Ports/UseCases)"]
        UC1[GenerateInvoicesUseCase]
        UC2[ProcessPaymentUseCase]
        EVT[Event Dispatcher]
    end

    subgraph Domain ["Camada de Domínio (Core Logic)"]
        INV[Invoice Entity]
        TRF[Transfer Entity]
        MON[Money Value Object]
        RULES[Business Rules]
    end

    %% Fluxos
    MQ --> WRK
    WRK --> UC1
    API --> UC2
    UC1 & UC2 --> Domain
    UC1 & UC2 --> DB
    UC1 --> SB
    UC2 --> SB
    
    %% Observabilidade
    WRK & API -- "Events" --> EVT
    EVT -- "Metrics/Traces" --> OTEL
```

---

## 2. Ciclo de Vida do Worker (Automação 24h)

O agendador utiliza uma técnica de *Self-Chaining* via RabbitMQ. O ciclo tem um tempo de vida finito para garantir a economia de recursos em ambiente Sandbox.

```mermaid
flowchart TD
    Start((Início do Ciclo)) --> Task[Executar generate_invoices_task]
    Task --> Check_Enabled{Agendamento Habilitado?}
    
    Check_Enabled -- "Não" --> Stop[Interromper Corrente]
    Check_Enabled -- "Sim" --> Check_Life{Tempo decorrido <br/> >= LIFECYCLE_HOURS?}
    
    Check_Life -- "Sim" --> Stop
    Check_Life -- "Não" --> Exec[Gerar Lote de Faturas]
    
    Exec --> DB_Commit[Salvar via UPSERT]
    DB_Commit --> Dispatch[Disparar Evento Metrics]
    Dispatch --> Schedule[Agendar Próxima via Countdown]
    Schedule --> Task
    
    Stop --> End((Fim))
```

---

## 3. Máquina de Estados (Financeiro)

O fluxo de vida das entidades é garantido por uma máquina de estados rígida, validada por webhooks e assinaturas digitais.

### Fluxo da Fatura (Invoice)
As transições são protegidas no domínio e persistidas de forma idempotente.

```mermaid
stateDiagram-v2
    [*] --> pending: Batch Generation
    pending --> paid: Webhook 'paid'
    pending --> credited: Webhook 'credited'
    paid --> credited: Webhook 'credited'
    
    credited --> transfer_executed: Execute Repasse
    
    pending --> expired: Expiration
    pending --> failed: Provider Error
    
    credited --> [*]: Finalizado
```

### Fluxo da Transferência (Transfer)
```mermaid
stateDiagram-v2
    [*] --> created: Invoice Credited
    created --> success: Repasse Concluído via SDK
    created --> failed: Gateway Error
    
    success --> [*]
    failed --> created: Retry Logic (Celery)
```

---

## 4. Garantias de Integridade Financeira

1.  **Money Value Object**: Todos os valores monetários são encapsulados no objeto `Money`, garantindo precisão em centavos e impedindo valores negativos ou operações inválidas.
2.  **Double-Layer Idempotency**:
    - **Infra**: O `WebhookEventRepository` registra cada `event_id` único no PostgreSQL usando `ON CONFLICT DO NOTHING`.
    - **Domínio**: A entidade `Invoice` valida a transição de estado. Se um evento tenta mover para um estado já atingido ou inválido, o processo é ignorado ou corrigido.
3.  **Pessimistic Locking**: O processamento de pagamentos utiliza `SELECT FOR UPDATE` para bloquear a linha da fatura no banco, evitando condições de corrida entre múltiplos workers Celery.
4.  **Resiliência via UPSERT**: O `PaymentRepository` utiliza a estratégia de UPSERT (`ON CONFLICT DO UPDATE`) para todas as persistências de entidades, garantindo que retentativas de jobs não criem duplicatas indesejadas.
5.  **Observabilidade de Negócio**: Métricas personalizadas como `payment.scheduler.status` e `payment.invoices.next_run_timestamp` permitem monitoramento em tempo real do status da automação no Grafana.

---

### Fluxo de Execução E2E

1.  **Geração**: O Worker gera faturas aleatórias (nomes/CPFs via Faker) e as envia para o StarkBank.
2.  **Webhooks**: A API recebe eventos `paid` e `credited`.
3.  **Orquestração**: 
    - Evento `paid`: Atualiza status para `PAID`.
    - Evento `credited`: Atualiza status para `CREDITED` e dispara `execute_transfer` (Repasse do valor líquido).
4.  **Telemetria**: Rastreamento completo de cada webhook, desde a recepção na API até a conclusão do repasse no Worker.
