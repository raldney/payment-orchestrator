from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID

from app.domain.entities.invoice import Invoice
from app.domain.entities.transfer import Transfer


class InvoiceRepository(ABC):
    """
    Porta de Saída (Output Port) para persistência de Faturas.
    Define as operações atômicas necessárias para o domínio.
    """
    @abstractmethod
    async def save_invoice(self, invoice: Invoice) -> Invoice:
        """Persiste uma nova fatura ou atualiza uma existente."""
        pass

    @abstractmethod
    async def get_invoice_by_id(self, invoice_id: UUID | str) -> Invoice | None:
        """Recupera uma fatura pelo seu UUID interno."""
        pass

    @abstractmethod
    async def get_invoice_by_external_id(self, external_id: str, for_update: bool = False) -> Invoice | None:
        """
        Busca uma fatura pelo ID externo (Stark Bank).
        Se for_update=True, realiza o bloqueio pessimista (SELECT FOR UPDATE) do registro.
        """
        pass

class TransferRepository(ABC):
    """Gerencia a persistência de transferências e vinculação com faturas."""
    @abstractmethod
    async def save_transfer(self, transfer: Transfer) -> Transfer: pass

    @abstractmethod
    async def get_transfer_by_invoice_id(self, invoice_id: UUID) -> Transfer | None: pass

class WebhookEventRepository(ABC):
    """Audit Log e Idempotência de Webhooks."""
    @abstractmethod
    async def log_webhook_event(self, source: str, event_type: str, external_event_id: str, raw_payload: dict[str, Any] | None = None) -> bool:
        """Registra e verifica idempotência. Retorna True se o evento for novo."""
        pass

    @abstractmethod
    async def update_webhook_event_transfer(self, source: str, external_event_id: str, transfer_id: UUID) -> None:
        """Vincula o evento original ao repasse realizado para auditoria completa."""
        pass
