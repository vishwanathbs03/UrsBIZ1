"""Idempotency Database Model (Phase 5 Platform Resilience).

Prevents duplicate writes, concurrent race conditions, and replay issues
across uploads, lifecycle transitions, and report generation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import (
    DateTime,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.utils.database import Base


class IdempotencyRecord(Base):
    """Stores operation idempotency keys and cached response payloads."""

    __tablename__ = "idempotency_records"
    __table_args__ = (
        UniqueConstraint("business_id", "idempotency_key", name="uq_idempotency_business_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    business_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    operation_type: Mapped[str] = mapped_column(String(64), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PROCESSING")
    response_payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
