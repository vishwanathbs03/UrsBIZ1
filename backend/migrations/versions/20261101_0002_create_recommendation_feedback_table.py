"""create recommendation_feedback table (Phase 5 Advanced Intelligence)

Revision ID: 20261101_0002
Revises: 20261101_0001
Create Date: 2026-11-01 02:00:01

Creates persistent feedback and suppression table for business recommendations:
  - Useful, Not relevant, Already implemented, Not feasible, Need more explanation
  - Automatic suppression tracking and outcome notes
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20261101_0002"
down_revision: Union[str, None] = "20261101_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "recommendation_feedback",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("business_id", sa.Integer(), nullable=False),
        sa.Column("recommendation_id", sa.String(length=100), nullable=False),
        sa.Column("feedback_type", sa.String(length=50), nullable=False),
        sa.Column("outcome_notes", sa.Text(), nullable=True),
        sa.Column("suppress_recommendation", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["business_id"],
            ["businesses.id"],
            name="fk_recommendation_feedback_business_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_recommendation_feedback"),
    )
    op.create_index(
        "ix_recommendation_feedback_business_id",
        "recommendation_feedback",
        ["business_id"],
        unique=False,
    )
    op.create_index(
        "ix_recommendation_feedback_recommendation_id",
        "recommendation_feedback",
        ["recommendation_id"],
        unique=False,
    )
    op.create_index(
        "ix_recommendation_feedback_feedback_type",
        "recommendation_feedback",
        ["feedback_type"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_recommendation_feedback_feedback_type", table_name="recommendation_feedback")
    op.drop_index("ix_recommendation_feedback_recommendation_id", table_name="recommendation_feedback")
    op.drop_index("ix_recommendation_feedback_business_id", table_name="recommendation_feedback")
    op.drop_table("recommendation_feedback")
