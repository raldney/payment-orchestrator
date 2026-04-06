# 📉 Observabilidade com LGTM Stack (Loki, Grafana, Tempo, Mimir)

Este projeto utiliza a stack **LGTM** completa para fornecer telemetria de 3 pilares: Logs, Métricas e Traces, garantindo visibilidade total sobre a orquestração financeira.

---

## 🏗️ Arquitetura de Métricas (Grafana Mimir)

O **Grafana Mimir** é o nosso banco de dados de séries temporais (TSDB). Ele pode operar em dois modos principais:

### 1. Modo Monolítico (Local / Dev)
Configuração padrão deste projeto (`target: all`). Todos os componentes (Ingester, Querier, Distributor, Compactor) rodam em um único container.
- **Vantagem**: Simplicidade operacional e baixo consumo de recursos para desenvolvimento local.
- **Saúde do Ring**: Verifique o status dos componentes locais com:
  ```bash
  docker compose exec mimir wget -qO- localhost:9009/ingester/ring
  ```

### 2. Modo Microsserviços
Para implantações distribuídas, as funções são desacopladas em processos independentes:
- **Distributors**: Recebem métricas via OTLP e realizam o hashing para os Ingesters.
- **Ingesters**: Mantêm dados em memória para escrita e consulta rápida.
- **Queriers**: Processam consultas a partir dos Ingesters e do Object Store.
- **Compactors**: Consolidam blocos de dados no armazenamento persistente.

---

## 📊 Estabilidade de Métricas em Ambientes Multi-Processo

Em sistemas que usam `fork()` ou múltiplos workers (Celery/Gunicorn), a colisão de IDs de instância é um risco comum.

- **Service Instance ID**: Este projeto gera um ID único (`hostname-pid-hash`) para cada worker após o boot, garantindo que as métricas não se sobreponham.
- **Persistência de Contadores**: Para evitar que gráficos "zerem" quando um worker é reiniciado, todos os Business KPIs utilizam a função `max_over_time()` ou `sum()` no Grafana. Isso mantém a volumetria histórica estável mesmo com rotatividade de processos.

---

## ⏲️ Monitoramento de Automação

Adicionamos seções exclusivas no Dashboard (`http://localhost:3000`) para monitorar o worker autogerenciado:

- **Próximo Lote**: Exibe o horário exato em que o ciclo de faturamento será disparado.
- **Ciclo de Vida (TTL)**: Rastreia o tempo restante das 24h de automação (`LIFECYCLE_HOURS`).
- **Idempotência**: Gráficos de "Eventos Ignorados" mostram a eficácia da proteção contra duplicidade em tempo real.

---

## 🛡️ Segurança e LGPD (PII Masking)

Em conformidade com a LGPD, o sistema implementa **PII Sanitization** automática na camada de logs:
- **Campos Mascarados**: CPF/CNPJ (`tax_id`), Nomes, E-mails, Números de Conta e Telefone.
- **Processamento**: O `JsonFormatter` personalizado analisa o log estruturado e substitui valores sensíveis por `[MASKED]` antes de enviá-los ao Grafana Loki.

---

## 🛠️ Comandos Úteis de Diagnóstico

**Verificar se o Mimir está recebendo métricas:**
```bash
docker compose exec mimir wget -qO- http://localhost:9009/prometheus/api/v1/query?query=up
```

**Verificar exportação do OTel Collector:**
```bash
docker compose logs -f otel-collector
```
