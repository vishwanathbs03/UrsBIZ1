"""create ap subledger tables (Wave 1 Financial Intelligence)

Revision ID: 20261115_0002
Revises: 20261115_0001
Create Date: 2026-11-15 11:00:00

Creates:
  - vendor_bills: Accounts payable vendor bills with tenant isolation.
  - vendor_bill_lines: Itemized line items linked to vendor_bills.
  - vendor_payments: Realized supplier disbursements.
  - vendor_payment_allocations: Many-to-many allocation clearing disbursements against bills.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20261115_0002"
down_revision: Union[str, None] = "20261115_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create vendor_bills table
    op.create_table(
        "vendor_bills",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "business_id",
            sa.Integer(),
            sa.ForeignKey("businesses.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("vendor_name", sa.String(255), nullable=False),
        sa.Column("vendor_gstin", sa.String(15), nullable=True),
        sa.Column("bill_number", sa.String(100), nullable=False),
        sa.Column("gross_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("tax_amount", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
        sa.Column("amount_paid", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
        sa.Column("outstanding_balance", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
        sa.Column("status", sa.String(50), nullable=False, server_default="UNPAID"),
        sa.Column("bill_date", sa.Date(), nullable=False),
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
        sa.UniqueConstraint("id", "business_id", name="uq_vendor_bills_tenant"),
    )
    op.create_index("ix_vendor_bills_business_id", "vendor_bills", ["business_id"], unique=False)
    op.create_index("ix_vendor_bills_vendor_name", "vendor_bills", ["vendor_name"], unique=False)
    op.create_index("ix_vendor_bills_bill_number", "vendor_bills", ["bill_number"], unique=False)
    op.create_index("ix_vendor_bills_bill_date", "vendor_bills", ["bill_date"], unique=False)
    op.create_index("ix_vendor_bills_due_date", "vendor_bills", ["due_date"], unique=False)
    op.create_index("ix_vendor_bills_status", "vendor_bills", ["status"], unique=False)

    # 2. Create vendor_bill_lines table
    op.create_table(
        "vendor_bill_lines",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "business_id",
            sa.Integer(),
            sa.ForeignKey("businesses.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("bill_id", sa.BigInteger(), nullable=False),
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
            ["bill_id", "business_id"],
            ["vendor_bills.id", "vendor_bills.business_id"],
            name="fk_vendor_bill_lines_tenant",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_vendor_bill_lines_business_id", "vendor_bill_lines", ["business_id"], unique=False)
    op.create_index("ix_vendor_bill_lines_bill_id", "vendor_bill_lines", ["bill_id"], unique=False)

    # 3. Create vendor_payments table
    op.create_table(
        "vendor_payments",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "business_id",
            sa.Integer(),
            sa.ForeignKey("businesses.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("vendor_name", sa.String(255), nullable=True),
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
        sa.CheckConstraint("amount > 0", name="chk_vendor_payment_amount_positive"),
        sa.UniqueConstraint("id", "business_id", name="uq_vendor_payments_tenant"),
    )
    op.create_index("ix_vendor_payments_business_id", "vendor_payments", ["business_id"], unique=False)
    op.create_index("ix_vendor_payments_payment_date", "vendor_payments", ["payment_date"], unique=False)
    op.create_index("ix_vendor_payments_status", "vendor_payments", ["status"], unique=False)

    # 4. Create vendor_payment_allocations table
    op.create_table(
        "vendor_payment_allocations",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "business_id",
            sa.Integer(),
            sa.ForeignKey("businesses.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("bill_id", sa.BigInteger(), nullable=False),
        sa.Column("payment_id", sa.BigInteger(), nullable=False),
        sa.Column("allocated_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="ALLOCATED"),
        sa.Column(
            "allocated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("allocated_amount > 0", name="chk_vendor_alloc_amount_positive"),
        sa.ForeignKeyConstraint(
            ["bill_id", "business_id"],
            ["vendor_bills.id", "vendor_bills.business_id"],
            name="fk_alloc_bill_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["payment_id", "business_id"],
            ["vendor_payments.id", "vendor_payments.business_id"],
            name="fk_alloc_vendor_payment_tenant",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("id", "business_id", name="uq_vendor_allocations_tenant"),
    )
    op.create_index("ix_vendor_payment_allocations_business_id", "vendor_payment_allocations", ["business_id"], unique=False)
    op.create_index("ix_vendor_payment_allocations_bill_id", "vendor_payment_allocations", ["bill_id"], unique=False)
    op.create_index("ix_vendor_payment_allocations_payment_id", "vendor_payment_allocations", ["payment_id"], unique=False)


def downgrade() -> None:
    op.drop_table("vendor_payment_allocations")
    op.drop_table("vendor_payments")
    op.drop_table("vendor_bill_lines")
    op.drop_table("vendor_bills")
