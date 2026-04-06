from abc import ABC, abstractmethod

from app.domain.entities.invoice import Invoice


class BillingGateway(ABC):

    @abstractmethod
    async def create_invoices(self, invoices: list[Invoice]) -> list[Invoice]:
        """Cria um lote de faturas no provedor externo."""
        pass
