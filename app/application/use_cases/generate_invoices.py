import random

from faker import Faker

from app.application.ports.billing import BillingGateway
from app.application.ports.repo import InvoiceRepository
from app.domain.entities.invoice import Invoice, InvoiceStatus
from app.domain.events import InvoicesGenerated
from app.domain.value_objects.money import Money
from app.infra.config import settings


class GenerateInvoiceBatchUseCase:
    """
    Caso de Uso: Geração de Lote de Faturas.

    Responsável por automatizar a criação de faturas aleatórias para o ambiente
    de Sandbox do Stark Bank, permitindo alimentar o fluxo de orquestração financeira.
    """
    def __init__(self, repo: InvoiceRepository, billing: BillingGateway):
        """
        Inicializa o caso de uso.

        Args:
            repo: Repositório para persistência local das faturas.
            billing: Gateway para criação das faturas no provedor externo.
        """
        self.repo = repo
        self.billing = billing
        self.faker = Faker('pt_BR')

    async def execute(
        self,
        count: int | None = None,
        min_size: int | None = None,
        max_size: int | None = None
    ) -> tuple[list[Invoice], InvoicesGenerated]:
        """
        Gera e persiste um lote de faturas aleatórias.

        Args:
            count: Quantidade exata de faturas a gerar.
            min_size: Tamanho mínimo do lote (se count for None).
            max_size: Tamanho máximo do lote (se count for None).

        Returns:
            Uma tupla contendo a lista de faturas criadas e o evento de domínio.
        """
        if count is None:
            min_s = min_size if min_size is not None else settings.batch_size_min
            max_s = max_size if max_size is not None else settings.batch_size_max
            count = random.randint(min_s, max_s)

        invoices = []
        total_amount = 0

        for _ in range(count):
            amount_val = random.randint(settings.batch_amount_min, settings.batch_amount_max)
            amount = Money(amount_val)

            invoice = Invoice(
                external_id="",
                amount=amount,
                tax_id=self.faker.cpf(),
                name=self.faker.name(),
                status=InvoiceStatus.PENDING,
            )
            invoices.append(invoice)
            total_amount += amount.amount

        external_invoices = await self.billing.create_invoices(invoices)

        for inv in external_invoices:
            await self.repo.save_invoice(inv)

        return external_invoices, InvoicesGenerated(count=len(external_invoices), total_amount=total_amount)
