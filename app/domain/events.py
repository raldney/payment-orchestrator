import uuid
from dataclasses import dataclass

from app.application.events import DomainEvent


@dataclass
class InvoicesGenerated(DomainEvent):
    count: int
    total_amount: int


@dataclass
class PaymentProcessed(DomainEvent):
    invoice_id: uuid.UUID
    transfer_id: uuid.UUID
    amount: int
    external_id: str
    fee: int
