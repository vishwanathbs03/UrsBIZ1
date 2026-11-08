"""create ar subledger tables (Wave 1 Financial Intelligence)

Revision ID: 20261115_0001
Revises: 20261107_0001
Create Date: 2026-11-15 10:00:00

Creates:
  - ar_invoices: Accounts receivable invoice records with tenant isolation.
  - ar_invoice_lines: Itemized invoice line items linked to ar_invoices.
  - customer_payments: Realized customer payment collections.
  - ar_payment_allocations: Many-to-many allocation clearing payments against invoices.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20261115_0001"
down_revision: Union[str, None] = "20261107_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create ar_invoices table
    op.create_table(
        "ar_invoices",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "business_id",
            sa.Integer(),
            sa.ForeignKey("businesses.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("customer_name", sa.String(255), nullable=True),
        sa.Column("customer_gstin", sa.String(15), nullable=True),
        sa.Column("invoice_number", sa.String(100), nullable=False),
        sa.Column("gross_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("tax_amount", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
        sa.Column("amount_paid", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
        sa.Column("outstanding_balance", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
        sa.Column("status", sa.String(50), nullable=False, server_default="UNPAID"),
        sa.Column("invoice_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
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
        sa.UniqueConstraint("id", "business_id", name="uq_ar_invoices_tenant"),
    )
    op.create_index("ix_ar_invoices_business_id", "ar_invoices", ["business_id"], unique=False)
    op.create_index("ix_ar_invoices_invoice_number", "ar_invoices", ["invoice_number"], unique=False)
    op.create_index("ix_ar_invoices_invoice_date", "ar_invoices", ["invoice_date"], unique=False)
    op.create_index("ix_ar_invoices_due_date", "ar_invoices", ["due_date"], unique=False)
    op.create_index("ix_ar_invoices_status", "ar_invoices", ["status"], unique=False)
    op.create_index("ix_ar_invoices_customer_name", "ar_invoices", ["customer_name"], unique=False)

    # 2. Create ar_invoice_lines table
    op.create_table(
        "ar_invoice_lines",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "business_id",
            sa.Integer(),
            sa.ForeignKey("businesses.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("invoice_id", sa.BigInteger(), nullable=False),
        sa.Column("item_description", sa.String(255), nullable=False),
        sa.Column("hsn_sac_code", sa.String(10), nullable=True),
        sa.Column("quantity", sa.Numeric(12, 4), nullable=False, server_default="1.0000"),
        sa.Column("unit_price", sa.Numeric(18, 2), nullable=False),
        sa.Column("taxable_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("tax_rate", sa.Numeric(5, 2), nullable=False, server_default="0.00"),
        sa.Column("tax_amount", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
        sa.Column("total_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["invoice_id", "business_id"],
            ["ar_invoices.id", "ar_invoices.business_id"],
            name="fk_ar_invoice_lines_tenant",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_ar_invoice_lines_business_id", "ar_invoice_lines", ["business_id"], unique=False)
    op.create_index("ix_ar_invoice_lines_invoice_id", "ar_invoice_lines", ["invoice_id"], unique=False)

    # 3. Create customer_payments table
    op.create_table(
        "customer_payments",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "business_id",
            sa.Integer(),
            sa.ForeignKey("businesses.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("customer_name", sa.String(255), nullable=True),
        sa.Column("payment_reference", sa.String(100), nullable=False),
        sa.Column("payment_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("payment_method", sa.String(50), nullable=False, server_default="BANK_TRANSFER"),
        sa.Column("unallocated_balance", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
        sa.Column("status", sa.String(50), nullable=False, server_default="SETTLED"),
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
        sa.CheckConstraint("amount > 0", name="chk_customer_payment_amount_positive"),
        sa.UniqueConstraint("id", "business_id", name="uq_customer_payments_tenant"),
    )
    op.create_index("ix_customer_payments_business_id", "customer_payments", ["business_id"], unique=False)
    op.create_index("ix_customer_payments_payment_date", "customer_payments", ["payment_date"], unique=False)
    op.create_index("ix_customer_payments_status", "customer_payments", ["status"], unique=False)

    # 4. Create ar_payment_allocations table
    op.create_table(
        "ar_payment_allocations",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "business_id",
            sa.Integer(),
            sa.ForeignKey("businesses.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("invoice_id", sa.BigInteger(), nullable=False),
        sa.Column("payment_id", sa.BigInteger(), nullable=False),
        sa.Column("allocated_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="ALLOCATED"),
        sa.Column(
            "allocated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("allocated_amount > 0", name="chk_ar_alloc_amount_positive"),
        sa.ForeignKeyConstraint(
            ["invoice_id", "business_id"],
            ["ar_invoices.id", "ar_invoices.business_id"],
            name="fk_alloc_invoice_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["payment_id", "business_id"],
            ["customer_payments.id", "customer_payments.business_id"],
            name="fk_alloc_payment_tenant",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("id", "business_id", name="uq_ar_allocations_tenant"),
    )
    op.create_index("ix_ar_payment_allocations_business_id", "ar_payment_allocations", ["business_id"], unique=False)
    op.create_index("ix_ar_payment_allocations_invoice_id", "ar_payment_allocations", ["invoice_id"], unique=False)
    op.create_index("ix_ar_payment_allocations_payment_id", "ar_payment_allocations", ["payment_id"], unique=False)


def downgrade() -> None:
    op.drop_table("ar_payment_allocations")
    op.drop_table("customer_payments")
    op.drop_table("ar_invoice_lines")
    op.drop_table("ar_invoices")
