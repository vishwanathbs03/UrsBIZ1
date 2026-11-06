"""create connector and integration tables (Phase 6.27)

Revision ID: 20261106_0001
Revises: 20261105_0002
Create Date: 2026-11-06 21:30:00

Creates:
  - integration_connections: configured data source connections and encrypted credentials.
  - integration_sync_executions: synchronization execution tracking and record counts.
  - integration_audits: append-only integration lifecycle audit records with database-level immutability triggers.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20261106_0001"
down_revision: Union[str, None] = "20261105_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create integration_connections table
    op.create_table(
        "integration_connections",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "business_id",
            sa.Integer(),
            sa.ForeignKey("businesses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("connector_id", sa.String(50), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column(
            "status",
            sa.String(30),
            nullable=False,
            server_default="NOT_CONFIGURED",
        ),
        sa.Column("configuration", sa.JSON(), nullable=False),
        sa.Column("encrypted_credentials", sa.Text(), nullable=True),
        sa.Column("credential_fingerprint", sa.String(64), nullable=True),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_sync_status", sa.String(30), nullable=True),
        sa.Column("last_error_category", sa.String(50), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.Column("sync_cursor", sa.String(255), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("business_id", "connector_id", "name", name="uq_integration_connection_name"),
    )
    op.create_index("ix_integration_connections_business_id", "integration_connections", ["business_id"])
    op.create_index("ix_integration_connections_connector_id", "integration_connections", ["connector_id"])
    op.create_index("ix_integration_connections_status", "integration_connections", ["status"])

    # 2. Create integration_sync_executions table
    op.create_table(
        "integration_sync_executions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "business_id",
            sa.Integer(),
            sa.ForeignKey("businesses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "connection_id",
            sa.Integer(),
            sa.ForeignKey("integration_connections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("connector_id", sa.String(50), nullable=False),
        sa.Column("execution_id", sa.String(64), unique=True, nullable=False),
        sa.Column(
            "trigger_type",
            sa.String(30),
            nullable=False,
            server_default="MANUAL",
        ),
        sa.Column(
            "status",
            sa.String(30),
            nullable=False,
            server_default="QUEUED",
        ),
        sa.Column("records_discovered", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_imported", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_skipped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duplicate_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("validation_failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_category", sa.String(50), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sync_cursor_before", sa.String(255), nullable=True),
        sa.Column("sync_cursor_after", sa.String(255), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("summary", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_integration_sync_executions_business_id", "integration_sync_executions", ["business_id"])
    op.create_index("ix_integration_sync_executions_connection_id", "integration_sync_executions", ["connection_id"])
    op.create_index("ix_integration_sync_executions_connector_id", "integration_sync_executions", ["connector_id"])
    op.create_index("ix_integration_sync_executions_execution_id", "integration_sync_executions", ["execution_id"])
    op.create_index("ix_integration_sync_executions_status", "integration_sync_executions", ["status"])

    # 3. Create integration_audits table (RESTRICT on business_id for audit retention)
    op.create_table(
        "integration_audits",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "business_id",
            sa.Integer(),
            sa.ForeignKey("businesses.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("connection_id", sa.Integer(), nullable=True),
        sa.Column("connector_id", sa.String(50), nullable=True),
        sa.Column(
            "actor_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_integration_audits_business_id", "integration_audits", ["business_id"])
    op.create_index("ix_integration_audits_connection_id", "integration_audits", ["connection_id"])
    op.create_index("ix_integration_audits_connector_id", "integration_audits", ["connector_id"])
    op.create_index("ix_integration_audits_event_type", "integration_audits", ["event_type"])
    op.create_index("ix_integration_audits_created_at", "integration_audits", ["created_at"])

    # 4. Database-level immutability triggers for integration_audits
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "sqlite":
        op.execute("""
        CREATE TRIGGER IF NOT EXISTS trg_prevent_integration_audits_update
        BEFORE UPDATE ON integration_audits
        BEGIN
            SELECT RAISE(ABORT, 'IntegrationAudit records are append-only and cannot be updated.');
        END;
        """)
        op.execute("""
        CREATE TRIGGER IF NOT EXISTS trg_prevent_integration_audits_delete
        BEFORE DELETE ON integration_audits
        BEGIN
            SELECT RAISE(ABORT, 'IntegrationAudit records are append-only and cannot be deleted.');
        END;
        """)
    elif dialect == "postgresql":
        op.execute("""
        CREATE OR REPLACE FUNCTION trg_prevent_integration_audits_modification()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'IntegrationAudit records are append-only and cannot be modified or deleted.';
        END;
        $$ LANGUAGE plpgsql;
        """)
        op.execute("""
        CREATE TRIGGER trg_no_update_integration_audits
        BEFORE UPDATE ON integration_audits
        FOR EACH ROW EXECUTE FUNCTION trg_prevent_integration_audits_modification();
        """)
        op.execute("""
        CREATE TRIGGER trg_no_delete_integration_audits
        BEFORE DELETE ON integration_audits
        FOR EACH ROW EXECUTE FUNCTION trg_prevent_integration_audits_modification();
        """)


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "sqlite":
        op.execute("DROP TRIGGER IF EXISTS trg_prevent_integration_audits_update;")
        op.execute("DROP TRIGGER IF EXISTS trg_prevent_integration_audits_delete;")
    elif dialect == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS trg_no_update_integration_audits ON integration_audits;")
        op.execute("DROP TRIGGER IF EXISTS trg_no_delete_integration_audits ON integration_audits;")
        op.execute("DROP FUNCTION IF EXISTS trg_prevent_integration_audits_modification();")

    op.drop_table("integration_audits")
    op.drop_table("integration_sync_executions")
    op.drop_table("integration_connections")
