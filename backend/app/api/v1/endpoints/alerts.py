"""Business Alerts / Event Centre API Endpoints (Prompt 6.22).

Dedicated routes for:
  - GET /alerts: List tenant-isolated business alerts with filtering (severity, status, nature) and pagination
  - GET /alerts/summary: Aggregated counters (total, unread, critical, nature distribution)
  - POST /alerts/evaluate: Trigger deterministic proactive scan
  - GET /alerts/{event_id}: Retrieve single alert details
  - PATCH /alerts/{event_id}/status: Transition lifecycle status with audit history
  - GET /alerts/{event_id}/history: Retrieve immutable audit trail
  - POST /alerts/{event_id}/explain: Grounded plain-language explanation (non-mutating)
"""

from __future__ import annotations

from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.middleware.auth_deps import get_current_user
from app.models.business import Business
from app.models.user import User
from app.repositories.business_repository import BusinessRepository
from app.schemas.business_monitoring import (
    AlertArchiveRequest,
    AlertAuditHistoryItem,
    AlertExplainRequest,
    AlertExplainResponse,
    AlertStatusUpdate,
    AlertSummaryResponse,
    BusinessSignalItem,
    MonitoringEvaluationResponse,
)
from app.services.business_alerts_service import BusinessAlertsService
from app.utils.database import get_db

router = APIRouter(prefix="/alerts", tags=["business-alerts"])


def _get_active_business(user: User, db: Session) -> Business:
    """Resolve active business for the authenticated user enforcing strict ownership."""
    biz_repo = BusinessRepository(db)
    b = biz_repo.get_by_owner(user.id)
    if not b:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No business profile found for the authenticated user",
        )
    return b


class AlertListResponse(BaseModel):
    """Paginated list of business alerts."""

    model_config = ConfigDict(extra="ignore")

    business_id: int
    total: int
    limit: int
    offset: int
    alerts: list[BusinessSignalItem]


@router.get(
    "",
    response_model=AlertListResponse,
    status_code=status.HTTP_200_OK,
    summary="List tenant-isolated business alerts with filtering and pagination",
)
def list_alerts(
    severity: Optional[str] = Query(None, description="CRITICAL | HIGH | MEDIUM | LOW | INFORMATIONAL"),
    alert_status: Optional[str] = Query(None, alias="status", description="NEW | ACKNOWLEDGED | RESOLVED | DISMISSED | ARCHIVED"),
    event_nature: Optional[str] = Query(None, description="CONFIRMED_EVENT | WARNING | ESTIMATE | ASSUMPTION"),
    include_suppressed: bool = Query(False, description="Include cooldown-suppressed alerts"),
    include_archived: bool = Query(False, description="Include soft-deleted/archived alerts"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AlertListResponse:
    business = _get_active_business(current_user, db)
    service = BusinessAlertsService(db)
    items, total = service.list_alerts(
        business_id=business.id,
        severity=severity,
        alert_status=alert_status,
        event_nature=event_nature,
        include_suppressed=include_suppressed,
        include_archived=include_archived,
        limit=limit,
        offset=offset,
    )
    return AlertListResponse(
        business_id=business.id,
        total=total,
        limit=limit,
        offset=offset,
        alerts=items,
    )


@router.get(
    "/summary",
    response_model=AlertSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get aggregated counters and statistics for the Event Centre dashboard",
)
def get_alerts_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AlertSummaryResponse:
    business = _get_active_business(current_user, db)
    service = BusinessAlertsService(db)
    return service.get_summary(business.id)


@router.post(
    "/evaluate",
    response_model=MonitoringEvaluationResponse,
    status_code=status.HTTP_200_OK,
    summary="Trigger incremental proactive change detection scan for the active business",
)
def evaluate_alerts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MonitoringEvaluationResponse:
    business = _get_active_business(current_user, db)
    service = BusinessAlertsService(db)
    return service.evaluate_business(business)


@router.get(
    "/{event_id}",
    response_model=BusinessSignalItem,
    status_code=status.HTTP_200_OK,
    summary="Get a single business alert by event_id",
)
def get_alert(
    event_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BusinessSignalItem:
    business = _get_active_business(current_user, db)
    service = BusinessAlertsService(db)
    record = service.get_alert(business.id, event_id)
    return service._to_schema_item(record)


@router.patch(
    "/{event_id}/status",
    response_model=BusinessSignalItem,
    status_code=status.HTTP_200_OK,
    summary="Update alert lifecycle status with enforced transitions and audit logging",
)
def update_alert_status(
    event_id: str,
    payload: AlertStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BusinessSignalItem:
    business = _get_active_business(current_user, db)
    service = BusinessAlertsService(db)
    return service.update_alert_status(
        business=business,
        event_id=event_id,
        new_status=payload.status,
        reason=payload.reason,
        user_id=current_user.id,
    )


@router.post(
    "/{event_id}/archive",
    response_model=BusinessSignalItem,
    status_code=status.HTTP_200_OK,
    summary="Soft-delete/archive an alert preserving historical audit evidence",
)
def archive_alert(
    event_id: str,
    payload: Optional[AlertArchiveRequest] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BusinessSignalItem:
    business = _get_active_business(current_user, db)
    service = BusinessAlertsService(db)
    reason = payload.reason if payload else None
    return service.archive_alert(
        business=business,
        event_id=event_id,
        user_id=current_user.id,
        reason=reason,
    )


@router.delete(
    "/{event_id}",
    response_model=BusinessSignalItem,
    status_code=status.HTTP_200_OK,
    summary="Soft-delete an alert preserving historical audit evidence (alias for archive)",
)
def delete_alert(
    event_id: str,
    reason: Optional[str] = Query(None, description="Optional reason for deletion/archival"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BusinessSignalItem:
    business = _get_active_business(current_user, db)
    service = BusinessAlertsService(db)
    return service.archive_alert(
        business=business,
        event_id=event_id,
        user_id=current_user.id,
        reason=reason or "Deleted by user",
    )


@router.get(
    "/{event_id}/history",
    response_model=list[AlertAuditHistoryItem],
    status_code=status.HTTP_200_OK,
    summary="Get complete audit history of status transitions for an alert",
)
def get_alert_history(
    event_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[AlertAuditHistoryItem]:
    business = _get_active_business(current_user, db)
    service = BusinessAlertsService(db)
    return service.get_alert_history(business.id, event_id)


@router.post(
    "/{event_id}/explain",
    response_model=AlertExplainResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate plain-language explanation of an alert without modifying underlying evidence",
)
def explain_alert(
    event_id: str,
    payload: AlertExplainRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AlertExplainResponse:
    business = _get_active_business(current_user, db)
    service = BusinessAlertsService(db)
    return service.explain_alert(business.id, event_id, language=payload.language)
