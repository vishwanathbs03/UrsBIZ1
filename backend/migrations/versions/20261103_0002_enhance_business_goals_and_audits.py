"""enhance business_goals and create business_goal_audits (Prompt 6.24)

Revision ID: 20261103_0002
Revises: 20261103_0001
Create Date: 2026-11-03 23:45:00

Adds:
  - Metric connection, measurement method, and tracking columns to business_goals:
      * metric_key (VARCHAR(64), indexed)
      * measurement_method (VARCHAR(32), default 'AUTOMATED_METRIC')
      * baseline_value (FLOAT, nullable)
      * target_value (FLOAT, default 0.0)
      * current_value (FLOAT, nullable)
      * progress_pct (FLOAT, nullable)
      * unit (VARCHAR(32), default 'INR')
      * start_date (DATE, nullable)
      * status (VARCHAR(32), default 'ACTIVE', indexed)
      * status_notes (TEXT, nullable)
      * data_availability (VARCHAR(32), default 'AVAILABLE')
      * last_evaluated_at (DATETIME(timezone=True), nullable)
      * created_by_user_id (INTEGER, nullable)
      * is_archived (BOOLEAN, default 0, indexed)
      * archived_at (DATETIME(timezone=True), nullable)
      * archived_by_user_id (INTEGER, nullable)
  - Creates business_goal_audits table with non-cascading foreign key to business_goals
    so deleting/archiving a goal preserves immutable audit records.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20261103_0002"
down_revision: Union[str, None] = "20261103_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Enhance business_goals table with tracking & measurement columns
    with op.batch_alter_table("business_goals") as batch_op:
        batch_op.add_column(
            sa.Column("metric_key", sa.String(length=64), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "measurement_method",
                sa.String(length=32),
                nullable=False,
                server_default="AUTOMATED_METRIC",
            )
        )
        batch_op.add_column(
            sa.Column("baseline_value", sa.Float(), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "target_value",
                sa.Float(),
                nullable=False,
                server_default="0.0",
            )
        )
        batch_op.add_column(
            sa.Column("current_value", sa.Float(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("progress_pct", sa.Float(), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "unit",
                sa.String(length=32),
                nullable=False,
                server_default="INR",
            )
        )
        batch_op.add_column(
            sa.Column("start_date", sa.Date(), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "status",
                sa.String(length=32),
                nullable=False,
                server_default="ACTIVE",
            )
        )
        batch_op.add_column(
            sa.Column("status_notes", sa.Text(), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "data_availability",
                sa.String(length=32),
                nullable=False,
                server_default="AVAILABLE",
            )
        )
        batch_op.add_column(
            sa.Column("last_evaluated_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "created_by_user_id",
                sa.Integer(),
                sa.ForeignKey(
                    "users.id",
                    name="fk_business_goals_created_by_user_id",
                    ondelete="SET NULL",
                ),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "is_archived",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch_op.add_column(
            sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "archived_by_user_id",
                sa.Integer(),
                sa.ForeignKey(
                    "users.id",
                    name="fk_business_goals_archived_by_user_id",
                    ondelete="SET NULL",
                ),
                nullable=True,
            )
        )

        batch_op.create_index(
            "ix_business_goals_metric_key",
            ["metric_key"],
            unique=False,
        )
        batch_op.create_index(
            "ix_business_goals_status",
            ["status"],
            unique=False,
        )
        batch_op.create_index(
            "ix_business_goals_is_archived",
            ["is_archived"],
            unique=False,
        )
        batch_op.create_index(
            "ix_business_goals_biz_status",
            ["business_id", "status"],
            unique=False,
        )

    # 2. Create business_goal_audits table
    # Note: goal_id uses ondelete="SET NULL" so archiving/deleting a goal never destroys historical audit evidence.
    op.create_table(
        "business_goal_audits",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("goal_id", sa.Integer(), nullable=True),
        sa.Column("business_id", sa.Integer(), nullable=False),
        sa.Column("changed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("old_status", sa.String(length=32), nullable=True),
        sa.Column("new_status", sa.String(length=32), nullable=True),
        sa.Column("measured_value", sa.Float(), nullable=True),
        sa.Column("target_value", sa.Float(), nullable=True),
        sa.Column("progress_pct", sa.Float(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("snapshot_data", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["goal_id"],
            ["business_goals.id"],
            name="fk_business_goal_audits_goal_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["business_id"],
            ["businesses.id"],
            name="fk_business_goal_audits_business_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["changed_by_user_id"],
            ["users.id"],
            name="fk_business_goal_audits_user_id",
            ondelete="SET NULL",
        ),
    )
    op.create_index(
        "ix_business_goal_audits_goal_id",
        "business_goal_audits",
        ["goal_id"],
        unique=False,
    )
    op.create_index(
        "ix_business_goal_audits_business_id",
        "business_goal_audits",
        ["business_id"],
        unique=False,
    )
    op.create_index(
        "ix_business_goal_audits_created_at",
        "business_goal_audits",
        ["created_at"],
        unique=False,
    )

    # 3. Create database-level triggers enforcing append-only immutability
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(sa.text("""
            CREATE OR REPLACE FUNCTION trg_prevent_business_goal_audits_modification()
            RETURNS TRIGGER AS $$
            BEGIN
                RAISE EXCEPTION 'BusinessGoalAudit records are append-only and cannot be modified or deleted.';
            END;
            $$ LANGUAGE plpgsql;
        """))
        op.execute(sa.text("""
            DROP TRIGGER IF EXISTS trg_no_update_business_goal_audits ON business_goal_audits;
            CREATE TRIGGER trg_no_update_business_goal_audits
            BEFORE UPDATE ON business_goal_audits
            FOR EACH ROW EXECUTE FUNCTION trg_prevent_business_goal_audits_modification();
        """))
        op.execute(sa.text("""
            DROP TRIGGER IF EXISTS trg_no_delete_business_goal_audits ON business_goal_audits;
            CREATE TRIGGER trg_no_delete_business_goal_audits
            BEFORE DELETE ON business_goal_audits
            FOR EACH ROW EXECUTE FUNCTION trg_prevent_business_goal_audits_modification();
        """))
    else:
        # SQLite
        op.execute(sa.text("""
            CREATE TRIGGER IF NOT EXISTS trg_prevent_business_goal_audits_update
            BEFORE UPDATE ON business_goal_audits
            BEGIN
                SELECT RAISE(ABORT, 'BusinessGoalAudit records are append-only and cannot be updated.');
            END;
        """))
        op.execute(sa.text("""
            CREATE TRIGGER IF NOT EXISTS trg_prevent_business_goal_audits_delete
            BEFORE DELETE ON business_goal_audits
            BEGIN
                SELECT RAISE(ABORT, 'BusinessGoalAudit records are append-only and cannot be deleted.');
            END;
        """))


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(sa.text("DROP TRIGGER IF EXISTS trg_no_update_business_goal_audits ON business_goal_audits;"))
        op.execute(sa.text("DROP TRIGGER IF EXISTS trg_no_delete_business_goal_audits ON business_goal_audits;"))
        op.execute(sa.text("DROP FUNCTION IF EXISTS trg_prevent_business_goal_audits_modification();"))
    else:
        op.execute(sa.text("DROP TRIGGER IF EXISTS trg_prevent_business_goal_audits_update;"))
        op.execute(sa.text("DROP TRIGGER IF EXISTS trg_prevent_business_goal_audits_delete;"))

    op.drop_index("ix_business_goal_audits_created_at", table_name="business_goal_audits")
    op.drop_index("ix_business_goal_audits_business_id", table_name="business_goal_audits")
    op.drop_index("ix_business_goal_audits_goal_id", table_name="business_goal_audits")
    op.drop_table("business_goal_audits")

    with op.batch_alter_table("business_goals") as batch_op:
        batch_op.drop_index("ix_business_goals_biz_status")
        batch_op.drop_index("ix_business_goals_is_archived")
        batch_op.drop_index("ix_business_goals_status")
        batch_op.drop_index("ix_business_goals_metric_key")
        batch_op.drop_column("archived_by_user_id")
        batch_op.drop_column("archived_at")
        batch_op.drop_column("is_archived")
        batch_op.drop_column("created_by_user_id")
        batch_op.drop_column("last_evaluated_at")
        batch_op.drop_column("data_availability")
        batch_op.drop_column("status_notes")
        batch_op.drop_column("status")
        batch_op.drop_column("start_date")
        batch_op.drop_column("unit")
        batch_op.drop_column("progress_pct")
        batch_op.drop_column("current_value")
        batch_op.drop_column("target_value")
        batch_op.drop_column("baseline_value")
        batch_op.drop_column("measurement_method")
        batch_op.drop_column("metric_key")
