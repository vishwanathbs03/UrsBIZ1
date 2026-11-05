"""Collaboration and Member Management Service (Phase 6.26).

Handles:
  - Listing members and invitations
  - Inviting collaborators with role hierarchy validation
  - Accepting invitations via secure cryptographic tokens
  - Role modifications with privilege escalation protection
  - Collaborator removal and offboarding
  - Business ownership transfer
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.business import Business
from app.models.collaboration import (
    BusinessInvitation,
    BusinessMember,
    BusinessRole,
    InvitationStatus,
    MemberStatus,
)
from app.models.user import User
from app.schemas.collaboration import (
    InvitationCreateRequest,
    InvitationOut,
    MemberOut,
    TransferOwnershipResponse,
)
from app.services.rbac_service import (
    Permission,
    RBACService,
    ROLE_HIERARCHY,
)


class CollaborationService:
    """Service orchestrating multi-user collaboration and member lifecycles."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list_members(self, business: Business, current_user_role: BusinessRole) -> list[MemberOut]:
        """List all team members for a business, ensuring owner is included."""
        members: list[MemberOut] = []

        # 1. Fetch primary owner user
        owner_user = self.db.query(User).filter(User.id == business.owner_id).first()
        if owner_user:
            members.append(
                MemberOut(
                    id=0,  # Implicit primary owner ID marker
                    business_id=business.id,
                    user_id=owner_user.id,
                    user_email=owner_user.email,
                    user_full_name=owner_user.full_name,
                    role=BusinessRole.OWNER.value,
                    status=MemberStatus.ACTIVE.value,
                    joined_at=business.created_at,
                    invited_by_email=None,
                )
            )

        # 2. Fetch all explicit collaborators
        db_members = (
            self.db.query(BusinessMember)
            .filter(
                BusinessMember.business_id == business.id,
                BusinessMember.status != MemberStatus.REVOKED.value,
                BusinessMember.user_id != business.owner_id,  # Avoid duplicate owner entry
            )
            .order_by(BusinessMember.joined_at.asc())
            .all()
        )

        for m in db_members:
            u = self.db.query(User).filter(User.id == m.user_id).first()
            if not u:
                continue
            inv_by_email = None
            if m.invited_by_user_id:
                inv_by = self.db.query(User).filter(User.id == m.invited_by_user_id).first()
                if inv_by:
                    inv_by_email = inv_by.email

            members.append(
                MemberOut(
                    id=m.id,
                    business_id=m.business_id,
                    user_id=m.user_id,
                    user_email=u.email,
                    user_full_name=u.full_name,
                    role=m.role,
                    status=m.status,
                    joined_at=m.joined_at,
                    invited_by_email=inv_by_email,
                )
            )

        return members

    def create_invitation(
        self,
        business: Business,
        actor: User,
        actor_role: BusinessRole,
        req: InvitationCreateRequest,
    ) -> InvitationOut:
        """Create a secure invitation with strict cross-user privilege escalation protection."""
        target_role = req.role

        # 1. Permission check
        RBACService.check_permission(actor_role, Permission.MEMBERS_MANAGE)

        # 2. Owner role cannot be assigned via invitation (transfer-ownership only)
        if target_role == BusinessRole.OWNER:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot invite a user as Owner. Ownership must be transferred explicitly.",
            )

        # 3. Privilege escalation guard: Actor cannot invite a role equal or higher in hierarchy
        if not RBACService.can_manage_target_role(actor_role, target_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Privilege escalation prevented: Role '{actor_role.value}' cannot invite "
                    f"a user with equal or higher role '{target_role.value}'."
                ),
            )

        # 4. Check if invited user is already an active member or owner
        target_email = req.email.strip().lower()
        existing_user = self.db.query(User).filter(User.email == target_email).first()
        if existing_user:
            if existing_user.id == business.owner_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"User {target_email} is already the Owner of this business.",
                )
            existing_member = self.db.query(BusinessMember).filter(
                BusinessMember.business_id == business.id,
                BusinessMember.user_id == existing_user.id,
                BusinessMember.status == MemberStatus.ACTIVE.value,
            ).first()
            if existing_member:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"User {target_email} is already an active member of this business.",
                )

        # 5. Revoke any existing pending invitations for this email in this business
        pending_invs = self.db.query(BusinessInvitation).filter(
            BusinessInvitation.business_id == business.id,
            BusinessInvitation.email == target_email,
            BusinessInvitation.status == InvitationStatus.PENDING.value,
        ).all()
        for p in pending_invs:
            p.status = InvitationStatus.REVOKED.value

        # 6. Generate cryptographic token and expiration (7 days)
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(days=7)

        inv = BusinessInvitation(
            business_id=business.id,
            email=target_email,
            role=target_role.value,
            token=token,
            invited_by_user_id=actor.id,
            status=InvitationStatus.PENDING.value,
            expires_at=expires_at,
        )
        self.db.add(inv)
        self.db.commit()
        self.db.refresh(inv)

        return InvitationOut(
            id=inv.id,
            business_id=inv.business_id,
            email=inv.email,
            role=inv.role,
            status=inv.status,
            token=token,
            expires_at=inv.expires_at,
            created_at=inv.created_at,
            invited_by_user_id=inv.invited_by_user_id,
            invitation_url=f"/collaboration/accept?token={token}",
        )

    def list_invitations(self, business: Business) -> list[InvitationOut]:
        """List active pending invitations for a business."""
        invs = (
            self.db.query(BusinessInvitation)
            .filter(
                BusinessInvitation.business_id == business.id,
                BusinessInvitation.status == InvitationStatus.PENDING.value,
            )
            .order_by(BusinessInvitation.created_at.desc())
            .all()
        )
        now = datetime.now(timezone.utc)
        results = []
        for inv in invs:
            # Mark expired if past date
            if inv.expires_at.tzinfo is None:
                exp = inv.expires_at.replace(tzinfo=timezone.utc)
            else:
                exp = inv.expires_at
            if exp < now:
                inv.status = InvitationStatus.EXPIRED.value
                self.db.commit()
                continue
            results.append(
                InvitationOut(
                    id=inv.id,
                    business_id=inv.business_id,
                    email=inv.email,
                    role=inv.role,
                    status=inv.status,
                    expires_at=inv.expires_at,
                    created_at=inv.created_at,
                    invited_by_user_id=inv.invited_by_user_id,
                    invitation_url=f"/collaboration/accept?token={inv.token}",
                )
            )
        return results

    def accept_invitation(self, token: str, accepting_user: User) -> dict[str, Any]:
        """Accept an invitation, creating or updating BusinessMember."""
        inv = self.db.query(BusinessInvitation).filter(BusinessInvitation.token == token).first()
        if not inv:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invitation not found or invalid token.",
            )

        if inv.status != InvitationStatus.PENDING.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invitation is no longer pending (status: {inv.status}).",
            )

        now = datetime.now(timezone.utc)
        exp = inv.expires_at if inv.expires_at.tzinfo else inv.expires_at.replace(tzinfo=timezone.utc)
        if exp < now:
            inv.status = InvitationStatus.EXPIRED.value
            self.db.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invitation has expired. Please ask an administrator for a new invite.",
            )

        # Validate that the accepting user's email matches the invite
        if accepting_user.email.strip().lower() != inv.email.strip().lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This invitation was sent to {inv.email}, but you are signed in as {accepting_user.email}.",
            )

        business = self.db.query(Business).filter(Business.id == inv.business_id).first()
        if not business:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Associated business no longer exists.")

        # Create or update membership
        existing_member = self.db.query(BusinessMember).filter(
            BusinessMember.business_id == inv.business_id,
            BusinessMember.user_id == accepting_user.id,
        ).first()

        if existing_member:
            existing_member.role = inv.role
            existing_member.status = MemberStatus.ACTIVE.value
            existing_member.joined_at = datetime.now(timezone.utc)
        else:
            member = BusinessMember(
                business_id=inv.business_id,
                user_id=accepting_user.id,
                role=inv.role,
                status=MemberStatus.ACTIVE.value,
                invited_by_user_id=inv.invited_by_user_id,
                joined_at=datetime.now(timezone.utc),
            )
            self.db.add(member)

        inv.status = InvitationStatus.ACCEPTED.value

        # If user has no active business set, set it to this newly joined business
        if not accepting_user.active_business_id:
            accepting_user.active_business_id = inv.business_id

        self.db.commit()

        return {
            "success": True,
            "message": f"Successfully joined {business.legal_name} as {inv.role}.",
            "business_id": business.id,
            "business_name": business.legal_name,
            "role": inv.role,
        }

    def update_member_role(
        self,
        business: Business,
        actor: User,
        actor_role: BusinessRole,
        member_id: int,
        new_role: BusinessRole,
    ) -> MemberOut:
        """Update a collaborator's role with privilege escalation defense."""
        RBACService.check_permission(actor_role, Permission.MEMBERS_MANAGE)

        member = self.db.query(BusinessMember).filter(
            BusinessMember.id == member_id,
            BusinessMember.business_id == business.id,
        ).first()
        if not member:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Member {member_id} not found.")

        # Cannot modify the primary owner via member role update
        if member.user_id == business.owner_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot modify the primary Owner's role. Use transfer-ownership instead.",
            )

        # Target role cannot be Owner
        if new_role == BusinessRole.OWNER:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot assign Owner role. Use transfer-ownership instead.",
            )

        current_target_role = RBACService.get_role_enum(member.role)

        # Actor cannot modify a member with equal or higher rank
        if not RBACService.can_manage_target_role(actor_role, current_target_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Privilege escalation prevented: Role '{actor_role.value}' cannot modify "
                    f"a member holding equal or higher role '{current_target_role.value}'."
                ),
            )

        # Actor cannot promote anyone to equal or higher rank
        if not RBACService.can_manage_target_role(actor_role, new_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Privilege escalation prevented: Role '{actor_role.value}' cannot assign "
                    f"equal or higher role '{new_role.value}'."
                ),
            )

        member.role = new_role.value
        self.db.commit()
        self.db.refresh(member)

        u = self.db.query(User).filter(User.id == member.user_id).first()
        return MemberOut(
            id=member.id,
            business_id=member.business_id,
            user_id=member.user_id,
            user_email=u.email if u else "",
            user_full_name=u.full_name if u else "",
            role=member.role,
            status=member.status,
            joined_at=member.joined_at,
        )

    def remove_member(
        self,
        business: Business,
        actor: User,
        actor_role: BusinessRole,
        member_id: int,
    ) -> dict[str, Any]:
        """Remove a collaborator from the business."""
        RBACService.check_permission(actor_role, Permission.MEMBERS_MANAGE)

        member = self.db.query(BusinessMember).filter(
            BusinessMember.id == member_id,
            BusinessMember.business_id == business.id,
        ).first()
        if not member:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Member {member_id} not found.")

        if member.user_id == business.owner_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot remove the primary Owner from the business.",
            )

        target_role = RBACService.get_role_enum(member.role)
        if not RBACService.can_manage_target_role(actor_role, target_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: Role '{actor_role.value}' cannot remove member with role '{target_role.value}'.",
            )

        # Reset active_business_id if it pointed to this business
        target_user = self.db.query(User).filter(User.id == member.user_id).first()
        if target_user and target_user.active_business_id == business.id:
            target_user.active_business_id = None

        self.db.delete(member)
        self.db.commit()

        return {"success": True, "message": "Collaborator removed successfully."}

    def transfer_ownership(
        self,
        business: Business,
        current_owner: User,
        new_owner_user_id: int,
    ) -> TransferOwnershipResponse:
        """Transfer sole business ownership to an existing active member."""
        if business.owner_id != current_owner.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the current Owner can transfer ownership of the business.",
            )

        if new_owner_user_id == current_owner.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You are already the Owner of this business.",
            )

        # Validate target user is an active member or existing user
        target_user = self.db.query(User).filter(User.id == new_owner_user_id).first()
        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {new_owner_user_id} not found.",
            )

        # Ensure target user is a member of the business
        target_member = self.db.query(BusinessMember).filter(
            BusinessMember.business_id == business.id,
            BusinessMember.user_id == new_owner_user_id,
            BusinessMember.status == MemberStatus.ACTIVE.value,
        ).first()
        if not target_member:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Target user must be an active member of this business before ownership can be transferred.",
            )

        previous_owner_id = business.owner_id

        # 1. Update business owner
        business.owner_id = target_user.id

        # 2. Previous owner becomes Administrator in business_members table
        prev_owner_member = self.db.query(BusinessMember).filter(
            BusinessMember.business_id == business.id,
            BusinessMember.user_id == previous_owner_id,
        ).first()

        if prev_owner_member:
            prev_owner_member.role = BusinessRole.ADMINISTRATOR.value
            prev_owner_member.status = MemberStatus.ACTIVE.value
        else:
            prev_member = BusinessMember(
                business_id=business.id,
                user_id=previous_owner_id,
                role=BusinessRole.ADMINISTRATOR.value,
                status=MemberStatus.ACTIVE.value,
                joined_at=business.created_at,
            )
            self.db.add(prev_member)

        # 3. Remove target member entry since they are now the primary owner
        self.db.delete(target_member)

        self.db.commit()

        return TransferOwnershipResponse(
            success=True,
            message=f"Ownership successfully transferred to {target_user.full_name} ({target_user.email}).",
            business_id=business.id,
            previous_owner_id=previous_owner_id,
            new_owner_id=target_user.id,
        )
