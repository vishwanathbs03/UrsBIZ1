"""Comprehensive tests for Business Decision Workbench (Phase 6.18 Extension).

Verifies:
  - Multi-option deterministic evaluation across decision categories
  - Separation of observed facts, calculated estimates, assumptions, and AI explanations
  - Mandatory scenario disclaimers (zero guarantees)
  - Missing-data transparency without metric fabrication
  - Full decision lifecycle (Draft -> Decided -> Outcome Reviewed)
  - Strict tenant and user ownership isolation
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = "sqlite:///" + str(BACKEND / "atlas_ai.db").replace("\\", "/")
os.environ["JWT_SECRET_KEY"] = "test-secret-32-bytes-long-key-12345"

from app.main import app
from app.utils.database import Base, engine

Base.metadata.create_all(bind=engine)


def _setup_user_and_business(client: TestClient, prefix: str) -> dict:
    ts = int(time.time() * 1000)
    email = f"{prefix}_{ts}@example.com"
    password = "Password123!"

    # 1. Register
    reg = client.post(
        "/api/v1/auth/register",
        json={"full_name": f"{prefix} Owner", "email": email, "password": password},
    )
    assert reg.status_code == 201, reg.text

    # 2. Login
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200, login.text
    cookies = login.cookies

    # 3. Create Business
    biz_resp = client.post(
        "/api/v1/business",
        json={
            "basic": {
                "legal_name": f"{prefix} Industries Pvt Ltd",
                "trade_name": f"{prefix} Tools",
                "industry": "Manufacturing",
                "established_year": 2020,
                "employee_count": 18,
                "annual_revenue": 1250000.0,
                "revenue_currency": "INR",
                "city": "Bengaluru",
                "state_region": "Karnataka",
                "country": "IN",
            }
        },
        cookies=cookies,
    )
    assert biz_resp.status_code == 201, biz_resp.text
    biz_data = biz_resp.json()

    return {
        "email": email,
        "cookies": cookies,
        "business": biz_data,
    }


# ===========================================================================
# 1. Option Evaluation Tests
# ===========================================================================


def test_evaluate_discount_decision():
    """Verify evaluation of 'offer_discount' returns 3 structured options with evidence & disclaimers."""
    client = TestClient(app)
    account = _setup_user_and_business(client, "disc_eval")
    cookies = account["cookies"]

    payload = {
        "decision_type": "offer_discount",
        "objective": "Should I offer a volume discount to boost orders without sacrificing gross profit?",
    }
    resp = client.post("/api/v1/decisions/evaluate", json=payload, cookies=cookies)
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["decision_type"] == "offer_discount"
    assert "Baseline revenue" in data["ai_executive_summary"] or "Evaluation" in data["ai_executive_summary"]
    assert len(data["options"]) == 3

    opt_ids = [o["option_id"] for o in data["options"]]
    assert "opt_status_quo" in opt_ids
    assert "opt_targeted_discount" in opt_ids
    assert "opt_storewide_discount" in opt_ids

    # Verify option structure for targeted discount
    targeted_opt = next(o for o in data["options"] if o["option_id"] == "opt_targeted_discount")
    assert len(targeted_opt["supporting_evidence"]) > 0
    assert len(targeted_opt["assumptions"]) > 0
    assert len(targeted_opt["potential_benefits"]) > 0
    assert len(targeted_opt["potential_risks"]) > 0
    assert targeted_opt["confidence"] > 0

    # Verify mandatory scenario disclaimer
    disclaimer = targeted_opt["estimated_impact"]["disclaimer"]
    assert "Illustrative scenario estimate — not a guaranteed prediction." in disclaimer


def test_evaluate_price_increase_decision():
    """Verify evaluation of 'increase_price' returns inelasticity-based options."""
    client = TestClient(app)
    account = _setup_user_and_business(client, "price_eval")
    cookies = account["cookies"]

    payload = {
        "decision_type": "increase_price",
        "objective": "Should I increase prices on my top-selling lines to protect margins against inflation?",
    }
    resp = client.post("/api/v1/decisions/evaluate", json=payload, cookies=cookies)
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["decision_type"] == "increase_price"
    opt_ids = [o["option_id"] for o in data["options"]]
    assert "opt_maintain_prices" in opt_ids
    assert "opt_selective_price_increase" in opt_ids
    assert "opt_general_price_increase" in opt_ids


def test_evaluate_customer_focus_decision():
    """Verify evaluation of 'customer_focus' compares retention vs acquisition."""
    client = TestClient(app)
    account = _setup_user_and_business(client, "cust_focus")
    cookies = account["cookies"]

    payload = {
        "decision_type": "customer_focus",
        "objective": "Should I focus on existing high-value customer retention or outbound acquisition?",
    }
    resp = client.post("/api/v1/decisions/evaluate", json=payload, cookies=cookies)
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["decision_type"] == "customer_focus"
    opt_ids = [o["option_id"] for o in data["options"]]
    assert "opt_key_account_retention" in opt_ids
    assert "opt_aggressive_acquisition" in opt_ids


def test_evaluate_missing_sales_data_transparency():
    """Verify that when no sales transaction records exist, missing information is explicitly disclosed without fake metrics."""
    client = TestClient(app)
    account = _setup_user_and_business(client, "missing_sales")
    cookies = account["cookies"]

    payload = {
        "decision_type": "expand_product_range",
        "objective": "Should I launch a new product range next month?",
    }
    resp = client.post("/api/v1/decisions/evaluate", json=payload, cookies=cookies)
    assert resp.status_code == 200, resp.text
    data = resp.json()

    # When no sales transactions uploaded, has_sales_data is False
    assert data["baseline_snapshot"]["has_sales_data"] is False
    
    # Missing info must explicitly disclose missing transaction records
    first_opt = data["options"][0]
    assert any("transaction data" in m for m in first_opt["missing_information"])
    assert len(first_opt["recommended_additional_data"]) > 0


# ===========================================================================
# 2. Decision Lifecycle & Persistence (CRUD) Tests
# ===========================================================================


def test_decision_crud_and_lifecycle():
    """Verify full decision lifecycle: evaluate -> create -> select option & decide -> update review -> delete."""
    client = TestClient(app)
    account = _setup_user_and_business(client, "crud_cycle")
    cookies = account["cookies"]

    # 1. Evaluate options
    eval_resp = client.post(
        "/api/v1/decisions/evaluate",
        json={"decision_type": "offer_discount", "objective": "Test discount strategy"},
        cookies=cookies,
    )
    assert eval_resp.status_code == 200, eval_resp.text
    eval_data = eval_resp.json()

    # 2. Save as Draft
    create_payload = {
        "decision_type": eval_data["decision_type"],
        "title": "Pricing Strategy Q3",
        "objective": eval_data["objective"],
        "baseline_snapshot": eval_data["baseline_snapshot"],
        "options": eval_data["options"],
        "status": "Draft",
    }
    create_resp = client.post("/api/v1/decisions", json=create_payload, cookies=cookies)
    assert create_resp.status_code == 201, create_resp.text
    created = create_resp.json()
    decision_id = created["id"]
    assert created["status"] == "Draft"
    assert created["selected_option_id"] is None

    # 3. Update to 'Decided' with selected option and rationale
    update_payload = {
        "status": "Decided",
        "selected_option_id": "opt_targeted_discount",
        "selected_option_title": "Targeted 5% Volume Discount",
        "decision_rationale": "Chose targeted discount to protect unit margins while incentivizing bulk reorders.",
    }
    update_resp = client.patch(f"/api/v1/decisions/{decision_id}", json=update_payload, cookies=cookies)
    assert update_resp.status_code == 200, update_resp.text
    updated = update_resp.json()
    assert updated["status"] == "Decided"
    assert updated["selected_option_id"] == "opt_targeted_discount"
    assert updated["decided_at"] is not None

    # 4. List decisions
    list_resp = client.get("/api/v1/decisions", cookies=cookies)
    assert list_resp.status_code == 200, list_resp.text
    list_data = list_resp.json()
    assert list_data["total"] >= 1
    assert any(d["id"] == decision_id for d in list_data["items"])

    # 5. Fetch single decision
    get_resp = client.get(f"/api/v1/decisions/{decision_id}", cookies=cookies)
    assert get_resp.status_code == 200, get_resp.text
    assert get_resp.json()["id"] == decision_id

    # 6. Post-decision review update
    review_payload = {
        "review_status": "Outcome_Observed",
        "review_notes": "14-day outcome observed: +6.8% volume increase without adverse customer churn.",
    }
    rev_resp = client.patch(f"/api/v1/decisions/{decision_id}", json=review_payload, cookies=cookies)
    assert rev_resp.status_code == 200, rev_resp.text
    assert rev_resp.json()["review_status"] == "Outcome_Observed"
    assert rev_resp.json()["review_notes"] == review_payload["review_notes"]

    # 7. Delete decision
    del_resp = client.delete(f"/api/v1/decisions/{decision_id}", cookies=cookies)
    assert del_resp.status_code == 200, del_resp.text
    assert del_resp.json()["deleted"] is True

    # 8. Verify 404 after deletion
    get_after_del = client.get(f"/api/v1/decisions/{decision_id}", cookies=cookies)
    assert get_after_del.status_code == 404


# ===========================================================================
# 3. Tenant Isolation Tests
# ===========================================================================


def test_decision_tenant_isolation():
    """Verify that User B cannot read, modify, or delete User A's decisions (Strict Tenant Isolation)."""
    client_a = TestClient(app)
    account_a = _setup_user_and_business(client_a, "tenant_a")
    cookies_a = account_a["cookies"]

    client_b = TestClient(app)
    account_b = _setup_user_and_business(client_b, "tenant_b")
    cookies_b = account_b["cookies"]

    # 1. User A creates a decision
    eval_resp = client_a.post(
        "/api/v1/decisions/evaluate",
        json={"decision_type": "reduce_expenses", "objective": "Expense reduction for User A"},
        cookies=cookies_a,
    )
    eval_data = eval_resp.json()

    create_resp = client_a.post(
        "/api/v1/decisions",
        json={
            "decision_type": "reduce_expenses",
            "title": "User A Private Decision",
            "objective": "Confidential cost cut",
            "baseline_snapshot": eval_data["baseline_snapshot"],
            "options": eval_data["options"],
            "status": "Draft",
        },
        cookies=cookies_a,
    )
    assert create_resp.status_code == 201
    decision_a_id = create_resp.json()["id"]

    # 2. User B tries to GET User A's decision -> MUST return 404
    get_b = client_b.get(f"/api/v1/decisions/{decision_a_id}", cookies=cookies_b)
    assert get_b.status_code == 404, "Cross-tenant decision access was leaked!"

    # 3. User B tries to PATCH User A's decision -> MUST return 404
    patch_b = client_b.patch(
        f"/api/v1/decisions/{decision_a_id}",
        json={"title": "Hacked Title"},
        cookies=cookies_b,
    )
    assert patch_b.status_code == 404, "Cross-tenant decision modification succeeded!"

    # 4. User B tries to DELETE User A's decision -> MUST return 404
    del_b = client_b.delete(f"/api/v1/decisions/{decision_a_id}", cookies=cookies_b)
    assert del_b.status_code == 404, "Cross-tenant decision deletion succeeded!"

    # 5. User B lists decisions -> MUST NOT contain User A's decision
    list_b = client_b.get("/api/v1/decisions", cookies=cookies_b)
    assert list_b.status_code == 200
    b_ids = [d["id"] for d in list_b.json()["items"]]
    assert decision_a_id not in b_ids, "User A's decision leaked in User B's list!"


# ===========================================================================
# 4. Boundary Tests & Audit History (Verification Items B & D)
# ===========================================================================


def test_evaluate_discount_negative_or_exceeded_gross_margin():
    """Verify boundary conditions: discount >= margin or negative margin triggers explicit risk disclosures."""
    client = TestClient(app)
    account = _setup_user_and_business(client, "margin_boundaries")
    cookies = account["cookies"]

    # 1. Discount exceeding margin: 25% discount on 20% margin
    resp_exceeded = client.post(
        "/api/v1/decisions/evaluate",
        json={
            "decision_type": "offer_discount",
            "objective": "Test aggressive 25% discount",
            "custom_parameters": {"discount_pct": 25.0, "gross_margin_pct": 20.0},
        },
        cookies=cookies,
    )
    assert resp_exceeded.status_code == 200
    data_exceeded = resp_exceeded.json()
    opt2_risks = data_exceeded["options"][1]["potential_risks"]
    assert any("meets or exceeds available gross margin" in r for r in opt2_risks)

    # 2. Negative margin: -5% gross margin
    resp_negative = client.post(
        "/api/v1/decisions/evaluate",
        json={
            "decision_type": "offer_discount",
            "objective": "Test discount under negative margin",
            "custom_parameters": {"discount_pct": 5.0, "gross_margin_pct": -5.0},
        },
        cookies=cookies,
    )
    assert resp_negative.status_code == 200
    data_negative = resp_negative.json()
    opt2_neg_risks = data_negative["options"][1]["potential_risks"]
    assert any("Gross margin is zero or negative" in r for r in opt2_neg_risks)


def test_decision_soft_delete_audit_trail():
    """Verify decision cancellation/soft deletion preserves complete audit trail (Audit Item D)."""
    client = TestClient(app)
    account = _setup_user_and_business(client, "audit_trail")
    cookies = account["cookies"]

    # 1. Create a decision
    create_payload = {
        "decision_type": "reduce_expenses",
        "title": "Vendor Renegotiation Q4",
        "objective": "Lower raw material costs by 8%",
        "status": "Draft",
    }
    create_resp = client.post("/api/v1/decisions", json=create_payload, cookies=cookies)
    assert create_resp.status_code == 201
    decision_id = create_resp.json()["id"]

    # 2. Soft-delete with cancellation reason
    del_resp = client.delete(
        f"/api/v1/decisions/{decision_id}?cancellation_reason=Vendor agreed to tier rebate",
        cookies=cookies,
    )
    assert del_resp.status_code == 200
    del_data = del_resp.json()
    assert del_data["deleted"] is True
    assert del_data["soft_deleted"] is True

    # 3. Standard GET returns 404 (hidden from active view)
    get_resp = client.get(f"/api/v1/decisions/{decision_id}", cookies=cookies)
    assert get_resp.status_code == 404

    # 4. Standard list excludes it
    list_active = client.get("/api/v1/decisions", cookies=cookies)
    assert list_active.status_code == 200
    assert not any(d["id"] == decision_id for d in list_active.json()["items"])

    # 5. List with include_archived=true preserves the auditable record
    list_all = client.get("/api/v1/decisions?include_archived=true", cookies=cookies)
    assert list_all.status_code == 200
    archived_item = next((d for d in list_all.json()["items"] if d["id"] == decision_id), None)
    assert archived_item is not None
    assert archived_item["is_deleted"] is True
    assert archived_item["status"] == "Cancelled"
    assert archived_item["cancellation_reason"] == "Vendor agreed to tier rebate"
    assert archived_item["deleted_at"] is not None
    assert archived_item["deleted_by_id"] is not None

    # 6. Direct GET with include_archived=true retrieves full history
    get_archived = client.get(f"/api/v1/decisions/{decision_id}?include_archived=true", cookies=cookies)
    assert get_archived.status_code == 200
    assert get_archived.json()["id"] == decision_id
    assert get_archived.json()["is_deleted"] is True


def test_evaluate_additional_decision_types():
    """Verify evaluation for expand_product_range, reduce_expenses, and test_sales_channel."""
    client = TestClient(app)
    account = _setup_user_and_business(client, "additional_decisions")
    cookies = account["cookies"]

    # 1. Expand Product Range
    resp_expand = client.post(
        "/api/v1/decisions/evaluate",
        json={"decision_type": "expand_product_range", "objective": "Expand into adjacent accessories"},
        cookies=cookies,
    )
    assert resp_expand.status_code == 200
    data_expand = resp_expand.json()
    opt_ids_expand = [o["option_id"] for o in data_expand["options"]]
    assert "opt_status_quo_catalog" in opt_ids_expand
    assert "opt_adjacent_expansion" in opt_ids_expand
    assert "opt_broad_line_launch" in opt_ids_expand

    # 2. Reduce Expenses
    resp_reduce = client.post(
        "/api/v1/decisions/evaluate",
        json={"decision_type": "reduce_expenses", "objective": "Lower operating overhead"},
        cookies=cookies,
    )
    assert resp_reduce.status_code == 200
    data_reduce = resp_reduce.json()
    opt_ids_reduce = [o["option_id"] for o in data_reduce["options"]]
    assert "opt_status_quo_expenses" in opt_ids_reduce
    assert "opt_targeted_renegotiation" in opt_ids_reduce
    assert "opt_austerity_headcount_freeze" in opt_ids_reduce

    # 3. Test Sales Channel
    resp_channel = client.post(
        "/api/v1/decisions/evaluate",
        json={"decision_type": "test_sales_channel", "objective": "Test direct digital e-commerce"},
        cookies=cookies,
    )
    assert resp_channel.status_code == 200
    data_channel = resp_channel.json()
    opt_ids_channel = [o["option_id"] for o in data_channel["options"]]
    assert "opt_status_quo_channel" in opt_ids_channel
    assert "opt_direct_digital_pilot" in opt_ids_channel
    assert "opt_marketplace_listing" in opt_ids_channel


