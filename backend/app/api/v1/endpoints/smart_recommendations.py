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
from app.schemas.portfolio import (
    PortfolioSequenceUpdateRequest,
    RecommendationPortfolioResponse,
)
from app.schemas.recommendation_outcomes import (
    BeforeAfterMeasurementResponse,
    CompleteHistoryResponse,
    OutcomeRecordingRequest,
    OutcomeTrackingResponse,
    RecommendationEffectivenessResponse,
    RecommendationHistoryResponse,
)
from app.schemas.business_monitoring import (
    BusinessSignalsFeedResponse,
    MonitoringEvaluationResponse,
    MonitoringPreferencesSchema,
    MonitoringPreferencesUpdate,
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
    "/portfolio",
    response_model=RecommendationPortfolioResponse,
    status_code=status.HTTP_200_OK,
    summary="Get optimized recommendation portfolio with dependencies, conflicts, and execution sequence",
)
def get_recommendation_portfolio(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RecommendationPortfolioResponse:
    business = _get_active_business(current_user, db)
    engine = SmartRecommendationEngine(db)
    return engine.get_recommendation_portfolio(business=business)


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


@router.get(
    "/effectiveness/analytics",
    response_model=RecommendationEffectivenessResponse,
    status_code=status.HTTP_200_OK,
    summary="Get recommendation effectiveness intelligence with small-sample safeguards",
)
def get_recommendation_effectiveness(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RecommendationEffectivenessResponse:
    business = _get_active_business(current_user, db)
    engine = SmartRecommendationEngine(db)
    return engine.get_effectiveness_analytics(business=business)


@router.get(
    "/history/all",
    response_model=CompleteHistoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get complete historical audit log of recommendation events and decisions",
)
def get_complete_recommendation_history(
    limit: int = Query(default=100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CompleteHistoryResponse:
    business = _get_active_business(current_user, db)
    engine = SmartRecommendationEngine(db)
    return engine.get_complete_history(business=business, limit=limit)


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


@router.post(
    "/{recommendation_id}/outcome",
    response_model=OutcomeTrackingResponse,
    status_code=status.HTTP_200_OK,
    summary="Record implementation outcome, feedback, and before/after measurements",
)
def record_recommendation_outcome(
    recommendation_id: str,
    payload: OutcomeRecordingRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OutcomeTrackingResponse:
    business = _get_active_business(current_user, db)
    engine = SmartRecommendationEngine(db)
    return engine.record_outcome(business=business, recommendation_id=recommendation_id, req=payload)


@router.get(
    "/{recommendation_id}/outcome",
    response_model=OutcomeTrackingResponse,
    status_code=status.HTTP_200_OK,
    summary="Get recommendation outcome tracking and empirical before/after measurements",
)
def get_recommendation_outcome(
    recommendation_id: str,
    window_days: int = Query(default=30, ge=7, le=90),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OutcomeTrackingResponse:
    business = _get_active_business(current_user, db)
    engine = SmartRecommendationEngine(db)
    return engine.get_outcome(business=business, recommendation_id=recommendation_id, window_days=window_days)


@router.get(
    "/{recommendation_id}/history",
    response_model=RecommendationHistoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get immutable audit version history for a specific recommendation",
)
def get_recommendation_version_history(
    recommendation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RecommendationHistoryResponse:
    business = _get_active_business(current_user, db)
    engine = SmartRecommendationEngine(db)
    return engine.get_recommendation_history(business=business, recommendation_id=recommendation_id)


# --------------------------------------------------------------------------- #
# Proactive AI Business Monitoring & Event-Driven Intelligence (Phase 5)       #
# --------------------------------------------------------------------------- #

@router.get(
    "/monitoring/signals",
    response_model=BusinessSignalsFeedResponse,
    status_code=status.HTTP_200_OK,
    summary="Get proactive business signals, emerging risks, and opportunities feed",
)
def get_monitoring_signals(
    min_severity: Optional[str] = Query(None, description="'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'INFORMATIONAL'"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BusinessSignalsFeedResponse:
    business = _get_active_business(current_user, db)
    engine = SmartRecommendationEngine(db)
    return engine.get_signals_feed(business=business, min_severity=min_severity)


@router.post(
    "/monitoring/evaluate",
    response_model=MonitoringEvaluationResponse,
    status_code=status.HTTP_200_OK,
    summary="Trigger incremental proactive change detection scan and recommendation refresh",
)
def evaluate_business_monitoring(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MonitoringEvaluationResponse:
    business = _get_active_business(current_user, db)
    engine = SmartRecommendationEngine(db)
    return engine.evaluate_monitoring(business=business)


@router.get(
    "/monitoring/preferences",
    response_model=MonitoringPreferencesSchema,
    status_code=status.HTTP_200_OK,
    summary="Get owner monitoring preferences and notification settings",
)
def get_monitoring_preferences(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MonitoringPreferencesSchema:
    business = _get_active_business(current_user, db)
    engine = SmartRecommendationEngine(db)
    return engine.get_monitoring_preferences(business=business)


@router.put(
    "/monitoring/preferences",
    response_model=MonitoringPreferencesSchema,
    status_code=status.HTTP_200_OK,
    summary="Update owner monitoring preferences with critical safety preservation",
)
def update_monitoring_preferences(
    payload: MonitoringPreferencesUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MonitoringPreferencesSchema:
    business = _get_active_business(current_user, db)
    engine = SmartRecommendationEngine(db)
    return engine.update_monitoring_preferences(business=business, payload=payload)


@router.post(
    "/monitoring/signals/{event_id}/dismiss",
    status_code=status.HTTP_200_OK,
    summary="Acknowledge or dismiss a proactive business signal",
)
def dismiss_monitoring_signal(
    event_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    business = _get_active_business(current_user, db)
    engine = SmartRecommendationEngine(db)
    return engine.dismiss_signal(business=business, event_id=event_id)


