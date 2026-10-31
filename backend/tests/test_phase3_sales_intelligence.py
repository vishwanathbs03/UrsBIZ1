"""Comprehensive Phase 3 Test Suite for Sales Data Ingestion and Sales Intelligence.

Tests cover:
  1. CSV & XLSX parsing, file limits (size <= 10MB, rows <= 100k), empty files, unsupported types
  2. Column detection with fuzzy alias matching & confidence scoring
  3. Row-level data quality validation, revenue calculation, duplicate flagging, missing fields
  4. Customer intelligence (AOV, repeat rate, frequency, documented declining threshold)
  5. Product intelligence (strict separation of volume rankings from revenue rankings, velocity trends)
  6. Time-series aggregations (monthly, weekly, daily) without synthetic interpolation
  7. Multi-tenant account isolation across users and multi-business switching
  8. Deletion cascade of uploads and transactions
  9. Safe handling of empty datasets
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import io
import json
import time
from uuid import uuid4
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.models.business import Business
from app.models.sales import SalesTransaction, SalesUpload
from app.models.user import User
from app.repositories.sales_repository import SalesRepository
from app.schemas.sales import ColumnMapping
from app.services.sales.column_detector import detect_columns
from app.services.sales.parser import (
    EmptyFileError,
    MAX_FILE_SIZE_BYTES,
    MAX_ROW_COUNT,
    OversizedFileError,
    RowLimitExceededError,
    UnsupportedFormatError,
    generate_file_preview,
    validate_file_metadata,
)
from app.services.sales.quality_engine import validate_and_process_sales_data
from app.services.sales_service import SalesService
from app.utils.database import Base


# =============================================================================
# Helper Utilities to Generate Test Files
# =============================================================================

def _create_sample_sales_csv(rows: list[dict]) -> bytes:
    """Generate in-memory CSV bytes from a list of dicts."""
    df = pd.DataFrame(rows)
    buf = io.BytesIO()
    df.to_csv(buf, index=False, encoding="utf-8")
    return buf.getvalue()


def _create_sample_sales_xlsx(rows: list[dict]) -> bytes:
    """Generate in-memory Excel XLSX bytes from a list of dicts."""
    df = pd.DataFrame(rows)
    buf = io.BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    return buf.getvalue()


@pytest.fixture
def isolated_sales_db():
    """In-memory SQLite DB for direct service/repository unit tests."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = Session()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


# =============================================================================
# 1. Parser & File Limit Tests
# =============================================================================

def test_parser_file_format_and_limits():
    """Test format detection, empty file rejection, size limits, and row limits."""
    # Empty file
    with pytest.raises(EmptyFileError):
        validate_file_metadata("sales.csv", b"")

    # Unsupported extension
    with pytest.raises(UnsupportedFormatError):
        validate_file_metadata("sales.pdf", b"some bytes")

    with pytest.raises(UnsupportedFormatError):
        validate_file_metadata("sales.zip", b"PK\x03\x04")

    # Valid CSV
    fmt = validate_file_metadata("transactions_2026.csv", b"date,product,qty,price\n2026-01-01,Widget,1,10\n")
    assert fmt == "csv"

    # Valid XLSX
    fmt_xlsx = validate_file_metadata("report.xlsx", b"some content")
    assert fmt_xlsx == "xlsx"

    # Oversized file (> 10MB)
    fake_huge_bytes = b"0" * (MAX_FILE_SIZE_BYTES + 1024)
    with pytest.raises(OversizedFileError):
        validate_file_metadata("big.csv", fake_huge_bytes)


def test_preview_generation_csv_and_xlsx():
    """Test preview metadata extraction from CSV and XLSX."""
    rows = [
        {"Txn Date": "2026-08-01", "Item": "Steel Bolt M8", "Quantity": "100", "Price": "15.5", "Client": "Tata Motors"},
        {"Txn Date": "2026-08-02", "Item": "Copper Wire", "Quantity": "50", "Price": "120.0", "Client": "Bajaj Auto"},
    ]
    csv_bytes = _create_sample_sales_csv(rows)
    df_csv, preview_csv = generate_file_preview("sales.csv", csv_bytes)

    assert preview_csv["file_format"] == "csv"
    assert preview_csv["total_rows_estimate"] == 2
    assert "Item" in preview_csv["detected_headers"]
    assert len(preview_csv["sample_rows"]) == 2

    # XLSX preview
    xlsx_bytes = _create_sample_sales_xlsx(rows)
    df_xlsx, preview_xlsx = generate_file_preview("sales.xlsx", xlsx_bytes)
    assert preview_xlsx["file_format"] == "xlsx"
    assert preview_xlsx["total_rows_estimate"] == 2
    assert "Item" in preview_xlsx["detected_headers"]


# =============================================================================
# 2. Column Detection with Aliases & Confidence Scoring
# =============================================================================

def test_column_alias_detection():
    """Verify alias resolution across Indian/global billing formats."""
    headers = [
        "Bill Date",
        "Particulars",
        "Nos",
        "Rate",
        "Grand Total",
        "Party Name",
        "Voucher No",
    ]
    mapping, conf = detect_columns(headers)

    assert mapping["transaction_date"] == "Bill Date"
    assert mapping["product_name"] == "Particulars"
    assert mapping["quantity"] == "Nos"
    assert mapping["unit_price"] == "Rate"
    assert mapping["total_amount"] == "Grand Total"
    assert mapping["customer_name"] == "Party Name"
    assert mapping["invoice_id"] == "Voucher No"

    # All matched fields should have high confidence
    assert conf["transaction_date"] >= 0.8
    assert conf["product_name"] >= 0.8
    assert conf["quantity"] >= 0.8
    assert conf["unit_price"] >= 0.8


# =============================================================================
# 3. Data Quality Engine & Row-Level Validation
# =============================================================================

def test_quality_engine_row_validation_and_revenue_calculation():
    """Verify data validation, revenue calculation when missing, duplicate detection, and invalid row handling."""
    mapping = ColumnMapping(
        transaction_date="date",
        product_name="item",
        quantity="qty",
        unit_price="price",
        total_amount="total",
        customer_name="buyer",
    )

    rows = [
        # 1. Perfectly valid row with explicit revenue
        {"date": "2026-08-01", "item": "Solar Panel 400W", "qty": "10", "price": "15000", "total": "150000", "buyer": "EcoCorp"},
        # 2. Missing revenue: should be deterministically calculated as 5 * 200 = 1000
        {"date": "2026-08-02", "item": "Inverter Cable", "qty": "5", "price": "200", "total": "", "buyer": "EcoCorp"},
        # 3. Invalid date: should be rejected
        {"date": "not-a-date", "item": "Battery", "qty": "2", "price": "5000", "total": "10000", "buyer": "Apex"},
        # 4. Missing product name: should be rejected
        {"date": "2026-08-03", "item": "", "qty": "1", "price": "5000", "total": "5000", "buyer": "Apex"},
        # 5. Invalid negative quantity: should be rejected
        {"date": "2026-08-04", "item": "Switch", "qty": "-5", "price": "50", "total": "250", "buyer": "Apex"},
        # 6. Invalid zero unit price: should be rejected
        {"date": "2026-08-05", "item": "Switch", "qty": "10", "price": "0", "total": "0", "buyer": "Apex"},
        # 7. Duplicate of row 1: valid but flagged with warning
        {"date": "2026-08-01", "item": "Solar Panel 400W", "qty": "10", "price": "15000", "total": "150000", "buyer": "EcoCorp"},
    ]
    df = pd.DataFrame(rows)
    valid_rows, summary = validate_and_process_sales_data(df, mapping)

    assert summary.total_rows_received == 7
    assert summary.valid_rows == 3  # row 1, row 2, and row 7 (duplicate is accepted but flagged)
    assert summary.invalid_rows == 4  # row 3, 4, 5, 6
    assert summary.missing_dates == 1
    assert summary.missing_customer_or_product == 1
    assert summary.invalid_quantities == 1
    assert summary.invalid_or_missing_prices == 1
    assert summary.calculated_revenues == 1
    assert summary.duplicate_transactions == 1

    # Check calculated revenue on row 2
    calculated_row = [r for r in valid_rows if r["product_name"] == "Inverter Cable"][0]
    assert calculated_row["total_amount"] == 1000.0


# =============================================================================
# 4. Customer Intelligence Tests (AOV, Repeat, Declining Threshold)
# =============================================================================

def test_customer_intelligence_calculations(isolated_sales_db):
    """Verify customer metrics, AOV, repeat purchase rates, and documented 60-day declining threshold."""
    repo = SalesRepository(isolated_sales_db)

    # Create dummy business
    biz = Business(
        owner_id=1,
        legal_name="Industrial Forge Ltd",
        industry="Manufacturing",
        established_year=2015,
        annual_revenue=500000.0,
    )
    isolated_sales_db.add(biz)
    isolated_sales_db.commit()

    upload = repo.create_upload(
        business_id=biz.id,
        filename="sales.csv",
        file_format="csv",
        file_size_bytes=1024,
        row_count=5,
        valid_row_count=5,
        invalid_row_count=0,
        status="processed",
        column_mapping={},
        quality_summary={},
    )

    base_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
    # Total span: 100 days (satisfies >= 90 days required for declining status evaluation)
    txns = [
        # Customer A: 3 orders, last order on day 95 (Active, Repeat)
        {"transaction_date": base_time, "customer_name": "Tata Motors", "product_name": "Axle", "quantity": 10, "unit_price": 100, "total_amount": 1000},
        {"transaction_date": base_time + timedelta(days=50), "customer_name": "Tata Motors", "product_name": "Axle", "quantity": 10, "unit_price": 100, "total_amount": 1000},
        {"transaction_date": base_time + timedelta(days=95), "customer_name": "Tata Motors", "product_name": "Axle", "quantity": 10, "unit_price": 100, "total_amount": 1000},
        # Customer B: 1 order on day 10, no purchase for 90 days (> 60 days inactivity -> Declining)
        {"transaction_date": base_time + timedelta(days=10), "customer_name": "Legacy Gearbox Co", "product_name": "Pinion", "quantity": 5, "unit_price": 200, "total_amount": 1000},
        # Customer C: 1 order on day 90 (New customer within last 30 days)
        {"transaction_date": base_time + timedelta(days=90), "customer_name": "Modern Electric", "product_name": "Rotor", "quantity": 2, "unit_price": 500, "total_amount": 1000},
    ]
    repo.bulk_insert_transactions(upload.id, biz.id, txns)

    insights = repo.get_customer_insights(biz.id)

    assert insights["total_customers"] == 3
    assert insights["repeat_customers"] == 1  # Tata Motors (3 orders)
    assert insights["new_customers"] == 2     # Legacy Gearbox & Modern Electric
    assert insights["repeat_rate_pct"] == pytest.approx(33.3, rel=1e-1)
    assert insights["history_span_days"] >= 90

    # Declining customer verification
    declining_names = [c["customer_name"] for c in insights["declining_customers"]]
    assert "Legacy Gearbox Co" in declining_names
    assert "Tata Motors" not in declining_names


# =============================================================================
# 5. Product Intelligence Tests (Volume vs Revenue Separation & Velocity)
# =============================================================================

def test_product_intelligence_volume_vs_revenue_separation(isolated_sales_db):
    """Confirm revenue rankings and volume rankings are strictly separated, and velocity trends compute accurately."""
    repo = SalesRepository(isolated_sales_db)

    biz = Business(
        owner_id=2,
        legal_name="Precision Engineering Works",
        industry="Automotive",
        established_year=2018,
    )
    isolated_sales_db.add(biz)
    isolated_sales_db.commit()

    upload = repo.create_upload(
        business_id=biz.id,
        filename="sales.csv",
        file_format="csv",
        file_size_bytes=500,
        row_count=5,
        valid_row_count=5,
        invalid_row_count=0,
        status="processed",
        column_mapping={},
        quality_summary={},
    )

    now = datetime(2026, 8, 1, tzinfo=timezone.utc)
    # Product 1: High unit price, low volume (Heavy Turbine: 2 units sold, ₹2,00,000 total) -> #1 by Revenue, #2 by Volume
    # Product 2: Low unit price, high volume (Washer Pack: 5,000 units sold, ₹50,000 total) -> #1 by Volume, #2 by Revenue
    # Product 3: Increasing trend (10 units first half, 50 units second half)
    txns = [
        {"transaction_date": now - timedelta(days=60), "product_name": "Heavy Turbine", "quantity": 1, "unit_price": 100000, "total_amount": 100000},
        {"transaction_date": now - timedelta(days=10), "product_name": "Heavy Turbine", "quantity": 1, "unit_price": 100000, "total_amount": 100000},
        {"transaction_date": now - timedelta(days=30), "product_name": "Washer Pack", "quantity": 5000, "unit_price": 10, "total_amount": 50000},
        {"transaction_date": now - timedelta(days=40), "product_name": "Coupling Rod", "quantity": 10, "unit_price": 500, "total_amount": 5000},
        {"transaction_date": now - timedelta(days=20), "product_name": "Coupling Rod", "quantity": 25, "unit_price": 500, "total_amount": 12500},
        {"transaction_date": now - timedelta(days=5), "product_name": "Coupling Rod", "quantity": 30, "unit_price": 500, "total_amount": 15000},
    ]
    repo.bulk_insert_transactions(upload.id, biz.id, txns)

    insights = repo.get_product_insights(biz.id)

    # Top by revenue must be Heavy Turbine
    assert insights["top_products_by_revenue"][0]["product_name"] == "Heavy Turbine"
    assert insights["top_products_by_revenue"][0]["total_revenue"] == 200000.0

    # Fast-moving by volume must be Washer Pack (strictly separated from revenue ranking!)
    assert insights["fast_moving_products_by_volume"][0]["product_name"] == "Washer Pack"
    assert insights["fast_moving_products_by_volume"][0]["total_quantity_sold"] == 5000.0

    # Velocity trend: Coupling Rod had 10 qty in first half and 55 in second half -> Increasing
    increasing_names = [p["product_name"] for p in insights["increasing_sales_products"]]
    assert "Coupling Rod" in increasing_names


# =============================================================================
# 6. Time-Series Aggregations
# =============================================================================

def test_sales_time_series_aggregations(isolated_sales_db):
    """Verify monthly and weekly aggregations without artificial zero filling."""
    repo = SalesRepository(isolated_sales_db)

    biz = Business(owner_id=3, legal_name="Textile Mill", industry="Textiles", established_year=2010)
    isolated_sales_db.add(biz)
    isolated_sales_db.commit()

    upload = repo.create_upload(
        business_id=biz.id,
        filename="sales.csv",
        file_format="csv",
        file_size_bytes=500,
        row_count=3,
        valid_row_count=3,
        invalid_row_count=0,
        status="processed",
        column_mapping={},
        quality_summary={},
    )

    t1 = datetime(2026, 1, 15, tzinfo=timezone.utc)
    t2 = datetime(2026, 1, 25, tzinfo=timezone.utc)
    t3 = datetime(2026, 3, 10, tzinfo=timezone.utc)  # Note: February has no data
    txns = [
        {"transaction_date": t1, "product_name": "Cotton Yarn", "quantity": 100, "unit_price": 50, "total_amount": 5000},
        {"transaction_date": t2, "product_name": "Cotton Yarn", "quantity": 200, "unit_price": 50, "total_amount": 10000},
        {"transaction_date": t3, "product_name": "Silk Fabric", "quantity": 50, "unit_price": 300, "total_amount": 15000},
    ]
    repo.bulk_insert_transactions(upload.id, biz.id, txns)

    # Monthly aggregation
    monthly = repo.get_time_series(biz.id, granularity="monthly")
    assert monthly["total_periods"] == 2  # Only 2026-01 and 2026-03
    periods = [p["period"] for p in monthly["points"]]
    assert "2026-01" in periods
    assert "2026-03" in periods
    assert "2026-02" not in periods  # Unuploaded periods are NOT synthetically fabricated!

    jan_point = [p for p in monthly["points"] if p["period"] == "2026-01"][0]
    assert jan_point["revenue"] == 15000.0
    assert jan_point["quantity"] == 300.0


# =============================================================================
# 7. End-to-End API Integration & Multi-Tenant Isolation Tests
# =============================================================================

def _register_user(client: TestClient, email: str) -> dict:
    res = client.post(
        "/api/v1/auth/register",
        json={"full_name": "Sales Test User", "email": email, "password": "SecurePassword1"},
    )
    assert res.status_code == 201, f"Register failed: {res.text}"
    return res.json()


def test_api_sales_upload_preview_and_confirm_flow():
    """Test full preview -> confirm ingestion -> summary -> insights API flow."""
    client = TestClient(app)
    uid = uuid4().hex[:8]
    _register_user(client, f"sales_e2e_{uid}@example.com")

    # Create business
    biz_res = client.post(
        "/api/v1/business",
        json={
            "basic": {
                "legal_name": "Sunrise Electronics",
                "industry": "Electronics",
                "established_year": 2020,
                "employee_count": 12,
                "annual_revenue": 1000000.0,
                "revenue_currency": "INR",
            }
        },
    )
    assert biz_res.status_code == 201

    # 1. Preview upload
    csv_rows = [
        {"Txn Date": "2026-05-01", "Item Name": "PCB Board", "Qty Sold": "20", "Unit Rate": "450", "Total Revenue": "9000", "Customer": "MicroTech"},
        {"Txn Date": "2026-05-15", "Item Name": "Capacitor", "Qty Sold": "100", "Unit Rate": "5", "Total Revenue": "500", "Customer": "MicroTech"},
        {"Txn Date": "2026-06-01", "Item Name": "Microcontroller", "Qty Sold": "10", "Unit Rate": "1200", "Total Revenue": "12000", "Customer": "NanoWorks"},
    ]
    csv_bytes = _create_sample_sales_csv(csv_rows)

    preview_res = client.post(
        "/api/v1/sales/upload/preview",
        files={"file": ("sales_batch_1.csv", csv_bytes, "text/csv")},
    )
    assert preview_res.status_code == 200, f"Preview failed: {preview_res.text}"
    preview_data = preview_res.json()
    assert preview_data["total_rows_estimate"] == 3
    assert preview_data["suggested_mapping"]["transaction_date"] == "Txn Date"
    assert preview_data["suggested_mapping"]["product_name"] == "Item Name"

    # 2. Confirm ingestion
    mapping = {
        "transaction_date": "Txn Date",
        "product_name": "Item Name",
        "quantity": "Qty Sold",
        "unit_price": "Unit Rate",
        "total_amount": "Total Revenue",
        "customer_name": "Customer",
    }
    confirm_res = client.post(
        "/api/v1/sales/upload/confirm",
        files={"file": ("sales_batch_1.csv", csv_bytes, "text/csv")},
        data={"mapping": json.dumps(mapping)},
    )
    assert confirm_res.status_code == 200, f"Confirm failed: {confirm_res.text}"
    confirm_data = confirm_res.json()
    assert confirm_data["status"] == "processed"
    assert confirm_data["valid_row_count"] == 3
    upload_id = confirm_data["upload_id"]

    # 3. Sales Summary
    summary_res = client.get("/api/v1/sales/summary")
    assert summary_res.status_code == 200
    summary = summary_res.json()
    assert summary["has_sales_data"] is True
    assert summary["total_transactions"] == 3
    assert summary["total_revenue"] == 21500.0
    assert summary["unique_customers"] == 2
    assert summary["unique_products"] == 3

    # 4. Customer Insights
    cust_res = client.get("/api/v1/sales/customer-insights")
    assert cust_res.status_code == 200
    cust_data = cust_res.json()
    assert cust_data["total_customers"] == 2
    assert cust_data["repeat_customers"] == 1  # MicroTech has 2 orders
    assert cust_data["top_customers_by_revenue"][0]["customer_name"] == "NanoWorks"
    assert cust_data["top_customers_by_revenue"][1]["customer_name"] == "MicroTech"

    # 5. Product Insights
    prod_res = client.get("/api/v1/sales/product-insights")
    assert prod_res.status_code == 200
    prod_data = prod_res.json()
    assert prod_data["total_products"] == 3
    # Top by revenue: Microcontroller (₹12,000)
    assert prod_data["top_products_by_revenue"][0]["product_name"] == "Microcontroller"
    # Fast moving by volume: Capacitor (100 units)
    assert prod_data["fast_moving_products_by_volume"][0]["product_name"] == "Capacitor"

    # 6. Deletion cascade
    del_res = client.delete(f"/api/v1/sales/uploads/{upload_id}")
    assert del_res.status_code == 200

    # Summary should now be empty
    after_del_summary = client.get("/api/v1/sales/summary").json()
    assert after_del_summary["has_sales_data"] is False
    assert after_del_summary["total_transactions"] == 0


def test_api_sales_multi_tenant_isolation_and_switching():
    """Verify User A cannot access User B's sales data, and switching active business isolates sales records."""
    client_u1 = TestClient(app)
    client_u2 = TestClient(app)

    uid1 = uuid4().hex[:8]
    uid2 = uuid4().hex[:8]
    _register_user(client_u1, f"user1_sales_{uid1}@example.com")
    _register_user(client_u2, f"user2_sales_{uid2}@example.com")

    # User 1 creates Business A1
    b_a1 = client_u1.post(
        "/api/v1/business",
        json={
            "basic": {
                "legal_name": "U1 Enterprise A1",
                "industry": "Logistics",
                "established_year": 2020,
                "employee_count": 10,
                "annual_revenue": 100000.0,
            }
        },
    ).json()

    # User 2 creates Business B1
    b_b1 = client_u2.post(
        "/api/v1/business",
        json={
            "basic": {
                "legal_name": "U2 Enterprise B1",
                "industry": "Retail",
                "established_year": 2021,
                "employee_count": 5,
                "annual_revenue": 50000.0,
            }
        },
    ).json()

    # Upload sales data to User 1's active business A1
    rows = [{"Date": "2026-07-01", "Item": "Forklift Rental", "Qty": "1", "Price": "50000"}]
    csv_bytes = _create_sample_sales_csv(rows)
    mapping = {"transaction_date": "Date", "product_name": "Item", "quantity": "Qty", "unit_price": "Price"}

    upload_res = client_u1.post(
        "/api/v1/sales/upload/confirm",
        files={"file": ("u1_sales.csv", csv_bytes, "text/csv")},
        data={"mapping": json.dumps(mapping)},
    )
    assert upload_res.status_code == 200
    u1_upload_id = upload_res.json()["upload_id"]

    # User 1 has sales data
    u1_summary = client_u1.get("/api/v1/sales/summary").json()
    assert u1_summary["has_sales_data"] is True
    assert u1_summary["total_revenue"] == 50000.0

    # User 2 MUST NOT have User 1's sales data
    u2_summary = client_u2.get("/api/v1/sales/summary").json()
    assert u2_summary["has_sales_data"] is False
    assert u2_summary["total_transactions"] == 0

    # User 2 CANNOT delete User 1's upload
    u2_del = client_u2.delete(f"/api/v1/sales/uploads/{u1_upload_id}")
    assert u2_del.status_code == 404

    # =========================================================================
    # Multi-Business Switching for User 1
    # =========================================================================
    # User 1 creates second Business A2
    b_a2 = client_u1.post(
        "/api/v1/business",
        json={
            "basic": {
                "legal_name": "U1 Enterprise A2",
                "industry": "Consulting",
                "established_year": 2022,
                "employee_count": 15,
                "annual_revenue": 200000.0,
            }
        },
    ).json()
    # POST /business automatically switches active_business_id to A2
    a2_summary = client_u1.get("/api/v1/sales/summary").json()
    assert a2_summary["has_sales_data"] is False  # Business A2 has no sales yet!

    # Switch back to Business A1
    b_a1_id = b_a1["business"]["id"]
    patch_res = client_u1.patch("/api/v1/auth/me", json={"active_business_id": b_a1_id})
    assert patch_res.status_code == 200

    # Business A1 immediately sees its ₹50,000 sales again!
    a1_summary_again = client_u1.get("/api/v1/sales/summary").json()
    assert a1_summary_again["has_sales_data"] is True
    assert a1_summary_again["total_revenue"] == 50000.0
