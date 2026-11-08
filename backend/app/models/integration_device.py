"""SQLAlchemy ORM models for Integration Edge Devices and Replay-Prevention Nonces.

Part of Wave 1 Financial Intelligence Architecture:
  - IntegrationDevice: Edge/desktop sync device (Tally/ERP sync agent) bound to a tenant.
  - IntegrationDeviceNonce: Cryptographic replay-prevention nonces received from edge devices.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.utils.database import Base

if TYPE_CHECKING:
    from app.models.business import Business


class IntegrationDevice(Base):
    """Registered edge or desktop sync device (e.g., Tally connector agent)."""

    __tablename__ = "integration_devices"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    business_id: Mapped[int] = mapped_column(
        ForeignKey("businesses.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    device_uuid: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        unique=True,
        index=True,
    )
    public_key_hex: Mapped[str] = mapped_column(String(64), nullable=False)
    hostname: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="ACTIVE",
        server_default="ACTIVE",
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        server_default=func.now(),
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        UniqueConstraint("device_uuid", name="uq_integration_devices_uuid"),
    )

    # Relationships
    business: Mapped[Business] = relationship("Business")
    nonces: Mapped[list[IntegrationDeviceNonce]] = relationship(
        "IntegrationDeviceNonce",
        back_populates="device",
        cascade="all, delete-orphan",
    )


class IntegrationDeviceNonce(Base):
    """Replay-prevention nonces recorded from incoming signed edge integration requests."""

    __tablename__ = "integration_device_nonces"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    device_uuid: Mapped[str] = mapped_column(
        ForeignKey("integration_devices.device_uuid", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    nonce: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        server_default=func.now(),
        index=True,
    )

    __table_args__ = (
        UniqueConstraint("device_uuid", "nonce", name="uq_device_nonce"),
    )

    # Relationships
    device: Mapped[IntegrationDevice] = relationship(
        "IntegrationDevice",
        back_populates="nonces",
    )
