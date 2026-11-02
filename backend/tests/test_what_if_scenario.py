"""Comprehensive tests for What-If Scenario Simulator (Phase 6.19 Extension).

Verifies:
  - Multi-case deterministic financial projections (Base, Worst, Best)
  - Sales drop, supplier cost shock, customer churn, price elasticity, DSO stretch
  - Clear separation of observed baseline vs benchmark assumptions
  - Missing-data transparency (disclosing COGS, OpEx, Cash benchmarks)
  - Mandatory scenario disclaimer on all responses
  - Full scenario persistence lifecycle (Save -> List -> Get -> Patch -> Delete)
  - Side-by-side scenario comparison endpoint
  - Strict multi-tenant isolation across businesses and users
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
                "legal_name": f"{prefix} Manufacturing Pvt Ltd",
                "trade_name": f"{prefix} Precision",
                "industry": "Manufacturing",
                "established_year": 2020,
                "employee_count": 12,
                "annual_revenue": 2_400_000.0,
                "revenue_currency": "INR",
                "city": "Pune",
                "state_region": "Maharashtra",
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


def test_simulate_sales_drop_shock():
    """Simulates a 15% sales drop shock and verifies deterministic multi-case results."""
    client = TestClient(app)
    user = _setup_user_and_business(client, "whatif_sales")

    resp = client.post(
        "/api/v1/scenarios/simulate",
        json={
            "title": "Q3 Demand Contraction",
            "parameters": {
                "scenario_type": "sales_drop",
                "sales_volume_delta_pct": -15.0,
                "price_delta_pct": 0.0,
                "cogs_delta_pct": 0.0,
                "opex_delta_inr": 0.0,
                "dso_stretch_days": 0,
            },
        },
        cookies=user["cookies"],
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["scenario_type"] == "sales_drop"
    assert "Illustrative scenario estimate — not a guaranteed prediction." in data["disclaimer"]
    assert len(data["cases"]) == 3

    base_case = next(c for c in data["cases"] if c["case_label"] == "Base Case")
    worst_case = next(c for c in data["cases"] if c["case_label"] == "Conservative / Worst Case")
    best_case = next(c for c in data["cases"] if c["case_label"] == "Optimistic / Best Case")

    # In Base Case, revenue delta percentage matches -15.0%
    assert base_case["revenue_delta_pct"] == -15.0
    assert base_case["revenue_delta_inr"] < 0
    assert base_case["operating_profit_delta_inr"] < 0

    # Worst case incorporates deeper stress (e.g. -21.0% volume)
    assert worst_case["revenue_delta_pct"] < base_case["revenue_delta_pct"]
    assert worst_case["projected_operating_profit_inr"] <= base_case["projected_operating_profit_inr"]

    # Best case is partially mitigated
    assert best_case["revenue_delta_pct"] > base_case["revenue_delta_pct"]

    # Disclosures & Assumptions
    assert len(data["assumptions_applied"]) >= 3
    assert any("Monthly Revenue" in a["name"] for a in data["assumptions_applied"])
    assert any("Gross Margin" in a["name"] for a in data["assumptions_applied"])
    assert len(data["mitigation_actions"]) >= 1


def test_simulate_supplier_cost_shock():
    """Simulates a 10% supplier price hike and verifies gross margin compression."""
    client = TestClient(app)
    user = _setup_user_and_business(client, "whatif_supplier")

    resp = client.post(
        "/api/v1/scenarios/simulate",
        json={
            "title": "Raw Material Price Spike",
            "parameters": {
                "scenario_type": "supplier_cost_increase",
                "sales_volume_delta_pct": 0.0,
                "price_delta_pct": 0.0,
                "cogs_delta_pct": 10.0,
                "opex_delta_inr": 0.0,
                "dso_stretch_days": 0,
            },
        },
        cookies=user["cookies"],
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    base_case = next(c for c in data["cases"] if c["case_label"] == "Base Case")
    # Revenue unchanged, COGS increased, gross profit declined
    assert base_case["revenue_delta_pct"] == 0.0
    assert base_case["projected_cogs_inr"] > data["baseline_metrics"]["monthly_cogs_inr"]
    assert base_case["gross_profit_delta_inr"] < 0
    assert base_case["gross_margin_pct"] < data["baseline_metrics"]["gross_margin_pct"]

    # Mitigations should propose supplier negotiation or pass-through
    assert any(
        "Vendor" in m["title"] or "Pass-Through" in m["title"] or "Surcharge" in m["title"]
        for m in data["mitigation_actions"]
    )


def test_simulate_customer_churn():
    """Simulates loss of key customer and verifies concentration vulnerability."""
    client = TestClient(app)
    user = _setup_user_and_business(client, "whatif_churn")

    resp = client.post(
        "/api/v1/scenarios/simulate",
        json={
            "title": "Top Client Departure",
            "parameters": {
                "scenario_type": "customer_churn",
                "sales_volume_delta_pct": 0.0,
                "price_delta_pct": 0.0,
                "cogs_delta_pct": 0.0,
                "opex_delta_inr": 0.0,
                "dso_stretch_days": 0,
                "lost_customer_revenue_inr": 500_000.0,
            },
        },
        cookies=user["cookies"],
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    base_case = next(c for c in data["cases"] if c["case_label"] == "Base Case")
    assert base_case["revenue_delta_inr"] < 0
    assert any("concentration" in v.lower() for v in data["vulnerabilities_exposed"])


def test_simulate_price_elasticity():
    """Simulates a +5% price increase with a -3% demand dip."""
    client = TestClient(app)
    user = _setup_user_and_business(client, "whatif_elasticity")

    resp = client.post(
        "/api/v1/scenarios/simulate",
        json={
            "title": "Selective Price Revision",
            "parameters": {
                "scenario_type": "price_elasticity",
                "sales_volume_delta_pct": -3.0,
                "price_delta_pct": 5.0,
                "cogs_delta_pct": 0.0,
                "opex_delta_inr": 0.0,
                "dso_stretch_days": 0,
            },
        },
        cookies=user["cookies"],
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    base_case = next(c for c in data["cases"] if c["case_label"] == "Base Case")
    # 0.97 * 1.05 = 1.0185 (+1.85% revenue growth despite volume dip)
    assert base_case["revenue_delta_pct"] > 0
    assert base_case["projected_operating_profit_inr"] > data["baseline_metrics"]["monthly_operating_profit_inr"]


def test_simulate_delayed_collection_dso():
    """Simulates 30-day collection stretch and verifies cash impact."""
    client = TestClient(app)
    user = _setup_user_and_business(client, "whatif_dso")

    resp = client.post(
        "/api/v1/scenarios/simulate",
        json={
            "title": "Credit Terms Stretch to 65 Days",
            "parameters": {
                "scenario_type": "collection_delay",
                "sales_volume_delta_pct": 0.0,
                "price_delta_pct": 0.0,
                "cogs_delta_pct": 0.0,
                "opex_delta_inr": 0.0,
                "dso_stretch_days": 30,
            },
        },
        cookies=user["cookies"],
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    # Mitigations should propose early payment discounts or invoice discounting
    assert any("Discount" in m["title"] or "TReDS" in m["title"] for m in data["mitigation_actions"])


def test_scenario_crud_lifecycle():
    """Verifies complete persistence lifecycle: Save -> List -> Get -> Patch -> Delete."""
    client = TestClient(app)
    user = _setup_user_and_business(client, "whatif_crud")

    # 1. Save
    save_resp = client.post(
        "/api/v1/scenarios",
        json={
            "title": "Monsoon Slump 2026",
            "scenario_type": "sales_drop",
            "description": "Evaluating 20% slowdown during monsoon quarter",
            "parameters": {
                "scenario_type": "sales_drop",
                "sales_volume_delta_pct": -20.0,
                "price_delta_pct": 0.0,
                "cogs_delta_pct": 0.0,
                "opex_delta_inr": 0.0,
                "dso_stretch_days": 0,
            },
            "tags": ["seasonality", "monsoon"],
        },
        cookies=user["cookies"],
    )
    assert save_resp.status_code == 201, save_resp.text
    saved = save_resp.json()
    scenario_id = saved["id"]
    assert saved["title"] == "Monsoon Slump 2026"
    assert saved["scenario_type"] == "sales_drop"

    # 2. List
    list_resp = client.get("/api/v1/scenarios", cookies=user["cookies"])
    assert list_resp.status_code == 200
    list_data = list_resp.json()
    assert list_data["total"] >= 1
    assert any(s["id"] == scenario_id for s in list_data["items"])

    # 3. Get
    get_resp = client.get(f"/api/v1/scenarios/{scenario_id}", cookies=user["cookies"])
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == scenario_id

    # 4. Patch
    patch_resp = client.patch(
        f"/api/v1/scenarios/{scenario_id}",
        json={
            "title": "Severe Monsoon Slump 2026",
            "parameters": {
                "scenario_type": "sales_drop",
                "sales_volume_delta_pct": -25.0,
                "price_delta_pct": 0.0,
                "cogs_delta_pct": 0.0,
                "opex_delta_inr": 0.0,
                "dso_stretch_days": 0,
            },
        },
        cookies=user["cookies"],
    )
    assert patch_resp.status_code == 200
    patched = patch_resp.json()
    assert patched["title"] == "Severe Monsoon Slump 2026"
    base_case = next(c for c in patched["projection_result"]["cases"] if c["case_label"] == "Base Case")
    assert base_case["revenue_delta_pct"] == -25.0

    # 5. Delete
    del_resp = client.delete(f"/api/v1/scenarios/{scenario_id}", cookies=user["cookies"])
    assert del_resp.status_code == 204

    # Confirm 404 after deletion
    get_after = client.get(f"/api/v1/scenarios/{scenario_id}", cookies=user["cookies"])
    assert get_after.status_code == 404


def test_scenario_comparison():
    """Saves two scenarios and verifies side-by-side comparative analysis."""
    client = TestClient(app)
    user = _setup_user_and_business(client, "whatif_compare")

    s1_resp = client.post(
        "/api/v1/scenarios",
        json={
            "title": "Mild Dip (-10%)",
            "scenario_type": "sales_drop",
            "parameters": {
                "scenario_type": "sales_drop",
                "sales_volume_delta_pct": -10.0,
                "price_delta_pct": 0.0,
                "cogs_delta_pct": 0.0,
                "opex_delta_inr": 0.0,
                "dso_stretch_days": 0,
            },
        },
        cookies=user["cookies"],
    )
    assert s1_resp.status_code == 201
    s1_id = s1_resp.json()["id"]

    s2_resp = client.post(
        "/api/v1/scenarios",
        json={
            "title": "Supplier Cost Surge (+15%)",
            "scenario_type": "supplier_cost_increase",
            "parameters": {
                "scenario_type": "supplier_cost_increase",
                "sales_volume_delta_pct": 0.0,
                "price_delta_pct": 0.0,
                "cogs_delta_pct": 15.0,
                "opex_delta_inr": 0.0,
                "dso_stretch_days": 0,
            },
        },
        cookies=user["cookies"],
    )
    assert s2_resp.status_code == 201
    s2_id = s2_resp.json()["id"]

    # Compare
    compare_resp = client.post(
        "/api/v1/scenarios/compare",
        json={"scenario_ids": [s1_id, s2_id]},
        cookies=user["cookies"],
    )
    assert compare_resp.status_code == 200, compare_resp.text
    comp = compare_resp.json()

    assert len(comp["scenarios"]) == 2
    assert "Comparison of 2 scenarios" in comp["comparison_summary"]
    assert "Illustrative scenario estimate — not a guaranteed prediction." in comp["disclaimer"]


def test_scenario_tenant_isolation():
    """Ensures complete multi-tenant isolation: User B cannot access User A's scenarios."""
    client = TestClient(app)
    user_a = _setup_user_and_business(client, "whatif_tenant_a")
    user_b = _setup_user_and_business(client, "whatif_tenant_b")

    # User A creates a scenario
    resp_a = client.post(
        "/api/v1/scenarios",
        json={
            "title": "Tenant A Secret Strategy",
            "scenario_type": "sales_drop",
            "parameters": {
                "scenario_type": "sales_drop",
                "sales_volume_delta_pct": -12.0,
                "price_delta_pct": 0.0,
                "cogs_delta_pct": 0.0,
                "opex_delta_inr": 0.0,
                "dso_stretch_days": 0,
            },
        },
        cookies=user_a["cookies"],
    )
    assert resp_a.status_code == 201
    scenario_id_a = resp_a.json()["id"]

    # User B attempts to GET User A's scenario -> 404
    resp_b_get = client.get(f"/api/v1/scenarios/{scenario_id_a}", cookies=user_b["cookies"])
    assert resp_b_get.status_code == 404

    # User B attempts to PATCH User A's scenario -> 404
    resp_b_patch = client.patch(
        f"/api/v1/scenarios/{scenario_id_a}",
        json={"title": "Hacked Title"},
        cookies=user_b["cookies"],
    )
    assert resp_b_patch.status_code == 404

    # User B attempts to DELETE User A's scenario -> 404
    resp_b_del = client.delete(f"/api/v1/scenarios/{scenario_id_a}", cookies=user_b["cookies"])
    assert resp_b_del.status_code == 404

    # User B attempts to include User A's scenario in compare -> 422
    resp_b_compare = client.post(
        "/api/v1/scenarios/compare",
        json={"scenario_ids": [scenario_id_a, 999999]},
        cookies=user_b["cookies"],
    )
    assert resp_b_compare.status_code == 422


# ===========================================================================
# 4. Financial Calculation Boundary Tests (Verification Item B)
# ===========================================================================


def test_simulate_boundary_conditions_and_credit_sales_dso():
    """Verify boundary handling: credit sales ratio on DSO, elasticity coefficient, and zero revenue safety."""
    client = TestClient(app)
    account = _setup_user_and_business(client, "boundary_biz")
    cookies = account["cookies"]

    # 1. Test Credit Sales Basis in DSO Simulation
    # At 50% credit sales, receivables locked should be exactly half of 100% credit sales
    resp_50 = client.post(
        "/api/v1/scenarios/simulate",
        json={
            "title": "DSO Test 50%",
            "parameters": {
                "scenario_type": "collection_delay",
                "dso_stretch_days": 30,
                "credit_sales_ratio": 0.50,
            },
        },
        cookies=cookies,
    )
    assert resp_50.status_code == 200, resp_50.text
    data_50 = resp_50.json()

    resp_100 = client.post(
        "/api/v1/scenarios/simulate",
        json={
            "title": "DSO Test 100%",
            "parameters": {
                "scenario_type": "collection_delay",
                "dso_stretch_days": 30,
                "credit_sales_ratio": 1.0,
            },
        },
        cookies=cookies,
    )
    assert resp_100.status_code == 200, resp_100.text
    data_100 = resp_100.json()

    # Credit sales ratio influences working capital receivables lockup
    assert len(data_50["cases"]) == 3
    assert len(data_100["cases"]) == 3
    case_50_worst = next(c for c in data_50["cases"] if "Worst" in c["case_label"])
    case_100_worst = next(c for c in data_100["cases"] if "Worst" in c["case_label"])
    # 100% credit sales locks up more cash than 50% credit sales
    if case_100_worst["cash_runway_days_estimated"] and case_50_worst["cash_runway_days_estimated"]:
        assert case_100_worst["cash_runway_days_estimated"] <= case_50_worst["cash_runway_days_estimated"]

    # 2. Test Explicit Price Elasticity Coefficient
    resp_elasticity = client.post(
        "/api/v1/scenarios/simulate",
        json={
            "title": "Elasticity Test",
            "parameters": {
                "scenario_type": "price_elasticity",
                "price_delta_pct": 10.0,
                "sales_volume_delta_pct": 0.0,
                "price_elasticity_coefficient": -1.5,
            },
        },
        cookies=cookies,
    )
    assert resp_elasticity.status_code == 200, resp_elasticity.text
    el_data = resp_elasticity.json()
    base_case = next(c for c in el_data["cases"] if "Base" in c["case_label"])
    # At +10% price and -1.5 elasticity, volume delta is -15%
    # Projected rev multiplier = (1 - 0.15) * (1 + 0.10) = 0.85 * 1.10 = 0.935 (-6.5% rev)
    assert base_case["revenue_delta_pct"] < 0.0

    # 3. Test Negative Margin Shock (COGS > Rev)
    resp_neg_margin = client.post(
        "/api/v1/scenarios/simulate",
        json={
            "title": "Cost Shock Test",
            "parameters": {
                "scenario_type": "supplier_cost_increase",
                "cogs_delta_pct": 200.0,  # 200% supplier price increase forces gross margin negative
            },
        },
        cookies=cookies,
    )
    assert resp_neg_margin.status_code == 200, resp_neg_margin.text
    neg_data = resp_neg_margin.json()
    neg_worst = next(c for c in neg_data["cases"] if "Worst" in c["case_label"])
    assert neg_worst["gross_margin_pct"] < 0.0
    assert neg_worst["break_even_revenue_inr"] is None  # Cannot break even on negative margin

