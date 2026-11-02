"""create business_decisions table (Phase 6.18 Extension)

Revision ID: 20261102_0001
Revises: 20261101_0005
Create Date: 2026-11-02 19:15:00

Creates business_decisions table for:
  - Multi-option decision evaluations (pricing, discounting, customer focus, expansion)
  - Baseline evidence snapshots and deterministic scenario calculations
  - Selected option recording and rationale
  - Post-decision review notes and outcome linkage
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20261102_0001"
down_revision: Union[str, None] = "20261101_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "business_decisions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("business_id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("decision_type", sa.String(length=60), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("objective", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="Draft"),
        sa.Column("baseline_snapshot", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("options_payload", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("selected_option_id", sa.String(length=60), nullable=True),
        sa.Column("selected_option_title", sa.String(length=200), nullable=True),
        sa.Column("decision_rationale", sa.Text(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_status", sa.String(length=40), nullable=False, server_default="Pending"),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("outcome_id", sa.Integer(), nullable=True),
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
            name="fk_business_decisions_business_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name="fk_business_decisions_owner_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["outcome_id"],
            ["recommendation_outcomes.id"],
            name="fk_business_decisions_outcome_id",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_business_decisions"),
    )
    op.create_index("ix_business_decisions_business_id", "business_decisions", ["business_id"])
    op.create_index("ix_business_decisions_owner_id", "business_decisions", ["owner_id"])
    op.create_index("ix_business_decisions_decision_type", "business_decisions", ["decision_type"])
    op.create_index("ix_business_decisions_status", "business_decisions", ["status"])


def downgrade() -> None:
    op.drop_index("ix_business_decisions_status", table_name="business_decisions")
    op.drop_index("ix_business_decisions_decision_type", table_name="business_decisions")
    op.drop_index("ix_business_decisions_owner_id", table_name="business_decisions")
    op.drop_index("ix_business_decisions_business_id", table_name="business_decisions")
    op.drop_table("business_decisions")
