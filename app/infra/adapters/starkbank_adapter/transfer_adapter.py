import starkbank

from app.application.ports.transfer import TransferGateway
from app.domain.entities.transfer import Transfer
from app.infra.config import settings


class StarkBankTransferAdapter(TransferGateway):
    """
    Adaptador para repasses via Stark Bank (Transfer).

    Converte a entidade de domínio Transfer para o formato esperado pelo SDK
    e executa a operação financeira no ambiente configurado.
    """

    async def execute_transfer(self, transfer: Transfer) -> Transfer:
        """
        Executa uma transferência no Stark Bank.
        """
        from app.infra.observability import logger

        logger.info(
            "Executing Stark Bank transfer",
            extra={
                "amount": transfer.amount.amount,
                "invoice_id": transfer.invoice_id,
                "transfer_id": transfer.id,
            },
        )

        stark_transfer = starkbank.Transfer(
            amount=transfer.amount.amount,
            tax_id=settings.sandbox_tax_id,
            name="Stark Bank Sandbox User",
            bank_code=settings.sandbox_bank_code,
            branch_code=settings.sandbox_branch_code,
            account_number=settings.sandbox_account_number,
            account_type=settings.sandbox_account_type,
            tags=[f"transfer_{transfer.id}", f"invoice_{transfer.invoice_id}"],
        )

        created = starkbank.transfer.create([stark_transfer])[0]

        logger.info(
            "Stark Bank transfer created successfully",
            extra={
                "external_id": created.id,
                "status": created.status,
                "amount": created.amount,
            },
        )

        transfer.external_id = created.id

        return transfer
