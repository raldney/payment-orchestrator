import json
import logging
from io import StringIO

import pytest

from app.application.events import dispatcher
from app.domain.events import InvoicesGenerated, PaymentProcessed
from app.infra.observability import JsonFormatter


def test_json_formatter_masks_pii():
    formatter = JsonFormatter()
    log_output = StringIO()
    handler = logging.StreamHandler(log_output)
    handler.setFormatter(formatter)
    logger = logging.getLogger('test_pii_logger')
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    test_data = {'customer_tax_id': '123.456.789-00', 'unformatted_cpf': '11122233344', 'stark_private_key': 'private-key-long-string-secret', 'customer_name': 'Joao da Silva', 'user_email': 'joao.silva@email.com', 'bank_account_number': '6341320293482496'}
    logger.info('Testing PII masking', extra=test_data)
    log_json = json.loads(log_output.getvalue())
    assert '...' in log_json['customer_tax_id']
    assert '123.' in log_json['customer_tax_id']
    assert '...' in log_json['unformatted_cpf']
    assert '1112' in log_json['unformatted_cpf']
    assert '...' in log_json['customer_name']
    assert 'Joao' in log_json['customer_name']
    assert '...' in log_json['user_email']
    assert 'com' in log_json['user_email']
    assert '...' in log_json['bank_account_number']
    for key, original_val in test_data.items():
        assert log_json[key] != original_val

def test_event_dispatcher_notifies_observers():
    call_count = 0
    received_event = None

    def dummy_handler(event: InvoicesGenerated):
        nonlocal call_count, received_event
        call_count += 1
        received_event = event
    dispatcher.subscribe(InvoicesGenerated, dummy_handler)
    test_event = InvoicesGenerated(count=10, total_amount=5000)
    dispatcher.dispatch(test_event)
    assert call_count >= 1
    assert received_event.count == 10
    assert received_event.total_amount == 5000

@pytest.mark.asyncio
async def test_async_event_dispatcher():
    """Test that the Observer pattern works with async handlers."""
    import asyncio
    import uuid
    call_count = 0

    async def async_handler(event: PaymentProcessed):
        nonlocal call_count
        await asyncio.sleep(0.01)
        call_count += 1
    dispatcher.subscribe(PaymentProcessed, async_handler)
    test_event = PaymentProcessed(invoice_id=uuid.uuid4(), transfer_id=uuid.uuid4(), amount=1000, external_id='ext_123', fee=10)
    dispatcher.dispatch(test_event)
    await asyncio.sleep(0.1)
    assert call_count >= 1
