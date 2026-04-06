import starkbank

from app.application.ports.billing import BillingGateway
from app.domain.entities.invoice import Invoice, InvoiceStatus


class StarkBankBillingAdapter(BillingGateway):
    """
    Adaptador para o serviço de cobrança (Invoices) do Stark Bank.
    Converte as entidades de domínio para o formato esperado pelo SDK.
    """

    async def create_invoices(self, invoices: list[Invoice]) -> list[Invoice]:
        """Cria múltiplas faturas no Stark Bank e retorna com IDs externos preenchidos."""
        stark_invoices = [
            starkbank.Invoice(
                amount=inv.amount.amount,
                tax_id=inv.tax_id,
                name=inv.name,
                due=None,
                tags=[str(inv.id)],
            )
            for inv in invoices
        ]

        created = starkbank.invoice.create(stark_invoices)

        for domain_inv, stark_inv in zip(invoices, created):
            domain_inv.external_id = stark_inv.id
            domain_inv.status = InvoiceStatus.PENDING

        return invoices
