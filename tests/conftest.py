import socket
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.infra.config import settings

settings.otel_enabled = False

_original_getaddrinfo = socket.getaddrinfo

def _mocked_getaddrinfo(*args, **kwargs):
    host = args[0]
    if 'starkbank.com' in host:
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('127.0.0.1', 443))]
    return _original_getaddrinfo(*args, **kwargs)

socket.getaddrinfo = _mocked_getaddrinfo

from app.domain.entities.invoice import Invoice, InvoiceStatus
from app.domain.entities.transfer import Transfer, TransferStatus
from app.domain.value_objects.money import Money
from app.main import app


@pytest_asyncio.fixture
async def async_client() -> AsyncClient:
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
        yield client

@pytest.fixture
def make_invoice():
    def _factory(invoice_id: str='00000000-0000-0000-0000-000000000005', external_id: str='ext_stark-001', amount: int=1000, tax_id: str='11.222.333/0001-81', name: str='Test Person', status: InvoiceStatus=InvoiceStatus.PENDING) -> Invoice:
        return Invoice(id=invoice_id, external_id=external_id, amount=Money(amount), tax_id=tax_id, name=name, status=status)
    return _factory

@pytest.fixture
def make_transfer():
    def _factory(transfer_id: str='00000000-0000-0000-0000-000000000006', invoice_id: str='00000000-0000-0000-0000-000000000005', external_id: str='ext_tr-001', amount: int=990, fee: int=10, status: TransferStatus=TransferStatus.CREATED) -> Transfer:
        return Transfer(id=transfer_id, invoice_id=invoice_id, external_id=external_id, amount=Money(amount), fee=Money(fee), status=status)
    return _factory

@pytest.fixture
def mock_invoice_repo() -> AsyncMock:
    return AsyncMock()

@pytest.fixture
def mock_transfer_repo() -> AsyncMock:
    return AsyncMock()

@pytest.fixture
def mock_webhook_repo() -> AsyncMock:
    return AsyncMock()

@pytest.fixture
def mock_billing() -> AsyncMock:
    return AsyncMock()

@pytest.fixture
def mock_transfer_gateway() -> AsyncMock:
    return AsyncMock()
