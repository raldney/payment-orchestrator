"""initial_schema

Revision ID: acd29fa7b85d
Revises: 
Create Date: 2026-04-06 03:38:16.376056

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'acd29fa7b85d'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Criação manual dos tipos ENUM para garantir compatibilidade nativa Postgres
    op.execute("CREATE TYPE invoice_status_enum AS ENUM ('created', 'pending', 'paid', 'credited', 'overdue', 'expired', 'canceled', 'failed')")
    op.execute("CREATE TYPE transfer_status_enum AS ENUM ('created', 'processing', 'success', 'failed')")

    op.create_table('invoices',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('external_id', sa.String(length=255), nullable=True),
    sa.Column('amount', sa.Integer(), nullable=False),
    sa.Column('tax_id', sa.String(length=14), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('status', postgresql.ENUM('created', 'pending', 'paid', 'credited', 'overdue', 'expired', 'canceled', 'failed', name='invoice_status_enum', create_type=False), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_invoices_external_id'), 'invoices', ['external_id'], unique=True)
    op.create_index('ix_invoices_status_created_at', 'invoices', ['status', 'created_at'], unique=False)
    op.create_index(op.f('ix_invoices_tax_id'), 'invoices', ['tax_id'], unique=False)
    
    op.create_table('transfers',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('invoice_id', sa.UUID(), nullable=False),
    sa.Column('external_id', sa.String(length=255), nullable=True),
    sa.Column('amount', sa.Integer(), nullable=False),
    sa.Column('fee', sa.Integer(), nullable=True),
    sa.Column('status', postgresql.ENUM('created', 'processing', 'success', 'failed', name='transfer_status_enum', create_type=False), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('invoice_id', name='uq_transfer_per_invoice')
    )
    op.create_index(op.f('ix_transfers_external_id'), 'transfers', ['external_id'], unique=True)
    op.create_index(op.f('ix_transfers_invoice_id'), 'transfers', ['invoice_id'], unique=False)
    op.create_index('ix_transfers_status_created_at', 'transfers', ['status', 'created_at'], unique=False)
    
    op.create_table('webhook_events',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('source', sa.String(length=64), nullable=False),
    sa.Column('event_type', sa.String(length=128), nullable=False),
    sa.Column('external_event_id', sa.String(length=255), nullable=False),
    sa.Column('raw_payload', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('transfer_id', sa.UUID(), nullable=True),
    sa.Column('processed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['transfer_id'], ['transfers.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('source', 'external_event_id', name='uq_webhook_source_external_id')
    )
    op.create_index(op.f('ix_webhook_events_event_type'), 'webhook_events', ['event_type'], unique=False)
    op.create_index('ix_webhook_events_processed_at', 'webhook_events', ['processed_at'], unique=False)
    op.create_index(op.f('ix_webhook_events_transfer_id'), 'webhook_events', ['transfer_id'], unique=False)


def downgrade() -> None:
    op.drop_table('webhook_events')
    op.drop_table('transfers')
    op.drop_table('invoices')
    op.execute("DROP TYPE IF EXISTS transfer_status_enum")
    op.execute("DROP TYPE IF EXISTS invoice_status_enum")
