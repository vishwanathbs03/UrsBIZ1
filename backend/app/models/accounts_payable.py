"""SQLAlchemy ORM models for Accounts Payable (AP) Subledger.

Part of Wave 1 Financial Intelligence Architecture:
  - VendorBill: Authorized vendor bill / expense documents with tenant isolation.
  - VendorBillLine: Itemized lines per vendor bill.
  - VendorPayment: Realized supplier disbursements.
  - VendorPaymentAllocation: Payment allocations clearing payables.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.utils.database import Base

if TYPE_CHECKING:
    from app.models.business import Business


class VendorBill(Base):
    """Vendor purchase bill for trade creditor and OpEx tracking."""

    __tablename__ = "vendor_bills"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    business_id: Mapped[int] = mapped_column(
        ForeignKey("businesses.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    vendor_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    vendor_gstin: Mapped[str | None] = mapped_column(String(15), nullable=True)
    bill_number: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    gross_amount: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    tax_amount: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0.00, server_default="0.00")
    amount_paid: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0.00, server_default="0.00")
    outstanding_balance: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0.00, server_default="0.00")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="UNPAID", server_default="UNPAID", index=True)
    bill_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    due_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    business: Mapped["Business"] = relationship(foreign_keys=[business_id])
    lines: Mapped[list["VendorBillLine"]] = relationship(
        back_populates="bill",
        cascade="all, delete-orphan",
    )
    allocations: Mapped[list["VendorPaymentAllocation"]] = relationship(
        back_populates="bill",
    )

    __table_args__ = (
        UniqueConstraint("id", "business_id", name="uq_vendor_bills_tenant"),
    )


class VendorBillLine(Base):
    """Itemized line item within a vendor bill."""

    __tablename__ = "vendor_bill_lines"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    business_id: Mapped[int] = mapped_column(
        ForeignKey("businesses.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    bill_id: Mapped[int] = mapped_column(nullable=False, index=True)
    item_description: Mapped[str] = mapped_column(String(255), nullable=False)
    hsn_sac_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    quantity: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False, default=1.0000, server_default="1.0000")
    unit_price: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    taxable_amount: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    tax_rate: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=0.00, server_default="0.00")
    tax_amount: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0.00, server_default="0.00")
    total_amount: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    bill: Mapped["VendorBill"] = relationship(back_populates="lines")

    __table_args__ = (
        ForeignKeyConstraint(
            ["bill_id", "business_id"],
            ["vendor_bills.id", "vendor_bills.business_id"],
            name="fk_vendor_bill_lines_tenant",
            ondelete="CASCADE",
        ),
    )


class VendorPayment(Base):
    """Supplier disbursement payment event."""

    __tablename__ = "vendor_payments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    business_id: Mapped[int] = mapped_column(
        ForeignKey("businesses.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    vendor_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payment_reference: Mapped[str] = mapped_column(String(100), nullable=False)
    payment_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    amount: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    payment_method: Mapped[str] = mapped_column(String(50), nullable=False, default="BANK_TRANSFER", server_default="BANK_TRANSFER")
    unallocated_balance: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0.00, server_default="0.00")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="SETTLED", server_default="SETTLED", index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    business: Mapped["Business"] = relationship(foreign_keys=[business_id])
    allocations: Mapped[list["VendorPaymentAllocation"]] = relationship(
        back_populates="payment",
        overlaps="allocations",
    )

    __table_args__ = (
        CheckConstraint("amount > 0", name="chk_vendor_payment_amount_positive"),
        UniqueConstraint("id", "business_id", name="uq_vendor_payments_tenant"),
    )


class VendorPaymentAllocation(Base):
    """Allocation matching supplier payments to vendor bills."""

    __tablename__ = "vendor_payment_allocations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    business_id: Mapped[int] = mapped_column(
        ForeignKey("businesses.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    bill_id: Mapped[int] = mapped_column(nullable=False, index=True)
    payment_id: Mapped[int] = mapped_column(nullable=False, index=True)
    allocated_amount: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="ALLOCATED", server_default="ALLOCATED")

    allocated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    bill: Mapped["VendorBill"] = relationship(
        back_populates="allocations",
        overlaps="allocations",
    )
    payment: Mapped["VendorPayment"] = relationship(
        back_populates="allocations",
        overlaps="allocations,bill",
    )

    __table_args__ = (
        CheckConstraint("allocated_amount > 0", name="chk_vendor_alloc_amount_positive"),
        ForeignKeyConstraint(
            ["bill_id", "business_id"],
            ["vendor_bills.id", "vendor_bills.business_id"],
            name="fk_alloc_bill_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["payment_id", "business_id"],
            ["vendor_payments.id", "vendor_payments.business_id"],
            name="fk_alloc_vendor_payment_tenant",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("id", "business_id", name="uq_vendor_allocations_tenant"),
    )
