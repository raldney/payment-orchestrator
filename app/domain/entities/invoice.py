from dataclasses import dataclass, field
from enum import Enum
from uuid import UUID, uuid7

from app.domain.exceptions import DomainException
from app.domain.value_objects.money import Money


class InvoiceStatus(str, Enum):
    PENDING = "pending"
    PAID = "paid"
    CREDITED = "credited"
    FAILED = "failed"
    EXPIRED = "expired"

@dataclass
class Invoice:
    external_id: str
    amount: Money
    tax_id: str
    name: str
    status: InvoiceStatus = InvoiceStatus.PENDING
    id: UUID = field(default_factory=uuid7)

    def __post_init__(self):
        """Sanitiza o tax_id para garantir que contenha apenas números."""
        self.tax_id = "".join(filter(str.isdigit, self.tax_id))

    _ALLOWED_TRANSITIONS = {
        InvoiceStatus.PENDING: {InvoiceStatus.PAID, InvoiceStatus.CREDITED, InvoiceStatus.EXPIRED, InvoiceStatus.FAILED},
        InvoiceStatus.PAID: {InvoiceStatus.CREDITED, InvoiceStatus.FAILED},
        InvoiceStatus.CREDITED: set(),
        InvoiceStatus.FAILED: {InvoiceStatus.PENDING, InvoiceStatus.PAID, InvoiceStatus.CREDITED},
        InvoiceStatus.EXPIRED: set(),
    }

    def transition_to(self, new_status: InvoiceStatus) -> None:
        if new_status == self.status:
            return
        allowed = self._ALLOWED_TRANSITIONS.get(self.status, set())
        if new_status not in allowed:
            raise DomainException(f"Transição inválida de {self.status.value} para {new_status.value}")
        self.status = new_status

    @property
    def is_processable(self) -> bool:
        return self.status in [InvoiceStatus.PAID, InvoiceStatus.CREDITED]
