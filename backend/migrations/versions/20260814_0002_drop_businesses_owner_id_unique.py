"""drop uq_businesses_owner_id constraint (Sprint 23 multi-business support)

Revision ID: 20260814_0002
Revises: 20260814_0001
Create Date: 2026-08-14 00:00:01

Sprint 23 lifted the single-business-per-user cap to enable multiple
businesses per owner. While the Business ORM model defined owner_id
without unique=True, migration 20260101_0002 had created an explicit
`sa.UniqueConstraint("owner_id", name="uq_businesses_owner_id")` constraint
on the `businesses` table.

This migration drops that unique constraint across both PostgreSQL
and SQLite (via batch mode) while preserving the non-unique index on
`owner_id` for fast query performance.

Rollback procedure:
  alembic downgrade 20260814_0001
Re-applies the unique constraint on `businesses.owner_id`.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260814_0002"
down_revision: Union[str, None] = "20260814_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.drop_constraint("uq_businesses_owner_id", "businesses", type_="unique")
    else:
        with op.batch_alter_table("businesses", recreate="always") as batch_op:
            batch_op.drop_constraint("uq_businesses_owner_id", type_="unique")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.create_unique_constraint("uq_businesses_owner_id", "businesses", ["owner_id"])
    else:
        with op.batch_alter_table("businesses", recreate="always") as batch_op:
            batch_op.create_unique_constraint("uq_businesses_owner_id", ["owner_id"])
