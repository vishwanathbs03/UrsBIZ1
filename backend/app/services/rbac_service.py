"""Role-Based Access Control (RBAC) Service (Phase 6.26).

Implements:
  - 5 Roles: Owner, Administrator, Manager, Analyst, Viewer.
  - Role Hierarchy and Numerical Ranks.
  - Granular Permissions Matrix for every business action.
  - Cross-User Privilege Escalation Protection.
  - Authoritative multi-user Active Business Resolver.
"""

from __future__ import annotations

from enum import Enum
from typing import NamedTuple

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.business import Business
from app.models.collaboration import BusinessMember, BusinessRole, MemberStatus
from app.models.user import User


class Permission(str, Enum):
    """Granular permissions enforced across backend endpoints."""
    # Business & Governance
    BUSINESS_DELETE = "business:delete"
    BUSINESS_TRANSFER = "business:transfer"
    MEMBERS_VIEW = "members:view"
    MEMBERS_MANAGE = "members:manage"

    # Financial Decisions & Approvals
    FINANCIAL_APPROVE = "financial:approve"
    FINANCIAL_REQUEST = "financial:request"

    # Data Operations
    DATA_VIEW = "data:view"
    DATA_WRITE = "data:write"
    DATA_DELETE = "data:delete"

    # Goals, Simulations & Reports
    GOALS_MANAGE = "goals:manage"
    SIMULATION_RUN = "simulation:run"
    REPORTS_GENERATE = "reports:generate"
    REPORTS_DOWNLOAD = "reports:download"

    # Recommendations & Assistant
    RECOMMENDATION_ACT = "recommendation:act"
    CHAT_COLLABORATE = "chat:collaborate"


ROLE_HIERARCHY: dict[BusinessRole, int] = {
    BusinessRole.OWNER: 50,
    BusinessRole.ADMINISTRATOR: 40,
    BusinessRole.MANAGER: 30,
    BusinessRole.ANALYST: 20,
    BusinessRole.VIEWER: 10,
}

ROLE_PERMISSIONS: dict[BusinessRole, set[Permission]] = {
    BusinessRole.OWNER: {
        Permission.BUSINESS_DELETE,
        Permission.BUSINESS_TRANSFER,
        Permission.MEMBERS_VIEW,
        Permission.MEMBERS_MANAGE,
        Permission.FINANCIAL_APPROVE,
        Permission.FINANCIAL_REQUEST,
        Permission.DATA_VIEW,
        Permission.DATA_WRITE,
        Permission.DATA_DELETE,
        Permission.GOALS_MANAGE,
        Permission.SIMULATION_RUN,
        Permission.REPORTS_GENERATE,
        Permission.REPORTS_DOWNLOAD,
        Permission.RECOMMENDATION_ACT,
        Permission.CHAT_COLLABORATE,
    },
    BusinessRole.ADMINISTRATOR: {
        Permission.MEMBERS_VIEW,
        Permission.MEMBERS_MANAGE,
        Permission.FINANCIAL_APPROVE,
        Permission.FINANCIAL_REQUEST,
        Permission.DATA_VIEW,
        Permission.DATA_WRITE,
        Permission.DATA_DELETE,
        Permission.GOALS_MANAGE,
        Permission.SIMULATION_RUN,
        Permission.REPORTS_GENERATE,
        Permission.REPORTS_DOWNLOAD,
        Permission.RECOMMENDATION_ACT,
        Permission.CHAT_COLLABORATE,
    },
    BusinessRole.MANAGER: {
        Permission.MEMBERS_VIEW,
        Permission.FINANCIAL_APPROVE,
        Permission.FINANCIAL_REQUEST,
        Permission.DATA_VIEW,
        Permission.DATA_WRITE,
        Permission.GOALS_MANAGE,
        Permission.SIMULATION_RUN,
        Permission.REPORTS_GENERATE,
        Permission.REPORTS_DOWNLOAD,
        Permission.RECOMMENDATION_ACT,
        Permission.CHAT_COLLABORATE,
    },
    BusinessRole.ANALYST: {
        Permission.MEMBERS_VIEW,
        Permission.FINANCIAL_REQUEST,
        Permission.DATA_VIEW,
        Permission.SIMULATION_RUN,
        Permission.REPORTS_GENERATE,
        Permission.REPORTS_DOWNLOAD,
        Permission.CHAT_COLLABORATE,
    },
    BusinessRole.VIEWER: {
        Permission.MEMBERS_VIEW,
        Permission.DATA_VIEW,
        Permission.REPORTS_DOWNLOAD,
        Permission.CHAT_COLLABORATE,
    },
}


class BusinessContext(NamedTuple):
    """Encapsulates the authorized business, authenticated user, and resolved role."""
    business: Business
    user: User
    role: BusinessRole

    def has_permission(self, permission: Permission) -> bool:
        return RBACService.has_permission(self.role, permission)


class RBACService:
    """Authoritative RBAC and tenant authorization engine."""

    @staticmethod
    def get_role_enum(role_str: str) -> BusinessRole:
        for r in BusinessRole:
            if r.value.lower() == role_str.strip().lower():
                return r
        raise ValueError(f"Unknown business role: {role_str}")

    @staticmethod
    def has_permission(role: BusinessRole, permission: Permission) -> bool:
        allowed = ROLE_PERMISSIONS.get(role, set())
        return permission in allowed

    @staticmethod
    def check_permission(role: BusinessRole, permission: Permission) -> None:
        if not RBACService.has_permission(role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: Role '{role.value}' does not possess required permission '{permission.value}'.",
            )

    @staticmethod
    def can_manage_target_role(actor_role: BusinessRole, target_role: BusinessRole) -> bool:
        """Privilege escalation check: actor must have strictly higher hierarchy rank than target."""
        actor_rank = ROLE_HIERARCHY.get(actor_role, 0)
        target_rank = ROLE_HIERARCHY.get(target_role, 0)
        return actor_rank > target_rank

    @staticmethod
    def get_user_business_role(db: Session, user_id: int, business: Business) -> BusinessRole | None:
        """Resolve a user's role for a business."""
        if business.owner_id == user_id:
            return BusinessRole.OWNER

        member = db.query(BusinessMember).filter(
            BusinessMember.business_id == business.id,
            BusinessMember.user_id == user_id,
            BusinessMember.status == MemberStatus.ACTIVE.value,
        ).first()

        if member:
            try:
                return RBACService.get_role_enum(member.role)
            except ValueError:
                return None
        return None

    @staticmethod
    def resolve_active_business(user: User, db: Session) -> BusinessContext:
        """Resolve active business and authorized role for a user.

        Guarantees:
          - If user.active_business_id is set, validates ownership or active membership.
          - If user.active_business_id is unset, falls back to most recently owned or joined business.
          - Raises 404 if no authorized business is available.
        """
        # 1. Explicit active_business_id set on user profile
        if user.active_business_id is not None:
            business = db.query(Business).filter(Business.id == user.active_business_id).first()
            if business:
                role = RBACService.get_user_business_role(db, user.id, business)
                if role is not None:
                    return BusinessContext(business=business, user=user, role=role)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Active business {user.active_business_id} not found or inaccessible (user lacks active membership).",
            )

        # 2. Fallback: Most recently created business owned by the user
        owned_business = db.query(Business).filter(
            Business.owner_id == user.id
        ).order_by(Business.id.desc()).first()

        if owned_business:
            return BusinessContext(business=owned_business, user=user, role=BusinessRole.OWNER)

        # 3. Fallback: Most recently joined business where user is an active member
        stmt = (
            select(Business)
            .join(BusinessMember, BusinessMember.business_id == Business.id)
            .where(
                BusinessMember.user_id == user.id,
                BusinessMember.status == MemberStatus.ACTIVE.value,
            )
            .order_by(BusinessMember.id.desc())
        )
        membership_business = db.scalar(stmt)
        if membership_business:
            role = RBACService.get_user_business_role(db, user.id, membership_business)
            if role is not None:
                return BusinessContext(business=membership_business, user=user, role=role)

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active business profile or membership found for user. Please complete onboarding first.",
        )
