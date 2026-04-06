from dataclasses import dataclass, field
from enum import Enum
from uuid import UUID, uuid7

from app.domain.value_objects.money import Money


class TransferStatus(str, Enum):
    """Estados do ciclo de vida da transferência (Repasse)."""
    CREATED = "created"
    SUCCESS = "success"
    FAILED = "failed"

@dataclass
class Transfer:
    """
    Entidade Transferência - Representa um repasse financeiro executado.
    Vinculada a uma Fatura (invoice_id).
    """
    invoice_id: UUID
    external_id: str
    amount: Money
    fee: Money
    status: TransferStatus = TransferStatus.CREATED
    id: UUID = field(default_factory=uuid7)

    @property
    def total_cost(self) -> Money:
        """Custo total da transferência (Valor Líquido + Taxa)."""
        return self.amount + self.fee
