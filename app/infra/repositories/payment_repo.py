from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.invoice import Invoice, InvoiceStatus
from app.domain.entities.transfer import Transfer, TransferStatus
from app.domain.value_objects.money import Money
from app.infra.repositories.base import SqlAlchemyRepository
from app.infra.repositories.models import InvoiceModel, TransferModel, WebhookEventModel


class PaymentRepository(SqlAlchemyRepository):
    """
    Implementação concreta do Repositório de Pagamentos usando SQLAlchemy.
    Gerencia a persistência de Invoices, Transfers e Webhooks com suporte a transações.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def save_invoice(self, invoice: Invoice) -> Invoice:
        """
        Salva ou atualiza uma fatura usando UPSERT.
        """
        stmt = (
            pg_insert(InvoiceModel)
            .values(
                id=invoice.id,
                external_id=invoice.external_id,
                amount=invoice.amount.amount,
                tax_id=invoice.tax_id,
                name=invoice.name,
                status=invoice.status.value,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            .on_conflict_do_update(
                index_elements=["external_id"],
                set_={"status": invoice.status.value, "updated_at": datetime.now(UTC)},
            )
        )
        await self.session.execute(stmt)
        return invoice

    async def get_invoice_by_external_id(
        self, external_id: str, for_update: bool = False
    ) -> Invoice | None:
        """
        Recupera uma fatura pelo ID externo, opcionalmente
        aplicando bloqueio pessimista.
        """
        stmt = select(InvoiceModel).where(InvoiceModel.external_id == external_id)
        if for_update:
            stmt = stmt.with_for_update()

        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            return None
        return Invoice(
            id=model.id,
            external_id=model.external_id,
            amount=Money(model.amount),
            tax_id=model.tax_id,
            name=model.name,
            status=InvoiceStatus(model.status),
        )

    async def get_invoice_by_id(self, invoice_id: UUID | str) -> Invoice | None:
        """
        Recupera uma fatura pelo ID interno (UUID).
        """
        if isinstance(invoice_id, str):
            invoice_id = UUID(invoice_id)
        stmt = select(InvoiceModel).where(InvoiceModel.id == invoice_id)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            return None
        return Invoice(
            id=model.id,
            external_id=model.external_id,
            amount=Money(model.amount),
            tax_id=model.tax_id,
            name=model.name,
            status=InvoiceStatus(model.status),
        )

    async def list_invoices(
        self, limit: int = 50, offset: int = 0
    ) -> list[dict[str, Any]]:
        """
        Lista faturas cadastradas no sistema.
        """
        stmt = (
            select(InvoiceModel)
            .order_by(InvoiceModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()
        return [
            {
                "id": m.id,
                "external_id": m.external_id,
                "amount": m.amount,
                "tax_id": m.tax_id,
                "name": m.name,
                "status": m.status.value,
                "created_at": m.created_at,
            }
            for m in models
        ]

    async def save_transfer(self, transfer: Transfer) -> Transfer:
        """
        Salva ou atualiza uma transferência usando UPSERT
        para evitar conflitos de chave primária.
        """
        stmt = (
            pg_insert(TransferModel)
            .values(
                id=transfer.id,
                invoice_id=transfer.invoice_id,
                external_id=transfer.external_id,
                amount=transfer.amount.amount,
                fee=transfer.fee.amount,
                status=transfer.status.value,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            .on_conflict_do_update(
                index_elements=["id"],
                set_={
                    "status": transfer.status.value,
                    "external_id": transfer.external_id,
                    "updated_at": datetime.now(UTC),
                },
            )
        )
        await self.session.execute(stmt)
        return transfer

    async def get_transfer_by_invoice_id(self, invoice_id: UUID) -> Transfer | None:
        """
        Recupera a transferência vinculada a uma fatura específica.
        """
        stmt = select(TransferModel).where(TransferModel.invoice_id == invoice_id)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            return None
        return Transfer(
            id=model.id,
            invoice_id=model.invoice_id,
            external_id=model.external_id,
            amount=Money(model.amount),
            fee=Money(model.fee),
            status=TransferStatus(model.status),
        )

    async def list_transfers(
        self, limit: int = 50, offset: int = 0
    ) -> list[dict[str, Any]]:
        """
        Lista transferências cadastradas no sistema.
        """
        stmt = (
            select(TransferModel)
            .order_by(TransferModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()
        return [
            {
                "id": m.id,
                "invoice_id": m.invoice_id,
                "external_id": m.external_id,
                "amount": m.amount,
                "fee": m.fee,
                "status": m.status.value,
                "created_at": m.created_at,
            }
            for m in models
        ]

    async def log_webhook_event(
        self,
        source: str,
        event_type: str,
        external_event_id: str,
        raw_payload: dict[str, Any] | None = None,
    ) -> bool:
        """
        Registra um evento de webhook garantindo a idempotência
        via ON CONFLICT DO NOTHING.
        """
        stmt = (
            pg_insert(WebhookEventModel)
            .values(
                source=source,
                event_type=event_type,
                external_event_id=external_event_id,
                raw_payload=raw_payload,
                received_at=datetime.now(UTC),
            )
            .on_conflict_do_nothing()
        )
        result = await self.session.execute(stmt)
        return result.rowcount > 0

    async def update_webhook_event_transfer(
        self, source: str, external_event_id: str, transfer_id: UUID
    ) -> None:
        """
        Vincula uma transferência ao evento de webhook original.
        """
        stmt = (
            update(WebhookEventModel)
            .where(
                WebhookEventModel.source == source,
                WebhookEventModel.external_event_id == external_event_id,
            )
            .values(transfer_id=transfer_id)
        )
        await self.session.execute(stmt)
