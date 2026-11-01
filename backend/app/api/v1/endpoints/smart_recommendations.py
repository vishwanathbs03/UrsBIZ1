"""Context-Aware Smart Recommendations API Endpoints (Phase 5 Advanced Intelligence).

Endpoints for:
  - GET /recommendations: List context-grounded recommendations with category/priority/status filters
  - GET /recommendations/advanced-overview: Next Best Action, Multi-Signal Insights, Root Causes, and Opportunities
  - GET /recommendations/growth-strategy: 3-Horizon personalized growth roadmap
  - POST /recommendations/scenarios/simulate: Deterministic What-If impact simulation
  - POST /recommendations/feedback: Submit owner feedback and automatic recommendation suppression
  - PATCH /recommendations/{id}/status: Update recommendation lifecycle status
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
from app.schemas.advanced_recommendations import (
    AdvancedRecommendationsOverviewResponse,
    PersonalizedGrowthStrategy,
    RecommendationAskRequest,
    RecommendationAskResponse,
    RecommendationFeedbackCreate,
    RecommendationFeedbackResponse,
    ScenarioSimulationRequest,
    ScenarioSimulationResponse,
)
from app.schemas.smart_recommendations import (
    RecommendationExplainResponse,
    RecommendationStatusUpdateRequest,
    SmartRecommendationItem,
    SmartRecommendationsResponse,
)
from app.schemas.personalization import (
    PersonalizationSettingsUpdate,
    RecommendationPersonalizationProfile,
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
    limit: int = Query(50, ge=1, le=200, description="Pagination page size"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SmartRecommendationsResponse:
    business = _get_active_business(current_user, db)
    engine = SmartRecommendationEngine(db)
    res = engine.generate_recommendations(
        business=business,
        category_filter=category,
        priority_filter=priority,
        status_filter=status,
    )
    if offset > 0 or limit < len(res.recommendations):
        res.recommendations = res.recommendations[offset : offset + limit]
    return res


@router.get(
    "/advanced-overview",
    response_model=AdvancedRecommendationsOverviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Get advanced intelligence overview (Next Best Action, Multi-Signal Insights, Root Causes, Opportunities)",
)
def get_advanced_overview(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdvancedRecommendationsOverviewResponse:
    business = _get_active_business(current_user, db)
    engine = SmartRecommendationEngine(db)
    return engine.get_advanced_overview(business=business)


@router.get(
    "/growth-strategy",
    response_model=PersonalizedGrowthStrategy,
    status_code=status.HTTP_200_OK,
    summary="Get personalized 3-horizon growth strategy (0-30d, 31-90d, 3-12m)",
)
def get_growth_strategy(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PersonalizedGrowthStrategy:
    business = _get_active_business(current_user, db)
    engine = SmartRecommendationEngine(db)
    return engine.get_growth_strategy(business=business)


@router.get(
    "/personalization/profile",
    response_model=RecommendationPersonalizationProfile,
    status_code=status.HTTP_200_OK,
    summary="Get structured recommendation personalization profile (Business DNA, goals, constraints)",
)
def get_personalization_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RecommendationPersonalizationProfile:
    business = _get_active_business(current_user, db)
    engine = SmartRecommendationEngine(db)
    return engine.get_personalization_profile(business=business)


@router.put(
    "/personalization/settings",
    response_model=RecommendationPersonalizationProfile,
    status_code=status.HTTP_200_OK,
    summary="Update owner recommendation goals, resource constraints, and preferences",
)
def update_personalization_settings(
    payload: PersonalizationSettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RecommendationPersonalizationProfile:
    business = _get_active_business(current_user, db)
    engine = SmartRecommendationEngine(db)
    return engine.update_personalization_settings(business=business, payload=payload)


@router.post(
    "/scenarios/simulate",
    response_model=ScenarioSimulationResponse,
    status_code=status.HTTP_200_OK,
    summary="Simulate deterministic What-If business scenarios",
)
def simulate_scenario(
    payload: ScenarioSimulationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ScenarioSimulationResponse:
    business = _get_active_business(current_user, db)
    engine = SmartRecommendationEngine(db)
    return engine.simulate_scenario(business=business, req=payload)


@router.post(
    "/feedback",
    response_model=RecommendationFeedbackResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit owner feedback and auto-suppress dismissed recommendations",
)
def submit_recommendation_feedback(
    payload: RecommendationFeedbackCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RecommendationFeedbackResponse:
    business = _get_active_business(current_user, db)
    engine = SmartRecommendationEngine(db)
    return engine.record_feedback(business=business, req=payload)


@router.post(
    "/ask",
    response_model=RecommendationAskResponse,
    status_code=status.HTTP_200_OK,
    summary="Ask natural language questions to the AI Recommendation Consultant",
)
def ask_recommendation_question(
    payload: RecommendationAskRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RecommendationAskResponse:
    business = _get_active_business(current_user, db)
    engine = SmartRecommendationEngine(db)
    return engine.ask_recommendation_question(business=business, req=payload)


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
