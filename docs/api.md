# API Reference

A API é documentada automaticamente pelo FastAPI usando OpenAPI (Swagger) em `/docs`.

## Endpoints Principais

### Webhooks
- `POST /v1/webhooks/starkbank`: Recebe notificações de pagamento do Stark Bank. 
  - **Headers**: Requer `Digital-Signature`.
  - **Bypass**: Em ambiente de `DEBUG=true`, aceita o header `X-Test-Bypass: true` para ignorar a assinatura.

### Billing (Faturamento)
- `POST /v1/billing/generate-batch`: Dispara manualmente a geração de um novo lote de invoices.
- `GET /v1/billing/invoices`: Lista as faturas geradas (paginado).
- `GET /v1/billing/invoices/{invoice_id}`: Detalhes de uma fatura específica.
- `GET /v1/billing/schedule`: Informações sobre o próximo agendamento automático de faturas.

### Transfers (Repasses)
- `GET /v1/transfers/`: Lista as transferências realizadas (paginado).

### Health
- `GET /health`: Verifica se a API está operacional. Retorna `{"status": "healthy"}`.
