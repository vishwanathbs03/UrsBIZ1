"""Collaboration and Member Management Endpoints (Phase 6.26).

Enables multi-user business accounts, role assignment (Owner, Administrator,
Manager, Analyst, Viewer), invitation workflows, and ownership transfer.
"""

from __future__ import annotations

from typing import Annotated, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.middleware.auth_deps import get_current_user
from app.middleware.rbac_deps import get_active_business_context
from app.models.collaboration import BusinessInvitation, InvitationStatus
from app.models.user import User
from app.schemas.collaboration import (
    InvitationAcceptRequest,
    InvitationAcceptResponse,
    InvitationCreateRequest,
    InvitationListResponse,
    InvitationOut,
    MemberListResponse,
    MemberOut,
    MemberRoleUpdateRequest,
    TransferOwnershipRequest,
    TransferOwnershipResponse,
)
from app.services.collaboration_service import CollaborationService
from app.services.rbac_service import BusinessContext, Permission, RBACService
from app.utils.database import get_db

router = APIRouter(prefix="/collaboration", tags=["collaboration-rbac"])


@router.get(
    "/members",
    response_model=MemberListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all collaborators and roles for active business",
)
def list_members(
    ctx: Annotated[BusinessContext, Depends(get_active_business_context)],
    db: Annotated[Session, Depends(get_db)],
) -> MemberListResponse:
    RBACService.check_permission(ctx.role, Permission.MEMBERS_VIEW)
    service = CollaborationService(db)
    members = service.list_members(business=ctx.business, current_user_role=ctx.role)
    return MemberListResponse(
        business_id=ctx.business.id,
        total_members=len(members),
        current_user_role=ctx.role.value,
        members=members,
    )


@router.post(
    "/invitations",
    response_model=InvitationOut,
    status_code=status.HTTP_201_CREATED,
    summary="Invite a collaborator to join the active business",
)
def invite_member(
    req: InvitationCreateRequest,
    ctx: Annotated[BusinessContext, Depends(get_active_business_context)],
    db: Annotated[Session, Depends(get_db)],
) -> InvitationOut:
    service = CollaborationService(db)
    return service.create_invitation(
        business=ctx.business,
        actor=ctx.user,
        actor_role=ctx.role,
        req=req,
    )


@router.get(
    "/invitations",
    response_model=InvitationListResponse,
    status_code=status.HTTP_200_OK,
    summary="List pending invitations for the active business",
)
def list_invitations(
    ctx: Annotated[BusinessContext, Depends(get_active_business_context)],
    db: Annotated[Session, Depends(get_db)],
) -> InvitationListResponse:
    RBACService.check_permission(ctx.role, Permission.MEMBERS_MANAGE)
    service = CollaborationService(db)
    invs = service.list_invitations(business=ctx.business)
    return InvitationListResponse(business_id=ctx.business.id, invitations=invs)


@router.delete(
    "/invitations/{invitation_id}",
    status_code=status.HTTP_200_OK,
    summary="Revoke a pending collaborator invitation",
)
def revoke_invitation(
    invitation_id: int,
    ctx: Annotated[BusinessContext, Depends(get_active_business_context)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    RBACService.check_permission(ctx.role, Permission.MEMBERS_MANAGE)
    inv = (
        db.query(BusinessInvitation)
        .filter(BusinessInvitation.id == invitation_id, BusinessInvitation.business_id == ctx.business.id)
        .first()
    )
    if not inv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found.")
    inv.status = InvitationStatus.REVOKED.value
    db.commit()
    return {"success": True, "message": "Invitation revoked."}


@router.post(
    "/invitations/accept",
    response_model=InvitationAcceptResponse,
    status_code=status.HTTP_200_OK,
    summary="Accept an invitation using a secure token",
)
def accept_invitation(
    req: InvitationAcceptRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> InvitationAcceptResponse:
    service = CollaborationService(db)
    res = service.accept_invitation(token=req.token, accepting_user=current_user)
    return InvitationAcceptResponse(**res)


@router.put(
    "/members/{member_id}",
    response_model=MemberOut,
    status_code=status.HTTP_200_OK,
    summary="Update a collaborator's role in the active business",
)
@router.patch(
    "/members/{member_id}",
    response_model=MemberOut,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
@router.put(
    "/members/{member_id}/role",
    response_model=MemberOut,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
@router.patch(
    "/members/{member_id}/role",
    response_model=MemberOut,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
def update_member_role(
    member_id: int,
    req: MemberRoleUpdateRequest,
    ctx: Annotated[BusinessContext, Depends(get_active_business_context)],
    db: Annotated[Session, Depends(get_db)],
) -> MemberOut:
    service = CollaborationService(db)
    return service.update_member_role(
        business=ctx.business,
        actor=ctx.user,
        actor_role=ctx.role,
        member_id=member_id,
        new_role=req.role,
    )


@router.delete(
    "/members/{member_id}",
    status_code=status.HTTP_200_OK,
    summary="Remove a collaborator from the active business",
)
def remove_member(
    member_id: int,
    ctx: Annotated[BusinessContext, Depends(get_active_business_context)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    service = CollaborationService(db)
    return service.remove_member(
        business=ctx.business,
        actor=ctx.user,
        actor_role=ctx.role,
        member_id=member_id,
    )


@router.post(
    "/transfer-ownership",
    response_model=TransferOwnershipResponse,
    status_code=status.HTTP_200_OK,
    summary="Transfer business ownership to an existing active member",
)
def transfer_ownership(
    req: TransferOwnershipRequest,
    ctx: Annotated[BusinessContext, Depends(get_active_business_context)],
    db: Annotated[Session, Depends(get_db)],
) -> TransferOwnershipResponse:
    RBACService.check_permission(ctx.role, Permission.BUSINESS_TRANSFER)
    service = CollaborationService(db)
    return service.transfer_ownership(
        business=ctx.business,
        current_owner=ctx.user,
        new_owner_user_id=req.new_owner_user_id,
    )
