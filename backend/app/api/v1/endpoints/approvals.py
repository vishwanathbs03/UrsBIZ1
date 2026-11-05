"""Business Approval Workflow Endpoints (Phase 6.26).

Enables formal multi-user review and approval of financial decisions,
budget items, discounts, and strategic actions.
"""

from __future__ import annotations

from typing import Annotated
from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.middleware.rbac_deps import get_active_business_context
from app.schemas.collaboration import (
    ApprovalListResponse,
    ApprovalRequestCreate,
    ApprovalRequestOut,
    ApprovalReviewRequest,
    ApprovalSummaryResponse,
)
from app.services.approval_workflow_service import ApprovalWorkflowService
from app.services.rbac_service import BusinessContext
from app.utils.database import get_db

router = APIRouter(prefix="/approvals", tags=["approvals-workflow"])


@router.post(
    "",
    response_model=ApprovalRequestOut,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a business entity for managerial approval",
)
def submit_approval_request(
    req: ApprovalRequestCreate,
    request: Request,
    ctx: Annotated[BusinessContext, Depends(get_active_business_context)],
    db: Annotated[Session, Depends(get_db)],
) -> ApprovalRequestOut:
    service = ApprovalWorkflowService(db)
    client_ip = request.client.host if request.client else None
    return service.submit_request(
        business=ctx.business,
        requester=ctx.user,
        requester_role=ctx.role,
        req=req,
        ip_address=client_ip,
    )


@router.get(
    "",
    response_model=ApprovalListResponse,
    status_code=status.HTTP_200_OK,
    summary="List approval requests for active business",
)
def list_approval_requests(
    ctx: Annotated[BusinessContext, Depends(get_active_business_context)],
    db: Annotated[Session, Depends(get_db)],
    status: str | None = Query(None, description="Optional status filter: PENDING, APPROVED, REJECTED, CANCELLED"),
) -> ApprovalListResponse:
    service = ApprovalWorkflowService(db)
    items = service.list_requests(business=ctx.business, status_filter=status)
    return ApprovalListResponse(
        business_id=ctx.business.id,
        total=len(items),
        requests=items,
    )


@router.get(
    "/summary",
    response_model=ApprovalSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get summary counters of approval requests",
)
def get_approval_summary(
    ctx: Annotated[BusinessContext, Depends(get_active_business_context)],
    db: Annotated[Session, Depends(get_db)],
) -> ApprovalSummaryResponse:
    service = ApprovalWorkflowService(db)
    return service.get_summary_counts(business=ctx.business)


@router.get(
    "/{request_id}",
    response_model=ApprovalRequestOut,
    status_code=status.HTTP_200_OK,
    summary="Get single approval request with full audit trail",
)
def get_approval_request(
    request_id: int,
    ctx: Annotated[BusinessContext, Depends(get_active_business_context)],
    db: Annotated[Session, Depends(get_db)],
) -> ApprovalRequestOut:
    service = ApprovalWorkflowService(db)
    return service.get_request(business=ctx.business, request_id=request_id)


@router.post(
    "/{request_id}/review",
    response_model=ApprovalRequestOut,
    status_code=status.HTTP_200_OK,
    summary="Approve or reject a pending approval request",
)
def review_approval_request(
    request_id: int,
    req: ApprovalReviewRequest,
    request: Request,
    ctx: Annotated[BusinessContext, Depends(get_active_business_context)],
    db: Annotated[Session, Depends(get_db)],
) -> ApprovalRequestOut:
    service = ApprovalWorkflowService(db)
    client_ip = request.client.host if request.client else None
    return service.review_request(
        business=ctx.business,
        reviewer=ctx.user,
        reviewer_role=ctx.role,
        request_id=request_id,
        req=req,
        ip_address=client_ip,
    )


@router.post(
    "/{request_id}/cancel",
    response_model=ApprovalRequestOut,
    status_code=status.HTTP_200_OK,
    summary="Cancel a pending approval request",
)
def cancel_approval_request(
    request_id: int,
    request: Request,
    ctx: Annotated[BusinessContext, Depends(get_active_business_context)],
    db: Annotated[Session, Depends(get_db)],
) -> ApprovalRequestOut:
    service = ApprovalWorkflowService(db)
    client_ip = request.client.host if request.client else None
    return service.cancel_request(
        business=ctx.business,
        user=ctx.user,
        user_role=ctx.role,
        request_id=request_id,
        ip_address=client_ip,
    )
