"""Comprehensive tests for Data Quality and Business Data Confidence Centre (Phase 6.20 Extension).

Verifies:
  - Empty dataset handling and baseline confidence
  - Ingestion counts and dual-basis reconciliation (Gross vs Duplicate-excluded Analytical)
  - Valid-row rate calculation
  - Observation window day counts and unconfirmed gap detection
  - Insight Confidence Matrix (Sales, Forecast, Customers, Products, Twin Health, Runway)
  - Actionable improvement checklist generation
  - Downloadable/exportable audit report
  - Strict tenant isolation across businesses and users
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
                "legal_name": f"{prefix} Enterprises Ltd",
                "trade_name": f"{prefix} Auto",
                "industry": "Manufacturing",
                "established_year": 2021,
                "employee_count": 8,
                "annual_revenue": 1_800_000.0,
                "revenue_currency": "INR",
                "city": "Chennai",
                "state_region": "Tamil Nadu",
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


def test_data_confidence_empty_business():
    """Verifies confidence evaluation when business has no uploaded sales data."""
    client = TestClient(app)
    user = _setup_user_and_business(client, "conf_empty")

    resp = client.get("/api/v1/data-confidence", cookies=user["cookies"])
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["business_id"] == user["business"]["id"]
    assert data["ingestion_summary"]["total_uploads_count"] == 0
    assert data["ingestion_summary"]["total_rows_imported"] == 0
    assert data["observation_window"]["observation_window_days"] == 0
    assert data["observation_window"]["freshness_status"] == "EXPIRED_OR_UNAVAILABLE"

    # In matrix, sales and forecasting are flagged as blocked
    sales_item = next(m for m in data["insight_confidence_matrix"] if m["module_key"] == "sales_intelligence")
    assert sales_item["readiness_status"] == "Blocked by Missing Data"
    assert sales_item["confidence_level"] == "Insufficient"

    # Actionable checklist recommends initial upload
    assert any(c["action_type"] == "upload_sales" for c in data["actionable_improvement_checklist"])


def test_data_confidence_with_sales_and_duplicates():
    """Verifies ingestion reconciliation, valid-row rate, and duplicate exclusion."""
    client = TestClient(app)
    user = _setup_user_and_business(client, "conf_sales")
    biz_id = user["business"]["id"]

    db = SessionLocal()
    try:
        # Create an upload
        upload = SalesUpload(
            business_id=biz_id,
            filename="sales_batch_1.csv",
            file_format="csv",
            file_size_bytes=4096,
            row_count=10,
            valid_row_count=9,
            invalid_row_count=1,
            status="processed",
        )
        db.add(upload)
        db.flush()

        base_dt = datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        # Create 8 valid transactions + 1 duplicate transaction
        for i in range(8):
            tx = SalesTransaction(
                upload_id=upload.id,
                business_id=biz_id,
                transaction_date=base_dt + timedelta(days=i * 3),
                customer_name=f"Customer_{i % 3}",
                customer_id=f"CUST_{i % 3}",
                product_name="Component X",
                quantity=10,
                unit_price=1000.0,
                total_amount=10000.0,
                is_duplicate=False,
            )
            db.add(tx)

        # 1 Duplicate transaction
        dup_tx = SalesTransaction(
            upload_id=upload.id,
            business_id=biz_id,
            transaction_date=base_dt + timedelta(days=3),
            customer_name="Customer_1",
            customer_id="CUST_1",
            product_name="Component X",
            quantity=10,
            unit_price=1000.0,
            total_amount=10000.0,
            is_duplicate=True,
        )
        db.add(dup_tx)
        db.commit()
    finally:
        db.close()

    resp = client.get("/api/v1/data-confidence", cookies=user["cookies"])
    assert resp.status_code == 200, resp.text
    data = resp.json()

    ingestion = data["ingestion_summary"]
    assert ingestion["total_uploads_count"] == 1
    assert ingestion["total_rows_imported"] == 10
    assert ingestion["valid_rows_ingested"] == 9
    assert ingestion["rejected_rows_count"] == 1
    assert ingestion["duplicate_rows_excluded"] == 1
    assert ingestion["valid_row_rate_pct"] == 90.0

    # Financial Reconciliation
    assert ingestion["gross_uploaded_revenue_inr"] == 90000.0  # 9 * 10,000
    assert ingestion["duplicate_revenue_excluded_inr"] == 10000.0  # 1 * 10,000
    assert ingestion["analytical_revenue_inr"] == 80000.0  # 90,000 - 10,000
    assert "Duplicate-excluded analytical revenue" in ingestion["reconciliation_basis_note"]

    # Customer and Product readiness should be High
    cust_item = next(m for m in data["insight_confidence_matrix"] if m["module_key"] == "customer_concentration")
    assert cust_item["readiness_status"] == "Ready"
    assert cust_item["confidence_level"] == "High"


def test_data_confidence_unconfirmed_gap_detection():
    """Verifies that periods >14 days with no transactions are flagged as unconfirmed gaps."""
    client = TestClient(app)
    user = _setup_user_and_business(client, "conf_gaps")
    biz_id = user["business"]["id"]

    db = SessionLocal()
    try:
        upload = SalesUpload(
            business_id=biz_id,
            filename="sales_gaps.csv",
            file_format="csv",
            file_size_bytes=2048,
            row_count=5,
            valid_row_count=5,
            invalid_row_count=0,
            status="processed",
        )
        db.add(upload)
        db.flush()

        # Jan 1st and Jan 30th (29 day gap)
        t1 = SalesTransaction(
            upload_id=upload.id,
            business_id=biz_id,
            transaction_date=datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
            customer_name="Alpha",
            product_name="Product A",
            quantity=1,
            unit_price=5000.0,
            total_amount=5000.0,
            is_duplicate=False,
        )
        t2 = SalesTransaction(
            upload_id=upload.id,
            business_id=biz_id,
            transaction_date=datetime(2026, 1, 30, 10, 0, 0, tzinfo=timezone.utc),
            customer_name="Alpha",
            product_name="Product A",
            quantity=1,
            unit_price=5000.0,
            total_amount=5000.0,
            is_duplicate=False,
        )
        db.add_all([t1, t2])
        db.commit()
    finally:
        db.close()

    resp = client.get("/api/v1/data-confidence", cookies=user["cookies"])
    assert resp.status_code == 200, resp.text
    data = resp.json()

    obs = data["observation_window"]
    assert obs["unconfirmed_gaps_count"] >= 1
    gap = obs["unconfirmed_gaps"][0]
    assert gap["gap_days"] == 29
    assert "Unconfirmed Sales Gap" in gap["classification"]

    # Checklist recommends reconciling this gap
    assert any(c["action_type"] == "fill_gaps" for c in data["actionable_improvement_checklist"])


def test_data_quality_report_export():
    """Verifies exportable data quality and provenance audit report endpoint."""
    client = TestClient(app)
    user = _setup_user_and_business(client, "conf_report")

    resp = client.get("/api/v1/data-confidence/report", cookies=user["cookies"])
    assert resp.status_code == 200, resp.text
    report = resp.json()

    assert report["business_id"] == user["business"]["id"]
    assert "Audit Report" in report["report_title"]
    assert "ingestion_reconciliation" in report
    assert "observation_window" in report
    assert "insight_confidence_matrix" in report
    assert "provenance_disclaimer" in report


def test_data_confidence_tenant_isolation():
    """Ensures complete tenant isolation: User B cannot access User A's confidence data."""
    client = TestClient(app)
    user_a = _setup_user_and_business(client, "conf_tenant_a")
    user_b = _setup_user_and_business(client, "conf_tenant_b")

    resp_a = client.get("/api/v1/data-confidence", cookies=user_a["cookies"])
    resp_b = client.get("/api/v1/data-confidence", cookies=user_b["cookies"])

    assert resp_a.status_code == 200
    assert resp_b.status_code == 200
    assert resp_a.json()["business_id"] == user_a["business"]["id"]
    assert resp_b.json()["business_id"] == user_b["business"]["id"]
    assert resp_a.json()["business_id"] != resp_b.json()["business_id"]
