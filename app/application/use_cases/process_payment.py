from typing import Any

from app.application.ports.repo import (
    InvoiceRepository,
    TransferRepository,
    WebhookEventRepository,
)
from app.application.ports.transfer import TransferGateway
from app.domain.entities.invoice import Invoice, InvoiceStatus
from app.domain.entities.transfer import Transfer, TransferStatus
from app.domain.events import PaymentProcessed
from app.domain.value_objects.money import Money
from app.infra.observability import logger


class ProcessPaidInvoiceUseCase:
    """
    Caso de Uso: Processar Fatura Paga.
    """

    def __init__(
        self,
        invoice_repo: InvoiceRepository,
        transfer_repo: TransferRepository,
        webhook_repo: WebhookEventRepository,
        transfer_gateway: TransferGateway,
    ):
        self.invoice_repo = invoice_repo
        self.transfer_repo = transfer_repo
        self.webhook_repo = webhook_repo
        self.transfer_gateway = transfer_gateway

    async def execute(
        self,
        source: str,
        event_type: str,
        external_event_id: str,
        external_invoice_id: str,
        amount: int,
        fee: int | None,
        internal_id: str | None = None,
        raw_payload: dict[str, Any] | None = None,
    ) -> tuple[bool, PaymentProcessed | None]:
        if not await self.webhook_repo.log_webhook_event(
            source, event_type, external_event_id, raw_payload
        ):
            logger.info(f"Evento {external_event_id} já processado (idempotência).")
            return True, None

        invoice = await self._find_invoice(external_invoice_id, internal_id)
        if not invoice:
            logger.error(
                "Fatura não encontrada",
                extra={
                    "external_invoice_id": external_invoice_id,
                    "event_id": external_event_id,
                },
            )
            return False, None

        if event_type not in ["credited", "paid"]:
            return True, None

        target_status = (
            InvoiceStatus.PAID if event_type == "paid" else InvoiceStatus.CREDITED
        )

        try:
            await self._update_invoice_status(invoice, target_status, event_type)

            if event_type != "credited":
                return True, None

            return await self._orchestrate_transfer(
                invoice, amount, fee, source, external_event_id
            )

        except Exception as e:
            logger.error(
                "Erro na orquestração financeira",
                extra={"invoice_id": invoice.id, "error": str(e)},
            )
            raise

    async def _find_invoice(
        self, external_invoice_id: str, internal_id: str | None
    ) -> Invoice | None:
        invoice = await self.invoice_repo.get_invoice_by_external_id(
            external_invoice_id, for_update=True
        )
        if not invoice and internal_id:
            clean_id = internal_id
            if ":" in clean_id:
                clean_id = clean_id.split(":")[-1]
            if clean_id.startswith("inv_"):
                clean_id = clean_id.replace("inv_", "")

            invoice = await self.invoice_repo.get_invoice_by_id(clean_id)
        return invoice

    async def _update_invoice_status(
        self, invoice: Invoice, target_status: InvoiceStatus, event_type: str
    ) -> None:
        old_status = invoice.status
        logger.info(
            f"Orquestrando transição: {old_status.value} -> {target_status.value}",
            extra={"invoice_id": invoice.id, "event": event_type},
        )
        invoice.transition_to(target_status)
        await self.invoice_repo.save_invoice(invoice)

    async def _orchestrate_transfer(
        self,
        invoice: Invoice,
        amount: int,
        fee: int | None,
        source: str,
        external_event_id: str,
    ) -> tuple[bool, PaymentProcessed | None]:
        safe_fee = fee if fee is not None else 0
        liquid_amount = max(0, amount - safe_fee)

        existing_transfer = await self.transfer_repo.get_transfer_by_invoice_id(
            invoice.id
        )
        if existing_transfer:
            logger.info(
                "Repasse já processado anteriormente",
                extra={"invoice_id": invoice.id, "transfer_id": existing_transfer.id},
            )
            return True, None

        if liquid_amount == 0:
            logger.info("Valor líquido zero, skipping repasse")
            return True, None

        transfer = Transfer(
            invoice_id=invoice.id,
            external_id=f"tr_{invoice.external_id}",
            amount=Money(liquid_amount),
            fee=Money(safe_fee),
            status=TransferStatus.CREATED,
        )

        await self.transfer_repo.save_transfer(transfer)

        logger.info(
            "Iniciando chamada ao gateway Stark Bank",
            extra={"invoice_id": invoice.id, "transfer_id": transfer.id},
        )
        executed_transfer = await self.transfer_gateway.execute_transfer(transfer)
        executed_transfer.status = TransferStatus.SUCCESS

        await self.transfer_repo.save_transfer(executed_transfer)
        await self.webhook_repo.update_webhook_event_transfer(
            source, external_event_id, executed_transfer.id
        )

        logger.info(
            "Status final: Repasse concluído com sucesso",
            extra={
                "invoice_id": invoice.id,
                "external_transfer_id": executed_transfer.external_id,
            },
        )

        return True, PaymentProcessed(
            invoice_id=invoice.id,
            transfer_id=executed_transfer.id,
            amount=liquid_amount,
            external_id=executed_transfer.external_id,
            fee=safe_fee,
        )
