"""create business_reports and business_report_audits (Prompt 6.25)

Revision ID: 20261105_0001
Revises: 20261103_0002
Create Date: 2026-11-05 21:15:00

Creates:
  - business_reports: generated business reports, export artifacts, and provenance metadata.
  - business_report_audits: append-only audit trail and accountability log for report generation,
    preview, and downloads.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20261105_0001"
down_revision: Union[str, None] = "20261103_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create business_reports table
    op.create_table(
        "business_reports",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("report_id", sa.String(64), nullable=False),
        sa.Column(
            "business_id",
            sa.Integer(),
            sa.ForeignKey("businesses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("report_type", sa.String(64), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("reporting_period", sa.String(100), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("format", sa.String(16), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="COMPLETED"),
        sa.Column("file_path", sa.String(512), nullable=True),
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
        sa.Column("mime_type", sa.String(128), nullable=False),
        sa.Column("checksum_sha256", sa.String(64), nullable=True),
        sa.Column("parameters", sa.JSON(), nullable=True),
        sa.Column("summary_metrics", sa.JSON(), nullable=True),
        sa.Column("provenance_metadata", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "archived_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("download_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_downloaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
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
    )

    op.create_index("ix_business_reports_report_id", "business_reports", ["report_id"], unique=True)
    op.create_index("ix_business_reports_business_id", "business_reports", ["business_id"], unique=False)
    op.create_index("ix_business_reports_created_by_user_id", "business_reports", ["created_by_user_id"], unique=False)
    op.create_index("ix_business_reports_report_type", "business_reports", ["report_type"], unique=False)
    op.create_index("ix_business_reports_status", "business_reports", ["status"], unique=False)
    op.create_index("ix_business_reports_is_archived", "business_reports", ["is_archived"], unique=False)
    op.create_index("ix_business_reports_biz_type", "business_reports", ["business_id", "report_type"], unique=False)

    # 2. Create business_report_audits table
    op.create_table(
        "business_report_audits",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "report_id",
            sa.Integer(),
            sa.ForeignKey("business_reports.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "business_id",
            sa.Integer(),
            sa.ForeignKey("businesses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("format", sa.String(16), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="SUCCESS"),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_index("ix_business_report_audits_report_id", "business_report_audits", ["report_id"], unique=False)
    op.create_index("ix_business_report_audits_business_id", "business_report_audits", ["business_id"], unique=False)
    op.create_index("ix_business_report_audits_user_id", "business_report_audits", ["user_id"], unique=False)
    op.create_index("ix_business_report_audits_created_at", "business_report_audits", ["created_at"], unique=False)

    # 3. Create database-level immutability triggers for audit records
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "sqlite":
        op.execute("""
        CREATE TRIGGER IF NOT EXISTS trg_prevent_business_report_audits_update
        BEFORE UPDATE ON business_report_audits
        BEGIN
            SELECT RAISE(ABORT, 'BusinessReportAudit records are append-only and cannot be updated.');
        END;
        """)
        op.execute("""
        CREATE TRIGGER IF NOT EXISTS trg_prevent_business_report_audits_delete
        BEFORE DELETE ON business_report_audits
        BEGIN
            SELECT RAISE(ABORT, 'BusinessReportAudit records are append-only and cannot be deleted.');
        END;
        """)
    elif dialect == "postgresql":
        op.execute("""
        CREATE OR REPLACE FUNCTION trg_prevent_business_report_audits_modification()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'BusinessReportAudit records are append-only and cannot be modified or deleted.';
        END;
        $$ LANGUAGE plpgsql;
        """)
        op.execute("""
        CREATE TRIGGER trg_no_update_business_report_audits
        BEFORE UPDATE ON business_report_audits
        FOR EACH ROW EXECUTE FUNCTION trg_prevent_business_report_audits_modification();
        """)
        op.execute("""
        CREATE TRIGGER trg_no_delete_business_report_audits
        BEFORE DELETE ON business_report_audits
        FOR EACH ROW EXECUTE FUNCTION trg_prevent_business_report_audits_modification();
        """)


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "sqlite":
        op.execute("DROP TRIGGER IF EXISTS trg_prevent_business_report_audits_update;")
        op.execute("DROP TRIGGER IF EXISTS trg_prevent_business_report_audits_delete;")
    elif dialect == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS trg_no_update_business_report_audits ON business_report_audits;")
        op.execute("DROP TRIGGER IF EXISTS trg_no_delete_business_report_audits ON business_report_audits;")
        op.execute("DROP FUNCTION IF EXISTS trg_prevent_business_report_audits_modification();")

    op.drop_table("business_report_audits")
    op.drop_table("business_reports")
