"""Business ORM model.

The parent row in the normalized Business Digital Twin. One-to-many
relationships fan out to products, certifications, digital presence,
export history, goals, and challenges.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.utils.database import Base

if TYPE_CHECKING:
    from app.models.certification import Certification
    from app.models.digital_presence import DigitalPresence
    from app.models.export_history import ExportHistory
    from app.models.product import Product
    from app.models.business_goal import BusinessGoal
    from app.models.business_challenge import BusinessChallenge
    from app.models.sales import SalesTransaction, SalesUpload


class Business(Base):
    """A business owned by a single user."""

    __tablename__ = "businesses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ---- Basic information ----
    legal_name: Mapped[str] = mapped_column(String(200), nullable=False)
    trade_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    industry: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    sub_industry: Mapped[str | None] = mapped_column(String(100), nullable=True)
    business_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    established_year: Mapped[int] = mapped_column(Integer, nullable=False)
    employee_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    annual_revenue: Mapped[float] = mapped_column(nullable=False, default=0)
    revenue_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state_region: Mapped[str | None] = mapped_column(String(100), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # ---- Capacity ----
    production_capacity: Mapped[str | None] = mapped_column(String(500), nullable=True)
    production_capacity_unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    capacity_utilization_pct: Mapped[int | None] = mapped_column(Integer, nullable=True)
    monthly_production_units: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # ---- Misc ----
    is_completed: Mapped[bool] = mapped_column(nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    # ---- Relationships ----
    products: Mapped[list["Product"]] = relationship(
        back_populates="business", cascade="all, delete-orphan", lazy="selectin"
    )
    certifications: Mapped[list["Certification"]] = relationship(
        back_populates="business", cascade="all, delete-orphan", lazy="selectin"
    )
    digital_presence: Mapped["DigitalPresence | None"] = relationship(
        back_populates="business", cascade="all, delete-orphan", lazy="selectin", uselist=False
    )
    export_history: Mapped[list["ExportHistory"]] = relationship(
        back_populates="business", cascade="all, delete-orphan", lazy="selectin"
    )
    goals: Mapped[list["BusinessGoal"]] = relationship(
        back_populates="business", cascade="all, delete-orphan", lazy="selectin"
    )
    challenges: Mapped[list["BusinessChallenge"]] = relationship(
        back_populates="business", cascade="all, delete-orphan", lazy="selectin"
    )
    sales_uploads: Mapped[list["SalesUpload"]] = relationship(
        back_populates="business", cascade="all, delete-orphan", lazy="selectin"
    )
    sales_transactions: Mapped[list["SalesTransaction"]] = relationship(
        back_populates="business", cascade="all, delete-orphan", lazy="selectin"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Business id={self.id} owner={self.owner_id} name={self.legal_name!r}>"
