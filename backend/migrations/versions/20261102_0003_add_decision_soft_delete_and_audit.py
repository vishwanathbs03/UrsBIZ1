"""add soft delete and audit history to business_decisions (Audit Item D)

Revision ID: 20261102_0003
Revises: 20261102_0002
Create Date: 2026-11-02 21:50:00

Adds soft deletion columns and audit history to business_decisions:
  - is_deleted (boolean flag)
  - deleted_at (timestamp)
  - deleted_by_id (FK to users)
  - cancellation_reason (explanation for cancellation)
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20261102_0003"
down_revision: Union[str, None] = "20261102_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("business_decisions") as batch_op:
        batch_op.add_column(sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("deleted_by_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("cancellation_reason", sa.Text(), nullable=True))
        batch_op.create_index("ix_business_decisions_is_deleted", ["is_deleted"])
        batch_op.create_foreign_key(
            "fk_business_decisions_deleted_by_id",
            "users",
            ["deleted_by_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("business_decisions") as batch_op:
        batch_op.drop_constraint("fk_business_decisions_deleted_by_id", type_="foreignkey")
        batch_op.drop_index("ix_business_decisions_is_deleted")
        batch_op.drop_column("cancellation_reason")
        batch_op.drop_column("deleted_by_id")
        batch_op.drop_column("deleted_at")
        batch_op.drop_column("is_deleted")
