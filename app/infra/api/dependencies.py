from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.use_cases.generate_invoices import GenerateInvoiceBatchUseCase
from app.application.use_cases.process_payment import ProcessPaidInvoiceUseCase
from app.infra.adapters.starkbank_adapter.billing_adapter import StarkBankBillingAdapter
from app.infra.adapters.starkbank_adapter.transfer_adapter import (
    StarkBankTransferAdapter,
)
from app.infra.database import get_db
from app.infra.repositories.payment_repo import PaymentRepository


async def get_process_payment_usecase(session: AsyncSession=Depends(get_db)) -> ProcessPaidInvoiceUseCase:
    repo = PaymentRepository(session)
    transfer_gateway = StarkBankTransferAdapter()
    return ProcessPaidInvoiceUseCase(invoice_repo=repo, transfer_repo=repo, webhook_repo=repo, transfer_gateway=transfer_gateway)

async def get_generate_invoices_usecase(session: AsyncSession=Depends(get_db)) -> GenerateInvoiceBatchUseCase:
    repo = PaymentRepository(session)
    billing_gateway = StarkBankBillingAdapter()
    return GenerateInvoiceBatchUseCase(repo=repo, billing=billing_gateway)
