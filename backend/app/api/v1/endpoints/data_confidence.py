"""Data Quality and Business Data Confidence Centre endpoints (Phase 6.20 Extension).

Routes:
  GET /api/v1/data-confidence         - Full confidence dashboard, ingestion breakdown, and insight readiness
  GET /api/v1/data-confidence/report  - Exportable data quality and provenance audit report
"""

from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.middleware.auth_deps import get_current_user
from app.models.user import User
from app.schemas.data_confidence import DataConfidenceCentreResponse
from app.services.data_confidence_service import DataConfidenceService
from app.utils.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/data-confidence", tags=["data-confidence"])


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
    response_model=DataConfidenceCentreResponse,
    summary="Get comprehensive data confidence dashboard and insight readiness matrix",
)
def get_data_confidence(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DataConfidenceCentreResponse:
    business_id = _resolve_business_id(current_user)
    service = DataConfidenceService(db)
    try:
        return service.evaluate_business_confidence(
            business_id=business_id,
            owner_id=current_user.id,
            persist_audit=True,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.get(
    "/report",
    summary="Generate an exportable data quality and provenance audit report",
)
def get_data_quality_report(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    business_id = _resolve_business_id(current_user)
    service = DataConfidenceService(db)
    try:
        data = service.evaluate_business_confidence(
            business_id=business_id,
            owner_id=current_user.id,
            persist_audit=False,
        )
        return {
            "business_id": business_id,
            "report_title": "UrsBiz Business Data Quality & Confidence Audit Report",
            "audit_timestamp": data.audit_timestamp,
            "overall_quality_status": data.overall_quality_status,
            "overall_confidence_score": data.overall_confidence_score,
            "ingestion_reconciliation": data.ingestion_summary.model_dump(),
            "observation_window": data.observation_window.model_dump(),
            "insight_confidence_matrix": [m.model_dump() for m in data.insight_confidence_matrix],
            "anomalies_detected": [a.model_dump() for a in data.anomalies_detected],
            "actionable_recommendations": [c.model_dump() for c in data.actionable_improvement_checklist],
            "provenance_disclaimer": data.disclaimer,
        }
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
