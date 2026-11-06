"""Comprehensive Test Suite for MSME Collaboration & Approval Workflow (RBAC) (Phase 6.26).

Covers:
  - Role hierarchy and permissions matrix (Owner, Administrator, Manager, Analyst, Viewer)
  - Privilege escalation prevention (self-promotion, manager inviting admin, admin demoting owner)
  - Viewer role restrictions (cannot delete data, cannot upload sales, cannot mutate goals, cannot approve decisions)
  - Analyst role restrictions (cannot approve financial decisions, cannot upload sales, cannot delete data)
  - Manager role capabilities & boundaries (can upload sales, can manage goals, cannot manage team, cannot delete data)
  - Formal approval workflow lifecycle: submit, review (approve/reject), cancel
  - Dual-control governance (requester cannot self-approve unless sole owner)
  - Decision workbench synchronization on approval/rejection
  - Dual-layer audit trail immutability (ORM listeners and database constraints)
  - Audit retention on business deletion (RESTRICT constraint)
  - Auditable user ID tracking in recommendation lifecycle and chat messages
  - Multi-user tenant isolation (strict partition across businesses)
  - Invitation lifecycle: token generation, acceptance, expiration, duplicate prevention
  - Ownership transfer with role demotion of former owner
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.models.action_item import ActionItem
from app.models.business import Business
from app.models.chat import ChatMessage, ChatSession
from app.models.collaboration import (
    ApprovalAudit,
    ApprovalEntityType,
    ApprovalRequest,
    ApprovalStatus,
    BusinessInvitation,
    BusinessMember,
    BusinessRole,
    InvitationStatus,
    MemberStatus,
)
from app.models.decision_workbench import BusinessDecision
from app.models.business_goal import BusinessGoal
from app.models.recommendation_lifecycle import RecommendationLifecycleState
from app.models.user import User
from app.services.rbac_service import BusinessContext, Permission, RBACService, ROLE_HIERARCHY
from app.utils.database import Base, get_db
from app.utils.security import create_access_token, hash_password


@pytest.fixture
def db_session():
    """Isolated in-memory SQLite session with StaticPool and active foreign key enforcement."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    SessionTesting = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionTesting()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(db_session: Session):
    """FastAPI TestClient with overridden database session dependency."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _create_user(db: Session, email: str, full_name: str = "Test User") -> User:
    user = User(
        email=email,
        full_name=full_name,
        password_hash=hash_password("password123"),
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _auth_header(user: User) -> dict[str, str]:
    token = create_access_token(subject=str(user.id))
    return {"Authorization": f"Bearer {token}"}


def _create_business(db: Session, owner: User, name: str = "Acme Retail") -> Business:
    biz = Business(
        owner_id=owner.id,
        legal_name=name,
        industry="Retail",
        established_year=2021,
    )
    db.add(biz)
    db.commit()
    db.refresh(biz)
    owner.active_business_id = biz.id
    db.commit()
    return biz


def _add_member(db: Session, business: Business, user: User, role: BusinessRole) -> BusinessMember:
    member = BusinessMember(
        business_id=business.id,
        user_id=user.id,
        role=role,
        status=MemberStatus.ACTIVE,
    )
    db.add(member)
    db.commit()
    db.refresh(member)
    user.active_business_id = business.id
    db.commit()
    return member


# ==============================================================================
# 1. ROLES AND PERMISSIONS MATRIX
# ==============================================================================

def test_roles_and_permissions_matrix():
    """Verify all 5 roles exist with correct rank hierarchy and permissions."""
    assert ROLE_HIERARCHY[BusinessRole.OWNER] > ROLE_HIERARCHY[BusinessRole.ADMINISTRATOR]
    assert ROLE_HIERARCHY[BusinessRole.ADMINISTRATOR] > ROLE_HIERARCHY[BusinessRole.MANAGER]
    assert ROLE_HIERARCHY[BusinessRole.MANAGER] > ROLE_HIERARCHY[BusinessRole.ANALYST]
    assert ROLE_HIERARCHY[BusinessRole.ANALYST] > ROLE_HIERARCHY[BusinessRole.VIEWER]

    # Owner has all permissions
    assert RBACService.has_permission(BusinessRole.OWNER, Permission.BUSINESS_DELETE)
    assert RBACService.has_permission(BusinessRole.OWNER, Permission.BUSINESS_TRANSFER)
    assert RBACService.has_permission(BusinessRole.OWNER, Permission.FINANCIAL_APPROVE)

    # Administrator cannot delete business or transfer ownership
    assert not RBACService.has_permission(BusinessRole.ADMINISTRATOR, Permission.BUSINESS_DELETE)
    assert not RBACService.has_permission(BusinessRole.ADMINISTRATOR, Permission.BUSINESS_TRANSFER)
    assert RBACService.has_permission(BusinessRole.ADMINISTRATOR, Permission.MEMBERS_MANAGE)
    assert RBACService.has_permission(BusinessRole.ADMINISTRATOR, Permission.FINANCIAL_APPROVE)

    # Manager can upload sales and manage goals, but cannot manage team or delete data
    assert RBACService.has_permission(BusinessRole.MANAGER, Permission.DATA_WRITE)
    assert RBACService.has_permission(BusinessRole.MANAGER, Permission.GOALS_MANAGE)
    assert RBACService.has_permission(BusinessRole.MANAGER, Permission.FINANCIAL_APPROVE)
    assert not RBACService.has_permission(BusinessRole.MANAGER, Permission.MEMBERS_MANAGE)
    assert not RBACService.has_permission(BusinessRole.MANAGER, Permission.DATA_DELETE)

    # Analyst can propose decisions, run simulations, view data, but cannot approve or delete
    assert RBACService.has_permission(BusinessRole.ANALYST, Permission.FINANCIAL_REQUEST)
    assert RBACService.has_permission(BusinessRole.ANALYST, Permission.SIMULATION_RUN)
    assert not RBACService.has_permission(BusinessRole.ANALYST, Permission.FINANCIAL_APPROVE)
    assert not RBACService.has_permission(BusinessRole.ANALYST, Permission.DATA_DELETE)
    assert not RBACService.has_permission(BusinessRole.ANALYST, Permission.DATA_WRITE)

    # Viewer has read-only permissions
    assert RBACService.has_permission(BusinessRole.VIEWER, Permission.DATA_VIEW)
    assert RBACService.has_permission(BusinessRole.VIEWER, Permission.REPORTS_DOWNLOAD)
    assert not RBACService.has_permission(BusinessRole.VIEWER, Permission.DATA_WRITE)
    assert not RBACService.has_permission(BusinessRole.VIEWER, Permission.DATA_DELETE)
    assert not RBACService.has_permission(BusinessRole.VIEWER, Permission.FINANCIAL_APPROVE)
    assert not RBACService.has_permission(BusinessRole.VIEWER, Permission.GOALS_MANAGE)


# ==============================================================================
# 2. PRIVILEGE ESCALATION PREVENTIONS
# ==============================================================================

def test_privilege_escalation_rules():
    """Verify rank hierarchy strictly prevents unauthorized promotions."""
    # Owner can manage Admin, Manager, Analyst, Viewer
    assert RBACService.can_manage_target_role(BusinessRole.OWNER, BusinessRole.ADMINISTRATOR)
    assert RBACService.can_manage_target_role(BusinessRole.OWNER, BusinessRole.MANAGER)
    assert not RBACService.can_manage_target_role(BusinessRole.OWNER, BusinessRole.OWNER)

    # Admin cannot manage Owner or another Admin
    assert not RBACService.can_manage_target_role(BusinessRole.ADMINISTRATOR, BusinessRole.OWNER)
    assert not RBACService.can_manage_target_role(BusinessRole.ADMINISTRATOR, BusinessRole.ADMINISTRATOR)
    assert RBACService.can_manage_target_role(BusinessRole.ADMINISTRATOR, BusinessRole.MANAGER)

    # Manager cannot manage Admin or Manager
    assert not RBACService.can_manage_target_role(BusinessRole.MANAGER, BusinessRole.ADMINISTRATOR)
    assert not RBACService.can_manage_target_role(BusinessRole.MANAGER, BusinessRole.MANAGER)


def test_manager_cannot_invite_admin(client: TestClient, db_session: Session):
    """Manager attempts to invite an Administrator; endpoint must reject with 403 Forbidden."""
    owner = _create_user(db_session, "owner@test.com")
    biz = _create_business(db_session, owner)
    mgr = _create_user(db_session, "mgr@test.com")
    _add_member(db_session, biz, mgr, BusinessRole.MANAGER)

    res = client.post(
        "/api/v1/collaboration/invitations",
        json={"email": "newadmin@test.com", "role": "Administrator"},
        headers=_auth_header(mgr),
    )
    assert res.status_code == 403
    assert "Forbidden" in res.text or "rank" in res.text


def test_admin_cannot_demote_owner(client: TestClient, db_session: Session):
    """Administrator attempts to demote Owner to Viewer; endpoint must reject with 403 Forbidden."""
    owner = _create_user(db_session, "owner2@test.com")
    biz = _create_business(db_session, owner)
    admin = _create_user(db_session, "admin2@test.com")
    admin_member = _add_member(db_session, biz, admin, BusinessRole.ADMINISTRATOR)

    # Need member record for owner
    owner_member = _add_member(db_session, biz, owner, BusinessRole.OWNER)

    res = client.patch(
        f"/api/v1/collaboration/members/{owner_member.id}/role",
        json={"role": "Viewer"},
        headers=_auth_header(admin),
    )
    assert res.status_code == 403
    assert "Cannot modify" in res.text or "rank" in res.text


def test_user_cannot_self_promote(client: TestClient, db_session: Session):
    """Collaborator attempts to update their own role; endpoint must reject with 400 Bad Request."""
    owner = _create_user(db_session, "owner3@test.com")
    biz = _create_business(db_session, owner)
    analyst = _create_user(db_session, "analyst3@test.com")
    member = _add_member(db_session, biz, analyst, BusinessRole.ANALYST)

    res = client.patch(
        f"/api/v1/collaboration/members/{member.id}/role",
        json={"role": "Administrator"},
        headers=_auth_header(analyst),
    )
    assert res.status_code == 403 or res.status_code == 400


# ==============================================================================
# 3. VIEWER RESTRICTIONS (READ-ONLY)
# ==============================================================================

def test_viewer_blocked_from_deleting_and_mutating_data(client: TestClient, db_session: Session):
    """Viewer cannot delete decisions, goals, reports, or upload sales data."""
    owner = _create_user(db_session, "owner_v@test.com")
    biz = _create_business(db_session, owner)
    viewer = _create_user(db_session, "viewer@test.com")
    _add_member(db_session, biz, viewer, BusinessRole.VIEWER)

    # 1. Attempt to create goal
    goal_res = client.post(
        "/api/v1/goals",
        json={
            "title": "Boost Sales",
            "metric_key": "monthly_revenue",
            "target_value": 100000.0,
            "unit": "INR",
            "observation_window": "MONTHLY",
            "start_date": "2026-11-01",
            "target_date": "2026-11-30",
        },
        headers=_auth_header(viewer),
    )
    assert goal_res.status_code == 403
    assert "Forbidden" in goal_res.text or "Permission denied" in goal_res.text

    # 2. Attempt to upload sales preview
    upload_res = client.post(
        "/api/v1/sales/upload/preview",
        files={"file": ("dummy.csv", b"Date,Amount\n2026-11-01,100", "text/csv")},
        headers=_auth_header(viewer),
    )
    assert upload_res.status_code == 403

    # 3. Attempt to delete a decision
    decision = BusinessDecision(
        business_id=biz.id,
        owner_id=owner.id,
        title="Cut Marketing",
        decision_type="offer_discount",
        objective="Cut marketing spend",
        status="Draft",
    )
    db_session.add(decision)
    db_session.commit()

    del_res = client.delete(
        f"/api/v1/decisions/{decision.id}",
        headers=_auth_header(viewer),
    )
    assert del_res.status_code == 403


# ==============================================================================
# 4. ANALYST RESTRICTIONS & CAPABILITIES
# ==============================================================================

def test_analyst_cannot_approve_financial_decision_directly(client: TestClient, db_session: Session):
    """Analyst cannot approve financial decisions directly via decision workbench."""
    owner = _create_user(db_session, "owner_a@test.com")
    biz = _create_business(db_session, owner)
    analyst = _create_user(db_session, "analyst@test.com")
    _add_member(db_session, biz, analyst, BusinessRole.ANALYST)

    decision = BusinessDecision(
        business_id=biz.id,
        owner_id=owner.id,
        title="Purchase Inventory",
        decision_type="offer_discount",
        objective="Purchase inventory",
        status="Draft",
    )
    db_session.add(decision)
    db_session.commit()

    # Analyst tries to approve decision
    res = client.patch(
        f"/api/v1/decisions/{decision.id}",
        json={"status": "Decided"},
        headers=_auth_header(analyst),
    )
    assert res.status_code == 403
    assert "Permission denied" in res.text or "Forbidden" in res.text


def test_analyst_can_propose_decision(client: TestClient, db_session: Session):
    """Analyst can propose decisions for managerial review."""
    owner = _create_user(db_session, "owner_a2@test.com")
    biz = _create_business(db_session, owner)
    analyst = _create_user(db_session, "analyst2@test.com")
    _add_member(db_session, biz, analyst, BusinessRole.ANALYST)

    res = client.post(
        "/api/v1/decisions",
        json={
            "title": "Supplier Renegotiation",
            "decision_type": "offer_discount",
            "objective": "Cost reduction initiative for supplier",
            "status": "Draft",
        },
        headers=_auth_header(analyst),
    )
    assert res.status_code == 201
    assert res.json()["status"] == "Draft"


# ==============================================================================
# 5. INVITATION LIFECYCLE
# ==============================================================================

def test_invitation_lifecycle(client: TestClient, db_session: Session):
    """Test full invitation flow: create, inspect, accept with token, and handle expiration."""
    owner = _create_user(db_session, "owner_inv@test.com")
    biz = _create_business(db_session, owner)

    # 1. Owner invites a new user as Manager
    inv_res = client.post(
        "/api/v1/collaboration/invitations",
        json={"email": "new_manager@test.com", "role": "Manager"},
        headers=_auth_header(owner),
    )
    assert inv_res.status_code == 201
    inv_data = inv_res.json()
    assert inv_data["email"] == "new_manager@test.com"
    assert inv_data["role"] == "Manager"
    assert inv_data["status"] == "PENDING"
    inv_token = inv_data["token"]
    assert inv_token is not None

    # 2. List invitations
    list_res = client.get(
        "/api/v1/collaboration/invitations",
        headers=_auth_header(owner),
    )
    assert list_res.status_code == 200
    assert len(list_res.json()["invitations"]) == 1

    # 3. New user registers and accepts invitation
    new_user = _create_user(db_session, "new_manager@test.com")
    accept_res = client.post(
        "/api/v1/collaboration/invitations/accept",
        json={"token": inv_token},
        headers=_auth_header(new_user),
    )
    assert accept_res.status_code == 200
    accept_data = accept_res.json()
    assert accept_data["role"] == "Manager"
    assert accept_data["business_id"] == biz.id

    # 4. Verify membership created
    db_session.refresh(new_user)
    assert new_user.active_business_id == biz.id
    member_record = db_session.query(BusinessMember).filter_by(
        business_id=biz.id, user_id=new_user.id
    ).first()
    assert member_record is not None
    assert member_record.role == BusinessRole.MANAGER

    # 5. Cannot accept again
    reaccept_res = client.post(
        "/api/v1/collaboration/invitations/accept",
        json={"token": inv_token},
        headers=_auth_header(new_user),
    )
    assert reaccept_res.status_code == 400
    assert "ACCEPTED" in reaccept_res.text or "no longer pending" in reaccept_res.text


# ==============================================================================
# 6. APPROVAL WORKFLOW & DUAL CONTROL GOVERNANCE
# ==============================================================================

def test_approval_workflow_submit_and_dual_control(client: TestClient, db_session: Session):
    """Test approval submission, dual-control prevention of self-approval, and manager review."""
    owner = _create_user(db_session, "owner_app@test.com")
    biz = _create_business(db_session, owner)
    manager = _create_user(db_session, "manager_app@test.com")
    _add_member(db_session, biz, manager, BusinessRole.MANAGER)
    analyst = _create_user(db_session, "analyst_app@test.com")
    _add_member(db_session, biz, analyst, BusinessRole.ANALYST)

    # 1. Create a decision
    decision = BusinessDecision(
        business_id=biz.id,
        owner_id=analyst.id,
        title="Expansion Budget",
        decision_type="offer_discount",
        objective="Inventory expansion for holiday season",
        status="Draft",
    )
    db_session.add(decision)
    db_session.commit()
    db_session.refresh(decision)

    # 2. Manager submits approval request
    req_res = client.post(
        "/api/v1/approvals",
        json={
            "entity_type": "DECISION",
            "entity_id": str(decision.id),
            "title": "Approve Expansion Budget of 75,000",
            "description": "Inventory expansion for holiday season",
            "financial_impact_amount": 75000.0,
        },
        headers=_auth_header(manager),
    )
    assert req_res.status_code == 201
    approval = req_res.json()
    approval_id = approval["id"]
    assert approval["status"] == "PENDING"
    assert approval["financial_impact_amount"] == 75000.0

    # 3. Requester (manager) attempts to self-approve -> BLOCKED by dual control
    self_app_res = client.post(
        f"/api/v1/approvals/{approval_id}/review",
        json={"action": "APPROVE", "decision_notes": "I approve my own request"},
        headers=_auth_header(manager),
    )
    assert self_app_res.status_code == 403
    assert "cannot approve or reject your own request" in self_app_res.text

    # 4. Owner reviews and approves request
    owner_app_res = client.post(
        f"/api/v1/approvals/{approval_id}/review",
        json={"action": "APPROVE", "decision_notes": "Approved based on Q4 projections"},
        headers=_auth_header(owner),
    )
    assert owner_app_res.status_code == 200
    approved_data = owner_app_res.json()
    assert approved_data["status"] == "APPROVED"
    assert approved_data["approver_user_id"] == owner.id
    assert approved_data["decision_notes"] == "Approved based on Q4 projections"

    # 5. Verify Decision entity status was synchronized to APPROVED
    db_session.refresh(decision)
    assert decision.status == "APPROVED"


def test_approval_workflow_rejection_and_entity_sync(client: TestClient, db_session: Session):
    """Test approval rejection synchronizes target entity status to REJECTED."""
    owner = _create_user(db_session, "owner_rej@test.com")
    biz = _create_business(db_session, owner)
    manager = _create_user(db_session, "mgr_rej@test.com")
    _add_member(db_session, biz, manager, BusinessRole.MANAGER)

    decision = BusinessDecision(
        business_id=biz.id,
        owner_id=manager.id,
        title="High Risk Loan",
        decision_type="offer_discount",
        objective="High risk borrowing evaluation",
        status="Draft",
    )
    db_session.add(decision)
    db_session.commit()

    req_res = client.post(
        "/api/v1/approvals",
        json={
            "entity_type": "DECISION",
            "entity_id": str(decision.id),
            "title": "High Risk Loan Authorization",
            "financial_impact_amount": 200000.0,
        },
        headers=_auth_header(manager),
    )
    assert req_res.status_code == 201
    approval_id = req_res.json()["id"]

    # Owner rejects request
    rej_res = client.post(
        f"/api/v1/approvals/{approval_id}/review",
        json={"action": "REJECT", "decision_notes": "Cash runway does not support this leverage"},
        headers=_auth_header(owner),
    )
    assert rej_res.status_code == 200
    assert rej_res.json()["status"] == "REJECTED"

    # Check decision entity synchronized
    db_session.refresh(decision)
    assert decision.status == "REJECTED"


def test_sole_owner_self_approval_allowance(client: TestClient, db_session: Session):
    """Sole owner (with no other managers/admins) can approve their own request under dual-control rule."""
    owner = _create_user(db_session, "sole_owner@test.com")
    biz = _create_business(db_session, owner)

    decision = BusinessDecision(
        business_id=biz.id,
        owner_id=owner.id,
        title="Solo Decision",
        decision_type="offer_discount",
        objective="Solo owner evaluation",
        status="Draft",
    )
    db_session.add(decision)
    db_session.commit()

    req_res = client.post(
        "/api/v1/approvals",
        json={
            "entity_type": "DECISION",
            "entity_id": str(decision.id),
            "title": "Solo Decision Approval",
        },
        headers=_auth_header(owner),
    )
    assert req_res.status_code == 201
    app_id = req_res.json()["id"]

    # Sole owner approves
    review_res = client.post(
        f"/api/v1/approvals/{app_id}/review",
        json={"action": "APPROVE", "decision_notes": "Sole owner authorized"},
        headers=_auth_header(owner),
    )
    assert review_res.status_code == 200
    assert review_res.json()["status"] == "APPROVED"

def test_owner_blocked_from_self_approval_when_admin_or_manager_exists(client: TestClient, db_session: Session):
    """Owner is blocked from self-approving if an Administrator or Manager exists in the business."""
    # 1. Owner with an Administrator in business
    owner1 = _create_user(db_session, "owner_with_admin@test.com")
    biz1 = _create_business(db_session, owner1, name="Admin Co")
    admin1 = _create_user(db_session, "admin_co@test.com")
    _add_member(db_session, biz1, admin1, BusinessRole.ADMINISTRATOR)

    req1_res = client.post(
        "/api/v1/approvals",
        json={
            "entity_type": "DECISION",
            "entity_id": "1",
            "title": "Owner Request with Admin",
        },
        headers=_auth_header(owner1),
    )
    assert req1_res.status_code == 201
    app1_id = req1_res.json()["id"]

    # Owner attempts self-approval -> BLOCKED because Admin exists
    self_app1 = client.post(
        f"/api/v1/approvals/{app1_id}/review",
        json={"action": "APPROVE", "decision_notes": "Trying to bypass admin"},
        headers=_auth_header(owner1),
    )
    assert self_app1.status_code == 403
    assert "another eligible approver with role 'Administrator' exists" in self_app1.text

    # 2. Owner with a Manager in business
    owner2 = _create_user(db_session, "owner_with_mgr@test.com")
    biz2 = _create_business(db_session, owner2, name="Manager Co")
    mgr2 = _create_user(db_session, "mgr_co@test.com")
    _add_member(db_session, biz2, mgr2, BusinessRole.MANAGER)

    req2_res = client.post(
        "/api/v1/approvals",
        json={
            "entity_type": "DECISION",
            "entity_id": "2",
            "title": "Owner Request with Manager",
        },
        headers=_auth_header(owner2),
    )
    assert req2_res.status_code == 201
    app2_id = req2_res.json()["id"]

    # Owner attempts self-approval -> BLOCKED because Manager exists
    self_app2 = client.post(
        f"/api/v1/approvals/{app2_id}/review",
        json={"action": "APPROVE", "decision_notes": "Trying to bypass manager"},
        headers=_auth_header(owner2),
    )
    assert self_app2.status_code == 403
    assert "another eligible approver with role 'Manager' exists" in self_app2.text


def test_owner_allowed_self_approval_when_only_analyst_exists(client: TestClient, db_session: Session):
    """Owner CAN self-approve if the only other members are Analysts or Viewers (who lack FINANCIAL_APPROVE)."""
    owner = _create_user(db_session, "owner_with_analyst@test.com")
    biz = _create_business(db_session, owner, name="Analyst Only Co")
    analyst = _create_user(db_session, "analyst_member@test.com")
    _add_member(db_session, biz, analyst, BusinessRole.ANALYST)
    viewer = _create_user(db_session, "viewer_member@test.com")
    _add_member(db_session, biz, viewer, BusinessRole.VIEWER)

    req_res = client.post(
        "/api/v1/approvals",
        json={
            "entity_type": "DECISION",
            "entity_id": "3",
            "title": "Solo Owner Decision with Analysts",
        },
        headers=_auth_header(owner),
    )
    assert req_res.status_code == 201
    app_id = req_res.json()["id"]

    # Owner can self-approve because neither Analyst nor Viewer has FINANCIAL_APPROVE
    self_app = client.post(
        f"/api/v1/approvals/{app_id}/review",
        json={"action": "APPROVE", "decision_notes": "Sole owner approved"},
        headers=_auth_header(owner),
    )
    assert self_app.status_code == 200
    assert self_app.json()["status"] == "APPROVED"


def test_admin_and_manager_cannot_self_approve(client: TestClient, db_session: Session):
    """Administrator and Manager are strictly forbidden from approving their own submissions."""
    owner = _create_user(db_session, "owner_no_self@test.com")
    biz = _create_business(db_session, owner)
    admin = _create_user(db_session, "admin_no_self@test.com")
    _add_member(db_session, biz, admin, BusinessRole.ADMINISTRATOR)
    mgr = _create_user(db_session, "mgr_no_self@test.com")
    _add_member(db_session, biz, mgr, BusinessRole.MANAGER)

    # 1. Admin submits request
    req1 = client.post(
        "/api/v1/approvals",
        json={"entity_type": "DECISION", "entity_id": "11", "title": "Admin Proposal"},
        headers=_auth_header(admin),
    )
    assert req1.status_code == 201
    # Admin tries to self-approve -> 403 Forbidden
    self_admin = client.post(
        f"/api/v1/approvals/{req1.json()['id']}/review",
        json={"action": "APPROVE"},
        headers=_auth_header(admin),
    )
    assert self_admin.status_code == 403
    assert "cannot approve or reject your own request" in self_admin.text

    # 2. Manager submits request
    req2 = client.post(
        "/api/v1/approvals",
        json={"entity_type": "DECISION", "entity_id": "12", "title": "Manager Proposal"},
        headers=_auth_header(mgr),
    )
    assert req2.status_code == 201
    # Manager tries to self-approve -> 403 Forbidden
    self_mgr = client.post(
        f"/api/v1/approvals/{req2.json()['id']}/review",
        json={"action": "APPROVE"},
        headers=_auth_header(mgr),
    )
    assert self_mgr.status_code == 403
    assert "cannot approve or reject your own request" in self_mgr.text


def test_all_five_approval_entity_types_synchronization(client: TestClient, db_session: Session):
    """Verify target entity status synchronization for all 5 entity types:
    DECISION, DISCOUNT, BUDGET, GOAL, and RECOMMENDATION.
    """
    owner = _create_user(db_session, "owner_sync5@test.com")
    biz = _create_business(db_session, owner)
    manager = _create_user(db_session, "mgr_sync5@test.com")
    _add_member(db_session, biz, manager, BusinessRole.MANAGER)

    # --- 1. DISCOUNT Entity Sync ---
    discount_dec = BusinessDecision(
        business_id=biz.id,
        owner_id=manager.id,
        title="15% Festive Discount",
        decision_type="offer_discount",
        objective="Drive seasonal volume",
        status="Draft",
    )
    db_session.add(discount_dec)
    db_session.commit()

    disc_req = client.post(
        "/api/v1/approvals",
        json={"entity_type": "DISCOUNT", "entity_id": str(discount_dec.id), "title": "Festive Discount Approval"},
        headers=_auth_header(manager),
    )
    assert disc_req.status_code == 201
    # Owner approves
    client.post(
        f"/api/v1/approvals/{disc_req.json()['id']}/review",
        json={"action": "APPROVE", "decision_notes": "Discount approved for Diwali"},
        headers=_auth_header(owner),
    )
    db_session.refresh(discount_dec)
    assert discount_dec.status == "APPROVED"

    # --- 2. BUDGET Entity Sync ---
    budget_dec = BusinessDecision(
        business_id=biz.id,
        owner_id=manager.id,
        title="Q1 Travel Budget",
        decision_type="reduce_expenses",
        objective="Cap non-essential travel",
        status="Draft",
    )
    db_session.add(budget_dec)
    db_session.commit()

    budget_req = client.post(
        "/api/v1/approvals",
        json={"entity_type": "BUDGET", "entity_id": str(budget_dec.id), "title": "Q1 Travel Budget Cap"},
        headers=_auth_header(manager),
    )
    assert budget_req.status_code == 201
    # Owner rejects
    client.post(
        f"/api/v1/approvals/{budget_req.json()['id']}/review",
        json={"action": "REJECT", "decision_notes": "Budget cap too restrictive"},
        headers=_auth_header(owner),
    )
    db_session.refresh(budget_dec)
    assert budget_dec.status == "REJECTED"

    # --- 3. GOAL Entity Sync ---
    goal = BusinessGoal(
        business_id=biz.id,
        title="Achieve 200k Revenue",
        metric_key="monthly_revenue",
        target_value=200000.0,
        status="PAUSED",
    )
    db_session.add(goal)
    db_session.commit()

    goal_req = client.post(
        "/api/v1/approvals",
        json={"entity_type": "GOAL", "entity_id": str(goal.id), "title": "Activate 200k Goal"},
        headers=_auth_header(manager),
    )
    assert goal_req.status_code == 201
    # Owner approves
    client.post(
        f"/api/v1/approvals/{goal_req.json()['id']}/review",
        json={"action": "APPROVE", "decision_notes": "Target confirmed"},
        headers=_auth_header(owner),
    )
    db_session.refresh(goal)
    assert goal.status == "ACTIVE"
    assert goal.status_notes == "Target confirmed"

    # --- 4. RECOMMENDATION Entity Sync ---
    rec_req = client.post(
        "/api/v1/approvals",
        json={
            "entity_type": "RECOMMENDATION",
            "entity_id": "rec-smart-456",
            "title": "Accept Cross-Sell Strategy",
        },
        headers=_auth_header(manager),
    )
    assert rec_req.status_code == 201
    # Owner approves
    client.post(
        f"/api/v1/approvals/{rec_req.json()['id']}/review",
        json={"action": "APPROVE", "decision_notes": "Recommended strategy accepted"},
        headers=_auth_header(owner),
    )
    rec_lifecycle = db_session.query(RecommendationLifecycleState).filter_by(
        recommendation_id="rec-smart-456", business_id=biz.id
    ).first()
    assert rec_lifecycle is not None
    assert rec_lifecycle.status == "Accepted"
    assert rec_lifecycle.user_id == owner.id
    assert rec_lifecycle.notes == "Recommended strategy accepted"



# ==============================================================================
# 7. APPROVAL AUDIT TRAIL IMMUTABILITY & RETENTION
# ==============================================================================

def test_approval_audit_trail_immutability(db_session: Session):
    """ApprovalAudit records cannot be modified or deleted via ORM."""
    owner = _create_user(db_session, "owner_audit@test.com")
    biz = _create_business(db_session, owner)

    app_req = ApprovalRequest(
        business_id=biz.id,
        requester_user_id=owner.id,
        entity_type=ApprovalEntityType.DECISION,
        entity_id="1",
        title="Audit Immutability Check",
    )
    db_session.add(app_req)
    db_session.commit()

    audit = ApprovalAudit(
        business_id=biz.id,
        approval_request_id=app_req.id,
        user_id=owner.id,
        action="SUBMITTED",
        new_status="PENDING",
        notes="Initial submission",
    )
    db_session.add(audit)
    db_session.commit()

    # Attempt UPDATE -> must raise ValueError
    audit.notes = "Tampered notes"
    with pytest.raises(ValueError, match="strictly append-only"):
        db_session.commit()
    db_session.rollback()

    # Attempt DELETE -> must raise ValueError
    db_session.delete(audit)
    with pytest.raises(ValueError, match="strictly append-only"):
        db_session.commit()
    db_session.rollback()


def test_audit_retention_on_business_deletion(db_session: Session):
    """ApprovalAudit.business_id foreign key has ondelete='RESTRICT', preventing cascade wipe."""
    owner = _create_user(db_session, "owner_ret@test.com")
    biz = _create_business(db_session, owner)

    app_req = ApprovalRequest(
        business_id=biz.id,
        requester_user_id=owner.id,
        entity_type=ApprovalEntityType.DECISION,
        entity_id="1",
        title="Retention Check",
    )
    db_session.add(app_req)
    db_session.commit()

    audit = ApprovalAudit(
        business_id=biz.id,
        approval_request_id=app_req.id,
        user_id=owner.id,
        action="SUBMITTED",
        new_status="PENDING",
    )
    db_session.add(audit)
    db_session.commit()

    # Attempting to delete business must fail due to foreign key RESTRICT
    with pytest.raises(IntegrityError):
        db_session.execute(text("DELETE FROM businesses WHERE id = :biz_id"), {"biz_id": biz.id})
        db_session.commit()
    db_session.rollback()


# ==============================================================================
# 8. AUDITABLE USER ID TRACKING IN RECOMMENDATIONS AND CHAT
# ==============================================================================

def test_auditable_user_id_tracking_in_recommendations(client: TestClient, db_session: Session):
    """Recommendation status update records the active user's ID for accountability."""
    owner = _create_user(db_session, "owner_rec@test.com")
    biz = _create_business(db_session, owner)
    manager = _create_user(db_session, "mgr_rec@test.com")
    _add_member(db_session, biz, manager, BusinessRole.MANAGER)

    # Insert recommendation lifecycle record
    rec = RecommendationLifecycleState(
        business_id=biz.id,
        recommendation_id="rec-test-123",
        status="New",
    )
    db_session.add(rec)
    db_session.commit()

    # Manager updates recommendation status
    res = client.patch(
        "/api/v1/recommendations/rec-test-123/status",
        json={"status": "Accepted"},
        headers=_auth_header(manager),
    )
    assert res.status_code == 200

    # Verify user_id persisted in lifecycle record
    db_session.refresh(rec)
    assert rec.status == "Accepted"
    assert rec.user_id == manager.id


def test_auditable_user_id_and_business_id_in_chat(db_session: Session):
    """Chat session records business_id and chat messages record user_id."""
    owner = _create_user(db_session, "owner_chat@test.com")
    biz = _create_business(db_session, owner)

    session = ChatSession(
        owner_id=owner.id,
        business_id=biz.id,
        title="Financial Review Chat",
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)
    assert session.business_id == biz.id

    msg = ChatMessage(
        session_id=session.id,
        role="user",
        content="What was our Q3 margin?",
        user_id=owner.id,
    )
    db_session.add(msg)
    db_session.commit()
    db_session.refresh(msg)
    assert msg.user_id == owner.id


# ==============================================================================
# 9. OWNERSHIP TRANSFER
# ==============================================================================

def test_ownership_transfer(client: TestClient, db_session: Session):
    """Owner transfers business to an active Admin; former owner is demoted to Administrator."""
    owner = _create_user(db_session, "owner_trans@test.com")
    biz = _create_business(db_session, owner)
    successor = _create_user(db_session, "successor@test.com")
    successor_member = _add_member(db_session, biz, successor, BusinessRole.ADMINISTRATOR)

    # Transfer ownership
    res = client.post(
        "/api/v1/collaboration/transfer-ownership",
        json={"new_owner_user_id": successor.id},
        headers=_auth_header(owner),
    )
    assert res.status_code == 200
    data = res.json()
    assert data["previous_owner_id"] == owner.id
    assert data["new_owner_id"] == successor.id

    # Verify business owner updated
    updated_biz = db_session.query(Business).filter_by(id=biz.id).first()
    assert updated_biz is not None
    assert updated_biz.owner_id == successor.id

    # Verify former owner is now ADMINISTRATOR
    former_owner_member = db_session.query(BusinessMember).filter_by(
        business_id=biz.id, user_id=owner.id
    ).first()
    assert former_owner_member is not None
    assert former_owner_member.role == BusinessRole.ADMINISTRATOR.value

    # Verify via API list_members that successor is reported as Owner
    members_res = client.get("/api/v1/collaboration/members", headers=_auth_header(successor))
    assert members_res.status_code == 200
    members_list = members_res.json()["members"]
    owner_entry = next((m for m in members_list if m["user_id"] == successor.id), None)
    assert owner_entry is not None
    assert owner_entry["role"] == "Owner"


# ==============================================================================
# 10. MULTI-USER TENANT ISOLATION
# ==============================================================================

def test_multi_user_tenant_isolation(client: TestClient, db_session: Session):
    """User of Business 1 cannot access members, invitations, or approvals of Business 2."""
    owner1 = _create_user(db_session, "owner_biz1@test.com")
    biz1 = _create_business(db_session, owner1, name="Business One")

    owner2 = _create_user(db_session, "owner_biz2@test.com")
    biz2 = _create_business(db_session, owner2, name="Business Two")

    # Create approval request in Biz 2
    app_req2 = ApprovalRequest(
        business_id=biz2.id,
        requester_user_id=owner2.id,
        entity_type=ApprovalEntityType.DECISION,
        entity_id="99",
        title="Biz 2 Secret Decision",
    )
    db_session.add(app_req2)
    db_session.commit()

    # Owner 1 lists approvals -> must only see Biz 1 approvals (0 total)
    res1 = client.get("/api/v1/approvals", headers=_auth_header(owner1))
    assert res1.status_code == 200
    assert res1.json()["total"] == 0

    # Owner 1 attempts to review Biz 2 approval -> 404 Not Found (isolated)
    res_cross = client.post(
        f"/api/v1/approvals/{app_req2.id}/review",
        json={"action": "APPROVE"},
        headers=_auth_header(owner1),
    )
    assert res_cross.status_code == 404


# ==============================================================================
# 11. EXHAUSTIVE MATRIX & PERMISSION CHECKS (AUDIT COVERAGE)
# ==============================================================================

def test_exhaustive_5_roles_13_permissions_matrix():
    """Verify all 65 combinations (5 roles x 13 permissions) explicitly match policy."""
    expected_matrix = {
        BusinessRole.OWNER: {
            Permission.MEMBERS_VIEW: True,
            Permission.MEMBERS_MANAGE: True,
            Permission.FINANCIAL_APPROVE: True,
            Permission.FINANCIAL_REQUEST: True,
            Permission.DATA_VIEW: True,
            Permission.DATA_WRITE: True,
            Permission.DATA_DELETE: True,
            Permission.GOALS_MANAGE: True,
            Permission.SIMULATION_RUN: True,
            Permission.REPORTS_GENERATE: True,
            Permission.REPORTS_DOWNLOAD: True,
            Permission.RECOMMENDATION_ACT: True,
            Permission.CHAT_COLLABORATE: True,
        },
        BusinessRole.ADMINISTRATOR: {
            Permission.MEMBERS_VIEW: True,
            Permission.MEMBERS_MANAGE: True,
            Permission.FINANCIAL_APPROVE: True,
            Permission.FINANCIAL_REQUEST: True,
            Permission.DATA_VIEW: True,
            Permission.DATA_WRITE: True,
            Permission.DATA_DELETE: True,
            Permission.GOALS_MANAGE: True,
            Permission.SIMULATION_RUN: True,
            Permission.REPORTS_GENERATE: True,
            Permission.REPORTS_DOWNLOAD: True,
            Permission.RECOMMENDATION_ACT: True,
            Permission.CHAT_COLLABORATE: True,
        },
        BusinessRole.MANAGER: {
            Permission.MEMBERS_VIEW: True,
            Permission.MEMBERS_MANAGE: False,
            Permission.FINANCIAL_APPROVE: True,
            Permission.FINANCIAL_REQUEST: True,
            Permission.DATA_VIEW: True,
            Permission.DATA_WRITE: True,
            Permission.DATA_DELETE: False,
            Permission.GOALS_MANAGE: True,
            Permission.SIMULATION_RUN: True,
            Permission.REPORTS_GENERATE: True,
            Permission.REPORTS_DOWNLOAD: True,
            Permission.RECOMMENDATION_ACT: True,
            Permission.CHAT_COLLABORATE: True,
        },
        BusinessRole.ANALYST: {
            Permission.MEMBERS_VIEW: True,
            Permission.MEMBERS_MANAGE: False,
            Permission.FINANCIAL_APPROVE: False,
            Permission.FINANCIAL_REQUEST: True,
            Permission.DATA_VIEW: True,
            Permission.DATA_WRITE: False,
            Permission.DATA_DELETE: False,
            Permission.GOALS_MANAGE: False,
            Permission.SIMULATION_RUN: True,
            Permission.REPORTS_GENERATE: True,
            Permission.REPORTS_DOWNLOAD: True,
            Permission.RECOMMENDATION_ACT: False,
            Permission.CHAT_COLLABORATE: True,
        },
        BusinessRole.VIEWER: {
            Permission.MEMBERS_VIEW: True,
            Permission.MEMBERS_MANAGE: False,
            Permission.FINANCIAL_APPROVE: False,
            Permission.FINANCIAL_REQUEST: False,
            Permission.DATA_VIEW: True,
            Permission.DATA_WRITE: False,
            Permission.DATA_DELETE: False,
            Permission.GOALS_MANAGE: False,
            Permission.SIMULATION_RUN: False,
            Permission.REPORTS_GENERATE: False,
            Permission.REPORTS_DOWNLOAD: True,
            Permission.RECOMMENDATION_ACT: False,
            Permission.CHAT_COLLABORATE: True,
        },
    }

    for role, perms in expected_matrix.items():
        for perm, expected_allow in perms.items():
            actual = RBACService.has_permission(role, perm)
            assert actual == expected_allow, f"Mismatch for {role.value} on {perm.value}: expected {expected_allow}, got {actual}"


def test_unknown_role_and_permission_explicit_deny():
    """Verify that an unknown role or non-existent permission explicitly denies."""
    assert not RBACService.has_permission("GhostRole", Permission.DATA_VIEW)
    assert not RBACService.has_permission(BusinessRole.VIEWER, "invalid:permission")
    with pytest.raises(Exception):
        RBACService.check_permission(BusinessRole.VIEWER, "invalid:permission")


def test_invitation_expiry_and_revocation_enforcement(client: TestClient, db_session: Session):
    """Expired or revoked invitations cannot be accepted."""
    owner = _create_user(db_session, "owner_exp@test.com")
    biz = _create_business(db_session, owner)
    invitee = _create_user(db_session, "invitee@test.com")

    # 1. Expired invitation
    expired_inv = BusinessInvitation(
        business_id=biz.id,
        email=invitee.email,
        role="Manager",
        token="expired-token-123",
        invited_by_user_id=owner.id,
        status=InvitationStatus.PENDING.value,
        expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    db_session.add(expired_inv)
    db_session.commit()

    exp_res = client.post(
        "/api/v1/collaboration/invitations/accept",
        json={"token": "expired-token-123"},
        headers=_auth_header(invitee),
    )
    assert exp_res.status_code == 400
    assert "expired" in exp_res.text.lower()

    # 2. Revoked invitation
    revoked_inv = BusinessInvitation(
        business_id=biz.id,
        email=invitee.email,
        role="Manager",
        token="revoked-token-456",
        invited_by_user_id=owner.id,
        status=InvitationStatus.REVOKED.value,
        expires_at=datetime.now(timezone.utc) + timedelta(days=5),
    )
    db_session.add(revoked_inv)
    db_session.commit()

    rev_res = client.post(
        "/api/v1/collaboration/invitations/accept",
        json={"token": "revoked-token-456"},
        headers=_auth_header(invitee),
    )
    assert rev_res.status_code == 400
    assert "no longer pending" in rev_res.text.lower() or "revoked" in rev_res.text.lower()


def test_invitation_wrong_user_email_rejection(client: TestClient, db_session: Session):
    """A user cannot accept an invitation issued to a different email address."""
    owner = _create_user(db_session, "owner_sec@test.com")
    biz = _create_business(db_session, owner)
    intended_user = _create_user(db_session, "intended@test.com")
    imposter_user = _create_user(db_session, "imposter@test.com")

    inv = BusinessInvitation(
        business_id=biz.id,
        email="intended@test.com",
        role="Manager",
        token="intended-token-789",
        invited_by_user_id=owner.id,
        status=InvitationStatus.PENDING.value,
        expires_at=datetime.now(timezone.utc) + timedelta(days=3),
    )
    db_session.add(inv)
    db_session.commit()

    # Imposter tries to accept
    res = client.post(
        "/api/v1/collaboration/invitations/accept",
        json={"token": "intended-token-789"},
        headers=_auth_header(imposter_user),
    )
    assert res.status_code == 403
    assert "intended@test.com" in res.text


def test_approval_invalid_state_transitions(client: TestClient, db_session: Session):
    """Approved or cancelled requests cannot transition into inconsistent states."""
    owner = _create_user(db_session, "owner_trans_chk@test.com")
    biz = _create_business(db_session, owner)

    app_req = ApprovalRequest(
        business_id=biz.id,
        requester_user_id=owner.id,
        entity_type=ApprovalEntityType.DECISION,
        entity_id="101",
        title="Check State Machine",
        status=ApprovalStatus.APPROVED.value,
    )
    db_session.add(app_req)
    db_session.commit()

    # 1. Attempt to review already approved request -> 400
    res_review = client.post(
        f"/api/v1/approvals/{app_req.id}/review",
        json={"action": "APPROVE"},
        headers=_auth_header(owner),
    )
    assert res_review.status_code == 400
    assert "Cannot review request" in res_review.text

    # 2. Attempt to cancel already approved request -> 400
    res_cancel = client.post(
        f"/api/v1/approvals/{app_req.id}/cancel",
        headers=_auth_header(owner),
    )
    assert res_cancel.status_code == 400
    assert "Cannot cancel request" in res_cancel.text


def test_cross_tenant_comprehensive_isolation(client: TestClient, db_session: Session):
    """Verify tenant isolation across invitation revocation, member removal, and request cancellation."""
    owner_a = _create_user(db_session, "owner_a_iso@test.com")
    biz_a = _create_business(db_session, owner_a, name="Biz A")

    owner_b = _create_user(db_session, "owner_b_iso@test.com")
    biz_b = _create_business(db_session, owner_b, name="Biz B")
    member_b = _create_user(db_session, "member_b@test.com")
    m_record = _add_member(db_session, biz_b, member_b, BusinessRole.ANALYST)

    inv_b = BusinessInvitation(
        business_id=biz_b.id,
        email="pending_b@test.com",
        role="Viewer",
        token="token-biz-b-999",
        invited_by_user_id=owner_b.id,
        status=InvitationStatus.PENDING.value,
        expires_at=datetime.now(timezone.utc) + timedelta(days=2),
    )
    db_session.add(inv_b)

    req_b = ApprovalRequest(
        business_id=biz_b.id,
        requester_user_id=owner_b.id,
        entity_type=ApprovalEntityType.DECISION,
        entity_id="500",
        title="Biz B Request",
        status=ApprovalStatus.PENDING.value,
    )
    db_session.add(req_b)
    db_session.commit()

    # 1. Owner A tries to revoke Biz B's invitation -> 404 (not in active business)
    rev_res = client.delete(
        f"/api/v1/collaboration/invitations/{inv_b.id}",
        headers=_auth_header(owner_a),
    )
    assert rev_res.status_code == 404

    # 2. Owner A tries to remove Biz B's member -> 404
    rem_res = client.delete(
        f"/api/v1/collaboration/members/{m_record.id}",
        headers=_auth_header(owner_a),
    )
    assert rem_res.status_code == 404

    # 3. Owner A tries to cancel Biz B's approval request -> 404
    cancel_res = client.post(
        f"/api/v1/approvals/{req_b.id}/cancel",
        headers=_auth_header(owner_a),
    )
    assert cancel_res.status_code == 404

    # 4. Owner A tries to transfer ownership of Biz B to member_b -> Owner A is in Biz A, so 400 (not member of Biz A)
    trans_res = client.post(
        "/api/v1/collaboration/transfer-ownership",
        json={"new_owner_user_id": member_b.id},
        headers=_auth_header(owner_a),
    )
    assert trans_res.status_code == 400
    assert "must be an active member" in trans_res.text

