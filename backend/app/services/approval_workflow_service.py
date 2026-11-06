"""Approval Workflow Service (Phase 6.26).

Manages:
  - Submission of formal approval requests for financial decisions, recommendations, budgets, and discounts.
  - Multi-user reviews (Approval / Rejection) with role-based authorization.
  - Cancellation lifecycle handling.
  - Append-only audit trail logging for all status transitions.
  - Cross-module synchronization with Decision Workbench items.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.business import Business
from app.models.action_item import ActionItem
from app.models.business_goal import BusinessGoal
from app.models.collaboration import (
    ApprovalAudit,
    ApprovalEntityType,
    ApprovalRequest,
    ApprovalStatus,
    BusinessMember,
    BusinessRole,
    MemberStatus,
)
from app.models.decision_workbench import BusinessDecision
from app.models.recommendation_lifecycle import RecommendationLifecycleState
from app.models.user import User
from app.schemas.collaboration import (
    ApprovalAuditOut,
    ApprovalRequestCreate,
    ApprovalRequestOut,
    ApprovalReviewRequest,
    ApprovalSummaryResponse,
)
from app.services.rbac_service import Permission, RBACService


class ApprovalWorkflowService:
    """Authoritative business logic for approval workflows and governance."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def submit_request(
        self,
        business: Business,
        requester: User,
        requester_role: BusinessRole,
        req: ApprovalRequestCreate,
        ip_address: str | None = None,
    ) -> ApprovalRequestOut:
        """Submit a new business entity for formal managerial review."""
        RBACService.check_permission(requester_role, Permission.FINANCIAL_REQUEST)

        approval_req = ApprovalRequest(
            business_id=business.id,
            requester_user_id=requester.id,
            entity_type=req.entity_type.value,
            entity_id=req.entity_id,
            title=req.title,
            description=req.description,
            financial_impact_amount=req.financial_impact_amount,
            status=ApprovalStatus.PENDING.value,
        )
        self.db.add(approval_req)
        self.db.flush()

        audit = ApprovalAudit(
            business_id=business.id,
            approval_request_id=approval_req.id,
            user_id=requester.id,
            action="SUBMITTED",
            previous_status=None,
            new_status=ApprovalStatus.PENDING.value,
            notes=f"Submitted for approval: {req.title}",
            ip_address=ip_address,
            details={"financial_impact": req.financial_impact_amount},
        )
        self.db.add(audit)
        self.db.commit()
        self.db.refresh(approval_req)

        return self._to_out(approval_req)

    def list_requests(
        self,
        business: Business,
        status_filter: str | None = None,
    ) -> list[ApprovalRequestOut]:
        """List approval requests for a business with optional status filter."""
        q = self.db.query(ApprovalRequest).filter(ApprovalRequest.business_id == business.id)
        if status_filter and status_filter.upper() != "ALL":
            q = q.filter(ApprovalRequest.status == status_filter.upper())
        items = q.order_by(ApprovalRequest.requested_at.desc()).all()
        return [self._to_out(item) for item in items]

    def get_request(self, business: Business, request_id: int) -> ApprovalRequestOut:
        """Fetch details of a single approval request with full audit history."""
        req = (
            self.db.query(ApprovalRequest)
            .filter(ApprovalRequest.id == request_id, ApprovalRequest.business_id == business.id)
            .first()
        )
        if not req:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Approval request {request_id} not found for active business.",
            )
        return self._to_out(req)

    def review_request(
        self,
        business: Business,
        reviewer: User,
        reviewer_role: BusinessRole,
        request_id: int,
        req: ApprovalReviewRequest,
        ip_address: str | None = None,
    ) -> ApprovalRequestOut:
        """Approve or reject a pending request, enforcing FINANCIAL_APPROVE authorization."""
        RBACService.check_permission(reviewer_role, Permission.FINANCIAL_APPROVE)

        approval_req = (
            self.db.query(ApprovalRequest)
            .filter(ApprovalRequest.id == request_id, ApprovalRequest.business_id == business.id)
            .first()
        )
        if not approval_req:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Approval request {request_id} not found.",
            )

        if approval_req.status != ApprovalStatus.PENDING.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot review request {request_id} with current status '{approval_req.status}'.",
            )

        # Dual-control governance: Requesters cannot approve their own requests
        if approval_req.requester_user_id == reviewer.id:
            # Sole-registered-owner exception:
            # An Owner can self-approve ONLY IF they are genuinely the sole registered owner
            # with NO other active members holding FINANCIAL_APPROVE authority (Administrator or Manager).
            if reviewer_role == BusinessRole.OWNER:
                other_approver = (
                    self.db.query(BusinessMember)
                    .filter(
                        BusinessMember.business_id == business.id,
                        BusinessMember.user_id != reviewer.id,
                        BusinessMember.status == MemberStatus.ACTIVE.value,
                        BusinessMember.role.in_([
                            BusinessRole.ADMINISTRATOR.value,
                            BusinessRole.MANAGER.value,
                        ]),
                    )
                    .first()
                )
                if other_approver:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=(
                            f"Dual-control governance violation: You cannot self-approve because another "
                            f"eligible approver with role '{other_approver.role}' exists in this business. "
                            "Independent review is required."
                        ),
                    )
            else:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Dual-control governance violation: You cannot approve or reject your own request. Another authorized manager or owner must review it.",
                )

        action = req.action.upper()
        new_status = ApprovalStatus.APPROVED.value if action == "APPROVE" else ApprovalStatus.REJECTED.value
        prev_status = approval_req.status

        approval_req.status = new_status
        approval_req.approver_user_id = reviewer.id
        approval_req.decision_notes = req.decision_notes
        approval_req.reviewed_at = datetime.now(timezone.utc)

        audit = ApprovalAudit(
            business_id=business.id,
            approval_request_id=approval_req.id,
            user_id=reviewer.id,
            action=action,
            previous_status=prev_status,
            new_status=new_status,
            notes=req.decision_notes,
            ip_address=ip_address,
        )
        self.db.add(audit)

        # Cross-module synchronization across all 5 supported entity types
        self._synchronize_target_entity(
            approval_req=approval_req,
            action=action,
            reviewer=reviewer,
            decision_notes=req.decision_notes,
        )

        self.db.commit()
        self.db.refresh(approval_req)

        return self._to_out(approval_req)

    def _synchronize_target_entity(
        self,
        approval_req: ApprovalRequest,
        action: str,
        reviewer: User,
        decision_notes: str | None,
    ) -> None:
        """Synchronize the status and attributes of the target entity upon approval/rejection."""
        entity_type = approval_req.entity_type
        entity_id_str = str(approval_req.entity_id)

        # 1. DECISION or DISCOUNT
        if entity_type in (ApprovalEntityType.DECISION.value, ApprovalEntityType.DISCOUNT.value):
            try:
                dec_id = int(entity_id_str)
                dec = self.db.query(BusinessDecision).filter(
                    BusinessDecision.id == dec_id,
                    BusinessDecision.business_id == approval_req.business_id,
                ).first()
                if dec:
                    dec.status = "APPROVED" if action == "APPROVE" else "REJECTED"
            except (ValueError, TypeError):
                pass

        # 2. BUDGET (can be BusinessDecision or ActionItem)
        elif entity_type == ApprovalEntityType.BUDGET.value:
            try:
                item_id = int(entity_id_str)
                dec = self.db.query(BusinessDecision).filter(
                    BusinessDecision.id == item_id,
                    BusinessDecision.business_id == approval_req.business_id,
                ).first()
                if dec:
                    dec.status = "APPROVED" if action == "APPROVE" else "REJECTED"
                else:
                    action_item = self.db.query(ActionItem).filter(
                        ActionItem.id == item_id,
                    ).first()
                    if action_item:
                        action_item.category = "Approved" if action == "APPROVE" else "Rejected"
            except (ValueError, TypeError):
                pass

        # 3. GOAL
        elif entity_type == ApprovalEntityType.GOAL.value:
            try:
                goal_id = int(entity_id_str)
                goal = self.db.query(BusinessGoal).filter(
                    BusinessGoal.id == goal_id,
                    BusinessGoal.business_id == approval_req.business_id,
                ).first()
                if goal:
                    if action == "APPROVE":
                        goal.status = "ACTIVE"
                        goal.status_notes = decision_notes or "Goal approved via approval workflow"
                    else:
                        goal.status = "PAUSED"
                        goal.status_notes = decision_notes or "Goal rejected via approval workflow"
            except (ValueError, TypeError):
                pass

        # 4. RECOMMENDATION
        elif entity_type == ApprovalEntityType.RECOMMENDATION.value:
            rec = self.db.query(RecommendationLifecycleState).filter(
                RecommendationLifecycleState.recommendation_id == entity_id_str,
                RecommendationLifecycleState.business_id == approval_req.business_id,
            ).first()
            if not rec:
                rec = RecommendationLifecycleState(
                    business_id=approval_req.business_id,
                    recommendation_id=entity_id_str,
                    status="New",
                )
                self.db.add(rec)

            rec.status = "Accepted" if action == "APPROVE" else "Dismissed"
            rec.user_id = reviewer.id
            if decision_notes:
                rec.notes = decision_notes

    def cancel_request(
        self,
        business: Business,
        user: User,
        user_role: BusinessRole,
        request_id: int,
        ip_address: str | None = None,
    ) -> ApprovalRequestOut:
        """Cancel a pending approval request."""
        approval_req = (
            self.db.query(ApprovalRequest)
            .filter(ApprovalRequest.id == request_id, ApprovalRequest.business_id == business.id)
            .first()
        )
        if not approval_req:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Approval request {request_id} not found.")

        if approval_req.status != ApprovalStatus.PENDING.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot cancel request {request_id} with status '{approval_req.status}'.",
            )

        # Only requester, Admin, or Owner can cancel
        is_requester = approval_req.requester_user_id == user.id
        is_admin_or_owner = user_role in (BusinessRole.OWNER, BusinessRole.ADMINISTRATOR)
        if not (is_requester or is_admin_or_owner):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: Only the original requester, an Administrator, or the Owner can cancel this request.",
            )

        prev_status = approval_req.status
        approval_req.status = ApprovalStatus.CANCELLED.value

        audit = ApprovalAudit(
            business_id=business.id,
            approval_request_id=approval_req.id,
            user_id=user.id,
            action="CANCELLED",
            previous_status=prev_status,
            new_status=ApprovalStatus.CANCELLED.value,
            notes="Cancelled by user.",
            ip_address=ip_address,
        )
        self.db.add(audit)
        self.db.commit()
        self.db.refresh(approval_req)

        return self._to_out(approval_req)

    def get_summary_counts(self, business: Business) -> ApprovalSummaryResponse:
        """Get summary counters of approval requests."""
        all_reqs = self.db.query(ApprovalRequest).filter(ApprovalRequest.business_id == business.id).all()
        pending = sum(1 for r in all_reqs if r.status == ApprovalStatus.PENDING.value)
        approved = sum(1 for r in all_reqs if r.status == ApprovalStatus.APPROVED.value)
        rejected = sum(1 for r in all_reqs if r.status == ApprovalStatus.REJECTED.value)
        cancelled = sum(1 for r in all_reqs if r.status == ApprovalStatus.CANCELLED.value)

        return ApprovalSummaryResponse(
            business_id=business.id,
            total=len(all_reqs),
            pending=pending,
            approved=approved,
            rejected=rejected,
            cancelled=cancelled,
        )

    def _to_out(self, req: ApprovalRequest) -> ApprovalRequestOut:
        """Convert ORM ApprovalRequest to Pydantic schema."""
        requester_name = None
        requester_email = None
        if req.requester:
            requester_name = req.requester.full_name
            requester_email = req.requester.email
        elif req.requester_user_id:
            u = self.db.query(User).filter(User.id == req.requester_user_id).first()
            if u:
                requester_name = u.full_name
                requester_email = u.email

        approver_name = None
        if req.approver:
            approver_name = req.approver.full_name
        elif req.approver_user_id:
            u = self.db.query(User).filter(User.id == req.approver_user_id).first()
            if u:
                approver_name = u.full_name

        audits_out: list[ApprovalAuditOut] = []
        if req.audits:
            for a in req.audits:
                user_email = None
                if a.user:
                    user_email = a.user.email
                elif a.user_id:
                    u = self.db.query(User).filter(User.id == a.user_id).first()
                    if u:
                        user_email = u.email
                audits_out.append(
                    ApprovalAuditOut(
                        id=a.id,
                        action=a.action,
                        previous_status=a.previous_status,
                        new_status=a.new_status,
                        notes=a.notes,
                        user_id=a.user_id,
                        user_email=user_email,
                        created_at=a.created_at,
                    )
                )

        return ApprovalRequestOut(
            id=req.id,
            business_id=req.business_id,
            requester_user_id=req.requester_user_id,
            requester_name=requester_name,
            requester_email=requester_email,
            entity_type=req.entity_type,
            entity_id=req.entity_id,
            title=req.title,
            description=req.description,
            financial_impact_amount=req.financial_impact_amount,
            status=req.status,
            approver_user_id=req.approver_user_id,
            approver_name=approver_name,
            decision_notes=req.decision_notes,
            requested_at=req.requested_at,
            reviewed_at=req.reviewed_at,
            audits=audits_out,
        )
