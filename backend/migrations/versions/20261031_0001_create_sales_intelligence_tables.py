"""create sales_uploads and sales_transactions tables (Phase 3 Sales Intelligence)

Revision ID: 20261031_0001
Revises: 20260814_0002
Create Date: 2026-10-31 00:00:01

Creates normalized tables for auditable historical sales data ingestion:
  - sales_uploads: metadata, mapping, and data quality summaries per upload
  - sales_transactions: normalized row-level sales transactions
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20261031_0001"
down_revision: Union[str, None] = "20260814_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create sales_uploads table
    op.create_table(
        "sales_uploads",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("business_id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("file_format", sa.String(length=10), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("valid_row_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("invalid_row_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="pending_confirmation"),
        sa.Column("column_mapping", sa.JSON(), nullable=True),
        sa.Column("quality_summary", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["business_id"],
            ["businesses.id"],
            name="fk_sales_uploads_business_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_sales_uploads"),
    )
    op.create_index(
        "ix_sales_uploads_business_id",
        "sales_uploads",
        ["business_id"],
        unique=False,
    )

    # 2. Create sales_transactions table
    op.create_table(
        "sales_transactions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("upload_id", sa.Integer(), nullable=False),
        sa.Column("business_id", sa.Integer(), nullable=False),
        sa.Column("transaction_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("invoice_id", sa.String(length=100), nullable=True),
        sa.Column("customer_id", sa.String(length=100), nullable=True),
        sa.Column("customer_name", sa.String(length=255), nullable=True),
        sa.Column("product_id", sa.String(length=100), nullable=True),
        sa.Column("product_name", sa.String(length=255), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("unit_price", sa.Float(), nullable=False),
        sa.Column("total_amount", sa.Float(), nullable=False),
        sa.Column("is_duplicate", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["business_id"],
            ["businesses.id"],
            name="fk_sales_transactions_business_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["upload_id"],
            ["sales_uploads.id"],
            name="fk_sales_transactions_upload_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_sales_transactions"),
    )
    op.create_index(
        "ix_sales_transactions_business_id",
        "sales_transactions",
        ["business_id"],
        unique=False,
    )
    op.create_index(
        "ix_sales_transactions_upload_id",
        "sales_transactions",
        ["upload_id"],
        unique=False,
    )
    op.create_index(
        "ix_sales_transactions_transaction_date",
        "sales_transactions",
        ["transaction_date"],
        unique=False,
    )
    op.create_index(
        "ix_sales_transactions_customer_name",
        "sales_transactions",
        ["customer_name"],
        unique=False,
    )
    op.create_index(
        "ix_sales_transactions_product_name",
        "sales_transactions",
        ["product_name"],
        unique=False,
    )
    op.create_index(
        "ix_sales_transactions_is_duplicate",
        "sales_transactions",
        ["is_duplicate"],
        unique=False,
    )


def downgrade() -> None:
    # Safely drop indexes and tables
    for idx in [
        "ix_sales_transactions_is_duplicate",
        "ix_sales_transactions_product_name",
        "ix_sales_transactions_customer_name",
        "ix_sales_transactions_transaction_date",
        "ix_sales_transactions_upload_id",
        "ix_sales_transactions_business_id",
    ]:
        try:
            op.drop_index(idx, table_name="sales_transactions")
        except Exception:
            pass

    op.drop_table("sales_transactions")

    try:
        op.drop_index("ix_sales_uploads_business_id", table_name="sales_uploads")
    except Exception:
        pass
    op.drop_table("sales_uploads")
