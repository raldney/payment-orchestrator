import datetime
import json
import logging
import os
import socket
import sys
import time
import uuid
from typing import Any

from fastapi import Request
from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.celery import CeleryInstrumentor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from app.application.events import dispatcher
from app.domain.events import InvoicesGenerated, PaymentProcessed
from app.infra.config import settings


class JsonFormatter(logging.Formatter):
    def _json_default(self, obj: Any) -> str:
        if isinstance(obj, (uuid.UUID, datetime.date, datetime.datetime)):
            return str(obj)
        return str(obj)

    def format(self, record: logging.LogRecord) -> str:
        log_record: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "message": record.getMessage(),
            "service_name": record.name,
            "code_filepath": record.pathname,
            "code_function": record.funcName,
            "code_lineno": record.lineno,
            "module": record.name,
        }
        if record.exc_info:
            log_record["exception.message"] = self.formatException(record.exc_info)
            exc_type = record.exc_info[0]
            log_record["exception.type"] = exc_type.__name__ if exc_type else "Unknown"
        standard_keys = {
            "args",
            "asctime",
            "created",
            "exc_info",
            "exc_text",
            "filename",
            "funcName",
            "levelname",
            "levelno",
            "lineno",
            "module",
            "msecs",
            "message",
            "msg",
            "name",
            "pathname",
            "process",
            "processName",
            "relativeCreated",
            "stack_info",
            "thread",
            "threadName",
            "taskName",
        }
        for key, value in record.__dict__.items():
            if key not in standard_keys:
                log_record[key] = value
        span_context = trace.get_current_span().get_span_context()
        if span_context.is_valid:
            log_record["trace_id"] = format(span_context.trace_id, "032x")
            log_record["span_id"] = format(span_context.span_id, "016x")
        log_record["service_name"] = "payment-orchestrator"
        log_record["service_component"] = os.getenv("SERVICE_COMPONENT", "unknown")
        sensitive_keywords = settings.log_sensitive_keywords
        for key in list(log_record.keys()):
            if any(kw in key.lower() for kw in sensitive_keywords):
                val = str(log_record[key])
                log_record[key] = f"{val[:4]}...{val[-4:]}" if len(val) > 8 else "***"
        return json.dumps(log_record, default=self._json_default)


def setup_logging():
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(level=log_level, handlers=[handler], force=True)
    loggers_to_clean = (
        "uvicorn",
        "uvicorn.access",
        "uvicorn.error",
        "celery",
        "celery.worker",
        "celery.task",
    )
    for logger_name in loggers_to_clean:
        lg = logging.getLogger(logger_name)
        lg.handlers = []
        lg.propagate = True


def setup_celery_logging(**kwargs):
    logger = kwargs.get("logger")
    if logger:
        for handler in logger.handlers:
            handler.setFormatter(JsonFormatter())
    setup_logging()


def get_resource():
    instance_id = f"{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex[:6]}"
    return Resource(
        attributes={
            "service.name": "payment-orchestrator",
            "service.instance.id": instance_id,
            "deployment.environment": settings.stark_environment,
        }
    )


def setup_tracing():
    if not settings.otel_enabled:
        return
    provider = TracerProvider(resource=get_resource())
    otlp_exporter = OTLPSpanExporter(
        endpoint=settings.otel_endpoint,
        insecure=True,
        timeout=settings.otel_export_timeout,
    )
    processor = BatchSpanProcessor(
        otlp_exporter,
        max_queue_size=settings.otel_batch_max_queue_size,
        max_export_batch_size=settings.otel_batch_export_size,
        schedule_delay_millis=settings.otel_batch_delay_ms,
    )
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)

logger = logging.getLogger("payment-orchestrator")
setup_logging()


# --- Configurações de Métricas (Globais) ---
meter_instance: metrics.Meter | None = None
invoices_created_counter: metrics.Counter | None = None
invoices_amount_counter: metrics.Counter | None = None
payments_processed_counter: metrics.Counter | None = None
transfers_executed_counter: metrics.Counter | None = None
next_invoice_generation_gauge: metrics.ObservableGauge | None = None
lifecycle_end_gauge: metrics.ObservableGauge | None = None
scheduler_status_gauge: metrics.ObservableGauge | None = None

_next_run_timestamp: float = 0.0
_lifecycle_end_timestamp: float = 0.0


def get_next_run_timestamp(_: Any):
    yield metrics.Observation(_next_run_timestamp)


def get_lifecycle_end_timestamp(_: Any):
    yield metrics.Observation(_lifecycle_end_timestamp)


def get_scheduler_status(_: Any):
    val = 1.0 if settings.generate_invoices_enabled else 0.0
    yield metrics.Observation(val)


def setup_metrics():
    """Configura o provedor de métricas e registra todos os instrumentos."""
    if not settings.otel_enabled:
        return

    global meter_instance, invoices_created_counter, invoices_amount_counter
    global payments_processed_counter, transfers_executed_counter
    global next_invoice_generation_gauge, lifecycle_end_gauge, scheduler_status_gauge

    # 1. Configura o Exportador e Reader
    otlp_exporter = OTLPMetricExporter(
        endpoint=settings.otel_endpoint,
        insecure=True,
        timeout=settings.otel_export_timeout,
    )
    reader = PeriodicExportingMetricReader(
        otlp_exporter,
        export_interval_millis=10000,
        export_timeout_millis=settings.otel_export_timeout * 1000,
    )

    # 2. Inicializa o Provider globalmente
    provider = MeterProvider(resource=get_resource(), metric_readers=[reader])
    metrics.set_meter_provider(provider)

    # 3. Cria o Meter e Instrumentos
    meter_instance = metrics.get_meter("payment.business")

    invoices_created_counter = meter_instance.create_counter(
        "payment_invoices_created", unit="1", description="Total invoices created"
    )
    invoices_amount_counter = meter_instance.create_counter(
        "payment_invoices_amount_cents",
        unit="cents",
        description="Total BRL volume generated in cents",
    )
    payments_processed_counter = meter_instance.create_counter(
        "payment_processed",
        unit="1",
        description="Total payments processed via webhook",
    )
    transfers_executed_counter = meter_instance.create_counter(
        "payment_transfers_executed",
        unit="1",
        description="Total transfers executed successfully",
    )

    # Instrumentos Assíncronos (Gauges)
    next_invoice_generation_gauge = meter_instance.create_observable_gauge(
        "payment_invoices_next_run_timestamp",
        callbacks=[get_next_run_timestamp],
        unit="s",
        description="Timestamp da próxima execução (Unix)",
    )
    lifecycle_end_gauge = meter_instance.create_observable_gauge(
        "payment_worker_lifecycle_end_timestamp",
        callbacks=[get_lifecycle_end_timestamp],
        unit="s",
        description="Timestamp de expiração do worker (Unix)",
    )
    scheduler_status_gauge = meter_instance.create_observable_gauge(
        "payment_scheduler_status",
        callbacks=[get_scheduler_status],
        unit="",
        description="Status do agendador (1=ON, 0=OFF)",
    )


def set_next_run_timestamp(ts: float):
    global _next_run_timestamp
    _next_run_timestamp = ts


def set_lifecycle_end_timestamp(ts: float):
    global _lifecycle_end_timestamp
    _lifecycle_end_timestamp = ts


def on_invoices_generated(event: InvoicesGenerated):
    if invoices_created_counter:
        invoices_created_counter.add(event.count)
    if invoices_amount_counter:
        invoices_amount_counter.add(event.total_amount)


def on_payment_processed(event: PaymentProcessed):
    if payments_processed_counter:
        payments_processed_counter.add(1)
    if transfers_executed_counter:
        transfers_executed_counter.add(1)


dispatcher.subscribe(InvoicesGenerated, on_invoices_generated)
dispatcher.subscribe(PaymentProcessed, on_payment_processed)


def instrument_app(app):
    if not settings.otel_enabled:
        return
    FastAPIInstrumentor.instrument_app(app, excluded_urls="health")

    @app.middleware("http")
    async def observability_middleware(request: Request, call_next):
        start_time = time.perf_counter()
        response = await call_next(request)
        process_time = time.perf_counter() - start_time
        logger.info(
            "HTTP Request Completed",
            extra={
                "http.method": request.method,
                "http.url": str(request.url),
                "http.status_code": response.status_code,
                "http.duration_ms": round(process_time * 1000, 2),
            },
        )
        return response


def instrument_worker():
    if not settings.otel_enabled:
        return
    CeleryInstrumentor().instrument()
