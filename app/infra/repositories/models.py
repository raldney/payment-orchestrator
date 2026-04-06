import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    TypeDecorator,
    UniqueConstraint,
    func,
)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.entities.invoice import InvoiceStatus
from app.domain.entities.transfer import TransferStatus
from app.infra.repositories.base import Base

if TYPE_CHECKING:
    pass


def gen_uuid7() -> uuid.UUID:
    return uuid.uuid7()


class EnumValueType(TypeDecorator):
    impl = String
    cache_ok = True

    def __init__(self, enum_class, pg_type_name: str):
        super().__init__()
        self.enum_class = enum_class
        self.pg_type_name = pg_type_name

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(
                SQLEnum(
                    *[e.value for e in self.enum_class],
                    name=self.pg_type_name,
                    native_enum=True,
                    create_type=False,
                )
            )
        return dialect.type_descriptor(String())

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return value.value if hasattr(value, "value") else str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        raw = value.value if hasattr(value, "value") else str(value).lower()
        return self.enum_class(raw)


class InvoiceModel(Base):
    __tablename__ = "invoices"
    __table_args__ = (Index("ix_invoices_status_created_at", "status", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=gen_uuid7
    )
    external_id: Mapped[str | None] = mapped_column(
        String(255), unique=True, index=True, nullable=True
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    tax_id: Mapped[str] = mapped_column(String(14), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[InvoiceStatus] = mapped_column(
        EnumValueType(InvoiceStatus, pg_type_name="invoice_status_enum"),
        nullable=False,
        default=InvoiceStatus.PENDING,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    transfers: Mapped[list["TransferModel"]] = relationship(
        "TransferModel", back_populates="invoice", lazy="selectin"
    )

    def __repr__(self) -> str:
        return (
            f"<InvoiceModel id={self.id!r} "
            f"status={self.status.value!r} amount={self.amount}>"
        )


class TransferModel(Base):
    __tablename__ = "transfers"
    __table_args__ = (
        UniqueConstraint("invoice_id", name="uq_transfer_per_invoice"),
        Index("ix_transfers_status_created_at", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=gen_uuid7
    )
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("invoices.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    external_id: Mapped[str | None] = mapped_column(
        String(255), unique=True, index=True, nullable=True
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    fee: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[TransferStatus] = mapped_column(
        EnumValueType(TransferStatus, pg_type_name="transfer_status_enum"),
        nullable=False,
        default=TransferStatus.CREATED,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    invoice: Mapped["InvoiceModel"] = relationship(
        "InvoiceModel", back_populates="transfers"
    )
    webhook_events: Mapped[list["WebhookEventModel"]] = relationship(
        "WebhookEventModel", back_populates="transfer", lazy="selectin"
    )

    def __repr__(self) -> str:
        return (
            f"<TransferModel id={self.id!r} invoice_id={self.invoice_id!r} "
            f"status={self.status.value!r} amount={self.amount}>"
        )


class WebhookEventModel(Base):
    __tablename__ = "webhook_events"
    __table_args__ = (
        UniqueConstraint(
            "source", "external_event_id", name="uq_webhook_source_external_id"
        ),
        Index("ix_webhook_events_processed_at", "processed_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=gen_uuid7
    )
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    event_type: Mapped[str] = mapped_column(String(128), nullable=True)
    external_event_id: Mapped[str] = mapped_column(String(255), nullable=False)
    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    transfer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("transfers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        name="processed_at",
        nullable=False,
        default=func.now(),
        server_default=func.now(),
    )

    transfer: Mapped["TransferModel"] = relationship(
        "TransferModel", back_populates="webhook_events", lazy="selectin"
    )

    def __repr__(self) -> str:
        return (
            f"<WebhookEventModel id={self.id!r} source={self.source!r} "
            f"external_event_id={self.external_event_id!r}>"
        )
