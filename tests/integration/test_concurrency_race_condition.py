import asyncio
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.application.use_cases.process_payment import ProcessPaidInvoiceUseCase
from app.domain.entities.invoice import InvoiceStatus


@pytest.mark.asyncio
async def test_race_condition_locks_multiple_identical_webhooks(
    mock_invoice_repo,
    mock_transfer_repo,
    mock_webhook_repo,
    mock_transfer_gateway,
    make_invoice,
):
    """
    Simula uma condição de corrida (Race Condition) com múltiplos webhooks idênticos.

    O teste garante que apenas a primeira execução prospere, enquanto as demais
    são bloqueadas pelo mecanismo de idempotência no repositório de webhooks.
    """
    event_id = "evt_duplicate_test"
    external_invoice_id = "stark_inv_id_123"

    use_case = ProcessPaidInvoiceUseCase(
        invoice_repo=mock_invoice_repo,
        transfer_repo=mock_transfer_repo,
        webhook_repo=mock_webhook_repo,
        transfer_gateway=mock_transfer_gateway,
    )

    invoice_mock = make_invoice(
        external_id=external_invoice_id, status=InvoiceStatus.PENDING
    )
    mock_invoice_repo.get_invoice_by_external_id.return_value = invoice_mock
    mock_transfer_repo.get_transfer_by_invoice_id.return_value = None
    lock_results = [True, False, False, False, False]

    async def mock_log_webhook_event(
        source: str,
        event_type: str,
        external_event_id: str,
        raw_payload: dict[str, Any] | None = None,
    ) -> bool:
        """Simula comportamento atômico de ON CONFLICT DO NOTHING."""
        return lock_results.pop(0) if lock_results else False

    mock_webhook_repo.log_webhook_event = AsyncMock(side_effect=mock_log_webhook_event)

    tasks = [
        use_case.execute(
            source="starkbank",
            event_type="credited",
            external_event_id=event_id,
            external_invoice_id=external_invoice_id,
            amount=1000,
            fee=10,
            raw_payload={"event": "credited"},
        )
        for _ in range(5)
    ]

    results = await asyncio.gather(*tasks)

    assert all(r[0] for r in results) is True
    assert mock_transfer_gateway.execute_transfer.call_count == 1
    assert mock_invoice_repo.save_invoice.call_count == 1
    assert invoice_mock.status == InvoiceStatus.CREDITED
