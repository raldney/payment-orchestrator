import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from httpx import ASGITransport

from app.domain.entities.invoice import Invoice, InvoiceStatus
from app.domain.entities.transfer import TransferStatus
from app.domain.value_objects.money import Money
from app.infra.config import settings
from app.infra.repositories.payment_repo import PaymentRepository
from app.infra.worker import app as celery_app
from app.main import app

celery_app.conf.update(
    task_always_eager=True,
    task_store_eager_result=False,
    result_backend=None,
    task_ignore_result=True,
)


@pytest.mark.asyncio
async def test_e2e_webhook_to_transfer_flow():
    original_debug = settings.debug
    settings.debug = True
    try:
        mock_db_state = {"invoices": {}, "transfers": {}}

        async def mock_save_invoice(inv):
            mock_db_state["invoices"][inv.external_id] = inv
            return inv

        async def mock_get_invoice_by_ext(ext_id, for_update=False):
            return mock_db_state["invoices"].get(ext_id)

        async def mock_get_transfer_by_inv(inv_id):
            return mock_db_state["transfers"].get(inv_id)

        async def mock_save_transfer(tr):
            mock_db_state["transfers"][tr.invoice_id] = tr
            return tr

        with (
            patch(
                "app.infra.repositories.payment_repo.PaymentRepository.save_invoice",
                side_effect=mock_save_invoice,
            ),
            patch(
                "app.infra.repositories.payment_repo.PaymentRepository.get_invoice_by_external_id",
                side_effect=mock_get_invoice_by_ext,
            ),
            patch(
                "app.infra.repositories.payment_repo.PaymentRepository.get_transfer_by_invoice_id",
                side_effect=mock_get_transfer_by_inv,
            ),
            patch(
                "app.infra.repositories.payment_repo.PaymentRepository.save_transfer",
                side_effect=mock_save_transfer,
            ),
            patch(
                "app.infra.repositories.payment_repo.PaymentRepository.log_webhook_event",
                return_value=True,
            ),
            patch(
                "app.infra.repositories.payment_repo.PaymentRepository.update_webhook_event_transfer",
                return_value=None,
            ),
            patch(
                "app.infra.adapters.starkbank_adapter.transfer_adapter.StarkBankTransferAdapter.execute_transfer",
                side_effect=lambda t: t,
            ),
            patch("starkbank.event.parse") as m_parse,
            patch("app.infra.database.AsyncSessionLocal", return_value=AsyncMock()),
            patch("celery.backends.base.Backend.mark_as_done", return_value=None),
            patch("celery.backends.base.Backend.mark_as_retry", return_value=None),
            patch("celery.backends.base.Backend.mark_as_failure", return_value=None),
        ):
            mock_log = MagicMock()
            mock_log.type = "credited"
            m_parse.return_value = MagicMock(log=mock_log)
            external_invoice_id = f"e2e_inv_{uuid.uuid4().hex[:8]}"
            invoice_id = uuid.uuid7()
            invoice = Invoice(
                id=invoice_id,
                external_id=external_invoice_id,
                amount=Money(50000),
                tax_id="20.018.183/0001-80",
                name="E2E Test User",
                status=InvoiceStatus.PENDING,
            )
            repo = PaymentRepository(AsyncMock())
            await repo.save_invoice(invoice)
            webhook_payload = {
                "event": {
                    "id": f"evt_e2e_{uuid.uuid4().hex[:8]}",
                    "subscription": "invoice",
                    "created": "2026-04-06T00:00:00Z",
                    "log": {
                        "id": f"log_e2e_{uuid.uuid4().hex[:8]}",
                        "type": "credited",
                        "created": "2026-04-06T00:00:00Z",
                        "invoice": {
                            "id": external_invoice_id,
                            "amount": 50000,
                            "fee": 100,
                            "status": "paid",
                            "tags": [],
                        },
                    },
                }
            }
            async with httpx.AsyncClient(
                transport=ASGITransport(app=app), base_url="http://testserver"
            ) as client:
                response = await client.post(
                    "/v1/webhooks/starkbank",
                    json=webhook_payload,
                    headers={"X-Test-Bypass": "true", "Digital-Signature": "e2e-sig"},
                )
            assert response.status_code == 200
            db_invoice = await repo.get_invoice_by_external_id(external_invoice_id)
            assert db_invoice is not None
            assert db_invoice.status == InvoiceStatus.CREDITED
            transfer = await repo.get_transfer_by_invoice_id(db_invoice.id)
            assert transfer is not None, (
                "Transfer should have been created by the worker"
            )
            assert transfer.status == TransferStatus.SUCCESS
            assert transfer.amount.amount == 49900
            assert transfer.fee.amount == 100
            print(
                f"\n✅ E2E Flow Success: Invoice {external_invoice_id} -> "
                f"Transfer {transfer.external_id}"
            )
    finally:
        settings.debug = original_debug
