"""create idempotency_records table (Phase 5 Platform Resilience)

Revision ID: 20261101_0004
Revises: 20261101_0003
Create Date: 2026-11-01 04:00:01

Creates idempotency_records table to enforce at-most-once semantics,
prevent duplicate uploads, guard against concurrent updates, and enable replay.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20261101_0004"
down_revision: Union[str, None] = "20261101_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "idempotency_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("business_id", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("operation_type", sa.String(length=64), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="PROCESSING"),
        sa.Column("response_payload", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_idempotency_records"),
        sa.UniqueConstraint("business_id", "idempotency_key", name="uq_idempotency_business_key"),
    )
    op.create_index("ix_idempotency_business_id", "idempotency_records", ["business_id"])
    op.create_index("ix_idempotency_key", "idempotency_records", ["idempotency_key"])


def downgrade() -> None:
    op.drop_index("ix_idempotency_key", table_name="idempotency_records")
    op.drop_index("ix_idempotency_business_id", table_name="idempotency_records")
    op.drop_table("idempotency_records")
