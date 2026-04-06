import asyncio
import time
from typing import Any

import redis
from celery import Celery
from celery.exceptions import MaxRetriesExceededError, Reject
from celery.signals import (
    after_setup_logger,
    after_setup_task_logger,
    worker_process_init,
    worker_ready,
)

from app.application.events import dispatcher
from app.application.use_cases.generate_invoices import GenerateInvoiceBatchUseCase
from app.application.use_cases.process_payment import ProcessPaidInvoiceUseCase
from app.infra.adapters.starkbank_adapter.billing_adapter import StarkBankBillingAdapter
from app.infra.adapters.starkbank_adapter.client import init_starkbank
from app.infra.adapters.starkbank_adapter.transfer_adapter import (
    StarkBankTransferAdapter,
)
from app.infra.config import settings
from app.infra.database import AsyncSessionLocal, engine
from app.infra.observability import (
    instrument_worker,
    logger,
    set_lifecycle_end_timestamp,
    set_next_run_timestamp,
    setup_celery_logging,
    setup_logging,
    setup_metrics,
    setup_tracing,
)
from app.infra.repositories.payment_repo import PaymentRepository

setup_logging()

app = Celery(
    "payment_orchestrator",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    worker_max_tasks_per_child=settings.worker_max_tasks_per_child,
    task_queues={
        "webhooks": {
            "exchange": "webhooks",
            "routing_key": "webhooks",
            "queue_arguments": {
                "x-dead-letter-exchange": "webhooks_dlq",
                "x-dead-letter-routing-key": "webhooks_dlq",
            },
        },
        "billing": {
            "exchange": "billing",
            "routing_key": "billing",
            "queue_arguments": {
                "x-dead-letter-exchange": "billing_dlq",
                "x-dead-letter-routing-key": "billing_dlq",
            },
        },
        "webhooks_dlq": {"exchange": "webhooks_dlq", "routing_key": "webhooks_dlq"},
        "billing_dlq": {"exchange": "billing_dlq", "routing_key": "billing_dlq"},
    },
    task_routes={
        "app.infra.worker.process_webhook_event_task": {"queue": "webhooks"},
        "app.infra.worker.generate_invoices_task": {"queue": "billing"},
    },
    task_default_queue="webhooks",
)

after_setup_logger.connect(setup_celery_logging)
after_setup_task_logger.connect(setup_celery_logging)


@worker_process_init.connect
def init_worker(**kwargs):
    """
    Inicializa recursos por processo do worker Celery.
    Garante pools de conexão frescos e instrumentação ativa.
    """
    engine.sync_engine.dispose()
    setup_tracing()
    setup_metrics()
    instrument_worker()
    init_starkbank()
    logger.info("Worker process initialized with fresh resources.")


@worker_ready.connect
def on_worker_ready(sender, **kwargs):
    """
    Bootstrap do worker quando o processo está pronto.
    Dispara a cadeia inicial de faturas se o agendamento estiver habilitado.
    """
    if not settings.generate_invoices_enabled:
        logger.info(
            "SCHEDULER: Agendamento automático desabilitado via configuração (on_worker_ready ignorado)."
        )
        return

    try:
        r = redis.from_url(settings.redis_url)
        lock_key = "lock:generate_invoices_initial_chain"
        if r.set(lock_key, "locked", ex=settings.bootstrap_lock_ttl, nx=True):
            logger.info("BOOTSTRAP: Disparando cadeia inicial de faturas...")
            generate_invoices_task.delay()
    except Exception as e:
        logger.error(f"BOOTSTRAP: Erro ao iniciar cadeia no Redis: {e}")


def _run_async(coro):
    """
    Executa uma corotina em um ambiente síncrono (Celery).
    Suporta loops já em execução através de nest_asyncio.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    else:
        import nest_asyncio

        nest_asyncio.apply()
        return loop.run_until_complete(coro)


@app.task(bind=True, retry_backoff=True, max_retries=settings.webhook_max_retries)
def process_webhook_event_task(
    self,
    source: str,
    event_type: str,
    external_event_id: str,
    external_invoice_id: str,
    amount: int,
    fee: int,
    internal_id: str | None = None,
    raw_payload: dict[str, Any] | None = None,
):
    """
    Tarefa Celery para processar eventos de webhook.
    """
    try:
        success = _run_async(
            _run_process_webhook(
                source=source,
                event_type=event_type,
                external_event_id=external_event_id,
                external_invoice_id=external_invoice_id,
                amount=amount,
                fee=fee,
                internal_id=internal_id,
                raw_payload=raw_payload,
            )
        )
        if not success:
            raise RuntimeError(
                f"Falha ao processar webhook {external_event_id}: Fatura não encontrada ou erro de negócio."
            )
    except Exception as exc:
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError as retry_exc:
            logger.critical(
                f"DLQ_TRIGGER: Webhook {external_event_id} falhou após retries."
            )
            raise Reject(reason=str(exc), requeue=False) from retry_exc


async def _run_process_webhook(*args, **kwargs) -> bool:
    """
    Lógica assíncrona para processamento de webhooks.
    """
    async with AsyncSessionLocal() as session:
        try:
            repo = PaymentRepository(session)
            transfer_gateway = StarkBankTransferAdapter()
            use_case = ProcessPaidInvoiceUseCase(repo, repo, repo, transfer_gateway)
            success, event = await use_case.execute(*args, **kwargs)
            if success:
                await session.commit()
                if event:
                    dispatcher.dispatch(event)
                return True
            await session.rollback()
            return False
        except Exception as e:
            await session.rollback()
            event_id = kwargs.get("external_event_id")
            logger.error(f"Erro no worker ao processar webhook {event_id}: {str(e)}")
            raise


@app.task(bind=True, retry_backoff=True, max_retries=settings.billing_max_retries)
def generate_invoices_task(self, start_time: float | None = None):
    """
    Tarefa Celery para geração periódica de faturas (Self-chaining).
    Respeita o ciclo de vida definido e agenda a próxima execução se habilitado.
    """
    if not settings.generate_invoices_enabled:
        logger.info(
            "SCHEDULER: Execução automática ignorada (generate_invoices_enabled=False)."
        )
        return

    if start_time is None:
        start_time = time.time()

    elapsed_hours = (time.time() - start_time) / 3600
    lifecycle_end = start_time + settings.lifecycle_hours * 3600
    set_lifecycle_end_timestamp(lifecycle_end)

    if elapsed_hours >= settings.lifecycle_hours:
        logger.info(
            f"LIFECYCLE: Ciclo de vida de {settings.lifecycle_hours}h atingido. Interrompendo agendamento automático."
        )
        return

    try:
        _run_async(_run_generate_invoices())
    except Exception as exc:
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError as retry_exc:
            logger.critical("DLQ_TRIGGER: Geração de faturas falhou permanentemente.")
            raise Reject(reason=str(exc), requeue=False) from retry_exc
    finally:
        if settings.generate_invoices_enabled and self.request.retries == 0:
            interval_sec = (
                settings.batch_interval_minutes * 60
                if settings.batch_interval_minutes > 0
                else settings.batch_interval_hours * 3600
            )
            next_run = time.time() + interval_sec
            set_next_run_timestamp(next_run)
            logger.info(f"SCHEDULER: Agendando próximo batch em {interval_sec}s.")
            generate_invoices_task.apply_async(
                kwargs={"start_time": start_time}, countdown=interval_sec
            )


async def _run_generate_invoices() -> None:
    """
    Lógica assíncrona para geração do lote de faturas.
    Pode ser executada manualmente mesmo se o agendador automático estiver desligado.
    """
    async with AsyncSessionLocal() as session:
        repo = PaymentRepository(session)
        billing = StarkBankBillingAdapter()
        use_case = GenerateInvoiceBatchUseCase(repo, billing)
        _, event = await use_case.execute()
        await session.commit()
        dispatcher.dispatch(event)
