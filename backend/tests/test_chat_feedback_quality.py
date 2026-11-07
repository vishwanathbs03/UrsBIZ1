"""Tests for Phase 6.28: AI Answer Feedback & Quality Evaluation."""
from __future__ import annotations

import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.models.business import Business
from app.models.chat import ChatMessage, ChatSession
from app.models.chat_feedback import ChatFeedback, FeedbackCategory
from app.models.collaboration import BusinessMember, BusinessRole, MemberStatus
from app.models.user import User
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


def _create_user(db: Session, email: str = "feedback_owner@test.com", full_name: str = "Feedback Tester") -> User:
    u = db.query(User).filter_by(email=email).first()
    if not u:
        u = User(
            email=email,
            full_name=full_name,
            password_hash=hash_password("fakehashpw12345"),
            is_active=True,
        )
        db.add(u)
        db.commit()
        db.refresh(u)
    return u


def _create_business(db: Session, owner: User, name: str = "Feedback MSME Corp") -> Business:
    biz = Business(
        owner_id=owner.id,
        legal_name=name,
        trade_name=name,
        industry="Retail",
        established_year=2021,
    )
    db.add(biz)
    db.commit()
    db.refresh(biz)

    # Owner membership
    mem = BusinessMember(
        business_id=biz.id,
        user_id=owner.id,
        role=BusinessRole.OWNER.value,
        status=MemberStatus.ACTIVE.value,
    )
    db.add(mem)

    # Set user active business
    owner.active_business_id = biz.id
    db.add(owner)
    db.commit()
    return biz


def _auth_header(user: User) -> dict[str, str]:
    tok = create_access_token(subject=str(user.id))
    return {"Authorization": f"Bearer {tok}"}


def _create_chat_turn(
    db: Session,
    business_id: int,
    user_id: int,
    user_prompt: str = "What was my total revenue last month?",
    assistant_reply: str = "Your total revenue last month was ₹450,000.",
    fallback_used: bool = False,
    sources: list[dict] | None = None,
) -> tuple[ChatMessage, ChatMessage]:
    """Helper to create a ChatSession with a user prompt and assistant response turn."""
    session = ChatSession(
        business_id=business_id,
        owner_id=user_id,
        title="Revenue Analysis",
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    user_msg = ChatMessage(
        session_id=session.id,
        user_id=user_id,
        role="user",
        kind="revenue",
        content=user_prompt,
    )
    db.add(user_msg)
    db.commit()
    db.refresh(user_msg)

    assistant_msg = ChatMessage(
        session_id=session.id,
        user_id=user_id,
        role="assistant",
        kind="revenue",
        content=assistant_reply,
        fallback_used=fallback_used,
        sources_json=json.dumps(sources or []),
    )
    db.add(assistant_msg)
    db.commit()
    db.refresh(assistant_msg)

    return user_msg, assistant_msg


# =============================================================================
# 1. FEEDBACK SUBMISSION & LIFECYCLE
# =============================================================================

def test_submit_feedback_on_assistant_turn(client: TestClient, db_session: Session):
    """Verify submitting structured feedback on an AI assistant response."""
    owner = _create_user(db_session, "owner_fb_01@test.com")
    biz = _create_business(db_session, owner, "Biz FB 01")
    user_msg, assistant_msg = _create_chat_turn(db_session, biz.id, owner.id)

    # Submit 5-star Helpful feedback
    res = client.post(
        f"/api/v1/chat/messages/{assistant_msg.id}/feedback",
        json={
            "rating": 5,
            "feedback_category": "Helpful",
            "notes": "Clear and precisely matched my GSTR-1 filings.",
        },
        headers=_auth_header(owner),
    )
    assert res.status_code == 201
    data = res.json()
    assert data["message_id"] == assistant_msg.id
    assert data["business_id"] == biz.id
    assert data["user_id"] == owner.id
    assert data["rating"] == 5
    assert data["is_positive"] is True
    assert data["feedback_category"] == "Helpful"
    assert data["notes"] == "Clear and precisely matched my GSTR-1 filings."

    # Retrieve feedback for the message
    get_res = client.get(
        f"/api/v1/chat/messages/{assistant_msg.id}/feedback",
        headers=_auth_header(owner),
    )
    assert get_res.status_code == 200
    assert get_res.json()["id"] == data["id"]

    # Idempotent re-submission (updates existing record)
    res_update = client.post(
        f"/api/v1/chat/messages/{assistant_msg.id}/feedback",
        json={
            "rating": 4,
            "feedback_category": "Helpful",
            "notes": "Updated: Still helpful but could include margins.",
        },
        headers=_auth_header(owner),
    )
    assert res_update.status_code == 201
    updated_data = res_update.json()
    assert updated_data["id"] == data["id"]
    assert updated_data["rating"] == 4
    assert "Still helpful" in updated_data["notes"]


def test_guard_rejects_feedback_on_user_message(client: TestClient, db_session: Session):
    """Verify feedback cannot be submitted on user prompt turns (only assistant responses)."""
    owner = _create_user(db_session, "owner_fb_guard@test.com")
    biz = _create_business(db_session, owner, "Biz FB Guard")
    user_msg, _ = _create_chat_turn(db_session, biz.id, owner.id)

    res = client.post(
        f"/api/v1/chat/messages/{user_msg.id}/feedback",
        json={
            "rating": 5,
            "feedback_category": "Helpful",
        },
        headers=_auth_header(owner),
    )
    assert res.status_code == 400
    assert "only be submitted on assistant responses" in res.json()["detail"]


def test_patch_and_delete_feedback_lifecycle(client: TestClient, db_session: Session):
    """Verify PATCH partial update and DELETE zero-retention compliance."""
    owner = _create_user(db_session, "owner_fb_lifecycle@test.com")
    biz = _create_business(db_session, owner, "Biz FB Lifecycle")
    _, assistant_msg = _create_chat_turn(db_session, biz.id, owner.id)

    # Initial submission
    client.post(
        f"/api/v1/chat/messages/{assistant_msg.id}/feedback",
        json={"rating": 2, "feedback_category": "Difficult to Understand", "notes": "Too technical"},
        headers=_auth_header(owner),
    )

    # PATCH update
    patch_res = client.patch(
        f"/api/v1/chat/messages/{assistant_msg.id}/feedback",
        json={"rating": 3, "notes": "Understood after re-reading."},
        headers=_auth_header(owner),
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["rating"] == 3
    assert patch_res.json()["feedback_category"] == "Difficult to Understand"
    assert patch_res.json()["notes"] == "Understood after re-reading."

    # DELETE zero-retention
    del_res = client.delete(
        f"/api/v1/chat/messages/{assistant_msg.id}/feedback",
        headers=_auth_header(owner),
    )
    assert del_res.status_code == 204

    # Verify feedback is gone
    get_after = client.get(
        f"/api/v1/chat/messages/{assistant_msg.id}/feedback",
        headers=_auth_header(owner),
    )
    assert get_after.status_code == 200
    assert get_after.json() is None


# =============================================================================
# 2. TENANT ISOLATION & ACCESS CONTROL
# =============================================================================

def test_tenant_isolation_on_chat_feedback(client: TestClient, db_session: Session):
    """Verify tenant isolation: a user cannot rate or inspect messages from another business."""
    owner1 = _create_user(db_session, "tenant1_owner@test.com")
    biz1 = _create_business(db_session, owner1, "Tenant 1 Enterprise")
    _, assistant_msg1 = _create_chat_turn(db_session, biz1.id, owner1.id)

    owner2 = _create_user(db_session, "tenant2_owner@test.com")
    biz2 = _create_business(db_session, owner2, "Tenant 2 Enterprise")

    # Owner2 attempts to submit feedback on Tenant 1's message -> 404 Not Found
    res = client.post(
        f"/api/v1/chat/messages/{assistant_msg1.id}/feedback",
        json={"rating": 1, "feedback_category": "Incorrect Information"},
        headers=_auth_header(owner2),
    )
    assert res.status_code == 404
    assert "not found in active business conversations" in res.json()["detail"]


def test_validation_of_feedback_categories_and_ratings(client: TestClient, db_session: Session):
    """Verify rating bounds (1-5) and exact frozen category validation."""
    owner = _create_user(db_session, "val_owner@test.com")
    biz = _create_business(db_session, owner, "Val Business")
    _, assistant_msg = _create_chat_turn(db_session, biz.id, owner.id)

    # Rating < 1 must fail
    res_low = client.post(
        f"/api/v1/chat/messages/{assistant_msg.id}/feedback",
        json={"rating": 0, "feedback_category": "Helpful"},
        headers=_auth_header(owner),
    )
    assert res_low.status_code == 422

    # Rating > 5 must fail
    res_high = client.post(
        f"/api/v1/chat/messages/{assistant_msg.id}/feedback",
        json={"rating": 6, "feedback_category": "Helpful"},
        headers=_auth_header(owner),
    )
    assert res_high.status_code == 422

    # Invalid category must fail
    res_bad_cat = client.post(
        f"/api/v1/chat/messages/{assistant_msg.id}/feedback",
        json={"rating": 3, "feedback_category": "MadeUpCategory"},
        headers=_auth_header(owner),
    )
    assert res_bad_cat.status_code == 422

    # All 5 frozen categories must succeed
    valid_categories = [
        "Helpful",
        "Incorrect Information",
        "Missing Evidence",
        "Outdated Data",
        "Difficult to Understand",
    ]
    for cat in valid_categories:
        res_ok = client.post(
            f"/api/v1/chat/messages/{assistant_msg.id}/feedback",
            json={"rating": 4, "feedback_category": cat},
            headers=_auth_header(owner),
        )
        assert res_ok.status_code == 201
        assert res_ok.json()["feedback_category"] == cat


# =============================================================================
# 3. QUALITY EVALUATION ANALYTICS & GROUNDING CORRELATION
# =============================================================================

def test_quality_analytics_and_grounding_correlation(client: TestClient, db_session: Session):
    """Verify aggregate quality analytics, category distribution, and grounding correlation."""
    owner = _create_user(db_session, "analytics_owner@test.com")
    biz = _create_business(db_session, owner, "Analytics Business")

    # Turn 1: Grounded answer with verified sources -> Rated 5 (Helpful)
    _, msg1 = _create_chat_turn(
        db_session, biz.id, owner.id,
        user_prompt="Explain gross margin trend",
        assistant_reply="Gross margin improved from 28% to 34% based on Q3 ledger.",
        fallback_used=False,
        sources=[{"title": "Q3 Sales Transactions", "records": 450}],
    )
    client.post(
        f"/api/v1/chat/messages/{msg1.id}/feedback",
        json={"rating": 5, "feedback_category": "Helpful"},
        headers=_auth_header(owner),
    )

    # Turn 2: Grounded answer with verified sources -> Rated 4 (Helpful)
    _, msg2 = _create_chat_turn(
        db_session, biz.id, owner.id,
        user_prompt="Who is my top customer?",
        assistant_reply="Hubli Wholesalers contributed 22% of total sales.",
        fallback_used=False,
        sources=[{"title": "Customer Concentration Report"}],
    )
    client.post(
        f"/api/v1/chat/messages/{msg2.id}/feedback",
        json={"rating": 4, "feedback_category": "Helpful"},
        headers=_auth_header(owner),
    )

    # Turn 3: Rule engine fallback used -> Rated 2 (Missing Evidence)
    _, msg3 = _create_chat_turn(
        db_session, biz.id, owner.id,
        user_prompt="Forecast demand for unknown widget",
        assistant_reply="Calculated via historical median fallback rules.",
        fallback_used=True,
        sources=[],
    )
    client.post(
        f"/api/v1/chat/messages/{msg3.id}/feedback",
        json={"rating": 2, "feedback_category": "Missing Evidence", "notes": "Fallback rule was too generic"},
        headers=_auth_header(owner),
    )

    # Turn 4: Rule engine fallback used -> Rated 1 (Outdated Data)
    _, msg4 = _create_chat_turn(
        db_session, biz.id, owner.id,
        user_prompt="Current inventory buffer",
        assistant_reply="Default fallback estimate based on initial profile.",
        fallback_used=True,
        sources=[],
    )
    client.post(
        f"/api/v1/chat/messages/{msg4.id}/feedback",
        json={"rating": 1, "feedback_category": "Outdated Data"},
        headers=_auth_header(owner),
    )

    # Turn 5: Missing / indeterminate provenance metadata -> rated 3 -> must be EXCLUDED from grounded and fallback comparison
    _, msg5 = _create_chat_turn(
        db_session, biz.id, owner.id,
        user_prompt="Unclassified message without sources",
        assistant_reply="Response without provenance envelope.",
        fallback_used=False,
        sources=[],
    )
    client.post(
        f"/api/v1/chat/messages/{msg5.id}/feedback",
        json={"rating": 3, "feedback_category": "Helpful"},
        headers=_auth_header(owner),
    )

    # Fetch quality evaluation analytics
    res = client.get("/api/v1/chat/feedback/analytics?days=30", headers=_auth_header(owner))
    assert res.status_code == 200
    analytics = res.json()

    assert analytics["business_id"] == biz.id
    assert analytics["total_feedback_count"] == 5
    assert analytics["helpful_count"] == 2
    assert analytics["unhelpful_count"] == 2
    assert analytics["helpfulness_rate"] == 0.40  # 2 of 5 helpful (rating >= 4)
    assert analytics["average_rating"] == 3.0  # (5 + 4 + 2 + 1 + 3) / 5 = 3.0
    assert analytics["quality_score"] > 0

    # Category breakdown
    dist = analytics["category_distribution"]
    assert dist["Helpful"] == 3
    assert dist["Missing Evidence"] == 1
    assert dist["Outdated Data"] == 1
    assert dist["Incorrect Information"] == 0
    assert dist["Difficult to Understand"] == 0

    # Grounding correlation: exactly 2 grounded and 2 fallback; unclassified message is strictly excluded
    corr = analytics["grounding_correlation"]
    assert corr["grounded_message_count"] == 2
    assert corr["grounded_average_rating"] == 4.5  # (5 + 4) / 2 = 4.5
    assert corr["fallback_message_count"] == 2
    assert corr["fallback_average_rating"] == 1.5  # (2 + 1) / 2 = 1.5
    assert corr["fallback_unhelpful_rate"] == 1.0  # 100% of fallback turns rated unhelpful (<=2)
    assert corr["unclassified_message_count"] == 1


def test_rbac_and_cross_user_feedback_isolation(client: TestClient, db_session: Session):
    """Verify RBAC role permissions and cross-user deletion privileges."""
    owner = _create_user(db_session, "rbac_owner@test.com", "Owner User")
    biz = _create_business(db_session, owner, "RBAC Quality Biz")

    # Member 1: Viewer
    viewer = _create_user(db_session, "viewer_user@test.com", "Viewer User")
    mem_viewer = BusinessMember(
        business_id=biz.id,
        user_id=viewer.id,
        role=BusinessRole.VIEWER.value,
        status=MemberStatus.ACTIVE.value,
    )
    db_session.add(mem_viewer)
    viewer.active_business_id = biz.id
    db_session.add(viewer)

    # Member 2: Administrator
    admin = _create_user(db_session, "admin_user@test.com", "Admin User")
    mem_admin = BusinessMember(
        business_id=biz.id,
        user_id=admin.id,
        role=BusinessRole.ADMINISTRATOR.value,
        status=MemberStatus.ACTIVE.value,
    )
    db_session.add(mem_admin)
    admin.active_business_id = biz.id
    db_session.add(admin)

    # Member 3: Analyst
    analyst = _create_user(db_session, "analyst_user@test.com", "Analyst User")
    mem_analyst = BusinessMember(
        business_id=biz.id,
        user_id=analyst.id,
        role=BusinessRole.ANALYST.value,
        status=MemberStatus.ACTIVE.value,
    )
    db_session.add(mem_analyst)
    analyst.active_business_id = biz.id
    db_session.add(analyst)
    db_session.commit()

    _, assistant_msg = _create_chat_turn(db_session, biz.id, owner.id)

    # 1. Viewer submits feedback (Viewer has DATA_VIEW permission)
    post_res = client.post(
        f"/api/v1/chat/messages/{assistant_msg.id}/feedback",
        json={"rating": 5, "feedback_category": "Helpful", "notes": "Viewer feedback"},
        headers=_auth_header(viewer),
    )
    assert post_res.status_code == 201
    assert post_res.json()["user_id"] == viewer.id

    # 2. Analyst attempts to delete Viewer's feedback -> not found / forbidden (only author or admin/owner)
    del_forbidden = client.delete(
        f"/api/v1/chat/messages/{assistant_msg.id}/feedback",
        headers=_auth_header(analyst),
    )
    assert del_forbidden.status_code == 404

    # 3. Administrator can delete any feedback for moderation / zero-retention
    del_admin = client.delete(
        f"/api/v1/chat/messages/{assistant_msg.id}/feedback",
        headers=_auth_header(admin),
    )
    assert del_admin.status_code == 204


def test_user_cascade_deletion_and_uniqueness_policy(client: TestClient, db_session: Session):
    """Verify user_id NOT NULL constraint, cascade deletion on user removal, and uniqueness."""
    owner = _create_user(db_session, "cascade_owner@test.com", "Cascade Owner")
    biz = _create_business(db_session, owner, "Cascade Business")
    _, assistant_msg = _create_chat_turn(db_session, biz.id, owner.id)

    # 1. Feedback must have user_id (cannot be NULL)
    with pytest.raises(Exception):
        null_fb = ChatFeedback(
            message_id=assistant_msg.id,
            business_id=biz.id,
            user_id=None,  # type: ignore[arg-type]
            rating=5,
            feedback_category="Helpful",
        )
        db_session.add(null_fb)
        db_session.commit()
    db_session.rollback()

    # 2. Submit valid feedback
    res = client.post(
        f"/api/v1/chat/messages/{assistant_msg.id}/feedback",
        json={"rating": 5, "feedback_category": "Helpful", "notes": "Cascade test note"},
        headers=_auth_header(owner),
    )
    assert res.status_code == 201
    fb_id = res.json()["id"]

    # Verify feedback exists in db
    fb = db_session.query(ChatFeedback).filter_by(id=fb_id).first()
    assert fb is not None
    assert fb.user_id == owner.id

    # 3. Deleting the user CASCADE deletes their feedback records (GDPR / zero-retention)
    db_session.delete(owner)
    db_session.commit()

    fb_after = db_session.query(ChatFeedback).filter_by(id=fb_id).first()
    assert fb_after is None, "ChatFeedback must be cascade-deleted when user is deleted"


def test_feedback_ownership_moderation_and_privacy(client: TestClient, db_session: Session):
    """Verify feedback ownership, cross-user update denial, manager deletion restriction,
    multi-tenant admin boundary, and analytics privacy (zero private notes exposure)."""
    owner = _create_user(db_session, "priv_owner@test.com", "Priv Owner")
    biz1 = _create_business(db_session, owner, "Business 1")
    biz2_owner = _create_user(db_session, "biz2_owner@test.com", "Biz2 Owner")
    biz2 = _create_business(db_session, biz2_owner, "Business 2")

    # Member in Biz1: Manager
    mgr = _create_user(db_session, "mgr_priv@test.com", "Manager User")
    mem_mgr = BusinessMember(
        business_id=biz1.id,
        user_id=mgr.id,
        role=BusinessRole.MANAGER.value,
        status=MemberStatus.ACTIVE.value,
    )
    db_session.add(mem_mgr)
    mgr.active_business_id = biz1.id
    db_session.add(mgr)

    # Member in Biz1: Analyst
    analyst = _create_user(db_session, "analyst_priv@test.com", "Analyst User")
    mem_analyst = BusinessMember(
        business_id=biz1.id,
        user_id=analyst.id,
        role=BusinessRole.ANALYST.value,
        status=MemberStatus.ACTIVE.value,
    )
    db_session.add(mem_analyst)
    analyst.active_business_id = biz1.id
    db_session.add(analyst)
    db_session.commit()

    _, msg1 = _create_chat_turn(db_session, biz1.id, owner.id)
    _, msg2 = _create_chat_turn(db_session, biz2.id, biz2_owner.id)

    # 1. Analyst submits feedback with sensitive private notes
    post_res = client.post(
        f"/api/v1/chat/messages/{msg1.id}/feedback",
        json={
            "rating": 2,
            "feedback_category": "Incorrect Information",
            "notes": "CONFIDENTIAL: Client GSTIN 29AAAAA0000A1Z5 discrepancy in reconciliation",
        },
        headers=_auth_header(analyst),
    )
    assert post_res.status_code == 201

    # 2. Manager attempts to UPDATE Analyst's feedback by submitting on message_id -> creates or updates ONLY Manager's own feedback
    patch_attempt = client.patch(
        f"/api/v1/chat/messages/{msg1.id}/feedback",
        json={"rating": 5, "notes": "Manager attempt to overwrite"},
        headers=_auth_header(mgr),
    )
    assert patch_attempt.status_code == 404
    assert "No feedback record found for message" in patch_attempt.json()["detail"]

    # 3. Manager attempts to DELETE Analyst's feedback -> forbidden / 404 (only owner or admin can moderate)
    del_attempt = client.delete(
        f"/api/v1/chat/messages/{msg1.id}/feedback",
        headers=_auth_header(mgr),
    )
    assert del_attempt.status_code == 404

    # 4. Biz2 Admin / Owner cannot delete Biz1 feedback
    del_biz2 = client.delete(
        f"/api/v1/chat/messages/{msg1.id}/feedback",
        headers=_auth_header(biz2_owner),
    )
    assert del_biz2.status_code == 404

    # 5. Analytics must expose purely aggregate statistics without leaking private notes or identifiers
    analytics_res = client.get("/api/v1/chat/feedback/analytics?days=30", headers=_auth_header(mgr))
    assert analytics_res.status_code == 200
    analytics_payload = analytics_res.json()
    analytics_str = json.dumps(analytics_payload)
    assert "CONFIDENTIAL" not in analytics_str
    assert "29AAAAA0000A1Z5" not in analytics_str
    assert "notes" not in analytics_str
    assert "user_id" not in analytics_str
    assert "message_id" not in analytics_str
