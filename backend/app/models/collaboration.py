"""ORM models for MSME Collaboration, Role-Based Access Control (RBAC), and Approvals (Phase 6.26).

Implements:
  - BusinessMember: Multi-user membership mapping users to businesses with distinct roles:
    (Owner, Administrator, Manager, Analyst, Viewer).
  - BusinessInvitation: Secure invitation lifecycle for onboarding collaborators.
  - ApprovalRequest: Formal approval workflows for financial decisions, recommendations, and strategic actions.
  - ApprovalAudit: Immutable audit trail for all approval requests and lifecycle actions.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    event,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.utils.database import Base

if TYPE_CHECKING:
    from app.models.business import Business
    from app.models.user import User


class BusinessRole(str, Enum):
    """5 Core Roles conforming to the frozen Phase 6.26 specification."""
    OWNER = "Owner"
    ADMINISTRATOR = "Administrator"
    MANAGER = "Manager"
    ANALYST = "Analyst"
    VIEWER = "Viewer"


class MemberStatus(str, Enum):
    """Membership statuses."""
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    REVOKED = "REVOKED"


class InvitationStatus(str, Enum):
    """Collaborator invitation statuses."""
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"


class ApprovalStatus(str, Enum):
    """Approval request review states."""
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class ApprovalEntityType(str, Enum):
    """Types of business entities requiring approval workflows."""
    DECISION = "DECISION"
    RECOMMENDATION = "RECOMMENDATION"
    BUDGET = "BUDGET"
    DISCOUNT = "DISCOUNT"
    GOAL = "GOAL"


class BusinessMember(Base):
    """Maps a user to a business workspace with an assigned role."""

    __tablename__ = "business_members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    business_id: Mapped[int] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=MemberStatus.ACTIVE.value, index=True)
    invited_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
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

    business: Mapped["Business"] = relationship(back_populates="members")
    user: Mapped["User"] = relationship(foreign_keys=[user_id])
    invited_by: Mapped["User | None"] = relationship(foreign_keys=[invited_by_user_id])

    __table_args__ = (
        UniqueConstraint("business_id", "user_id", name="uq_business_member_user"),
    )


class BusinessInvitation(Base):
    """An outstanding or resolved invitation to join a business."""

    __tablename__ = "business_invitations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    business_id: Mapped[int] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    token: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    invited_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=InvitationStatus.PENDING.value, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
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

    business: Mapped["Business"] = relationship(back_populates="invitations")
    invited_by: Mapped["User | None"] = relationship(foreign_keys=[invited_by_user_id])


class ApprovalRequest(Base):
    """Formal business approval request submitted by a collaborator."""

    __tablename__ = "business_approval_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    business_id: Mapped[int] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    requester_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)  # DECISION, RECOMMENDATION, etc.
    entity_id: Mapped[str] = mapped_column(String(128), nullable=False)   # Target record ID
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    financial_impact_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=ApprovalStatus.PENDING.value, index=True)
    approver_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    decision_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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

    business: Mapped["Business"] = relationship(back_populates="approval_requests")
    requester: Mapped["User | None"] = relationship(foreign_keys=[requester_user_id])
    approver: Mapped["User | None"] = relationship(foreign_keys=[approver_user_id])
    audits: Mapped[list["ApprovalAudit"]] = relationship(
        back_populates="approval_request",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="ApprovalAudit.created_at.asc()",
    )


class ApprovalAudit(Base):
    """Append-only audit trail capturing all approval workflow decisions and transitions.

    Foreign key business_id uses ondelete='RESTRICT' so deleting a business cannot silently
    destroy audit records without explicit archival handling.
    """

    __tablename__ = "business_approval_audits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    business_id: Mapped[int] = mapped_column(
        ForeignKey("businesses.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    approval_request_id: Mapped[int] = mapped_column(
        ForeignKey("business_approval_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False)  # SUBMITTED, APPROVED, REJECTED, CANCELLED
    previous_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    new_status: Mapped[str] = mapped_column(String(32), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )

    approval_request: Mapped["ApprovalRequest"] = relationship(back_populates="audits")
    user: Mapped["User | None"] = relationship(foreign_keys=[user_id])


# ------------------------------------------------------------------------------
# Immutability Protection for ApprovalAudit
# ------------------------------------------------------------------------------

@event.listens_for(ApprovalAudit, "before_update")
def _prevent_approval_audit_update(mapper, connection, target):
    raise ValueError("ApprovalAudit records are strictly append-only and cannot be updated.")


@event.listens_for(ApprovalAudit, "before_delete")
def _prevent_approval_audit_delete(mapper, connection, target):
    raise ValueError("ApprovalAudit records are strictly append-only and cannot be deleted.")
