"""Pydantic schemas for MSME Collaboration, RBAC, and Approvals (Phase 6.26)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.collaboration import (
    ApprovalEntityType,
    ApprovalStatus,
    BusinessRole,
    InvitationStatus,
    MemberStatus,
)


# ------------------------------------------------------------------------------
# Member Schemas
# ------------------------------------------------------------------------------

class MemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    business_id: int
    user_id: int
    user_email: str
    user_full_name: str
    role: str
    status: str
    joined_at: datetime
    invited_by_email: str | None = None


class MemberListResponse(BaseModel):
    business_id: int
    total_members: int
    current_user_role: str
    members: list[MemberOut]


class MemberRoleUpdateRequest(BaseModel):
    role: BusinessRole


class MemberStatusUpdateRequest(BaseModel):
    status: MemberStatus


# ------------------------------------------------------------------------------
# Invitation Schemas
# ------------------------------------------------------------------------------

class InvitationCreateRequest(BaseModel):
    email: EmailStr
    role: BusinessRole = Field(
        ...,
        description="Assigned role (Administrator, Manager, Analyst, Viewer). Owner cannot be assigned via invitation.",
    )


class InvitationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    business_id: int
    email: str
    role: str
    status: str
    token: str | None = None
    expires_at: datetime
    created_at: datetime
    invited_by_user_id: int | None = None
    invitation_url: str | None = None


class InvitationListResponse(BaseModel):
    business_id: int
    invitations: list[InvitationOut]


class InvitationAcceptRequest(BaseModel):
    token: str


class InvitationAcceptResponse(BaseModel):
    success: bool
    message: str
    business_id: int
    business_name: str
    role: str


# ------------------------------------------------------------------------------
# Ownership Transfer
# ------------------------------------------------------------------------------

class TransferOwnershipRequest(BaseModel):
    new_owner_user_id: int
    reason: str | None = None


class TransferOwnershipResponse(BaseModel):
    success: bool
    message: str
    business_id: int
    previous_owner_id: int
    new_owner_id: int


# ------------------------------------------------------------------------------
# Approval Workflow Schemas
# ------------------------------------------------------------------------------

class ApprovalRequestCreate(BaseModel):
    entity_type: ApprovalEntityType
    entity_id: str = Field(..., max_length=128)
    title: str = Field(..., min_length=3, max_length=255)
    description: str | None = None
    financial_impact_amount: float | None = Field(default=None, ge=0.0)


class ApprovalReviewRequest(BaseModel):
    action: str = Field(..., pattern="^(APPROVE|REJECT)$")
    decision_notes: str | None = Field(default=None, max_length=2000)


class ApprovalAuditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    action: str
    previous_status: str | None = None
    new_status: str
    notes: str | None = None
    user_id: int | None = None
    user_email: str | None = None
    created_at: datetime


class ApprovalRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    business_id: int
    requester_user_id: int | None = None
    requester_name: str | None = None
    requester_email: str | None = None
    entity_type: str
    entity_id: str
    title: str
    description: str | None = None
    financial_impact_amount: float | None = None
    status: str
    approver_user_id: int | None = None
    approver_name: str | None = None
    decision_notes: str | None = None
    requested_at: datetime
    reviewed_at: datetime | None = None
    audits: list[ApprovalAuditOut] = []


class ApprovalListResponse(BaseModel):
    business_id: int
    total: int
    requests: list[ApprovalRequestOut]


class ApprovalSummaryResponse(BaseModel):
    business_id: int
    total: int
    pending: int
    approved: int
    rejected: int
    cancelled: int
