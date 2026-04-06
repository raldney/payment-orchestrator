# Estratégia de Testes - Payment Orchestrator

Este documento descreve as abordagens de teste para garantir a integridade financeira e resiliência do sistema.

## 1. Testes de Unidade, Integração e E2E (Pytest)
Localizados em `tests/`.
- **Unit**: Focado em regras de negócio puras (ex: validação de status de fatura).
- **Integration**: Testa a comunicação entre camadas (UseCase -> Repositório -> Adaptador).
- **E2E (Mocked)**: Simula o fluxo completo (Webhook -> Celery Task -> Repository -> Gateway) de forma isolada, garantindo que a orquestração entre componentes funcione corretamente sem depender de infraestrutura externa (Postgres/Redis/RabbitMQ).
- **Mocking**: Conexões externas e de infraestrutura são mockadas para velocidade e portabilidade, permitindo rodar a suíte completa em ambientes de CI ou locais sem Docker.

## 2. Modo de Depuração e Bypass de Webhooks
Para facilitar testes e desenvolvimento local, o sistema possui uma flag `DEBUG` nas configurações:
- **`DEBUG=true`**: Permite o envio de webhooks do Stark Bank ignorando a validação de assinatura ECDSA, desde que o header `X-Test-Bypass: true` esteja presente. Isso é utilizado extensivamente nos testes de E2E e Integração.
- **`nest-asyncio`**: O worker utiliza o `nest-asyncio` para permitir a execução de tarefas assíncronas dentro de loops de eventos já existentes (comum em testes com `pytest-asyncio` e Celery em modo `eager`).

## 3. Testes de Carga e Estresse (k6)
Localizado em `tests/load/load_test_webhooks.js`.
- **Cenário Ramp-up**: Valida latência sob carga crescente.
- **Cenário Conflito (Idempotência)**: Simula múltiplas requests simultâneas com o **mesmo** ID para validar se a camada de infraestrutura/DB impede duplicidade.

## 🚀 Próximas Etapas sugeridas

Para expandir a cobertura de testes em ambientes distribuídos:

### Verificação de Concorrência com Banco Real
Atualmente, o `test_concurrency_race_condition.py` utiliza mocks. Uma melhoria recomendada é implementar um teste que utilize o PostgreSQL (via Docker) para:
- Validar se o bloqueio físico do `SELECT FOR UPDATE` isola corretamente as transações.
- Garantir que o `ON CONFLICT DO NOTHING` se comporta como esperado sob carga real.

### Testes de Resiliência de Fila
- **Injeção de Latência**: Simular lentidão no Redis ou RabbitMQ para verificar o comportamento de timeout dos workers.
- **Max Retries**: Extenuar as tentativas de retentativa de um webhook para garantir que eventos falhos acabem em uma Dead Letter Queue (DLQ) ou log estruturado de erro crítico.

### Auditoria de Idempotência em Longo Prazo
- Testar o comportamento do sistema quando um webhook é recebido meses após a fatura ter sido processada, garantindo que o log histórico de webhooks permanece eficiente.
