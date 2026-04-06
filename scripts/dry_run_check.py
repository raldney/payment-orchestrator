import asyncio
import os
import sys
import uuid
from unittest.mock import AsyncMock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.application.use_cases.generate_invoices import GenerateInvoiceBatchUseCase
from app.application.use_cases.process_payment import ProcessPaidInvoiceUseCase
from app.domain.entities.invoice import Invoice, InvoiceStatus
from app.domain.value_objects.money import Money


async def dry_run():
    """
    Simula uma execução completa do sistema sem dependências externas reais.
    """
    mock_repo = AsyncMock()
    mock_billing = AsyncMock()
    mock_transfer_gate = AsyncMock()
    mock_webhook_repo = AsyncMock()

    mock_billing.create_invoices.side_effect = lambda invs: invs
    mock_webhook_repo.log_webhook_event.return_value = True

    test_invoice = Invoice(
        id=uuid.uuid7(),
        external_id="stark_123",
        amount=Money(1000),
        tax_id="20018183000180",
        name="Test User",
        status=InvoiceStatus.PENDING,
    )

    mock_repo.get_invoice_by_external_id.return_value = test_invoice
    mock_repo.get_transfer_by_invoice_id.return_value = None

    gen_use_case = GenerateInvoiceBatchUseCase(repo=mock_repo, billing=mock_billing)
    print("--- Dry Run: Generating Invoices ---")
    invoices, event = await gen_use_case.execute(count=1)
    print(f"Generated {len(invoices)} invoices. Event total: {event.total_amount}")

    pay_use_case = ProcessPaidInvoiceUseCase(
        invoice_repo=mock_repo,
        transfer_repo=mock_repo,
        webhook_repo=mock_webhook_repo,
        transfer_gateway=mock_transfer_gate,
    )
    print("\n--- Dry Run: Processing Webhook (credited) ---")
    success, proc_event = await pay_use_case.execute(
        source="starkbank",
        event_type="credited",
        external_event_id="evt_test",
        external_invoice_id="stark_123",
        amount=1000,
        fee=50,
    )

    if success and proc_event:
        print(
            f"Success! Transfer ID: {proc_event.transfer_id} | Net: {proc_event.amount}"
        )
    else:
        print("Processing skipped or failed (check logs)")


if __name__ == "__main__":
    asyncio.run(dry_run())
