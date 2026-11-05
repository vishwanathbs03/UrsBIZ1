"""FastAPI dependency injection utilities for Role-Based Access Control (Phase 6.26).

Provides:
  - get_active_business_context: Resolves authorized Business and active BusinessRole.
  - require_permission(perm): Dependency factory enforcing granular permissions.
  - require_role(min_role): Dependency factory enforcing role hierarchy rank.
"""

from __future__ import annotations

from typing import Annotated, Callable
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.middleware.auth_deps import get_current_user
from app.models.business import Business
from app.models.user import User
from app.services.rbac_service import (
    BusinessContext,
    BusinessRole,
    Permission,
    RBACService,
    ROLE_HIERARCHY,
)
from app.utils.database import get_db


def get_active_business_context(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> BusinessContext:
    """Dependency to resolve the authenticated user's active business and role."""
    return RBACService.resolve_active_business(user=current_user, db=db)


def get_active_business_model(
    ctx: Annotated[BusinessContext, Depends(get_active_business_context)],
) -> Business:
    """Convenience dependency returning just the Business model."""
    return ctx.business


def require_permission(permission: Permission) -> Callable[[BusinessContext], BusinessContext]:
    """Dependency factory that validates the user's role possesses the requested permission."""
    def _dependency(
        ctx: Annotated[BusinessContext, Depends(get_active_business_context)],
    ) -> BusinessContext:
        RBACService.check_permission(role=ctx.role, permission=permission)
        return ctx

    return _dependency


def require_role(min_role: BusinessRole) -> Callable[[BusinessContext], BusinessContext]:
    """Dependency factory ensuring the user's role meets or exceeds a minimum hierarchy rank."""
    def _dependency(
        ctx: Annotated[BusinessContext, Depends(get_active_business_context)],
    ) -> BusinessContext:
        current_rank = ROLE_HIERARCHY.get(ctx.role, 0)
        required_rank = ROLE_HIERARCHY.get(min_role, 0)
        if current_rank < required_rank:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: Minimum role required is '{min_role.value}', but active role is '{ctx.role.value}'.",
            )
        return ctx

    return _dependency
