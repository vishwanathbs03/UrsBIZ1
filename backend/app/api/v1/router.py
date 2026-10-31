"""Aggregate router for API v1."""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    action_board,
    advisor,
    ai,
    analytics_sprint13,
    analytics_v1_router,
    auth,
    benchmark,
    business,
    chat,
    copilot,
    dashboard,
    dna,
    finance,
    forecasting,
    funding,
    compliance,
    growth,
    health,
    intelligence,
    insights,
    knowledge,
    notifications,
    ocr,
    opportunities,
    predictive_sprint14,
    readiness,
    recommendations,
    reports,
    risks,
    roadmap,
    rules,
    sales,
    scenario,
    schemes_sprint16,
    scoring,
    smart_recommendations,
    swot,
    twin,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(action_board.router)
api_router.include_router(auth.router)
api_router.include_router(analytics_sprint13.router)
api_router.include_router(analytics_v1_router.router)
api_router.include_router(business.router)
api_router.include_router(dashboard.router)
api_router.include_router(swot.router)
api_router.include_router(readiness.router)
api_router.include_router(opportunities.router)
api_router.include_router(benchmark.router)
api_router.include_router(risks.router)
api_router.include_router(growth.router)
api_router.include_router(funding.router)
api_router.include_router(compliance.router)
api_router.include_router(reports.router)
api_router.include_router(predictive_sprint14.router)
api_router.include_router(schemes_sprint16.router)
api_router.include_router(intelligence.router)
api_router.include_router(insights.router)
api_router.include_router(notifications.router)
api_router.include_router(scoring.router)
api_router.include_router(dna.router)
api_router.include_router(rules.router)
api_router.include_router(knowledge.router)
api_router.include_router(ai.router)
api_router.include_router(recommendations.router)
api_router.include_router(smart_recommendations.router)
api_router.include_router(roadmap.router)
api_router.include_router(scenario.router)
api_router.include_router(twin.router)
api_router.include_router(ocr.router)
api_router.include_router(finance.router)
api_router.include_router(copilot.router)
api_router.include_router(chat.router)
api_router.include_router(advisor.router)
api_router.include_router(sales.router)
api_router.include_router(forecasting.router)
