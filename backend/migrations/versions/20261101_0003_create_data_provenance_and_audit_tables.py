"""create data_provenance and quality_audit tables (Phase 5 Data Integrity)

Revision ID: 20261101_0003
Revises: 20261101_0002
Create Date: 2026-11-01 03:00:01

Creates centralized data provenance and quality audit tables:
  - business_data_provenance: granular traceable metric lineage
  - business_data_quality_audits: periodic audit logs, anomaly detection, and freshness tracking
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20261101_0003"
down_revision: Union[str, None] = "20261101_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create business_data_provenance table
    op.create_table(
        "business_data_provenance",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("business_id", sa.Integer(), nullable=False),
        sa.Column("metric_name", sa.String(length=100), nullable=False),
        sa.Column("metric_value", sa.JSON(), nullable=False),
        sa.Column("source_module", sa.String(length=50), nullable=False),
        sa.Column("source_record_ref", sa.String(length=255), nullable=True),
        sa.Column("measurement_period", sa.String(length=100), nullable=False),
        sa.Column("unit", sa.String(length=50), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=True, server_default="INR"),
        sa.Column("calculation_methodology", sa.Text(), nullable=False),
        sa.Column("data_quality_status", sa.String(length=30), nullable=False, server_default="VERIFIED"),
        sa.Column("nature", sa.String(length=30), nullable=False, server_default="actual"),
        sa.Column("freshness_status", sa.String(length=30), nullable=False, server_default="FRESH"),
        sa.Column("freshness_as_of", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=False, server_default="100.0"),
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
            name="fk_business_data_provenance_business_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_business_data_provenance"),
    )
    op.create_index(
        "ix_business_data_provenance_business_id",
        "business_data_provenance",
        ["business_id"],
        unique=False,
    )
    op.create_index(
        "ix_business_data_provenance_metric_name",
        "business_data_provenance",
        ["metric_name"],
        unique=False,
    )
    op.create_index(
        "ix_business_data_provenance_source_module",
        "business_data_provenance",
        ["source_module"],
        unique=False,
    )

    # 2. Create business_data_quality_audits table
    op.create_table(
        "business_data_quality_audits",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("business_id", sa.Integer(), nullable=False),
        sa.Column("audit_type", sa.String(length=50), nullable=False, server_default="comprehensive"),
        sa.Column("quality_score", sa.Float(), nullable=False, server_default="100.0"),
        sa.Column("overall_quality_status", sa.String(length=30), nullable=False, server_default="VERIFIED"),
        sa.Column("anomalies", sa.JSON(), nullable=False),
        sa.Column("cross_module_discrepancies", sa.JSON(), nullable=False),
        sa.Column("freshness_summary", sa.JSON(), nullable=False),
        sa.Column("unconfirmed_gaps_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duplicate_records_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["business_id"],
            ["businesses.id"],
            name="fk_business_data_quality_audits_business_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_business_data_quality_audits"),
    )
    op.create_index(
        "ix_business_data_quality_audits_business_id",
        "business_data_quality_audits",
        ["business_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_business_data_quality_audits_business_id", table_name="business_data_quality_audits")
    op.drop_table("business_data_quality_audits")
    op.drop_index("ix_business_data_provenance_source_module", table_name="business_data_provenance")
    op.drop_index("ix_business_data_provenance_metric_name", table_name="business_data_provenance")
    op.drop_index("ix_business_data_provenance_business_id", table_name="business_data_provenance")
    op.drop_table("business_data_provenance")
