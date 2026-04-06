# 🏦 Payment Orchestrator

> Automação de Faturas e Transferências (Stark Bank Sandbox)  
> **Arquitetura Hexagonal · Async-first · Stack LGTM · RabbitMQ 4.0 · PostgreSQL 18**

---

## 🛠️ Requisitos de Negócio

O sistema atende aos seguintes critérios operacionais:

1.  **Ciclo de Faturamento**: Geração automática de lotes de 8 a 12 faturas a cada 3 horas.
2.  **Ciclo de Vida**: A automação permanece ativa por um período total de 24 horas (`LIFECYCLE_HOURS`).
3.  **Reconciliação e Repasse**: Ao receber o crédito (`credited`) de uma fatura, o sistema realiza o repasse imediato (valor líquido) para a conta centralizadora.

### Conta de Liquidação (Stark Bank S.A.)
- **Banco**: 20018183 | **Agência**: 0001 | **Conta**: 6341320293482496
- **CNPJ**: 20.018.183/0001-80

---

## 🏁 Funcionalidades e Resiliência

Checklist técnico das proteções e automações implementadas:

- [x] **Idempotência**: Garantida via `event.id` e `ON CONFLICT DO NOTHING`.
- [x] **Orquestração de Eventos**: Disparo de transferências via webhooks assíncronos.
- [x] **Integridade Financeira**: Uso de transações SQL e `SELECT FOR UPDATE`.
- [x] **Automação Nativa**: Worker autogerenciado com self-chaining.
- [x] **Observabilidade LGTM**: Métricas de negócio, logs e traces integrados.
- [x] **Segurança**: Validação rigorosa de assinaturas ECDSA.

---

## 📋 Visão Geral

Sistema automatizado integrado ao **Stark Bank Sandbox** para:

1.  **Geração de Faturas**: Agendamento autogerenciado via RabbitMQ (Self-Chaining) com suporte a **Ciclo de Vida Limitado**.
2.  **Processamento de Webhooks**: Recepção, validação de assinaturas ECDSA e tratamento assíncrono de eventos.
3.  **Orquestração Financeira**: Execução de transferência automática do valor líquido após a confirmação do crédito.

---

## 🚀 Como Executar (Setup Rápido)

### 1. Clone e Configuração
```bash
git clone <repo-url>
cd payment-orchestrator
cp .env.example .env
```

### 2. Configuração das Variáveis de Ambiente
Edite o arquivo `.env` com suas credenciais do Stark Bank. Veja a [Tabela de Env Vars](#-variáveis-de-ambiente) abaixo.

### 3. Startup com Docker
```bash
docker compose up -d --build
```

### 4. Migração do Banco de Dados
Aguarde os containers subirem e execute a migração inicial:
```bash
docker compose exec api alembic upgrade head
```

---

## ⚙️ Variáveis de Ambiente

Principais configurações necessárias no arquivo `.env`:

### 🔑 Autenticação Stark Bank (Sandbox)
| Variável | Obrigatória | Descrição | Default/Exemplo |
| :--- | :---: | :--- | :--- |
| `STARK_PROJECT_ID` | ✅ | ID do projeto no Stark Bank | `6256488727183360` |
| `STARK_PRIVATE_KEY` | ✅ | Chave privada PEM (EC) | `"-----BEGIN EC..."` |
| `STARK_ENVIRONMENT` | ❌ | Ambiente do SDK | `sandbox` |

### 🖥️ App & Banco de Dados
| Variável | Obrigatória | Descrição | Default |
| :--- | :---: | :--- | :--- |
| `APP_PORT` | ❌ | Porta do servidor API (FastAPI) | `8000` |
| `DATABASE_URL` | ❌ | URL de conexão (asyncpg) | `postgresql+asyncpg://...` |
| `DB_POOL_SIZE`| ❌ | Tamanho do pool de conexões | `20` |

### 🚀 Mensageria & Cache (RabbitMQ / Redis)
| Variável | Obrigatória | Descrição | Default |
| :--- | :---: | :--- | :--- |
| `RABBITMQ_URL`| ❌ | URL de conexão com Broker | `amqp://...` |
| `REDIS_URL`   | ❌ | URL do Redis (Result Backend) | `redis://...` |

### 📊 Observabilidade (LGTM)
| Variável | Obrigatória | Descrição | Default |
| :--- | :---: | :--- | :--- |
| `LOG_LEVEL` | ❌ | Nível de log (DEBUG, INFO, etc) | `INFO` |
| `OTEL_ENABLED` | ❌ | Habilitar exportação OTel | `true` |
| `OTEL_ENDPOINT`| ❌ | Endpoint do OTel Collector | `http://otel-collector:4317` |

### 🧠 Regras de Negócio e Worker
| Variável | Obrigatória | Descrição | Default |
| :--- | :---: | :--- | :--- |
| `GENERATE_INVOICES_ENABLED` | ❌ | Habilitar geração automática | `true` |
| `LIFECYCLE_HOURS` | ❌ | Duração total da automação | `1` |
| `BATCH_INTERVAL_HOURS` | ❌ | Intervalo entre gerações | `3` |
| `BATCH_SIZE_MIN` | ❌ | Mínimo de faturas por lote | `8` |
| `BATCH_SIZE_MAX` | ❌ | Máximo de faturas por lote | `12` |
| `INVOICE_DUE_HOURS` | ❌ | Prazo de vencimento da fatura | `24` |

---

## 📖 Documentação da API (Swagger)

Com o sistema rodando, a documentação interativa está disponível em:
👉 **[http://localhost:8000/docs](http://localhost:8000/docs)**

---

## ☁️ Deploy na AWS (Infraestrutura)

O sistema está preparado para rodar em uma instância **EC2 (Ubuntu 24.04)** com Docker Engine, provisionada via **Terraform**.

### Estrutura da Infra
- **Provedor**: AWS (sa-east-1)
- **Engine**: Docker + Docker Compose (Produção)
- **Proxy**: Nginx com SSL/TLS (HTTPS) ativado.
- **Diretório no Host**: `/opt/payment-orchestrator`

### Como fazer o Deploy
1.  Navegue até `terraform/aws/` e inicialize o Terraform.
2.  Execute `terraform apply` para criar a VM e rede.
3.  O `startup.sh` instalará Docker e preparará o ambiente automaticamente.
4.  Suba os serviços em modo produção:
    ```bash
    docker compose -f docker-compose.prod.yaml up -d
    ```

---

## 🔗 Links Disponíveis (Produção)

Acesse os serviços através do IP público da instância (**{IP_DA_INSTANCIA}**). Toda comunicação externa é feita via **Porta 443 (HTTPS)**.

| Serviço | Link de Acesso | Descrição |
| :--- | :--- | :--- |
| **🚀 API Swagger** | [https://{IP_DA_INSTANCIA}/docs](https://{IP_DA_INSTANCIA}/docs) | Documentação interativa e testes de endpoints. |
| **📊 Grafana** | [https://{IP_DA_INSTANCIA}/grafana/](https://{IP_DA_INSTANCIA}/grafana/) | Dashboards de Negócio e Telemetria (Loki/Mimir). |
| **🐰 RabbitMQ** | [https://{IP_DA_INSTANCIA}/rabbitmq/](https://{IP_DA_INSTANCIA}/rabbitmq/) | Painel de controle de filas e agendamentos. |

---

## 📊 Observabilidade (Grafana)

Acesse **[grafana/](https://{IP_DA_INSTANCIA}/grafana/)** (em Produção) ou **[localhost:3000](http://localhost:3000)** (Local) para visualizar:

-   **⏲️ Automação**: Horário da próxima execução e tempo restante do ciclo do worker.
-   **💰 Business KPIs**: Invoices criadas, volume (BRL) e taxa de sucesso.
-   **📉 Telemetria Detalhada**: Verifique o guia completo em [docs/observability.md](docs/observability.md).

---

## 🛡️ Idempotência e Resiliência

-   **Double-Layer Idempotency**: Validação por ID de evento no banco e por status da entidade no domínio.
-   **Financial Lock**: Row-level locking no processamento para evitar duplicidade em concorrência.
-   **PII Masking**: O `JsonFormatter` mascara automaticamente campos sensíveis (CPF, Nomes) antes do envio ao Loki.

---

## 📄 Licença
MIT
