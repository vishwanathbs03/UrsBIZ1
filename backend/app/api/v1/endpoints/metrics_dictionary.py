"""Business Metrics Dictionary & Calculation Explorer API endpoints (Phase 6.21 Extension).

Routes:
  GET /api/v1/metrics                 - List all canonical metric definitions with category filter
  GET /api/v1/metrics/{metric_key}    - Get full definition, formula, and benchmark specs for a metric
  GET /api/v1/metrics/{metric_key}/explore - Step-by-step arithmetic exploration with active business data
"""

from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.middleware.auth_deps import get_current_user
from app.models.user import User
from app.schemas.metrics_dictionary import (
    MetricDefinition,
    MetricDictionaryResponse,
    MetricExplorerResult,
)
from app.services.metrics_dictionary_service import MetricsDictionaryService
from app.utils.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/metrics", tags=["metrics-dictionary"])


def _resolve_business_id(current_user: User) -> int:
    """Resolves active business ID with explicit 404 when user has no business."""
    biz_id = current_user.active_business_id
    if not biz_id and getattr(current_user, "businesses", None):
        biz_id = current_user.businesses[0].id
    if not biz_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active business profile found. Please create a business profile first.",
        )
    return biz_id


@router.get(
    "",
    response_model=MetricDictionaryResponse,
    summary="List all canonical business metric definitions",
)
def list_metrics(
    category: str | None = Query(default=None, description="Optional category filter (financial, sales, customer, operations, data_integrity)"),
    db: Session = Depends(get_db),
) -> MetricDictionaryResponse:
    service = MetricsDictionaryService(db)
    return service.list_metrics(category=category)


@router.get(
    "/{metric_key}",
    response_model=MetricDefinition,
    summary="Get full dictionary definition, formulas, and exclusion rules for a specific metric",
)
def get_metric(
    metric_key: str,
    db: Session = Depends(get_db),
) -> MetricDefinition:
    service = MetricsDictionaryService(db)
    metric = service.get_metric(metric_key)
    if not metric:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Metric '{metric_key}' not found in Metrics Dictionary.",
        )
    return metric


@router.get(
    "/{metric_key}/explore",
    response_model=MetricExplorerResult,
    summary="Explore step-by-step arithmetic calculation for active business",
)
def explore_metric(
    metric_key: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MetricExplorerResult:
    business_id = _resolve_business_id(current_user)
    service = MetricsDictionaryService(db)
    try:
        return service.explore_metric(
            business_id=business_id,
            owner_id=current_user.id,
            metric_key=metric_key,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
