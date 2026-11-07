"""FastAPI REST endpoints for AI answer feedback and quality evaluation (Phase 6.28)."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.middleware.rbac_deps import require_permission
from app.models.collaboration import BusinessRole
from app.services.rbac_service import BusinessContext, Permission
from app.schemas.chat_feedback import (
    ChatFeedbackAnalyticsResponse,
    ChatFeedbackCreateRequest,
    ChatFeedbackResponse,
    ChatFeedbackUpdateRequest,
)
from app.services.chat_feedback_service import ChatFeedbackService
from app.utils.database import get_db

router = APIRouter(prefix="/chat", tags=["AI Answer Feedback & Quality Evaluation"])


@router.post(
    "/messages/{message_id}/feedback",
    response_model=ChatFeedbackResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit or update feedback on an AI assistant response turn",
)
def submit_feedback(
    message_id: int,
    req: ChatFeedbackCreateRequest,
    ctx: Annotated[BusinessContext, Depends(require_permission(Permission.DATA_VIEW))],
    db: Annotated[Session, Depends(get_db)],
) -> ChatFeedbackResponse:
    """Submit structured rating, category, and qualitative notes on an assistant message.
    Strictly tenant-isolated to conversations within the active business.
    """
    service = ChatFeedbackService(db)
    return service.submit_feedback(
        business_id=ctx.business.id,
        user_id=ctx.user.id,
        message_id=message_id,
        request=req,
    )


@router.get(
    "/messages/{message_id}/feedback",
    response_model=ChatFeedbackResponse | None,
    summary="Retrieve user feedback for a specific AI assistant message",
)
def get_message_feedback(
    message_id: int,
    ctx: Annotated[BusinessContext, Depends(require_permission(Permission.DATA_VIEW))],
    db: Annotated[Session, Depends(get_db)],
) -> ChatFeedbackResponse | None:
    """Get the current user's feedback or latest feedback on the specified assistant message."""
    service = ChatFeedbackService(db)
    return service.get_message_feedback(
        business_id=ctx.business.id,
        message_id=message_id,
        user_id=ctx.user.id,
    )


@router.patch(
    "/messages/{message_id}/feedback",
    response_model=ChatFeedbackResponse,
    summary="Update feedback for a specific AI assistant message",
)
def update_feedback(
    message_id: int,
    req: ChatFeedbackUpdateRequest,
    ctx: Annotated[BusinessContext, Depends(require_permission(Permission.DATA_VIEW))],
    db: Annotated[Session, Depends(get_db)],
) -> ChatFeedbackResponse:
    """Update rating, category, or notes on previously submitted feedback."""
    service = ChatFeedbackService(db)
    return service.update_feedback(
        business_id=ctx.business.id,
        user_id=ctx.user.id,
        message_id=message_id,
        request=req,
    )


@router.delete(
    "/messages/{message_id}/feedback",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Delete feedback for an AI assistant message (zero-retention compliance)",
)
def delete_feedback(
    message_id: int,
    ctx: Annotated[BusinessContext, Depends(require_permission(Permission.DATA_VIEW))],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    """Remove feedback record. Business owners and administrators can remove any feedback;
    other roles can remove feedback they submitted.
    """
    service = ChatFeedbackService(db)
    can_manage = ctx.role in (BusinessRole.OWNER, BusinessRole.ADMINISTRATOR)
    service.delete_feedback(
        business_id=ctx.business.id,
        user_id=ctx.user.id,
        message_id=message_id,
        can_manage_all=can_manage,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/feedback/analytics",
    response_model=ChatFeedbackAnalyticsResponse,
    summary="Aggregate quality evaluation analytics and grounding correlation",
)
def get_quality_analytics(
    ctx: Annotated[BusinessContext, Depends(require_permission(Permission.DATA_VIEW))],
    db: Annotated[Session, Depends(get_db)],
    days: int = Query(default=30, ge=1, le=365, description="Lookback window in days"),
) -> ChatFeedbackAnalyticsResponse:
    """Retrieve quality metrics, helpfulness rates, category breakdown distributions,
    and grounding score correlations across assistant turns.
    """
    service = ChatFeedbackService(db)
    return service.get_quality_analytics(business_id=ctx.business.id, days=days)
