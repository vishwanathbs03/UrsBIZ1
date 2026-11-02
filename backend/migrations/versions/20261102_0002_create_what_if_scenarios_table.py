"""create what_if_scenarios table (Phase 6.19 Extension)

Revision ID: 20261102_0002
Revises: 20261102_0001
Create Date: 2026-11-02 19:45:00

Creates what_if_scenarios table for:
  - Financial what-if scenario simulations (sales drop, supplier price hike, customer churn, hiring, price elasticity, collection delay)
  - Multi-case outcome projections (Base Case, Conservative / Worst Case, Optimistic / Best Case)
  - Baseline capture, assumptions applied, and missing-data transparency
  - Saved scenario management, reload, and side-by-side comparison
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20261102_0002"
down_revision: Union[str, None] = "20261102_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "what_if_scenarios",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("business_id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("scenario_type", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("baseline_metrics", sa.JSON(), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("projection_result", sa.JSON(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(
            ["business_id"],
            ["businesses.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_what_if_scenarios_business_id"),
        "what_if_scenarios",
        ["business_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_what_if_scenarios_owner_id"),
        "what_if_scenarios",
        ["owner_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_what_if_scenarios_scenario_type"),
        "what_if_scenarios",
        ["scenario_type"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_what_if_scenarios_scenario_type"),
        table_name="what_if_scenarios",
    )
    op.drop_index(
        op.f("ix_what_if_scenarios_owner_id"),
        table_name="what_if_scenarios",
    )
    op.drop_index(
        op.f("ix_what_if_scenarios_business_id"),
        table_name="what_if_scenarios",
    )
    op.drop_table("what_if_scenarios")
