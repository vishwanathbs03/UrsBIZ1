"""Business Goals and Progress Tracker API Endpoints (Prompt 6.24).

Enables MSME owners to:
  - Define measurable business goals linked to authoritative metrics.
  - Track progress deterministically from verified business evidence.
  - Distinguish automated metrics from manual declarations and estimates.
  - Maintain an append-only audit trail and review trajectory over time.
  - Request non-mutating AI guidance and trajectory evaluations.
  - Enforce strict tenant isolation on every operation.
"""

from __future__ import annotations

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.middleware.auth_deps import get_current_user
from app.models.business import Business
from app.models.user import User
from app.repositories.business_repository import BusinessRepository
from app.schemas.business_goal import (
    BusinessGoalAuditOut,
    BusinessGoalCreate,
    BusinessGoalListResponse,
    BusinessGoalManualProgressUpdate,
    BusinessGoalOut,
    BusinessGoalStatusUpdate,
    BusinessGoalUpdate,
    GoalAIExplanationResponse,
)
from app.services.business_goal_service import BusinessGoalService
from app.utils.database import get_db

router = APIRouter(prefix="/goals", tags=["business-goals"])


def _get_active_business(user: User, db: Session) -> Business:
    """Resolve active business for authenticated user enforcing strict tenant isolation.

    If user.active_business_id is explicitly set:
        Must resolve to an accessible business owned by the user. If not found or
        unauthorized, raises 404 immediately to prevent silent business switching.
    If user.active_business_id is None (unselected):
        Falls back to the user's most recently created business.
    """
    repo = BusinessRepository(db)
    if user.active_business_id is not None:
        direct = repo.get_by_id_for_owner(
            business_id=user.active_business_id, owner_id=user.id
        )
        if direct is not None:
            return direct
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Active business profile {user.active_business_id} not found or inaccessible for current user.",
        )

    # Initial onboarding fallback when active_business_id was never set
    rows = repo.list_for_owner(user.id)
    if rows:
        return rows[-1]
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Active business profile not found. Please complete onboarding first.",
    )


@router.post(
    "",
    response_model=BusinessGoalOut,
    status_code=status.HTTP_201_CREATED,
    summary="Define a new measurable business goal linked to an authoritative metric",
)
def create_goal(
    payload: BusinessGoalCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> BusinessGoalOut:
    """Create a new business goal with strict tenant association."""
    biz = _get_active_business(current_user, db)
    svc = BusinessGoalService(db)
    try:
        return svc.create_goal(
            business_id=biz.id,
            user_id=current_user.id,
            payload=payload,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get(
    "",
    response_model=BusinessGoalListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all business goals with evaluated progress, counters, and data availability",
)
def list_goals(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    include_archived: bool = Query(
        False, description="Whether to include soft-deleted/archived goals"
    ),
    status_filter: str | None = Query(
        None, alias="status", description="Filter by status (ACTIVE, PAUSED, COMPLETED, EXPIRED)"
    ),
) -> BusinessGoalListResponse:
    """Retrieve all business goals for active business."""
    biz = _get_active_business(current_user, db)
    svc = BusinessGoalService(db)
    return svc.list_goals(
        business_id=biz.id,
        include_archived=include_archived,
        status=status_filter,
    )


@router.get(
    "/{goal_id}",
    response_model=BusinessGoalOut,
    status_code=status.HTTP_200_OK,
    summary="Get single business goal with fresh evaluated progress and related actions",
)
def get_goal(
    goal_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> BusinessGoalOut:
    """Retrieve single goal with strict tenant boundary check."""
    biz = _get_active_business(current_user, db)
    svc = BusinessGoalService(db)
    try:
        return svc.get_goal(goal_id=goal_id, business_id=biz.id, re_evaluate=True)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.put(
    "/{goal_id}",
    response_model=BusinessGoalOut,
    status_code=status.HTTP_200_OK,
    summary="Update goal details or target threshold",
)
def update_goal(
    goal_id: int,
    payload: BusinessGoalUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> BusinessGoalOut:
    """Update goal configuration and append to audit history."""
    biz = _get_active_business(current_user, db)
    svc = BusinessGoalService(db)
    try:
        return svc.update_goal(
            goal_id=goal_id,
            business_id=biz.id,
            user_id=current_user.id,
            payload=payload,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post(
    "/{goal_id}/status",
    response_model=BusinessGoalOut,
    status_code=status.HTTP_200_OK,
    summary="Transition goal status with state-machine validation",
)
def update_goal_status(
    goal_id: int,
    payload: BusinessGoalStatusUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> BusinessGoalOut:
    """Transition goal status adhering to validated lifecycle rules."""
    biz = _get_active_business(current_user, db)
    svc = BusinessGoalService(db)
    try:
        return svc.update_status(
            goal_id=goal_id,
            business_id=biz.id,
            user_id=current_user.id,
            payload=payload,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post(
    "/{goal_id}/progress",
    response_model=BusinessGoalOut,
    status_code=status.HTTP_200_OK,
    summary="Record manual self-reported progress for a goal",
)
def record_manual_progress(
    goal_id: int,
    payload: BusinessGoalManualProgressUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> BusinessGoalOut:
    """Record owner manual progress declaration."""
    biz = _get_active_business(current_user, db)
    svc = BusinessGoalService(db)
    try:
        return svc.record_manual_progress(
            goal_id=goal_id,
            business_id=biz.id,
            user_id=current_user.id,
            payload=payload,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post(
    "/{goal_id}/evaluate",
    response_model=BusinessGoalOut,
    status_code=status.HTTP_200_OK,
    summary="Trigger deterministic re-evaluation against latest business transactions",
)
def evaluate_goal(
    goal_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> BusinessGoalOut:
    """Re-evaluate progress deterministically."""
    biz = _get_active_business(current_user, db)
    svc = BusinessGoalService(db)
    try:
        return svc.get_goal(goal_id=goal_id, business_id=biz.id, re_evaluate=True)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.delete(
    "/{goal_id}",
    response_model=BusinessGoalOut,
    status_code=status.HTTP_200_OK,
    summary="Archive (soft-delete) a business goal while preserving its historical audit snapshots",
)
def archive_goal(
    goal_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    reason: str | None = Query(None, description="Optional archival rationale"),
) -> BusinessGoalOut:
    """Soft delete goal and write archival entry to immutable audit log."""
    biz = _get_active_business(current_user, db)
    svc = BusinessGoalService(db)
    try:
        return svc.archive_goal(
            goal_id=goal_id,
            business_id=biz.id,
            user_id=current_user.id,
            reason=reason,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get(
    "/{goal_id}/history",
    response_model=list[BusinessGoalAuditOut],
    status_code=status.HTTP_200_OK,
    summary="Fetch chronological audit history and progress snapshots for a goal",
)
def get_goal_history(
    goal_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[BusinessGoalAuditOut]:
    """Retrieve immutable audit snapshots for a goal."""
    biz = _get_active_business(current_user, db)
    svc = BusinessGoalService(db)
    return svc.get_goal_history(goal_id=goal_id, business_id=biz.id)


@router.post(
    "/{goal_id}/explain",
    response_model=GoalAIExplanationResponse,
    status_code=status.HTTP_200_OK,
    summary="Request non-mutating AI trajectory analysis and tactical suggestions",
)
def explain_goal_trajectory(
    goal_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> GoalAIExplanationResponse:
    """Generate grounded, non-mutating AI trajectory advice."""
    biz = _get_active_business(current_user, db)
    svc = BusinessGoalService(db)
    try:
        return svc.explain_goal(goal_id=goal_id, business_id=biz.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
