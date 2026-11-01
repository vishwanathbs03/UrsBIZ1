"""create recommendation_lifecycle table (Phase 5 Smart Recommendations)

Revision ID: 20261101_0001
Revises: 20261031_0001
Create Date: 2026-11-01 00:00:01

Creates persistent lifecycle tracking table for business recommendations:
  - New, Viewed, Accepted, In Progress, Completed, Dismissed
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20261101_0001"
down_revision: Union[str, None] = "20261031_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "recommendation_lifecycle",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("business_id", sa.Integer(), nullable=False),
        sa.Column("recommendation_id", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="New"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("first_viewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status_updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["business_id"],
            ["businesses.id"],
            name="fk_recommendation_lifecycle_business_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_recommendation_lifecycle"),
        sa.UniqueConstraint("business_id", "recommendation_id", name="uq_business_recommendation"),
    )
    op.create_index(
        "ix_recommendation_lifecycle_business_id",
        "recommendation_lifecycle",
        ["business_id"],
        unique=False,
    )
    op.create_index(
        "ix_recommendation_lifecycle_recommendation_id",
        "recommendation_lifecycle",
        ["recommendation_id"],
        unique=False,
    )
    op.create_index(
        "ix_recommendation_lifecycle_status",
        "recommendation_lifecycle",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_recommendation_lifecycle_status", table_name="recommendation_lifecycle")
    op.drop_index("ix_recommendation_lifecycle_recommendation_id", table_name="recommendation_lifecycle")
    op.drop_index("ix_recommendation_lifecycle_business_id", table_name="recommendation_lifecycle")
    op.drop_table("recommendation_lifecycle")
