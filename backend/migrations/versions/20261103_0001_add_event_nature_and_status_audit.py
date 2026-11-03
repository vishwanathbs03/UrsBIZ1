"""add event_nature and status audit history to business_signal_events (Prompt 6.22)

Revision ID: 20261103_0001
Revises: 20261102_0003
Create Date: 2026-11-03 19:40:00

Adds:
  - event_nature column to business_signal_events (CONFIRMED_EVENT, WARNING, ESTIMATE, ASSUMPTION)
  - indexes for event_nature and composite (business_id, status, event_nature)
  - business_signal_event_audits table for immutable status transition audit logging
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20261103_0001"
down_revision: Union[str, None] = "20261102_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add event_nature column and indexes to business_signal_events
    with op.batch_alter_table("business_signal_events") as batch_op:
        batch_op.add_column(
            sa.Column(
                "event_nature",
                sa.String(length=32),
                nullable=False,
                server_default="WARNING",
            )
        )
        batch_op.create_index("ix_business_signal_events_event_nature", ["event_nature"])
        batch_op.create_index(
            "ix_business_signal_events_biz_status_nature",
            ["business_id", "status", "event_nature"],
        )

    # 2. Create business_signal_event_audits table
    op.create_table(
        "business_signal_event_audits",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("business_id", sa.Integer(), nullable=False),
        sa.Column("previous_status", sa.String(length=32), nullable=False),
        sa.Column("new_status", sa.String(length=32), nullable=False),
        sa.Column("changed_by_user_id", sa.Integer(), nullable=False),
        sa.Column(
            "changed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["business_id"],
            ["businesses.id"],
            name="fk_business_signal_event_audits_business_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["changed_by_user_id"],
            ["users.id"],
            name="fk_business_signal_event_audits_user_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_business_signal_event_audits"),
    )
    op.create_index(
        "ix_business_signal_event_audits_event_id",
        "business_signal_event_audits",
        ["event_id"],
    )
    op.create_index(
        "ix_business_signal_event_audits_business_id",
        "business_signal_event_audits",
        ["business_id"],
    )
    op.create_index(
        "ix_business_signal_event_audits_changed_by_user_id",
        "business_signal_event_audits",
        ["changed_by_user_id"],
    )
    op.create_index(
        "ix_business_signal_event_audits_changed_at",
        "business_signal_event_audits",
        ["changed_at"],
    )


def downgrade() -> None:
    # 1. Drop business_signal_event_audits table
    op.drop_index("ix_business_signal_event_audits_changed_at", table_name="business_signal_event_audits")
    op.drop_index("ix_business_signal_event_audits_changed_by_user_id", table_name="business_signal_event_audits")
    op.drop_index("ix_business_signal_event_audits_business_id", table_name="business_signal_event_audits")
    op.drop_index("ix_business_signal_event_audits_event_id", table_name="business_signal_event_audits")
    op.drop_table("business_signal_event_audits")

    # 2. Revert business_signal_events column and indexes
    with op.batch_alter_table("business_signal_events") as batch_op:
        batch_op.drop_index("ix_business_signal_events_biz_status_nature")
        batch_op.drop_index("ix_business_signal_events_event_nature")
        batch_op.drop_column("event_nature")
