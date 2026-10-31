"""Context-Aware Smart Recommendations API Endpoints (Phase 5).

Endpoints for:
  - GET /recommendations: List context-grounded recommendations with category/priority/status filters
  - PATCH /recommendations/{id}/status: Update recommendation lifecycle status (New -> Viewed -> Accepted -> In Progress -> Completed -> Dismissed)
  - POST /recommendations/{id}/explain: AI explanation with deterministic fallback
"""

from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.middleware.auth_deps import get_current_user
from app.models.user import User
from app.repositories.business_repository import BusinessRepository
from app.repositories.recommendation_lifecycle_repository import (
    RecommendationLifecycleRepository,
)
from app.schemas.smart_recommendations import (
    RecommendationExplainResponse,
    RecommendationStatus,
    RecommendationStatusUpdateRequest,
    SmartRecommendationItem,
    SmartRecommendationsResponse,
)
from app.services.recommendations.explanation_service import explain_recommendation
from app.services.recommendations.recommendation_engine import SmartRecommendationEngine
from app.utils.database import get_db

router = APIRouter(prefix="/recommendations", tags=["smart-recommendations"])


def _get_active_business(user: User, db: Session):
    """Resolve active business for authenticated user enforcing tenant isolation."""
    repo = BusinessRepository(db)
    business = repo.get_by_owner(user.id)
    if not business:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active business profile found for this user.",
        )
    return business


@router.get(
    "",
    response_model=SmartRecommendationsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get context-aware business recommendations across 10 categories",
)
def get_smart_recommendations(
    category: Optional[str] = Query(None, description="Filter by category (e.g. 'Revenue Growth', 'Customer Retention')"),
    priority: Optional[str] = Query(None, description="Filter by priority ('Critical', 'High', 'Medium', 'Low')"),
    status: Optional[str] = Query(None, description="Filter by lifecycle status ('New', 'Viewed', 'Accepted', 'In Progress', 'Completed', 'Dismissed')"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SmartRecommendationsResponse:
    business = _get_active_business(current_user, db)
    engine = SmartRecommendationEngine(db)
    return engine.generate_recommendations(
        business=business,
        category_filter=category,
        priority_filter=priority,
        status_filter=status,
    )


@router.patch(
    "/{recommendation_id}/status",
    status_code=status.HTTP_200_OK,
    summary="Update recommendation lifecycle status",
)
def update_recommendation_status(
    recommendation_id: str,
    payload: RecommendationStatusUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    business = _get_active_business(current_user, db)
    repo = RecommendationLifecycleRepository(db)
    updated = repo.update_status(
        business_id=business.id,
        recommendation_id=recommendation_id,
        status=payload.status.value,
        notes=payload.notes,
    )
    return {
        "business_id": business.id,
        "recommendation_id": updated.recommendation_id,
        "status": updated.status,
        "status_updated_at": updated.status_updated_at.isoformat() if updated.status_updated_at else None,
        "notes": updated.notes,
    }


@router.post(
    "/{recommendation_id}/explain",
    response_model=RecommendationExplainResponse,
    status_code=status.HTTP_200_OK,
    summary="AI-powered explanation with deterministic fallback for a recommendation",
)
def explain_smart_recommendation(
    recommendation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RecommendationExplainResponse:
    business = _get_active_business(current_user, db)
    engine = SmartRecommendationEngine(db)
    response = engine.generate_recommendations(business=business, status_filter="all")

    target_rec: Optional[SmartRecommendationItem] = None
    for rec in response.recommendations:
        if rec.id == recommendation_id:
            target_rec = rec
            break

    if target_rec is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recommendation '{recommendation_id}' not found for active business.",
        )

    return explain_recommendation(
        rec=target_rec,
        business_name=business.legal_name,
        industry=business.industry or "General MSME",
    )
