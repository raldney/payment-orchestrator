import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.domain.entities.transfer import Transfer, TransferStatus
from app.domain.value_objects.money import Money
from app.infra.adapters.starkbank_adapter.transfer_adapter import (
    StarkBankTransferAdapter,
)


@pytest.mark.asyncio
async def test_starkbank_transfer_adapter_uses_liquid_amount():
    """
    Valida se o adaptador envia o valor líquido correto para o SDK do Stark Bank.

    O valor 'amount' passado ao SDK deve ser o valor líquido (já descontado da taxa).
    """
    adapter = StarkBankTransferAdapter()
    transfer = Transfer(
        id=uuid.uuid7(),
        invoice_id=uuid.uuid7(),
        external_id="tr_001",
        amount=Money(900),
        fee=Money(100),
        status=TransferStatus.CREATED,
    )

    with patch("starkbank.transfer.create") as mock_create:
        mock_transfer_obj = MagicMock()
        mock_transfer_obj.id = "stark_tr_123"
        mock_create.return_value = [mock_transfer_obj]

        result = await adapter.execute_transfer(transfer)

        args, _ = mock_create.call_args
        stark_item = args[0][0]

        assert stark_item.amount == 900
        assert result.external_id == "stark_tr_123"
