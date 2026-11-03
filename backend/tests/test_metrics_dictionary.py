"""Comprehensive tests for Business Metrics Dictionary & Calculation Explorer (Phase 6.21 Extension).

Verifies:
  - Canonical dictionary listing across all 11 core metrics
  - Category filtering (financial, sales, customer, operations, data_integrity)
  - Detailed metric definition retrieval (formulas, exclusion rules, limitations, benchmarks)
  - Dynamic Calculation Explorer with step-by-step arithmetic for active business
  - Accurate step-by-step deduplication and calculation of Average Order Value (AOV)
  - Ingestion revenue dual-basis reconciliation trace
  - Graceful missing-data guidance for businesses without sales records
  - Strict tenant isolation on calculation exploration
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
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
from app.models.sales import SalesTransaction, SalesUpload
from app.utils.database import Base, SessionLocal, engine

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
                "legal_name": f"{prefix} Precision Works Ltd",
                "trade_name": f"{prefix} Tech",
                "industry": "Manufacturing",
                "established_year": 2020,
                "employee_count": 15,
                "annual_revenue": 3_600_000.0,
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
        "business": biz_data.get("business", biz_data),
    }


def test_list_metrics_dictionary():
    """Verifies listing of all registered dictionary metrics and category filtering."""
    client = TestClient(app)

    # 1. Full List
    resp = client.get("/api/v1/metrics")
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["total"] >= 11
    keys = [m["key"] for m in data["metrics"]]
    assert "average_order_value" in keys
    assert "gross_margin" in keys
    assert "customer_concentration" in keys
    assert "repeat_customer_rate" in keys
    assert "digital_twin_health_score" in keys
    assert "valid_row_rate" in keys
    assert "ingestion_revenue_basis" in keys

    # 2. Filter by Category
    sales_resp = client.get("/api/v1/metrics?category=sales")
    assert sales_resp.status_code == 200
    sales_data = sales_resp.json()
    assert all(m["category"] == "sales" for m in sales_data["metrics"])
    assert any(m["key"] == "average_order_value" for m in sales_data["metrics"])


def test_get_single_metric_definition():
    """Verifies detailed definition retrieval for a specific metric."""
    client = TestClient(app)

    resp = client.get("/api/v1/metrics/average_order_value")
    assert resp.status_code == 200, resp.text
    metric = resp.json()

    assert metric["key"] == "average_order_value"
    assert "AOV" in metric["formula"]
    assert len(metric["exclusion_rules"]) >= 1
    assert "Duplicate" in metric["exclusion_rules"][0]
    assert "Manufacturing" in metric["industry_benchmarks"]
    assert len(metric["input_variables"]) >= 2

    # 404 for unknown metric
    not_found = client.get("/api/v1/metrics/non_existent_metric_xyz")
    assert not_found.status_code == 404


def test_explore_metric_aov_with_data():
    """Verifies step-by-step arithmetic exploration of Average Order Value with deduplication."""
    client = TestClient(app)
    user = _setup_user_and_business(client, "dict_aov")
    biz_id = user["business"]["id"]

    db = SessionLocal()
    try:
        upload = SalesUpload(
            business_id=biz_id,
            filename="orders.csv",
            file_format="csv",
            file_size_bytes=1024,
            row_count=5,
            valid_row_count=5,
            invalid_row_count=0,
            status="processed",
        )
        db.add(upload)
        db.flush()

        base_dt = datetime(2026, 2, 1, 10, 0, 0, tzinfo=timezone.utc)
        # 4 Valid transactions @ ₹5,000 each = ₹20,000
        for i in range(4):
            tx = SalesTransaction(
                upload_id=upload.id,
                business_id=biz_id,
                transaction_date=base_dt + timedelta(days=i),
                customer_name=f"Client_{i}",
                product_name="Tool Set",
                quantity=1,
                unit_price=5000.0,
                total_amount=5000.0,
                is_duplicate=False,
            )
            db.add(tx)

        # 1 Duplicate transaction @ ₹5,000
        dup_tx = SalesTransaction(
            upload_id=upload.id,
            business_id=biz_id,
            transaction_date=base_dt,
            customer_name="Client_0",
            product_name="Tool Set",
            quantity=1,
            unit_price=5000.0,
            total_amount=5000.0,
            is_duplicate=True,
        )
        db.add(dup_tx)
        db.commit()
    finally:
        db.close()

    resp = client.get("/api/v1/metrics/average_order_value/explore", cookies=user["cookies"])
    assert resp.status_code == 200, resp.text
    explorer = resp.json()

    assert explorer["has_live_data"] is True
    assert explorer["business_id"] == biz_id
    assert explorer["current_value"] == 5000.0  # ₹20,000 / 4 valid orders = ₹5,000
    assert "₹5,000.00" in explorer["formatted_current_value"]

    # Verify Step-by-Step Arithmetic Trace
    assert len(explorer["steps"]) == 3
    step1 = explorer["steps"][0]
    assert "Deduplicate" in step1["step_title"]
    assert step1["input_values"]["duplicate_revenue"] == 5000.0
    assert step1["input_values"]["gross_uploaded_revenue"] == 25000.0

    step2 = explorer["steps"][1]
    assert step2["input_values"]["valid_order_count"] == 4

    step3 = explorer["steps"][2]
    assert "AOV = Rev_net / N_orders" in step3["formula_snippet"]


def test_explore_metric_revenue_basis():
    """Verifies dual-basis reconciliation trace in calculation explorer."""
    client = TestClient(app)
    user = _setup_user_and_business(client, "dict_basis")
    biz_id = user["business"]["id"]

    db = SessionLocal()
    try:
        upload = SalesUpload(
            business_id=biz_id,
            filename="revenue_basis.csv",
            file_format="csv",
            file_size_bytes=1024,
            row_count=3,
            valid_row_count=3,
            invalid_row_count=0,
            status="processed",
        )
        db.add(upload)
        db.flush()

        base_dt = datetime(2026, 2, 1, 10, 0, 0, tzinfo=timezone.utc)
        # 2 Valid transactions (₹10k + ₹20k)
        t1 = SalesTransaction(
            upload_id=upload.id,
            business_id=biz_id,
            transaction_date=base_dt,
            customer_name="A",
            product_name="Part 1",
            quantity=1,
            unit_price=10000.0,
            total_amount=10000.0,
            is_duplicate=False,
        )
        t2 = SalesTransaction(
            upload_id=upload.id,
            business_id=biz_id,
            transaction_date=base_dt + timedelta(days=1),
            customer_name="B",
            product_name="Part 2",
            quantity=1,
            unit_price=20000.0,
            total_amount=20000.0,
            is_duplicate=False,
        )
        # 1 Duplicate transaction (₹10k)
        dup = SalesTransaction(
            upload_id=upload.id,
            business_id=biz_id,
            transaction_date=base_dt,
            customer_name="A",
            product_name="Part 1",
            quantity=1,
            unit_price=10000.0,
            total_amount=10000.0,
            is_duplicate=True,
        )
        db.add_all([t1, t2, dup])
        db.commit()
    finally:
        db.close()

    resp = client.get("/api/v1/metrics/ingestion_revenue_basis/explore", cookies=user["cookies"])
    assert resp.status_code == 200, resp.text
    explorer = resp.json()

    assert explorer["has_live_data"] is True
    assert explorer["current_value"] == 30000.0  # 40k gross - 10k dup = 30k net
    assert "₹30,000.00" in explorer["formatted_current_value"]
    assert len(explorer["steps"]) == 3
    assert explorer["steps"][0]["input_values"]["gross_revenue"] == 40000.0
    assert explorer["steps"][1]["input_values"]["duplicate_amount"] == 10000.0


def test_explore_metric_empty_sales():
    """Verifies graceful handling when a business has no sales transactions."""
    client = TestClient(app)
    user = _setup_user_and_business(client, "dict_empty")

    resp = client.get("/api/v1/metrics/average_order_value/explore", cookies=user["cookies"])
    assert resp.status_code == 200, resp.text
    explorer = resp.json()

    assert explorer["has_live_data"] is False
    assert explorer["current_value"] is None
    assert "Unavailable — no orders in the selected period" in explorer["formatted_current_value"]
    assert "Unavailable — no orders" in explorer["steps"][0]["output_value"]


def test_explore_metric_tenant_isolation():
    """Ensures complete tenant isolation: calculations are strictly scoped to the caller's business."""
    client = TestClient(app)
    user_a = _setup_user_and_business(client, "dict_tenant_a")
    user_b = _setup_user_and_business(client, "dict_tenant_b")

    resp_a = client.get("/api/v1/metrics/average_order_value/explore", cookies=user_a["cookies"])
    resp_b = client.get("/api/v1/metrics/average_order_value/explore", cookies=user_b["cookies"])

    assert resp_a.status_code == 200
    assert resp_b.status_code == 200
    assert resp_a.json()["business_id"] == user_a["business"]["id"]
    assert resp_b.json()["business_id"] == user_b["business"]["id"]
    assert resp_a.json()["business_id"] != resp_b.json()["business_id"]


# ===========================================================================
# 4. Metric Availability & Missing Ledger Transparency (Verification Item E)
# ===========================================================================


def test_explore_metric_gross_margin_unavailable_without_cogs():
    """Verify gross margin returns explicit Unavailable when COGS is not recorded (Audit Item E)."""
    client = TestClient(app)
    user = _setup_user_and_business(client, "dict_no_cogs")

    resp = client.get("/api/v1/metrics/gross_margin/explore", cookies=user["cookies"])
    assert resp.status_code == 200, resp.text
    explorer = resp.json()

    assert explorer["has_live_data"] is False
    assert explorer["current_value"] is None
    assert "Unavailable" in explorer["formatted_current_value"]
    assert "COGS" in explorer["formatted_current_value"]
    assert explorer["data_freshness"] == "Unavailable"
    assert "COGS Data Missing" in explorer["steps"][0]["output_value"]


def test_explore_metric_cash_runway_unavailable_without_cash_ledger():
    """Verify cash runway returns explicit Unavailable when bank/expense ledger is missing (Audit Item E)."""
    client = TestClient(app)
    user = _setup_user_and_business(client, "dict_no_runway")

    resp = client.get("/api/v1/metrics/cash_runway/explore", cookies=user["cookies"])
    assert resp.status_code == 200, resp.text
    explorer = resp.json()

    assert explorer["has_live_data"] is False
    assert explorer["current_value"] is None
    assert "Unavailable" in explorer["formatted_current_value"]
    assert "Cash & Burn Data Missing" in explorer["formatted_current_value"]
    assert explorer["data_freshness"] == "Unavailable"


def test_explore_metric_dso_unavailable_without_debtor_ledger():
    """Verify DSO returns explicit Unavailable when trade debtor ledger is absent (Audit Item E)."""
    client = TestClient(app)
    user = _setup_user_and_business(client, "dict_no_dso")

    resp = client.get("/api/v1/metrics/days_sales_outstanding/explore", cookies=user["cookies"])
    assert resp.status_code == 200, resp.text
    explorer = resp.json()

    assert explorer["has_live_data"] is False
    assert explorer["current_value"] is None
    assert "Unavailable" in explorer["formatted_current_value"]
    assert "Debtor Ledger Missing" in explorer["formatted_current_value"]
    assert explorer["data_freshness"] == "Unavailable"

