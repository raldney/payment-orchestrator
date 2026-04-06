from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.application.use_cases.generate_invoices import GenerateInvoiceBatchUseCase
from app.application.use_cases.process_payment import ProcessPaidInvoiceUseCase
from app.domain.entities.invoice import Invoice, InvoiceStatus
from app.domain.value_objects.money import Money
from app.infra.api.dependencies import (
    get_db,
    get_generate_invoices_usecase,
    get_process_payment_usecase,
)
from app.infra.config import settings
from app.infra.worker import app as celery_app
from app.main import app

celery_app.conf.update(task_always_eager=True, task_store_eager_result=True)


def _mock_invoice(amount: int = 2000) -> Invoice:
    return Invoice(
        id="00000000-0000-0000-0000-000000000003",
        external_id="ext_stark-api",
        amount=Money(amount),
        tax_id="529.982.247-25",
        name="API Test User",
        status=InvoiceStatus.PENDING,
    )


def _mock_generate_usecase(count: int = 8) -> AsyncMock:
    from app.domain.events import InvoicesGenerated

    mock = AsyncMock(spec=GenerateInvoiceBatchUseCase)
    invoices = [_mock_invoice() for _ in range(count)]
    event = InvoicesGenerated(count=count, total_amount=count * 2000)
    mock.execute.return_value = (invoices, event)
    return mock


class TestHealthEndpoint:
    @pytest.mark.asyncio
    async def test_health_returns_200(self, async_client: AsyncClient) -> None:
        response = await async_client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}


class TestBillingGenerateBatch:
    URL = "/v1/billing/generate-batch"

    @pytest.mark.asyncio
    async def test_success_returns_invoice_list(
        self, async_client: AsyncClient
    ) -> None:
        mock_uc = _mock_generate_usecase(count=8)
        mock_db = AsyncMock()

        async def get_mock_uc():
            return mock_uc

        async def get_mock_db():
            return mock_db

        app.dependency_overrides[get_generate_invoices_usecase] = get_mock_uc
        app.dependency_overrides[get_db] = get_mock_db
        original = settings.generate_invoices_enabled
        settings.generate_invoices_enabled = True
        try:
            response = await async_client.post(self.URL)
        finally:
            settings.generate_invoices_enabled = original
            app.dependency_overrides.clear()
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "success"
        assert len(body["invoices"]) == 8


class TestWebhookEndpoint:
    URL = "/v1/webhooks/starkbank"
    BODY = '{"event": "invoice.paid"}'

    def _invoice_event(
        self,
        event_type: str = "credited",
        event_id: str = "evt_01",
        invoice_id: str = "ext_stark-001",
        amount: int = 2000,
        fee: int = 50,
        tags: list[str] | None = None,
    ) -> MagicMock:
        mock_invoice = MagicMock()
        mock_invoice.id = invoice_id
        mock_invoice.amount = amount
        mock_invoice.fee = fee
        mock_invoice.tags = tags or []
        mock_event = MagicMock()
        mock_event.id = event_id
        mock_event.subscription = "invoice"
        mock_event.log.type = event_type
        mock_event.log.invoice = mock_invoice
        return mock_event

    @pytest.mark.asyncio
    async def test_missing_signature_returns_400(
        self, async_client: AsyncClient
    ) -> None:
        response = await async_client.post(self.URL, content=self.BODY)
        assert response.status_code == 400
        assert "Missing Digital-Signature" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_invalid_signature_returns_401(
        self, async_client: AsyncClient
    ) -> None:
        import starkbank.error

        with patch("starkbank.event.parse") as mock_parse:
            mock_parse.side_effect = starkbank.error.InvalidSignatureError("bad", [])
            response = await async_client.post(
                self.URL, content=self.BODY, headers={"Digital-Signature": "tampered"}
            )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_invoice_event_queues_task(self, async_client: AsyncClient) -> None:
        mock_event = self._invoice_event(event_type="credited", amount=2000, fee=50)
        with patch(
            "app.infra.api.v1.webhooks.process_webhook_event_task.delay"
        ) as mock_task:
            try:
                with patch("starkbank.event.parse", return_value=mock_event):
                    response = await async_client.post(
                        self.URL,
                        content=self.BODY,
                        headers={"Digital-Signature": "valid-sig"},
                    )
            finally:
                app.dependency_overrides.clear()
            assert response.status_code == 200
            mock_task.assert_called_once_with(
                source="starkbank",
                event_type="credited",
                external_event_id="evt_01",
                external_invoice_id="ext_stark-001",
                amount=2000,
                fee=50,
                internal_id=None,
                raw_payload={"event": "invoice.paid"},
            )

    @pytest.mark.asyncio
    async def test_invoice_event_extracts_internal_id_from_first_tag(
        self, async_client: AsyncClient
    ) -> None:
        internal_uuid = "e7fc8ae0-e70b-4f0b-a146-9bab87688bd0"
        mock_event = self._invoice_event(tags=[internal_uuid])
        with patch(
            "app.infra.api.v1.webhooks.process_webhook_event_task.delay"
        ) as mock_task:
            try:
                with patch("starkbank.event.parse", return_value=mock_event):
                    await async_client.post(
                        self.URL,
                        content=self.BODY,
                        headers={"Digital-Signature": "valid-sig"},
                    )
            finally:
                app.dependency_overrides.clear()
            mock_task.assert_called_once()
            args, kwargs = mock_task.call_args
            assert kwargs["internal_id"] == internal_uuid

    @pytest.mark.asyncio
    async def test_duplicate_webhook_still_returns_200(
        self, async_client: AsyncClient
    ) -> None:
        mock_event = self._invoice_event()
        with patch(
            "app.infra.api.v1.webhooks.process_webhook_event_task.delay"
        ) as mock_task:
            try:
                with patch("starkbank.event.parse", return_value=mock_event):
                    r1 = await async_client.post(
                        self.URL,
                        content=self.BODY,
                        headers={"Digital-Signature": "valid-sig"},
                    )
                    r2 = await async_client.post(
                        self.URL,
                        content=self.BODY,
                        headers={"Digital-Signature": "valid-sig"},
                    )
            finally:
                app.dependency_overrides.clear()
            assert r1.status_code == 200
            assert r2.status_code == 200
            assert mock_task.call_count == 2

    @pytest.mark.asyncio
    async def test_non_invoice_subscription_returns_200_without_processing(
        self, async_client: AsyncClient
    ) -> None:
        mock_event = MagicMock()
        mock_event.id = "evt_transfer"
        mock_event.subscription = "transfer"
        mock_event.log.type = "created"
        mock_uc = AsyncMock(spec=ProcessPaidInvoiceUseCase)

        async def get_mock_uc():
            return mock_uc

        app.dependency_overrides[get_process_payment_usecase] = get_mock_uc
        try:
            with patch("starkbank.event.parse", return_value=mock_event):
                response = await async_client.post(
                    self.URL,
                    content=self.BODY,
                    headers={"Digital-Signature": "valid-sig"},
                )
        finally:
            app.dependency_overrides.clear()
        assert response.status_code == 200
        mock_uc.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_non_allowed_invoice_type_is_ignored(
        self, async_client: AsyncClient
    ) -> None:
        mock_event = self._invoice_event()
        mock_event.log.type = "updated"
        with patch(
            "app.infra.api.v1.webhooks.process_webhook_event_task.delay"
        ) as mock_task:
            try:
                with patch("starkbank.event.parse", return_value=mock_event):
                    response = await async_client.post(
                        self.URL,
                        content=self.BODY,
                        headers={"Digital-Signature": "valid-sig"},
                    )
            finally:
                app.dependency_overrides.clear()
            assert response.status_code == 200
            mock_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_unknown_invoice_returns_200_without_error(
        self, async_client: AsyncClient
    ) -> None:
        mock_event = self._invoice_event(invoice_id="ext_unknown")
        with patch(
            "app.infra.api.v1.webhooks.process_webhook_event_task.delay"
        ) as mock_task:
            try:
                with patch("starkbank.event.parse", return_value=mock_event):
                    response = await async_client.post(
                        self.URL,
                        content=self.BODY,
                        headers={"Digital-Signature": "valid-sig"},
                    )
            finally:
                app.dependency_overrides.clear()
            assert response.status_code == 200
            mock_task.assert_called_once()
