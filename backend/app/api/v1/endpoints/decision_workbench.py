"""Business Decision Workbench API Endpoints (Phase 6.18 Extension).

Enables MSME owners to evaluate critical business options (pricing, discounts,
customer retention, expansion), review supporting evidence and risks,
record final choices, and track outcomes over time.
"""

from __future__ import annotations

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.middleware.auth_deps import get_current_user
from app.models.business import Business
from app.models.user import User
from app.repositories.business_repository import BusinessRepository
from app.schemas.decision_workbench import (
    DecisionCreateRequest,
    DecisionEvaluateRequest,
    DecisionEvaluateResponse,
    DecisionListResponse,
    DecisionOut,
    DecisionUpdateRequest,
)
from app.services.decision_workbench_service import BusinessDecisionService
from app.utils.database import get_db

router = APIRouter(prefix="/decisions", tags=["decision-workbench"])


def _get_active_business(user: User, db: Session) -> Business:
    """Resolve active business for authenticated user enforcing strict tenant isolation."""
    repo = BusinessRepository(db)
    business = repo.get_by_owner(user.id)
    if not business:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active business profile not found. Please complete onboarding first.",
        )
    return business


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
    business = _get_active_business(current_user, db)
    service = BusinessDecisionService(db)
    return service.evaluate_decision(business=business, user=current_user, req=req)


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
    business = _get_active_business(current_user, db)
    service = BusinessDecisionService(db)
    return service.save_decision(business=business, user=current_user, req=req)


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
    business = _get_active_business(current_user, db)
    service = BusinessDecisionService(db)
    return service.list_decisions(business=business, user=current_user, include_archived=include_archived)


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
    business = _get_active_business(current_user, db)
    service = BusinessDecisionService(db)
    decision = service.get_decision(
        decision_id=decision_id,
        business=business,
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
    business = _get_active_business(current_user, db)
    service = BusinessDecisionService(db)
    decision = service.update_decision(
        decision_id=decision_id,
        business=business,
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
    business = _get_active_business(current_user, db)
    service = BusinessDecisionService(db)
    success = service.delete_decision(
        decision_id=decision_id,
        business=business,
        user=current_user,
        cancellation_reason=cancellation_reason,
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Decision {decision_id} not found for active business",
        )
    return {"deleted": True, "id": decision_id, "soft_deleted": True}
