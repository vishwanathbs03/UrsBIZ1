"""Business Decision Workbench API Endpoints (Phase 6.18 & Phase 6.26 RBAC).

Enables MSME owners and collaborators to evaluate critical business options (pricing, discounts,
customer retention, expansion), review supporting evidence and risks,
record final choices, and track outcomes over time.

Enforces role-based permissions:
  - Viewers cannot delete data or approve financial decisions.
  - Analysts can evaluate and propose decisions, but cannot approve or delete.
  - Managers can propose and approve within operational authority.
  - Admins and Owners have full authority.
"""

from __future__ import annotations

from typing import Annotated, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.middleware.auth_deps import get_current_user
from app.models.business import Business
from app.models.user import User
from app.schemas.decision_workbench import (
    DecisionCreateRequest,
    DecisionEvaluateRequest,
    DecisionEvaluateResponse,
    DecisionListResponse,
    DecisionOut,
    DecisionUpdateRequest,
)
from app.services.decision_workbench_service import BusinessDecisionService
from app.services.rbac_service import BusinessContext, Permission, RBACService
from app.utils.database import get_db

router = APIRouter(prefix="/decisions", tags=["decision-workbench"])


def _get_business_context(user: User, db: Session) -> BusinessContext:
    """Resolve active business and user role enforcing tenant isolation and RBAC."""
    return RBACService.resolve_active_business(user=user, db=db)


@router.post(
    "/evaluate",
    response_model=DecisionEvaluateResponse,
    status_code=status.HTTP_200_OK,
    summary="Evaluate multi-option comparisons, evidence, and financial impacts for a decision objective",
)
def evaluate_decision(
    req: DecisionEvaluateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> DecisionEvaluateResponse:
    ctx = _get_business_context(current_user, db)
    RBACService.check_permission(ctx.role, Permission.FINANCIAL_REQUEST)
    service = BusinessDecisionService(db)
    return service.evaluate_decision(business=ctx.business, user=current_user, req=req)


@router.post(
    "",
    response_model=DecisionOut,
    status_code=status.HTTP_201_CREATED,
    summary="Save an evaluated decision into the business workspace",
)
def create_decision(
    req: DecisionCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> DecisionOut:
    ctx = _get_business_context(current_user, db)
    RBACService.check_permission(ctx.role, Permission.FINANCIAL_REQUEST)
    service = BusinessDecisionService(db)
    return service.save_decision(business=ctx.business, user=current_user, req=req)


@router.get(
    "",
    response_model=DecisionListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all decisions for the active business",
)
def list_decisions(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    include_archived: bool = False,
) -> DecisionListResponse:
    ctx = _get_business_context(current_user, db)
    RBACService.check_permission(ctx.role, Permission.DATA_VIEW)
    service = BusinessDecisionService(db)
    return service.list_decisions(business=ctx.business, user=current_user, include_archived=include_archived)


@router.get(
    "/{decision_id}",
    response_model=DecisionOut,
    status_code=status.HTTP_200_OK,
    summary="Retrieve a single decision with full option comparisons and evidence",
)
def get_decision(
    decision_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    include_archived: bool = False,
) -> DecisionOut:
    ctx = _get_business_context(current_user, db)
    RBACService.check_permission(ctx.role, Permission.DATA_VIEW)
    service = BusinessDecisionService(db)
    decision = service.get_decision(
        decision_id=decision_id,
        business=ctx.business,
        user=current_user,
        include_archived=include_archived,
    )
    if not decision:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Decision {decision_id} not found for active business",
        )
    return decision


@router.patch(
    "/{decision_id}",
    response_model=DecisionOut,
    status_code=status.HTTP_200_OK,
    summary="Update decision choice, rationale, status, or review notes",
)
def update_decision(
    decision_id: int,
    req: DecisionUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> DecisionOut:
    ctx = _get_business_context(current_user, db)
    RBACService.check_permission(ctx.role, Permission.FINANCIAL_REQUEST)

    # If approving a decision, verify FINANCIAL_APPROVE permission (Viewers and Analysts cannot approve)
    if req.status and (req.status in ("Decided", "Implemented") or req.status.upper() == "APPROVED"):
        RBACService.check_permission(ctx.role, Permission.FINANCIAL_APPROVE)

    service = BusinessDecisionService(db)
    decision = service.update_decision(
        decision_id=decision_id,
        business=ctx.business,
        user=current_user,
        req=req,
    )
    if not decision:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Decision {decision_id} not found for active business",
        )
    return decision


@router.delete(
    "/{decision_id}",
    status_code=status.HTTP_200_OK,
    summary="Cancel / soft-delete a decision record to preserve audit history",
)
def delete_decision(
    decision_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    cancellation_reason: str | None = None,
) -> dict[str, Any]:
    ctx = _get_business_context(current_user, db)
    RBACService.check_permission(ctx.role, Permission.DATA_DELETE)
    service = BusinessDecisionService(db)
    success = service.delete_decision(
        decision_id=decision_id,
        business=ctx.business,
        user=current_user,
        cancellation_reason=cancellation_reason,
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Decision {decision_id} not found for active business",
        )
    return {"deleted": True, "id": decision_id, "soft_deleted": True, "success": True, "message": f"Decision {decision_id} cancelled / soft-deleted"}
