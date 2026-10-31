"""ORM models for Sales Data Ingestion and Sales Intelligence (Phase 3).

Stores historical sales uploads and normalized transactional records associated
with a Business Digital Twin.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.utils.database import Base

if TYPE_CHECKING:
    from app.models.business import Business


class SalesUpload(Base):
    """An uploaded sales dataset event."""

    __tablename__ = "sales_uploads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    business_id: Mapped[int] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_format: Mapped[str] = mapped_column(String(10), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    valid_row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    invalid_row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="pending_confirmation"
    )
    column_mapping: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    quality_summary: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    business: Mapped["Business"] = relationship(back_populates="sales_uploads")
    transactions: Mapped[list["SalesTransaction"]] = relationship(
        back_populates="upload", cascade="all, delete-orphan"
    )


class SalesTransaction(Base):
    """A normalized historical sales transaction row."""

    __tablename__ = "sales_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    upload_id: Mapped[int] = mapped_column(
        ForeignKey("sales_uploads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    business_id: Mapped[int] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    transaction_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    invoice_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    customer_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    customer_name: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    product_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    product_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False)
    total_amount: Mapped[float] = mapped_column(Float, nullable=False)
    is_duplicate: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    business: Mapped["Business"] = relationship(back_populates="sales_transactions")
    upload: Mapped["SalesUpload"] = relationship(back_populates="transactions")
