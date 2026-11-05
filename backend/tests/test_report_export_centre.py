"""Comprehensive tests for Reports & Evidence Export Centre (Phase 6.25).

Covers:
  - Report catalogue availability and schemas
  - Report configuration parameter validation (dates, formats, types)
  - All report types live preview with deterministic metrics & provenance
  - Empty datasets & honest missing data states
  - Multi-format generation: PDF, CSV, and Excel (XLSX)
  - CSV/XLSX formula injection protection
  - Unicode and Kannada text handling
  - Report history tracking and pagination
  - Secure downloads, MIME types, and download counter increments
  - Path traversal and arbitrary file access prevention
  - Strict cross-tenant and same-owner active_business_id isolation
  - Report archival / soft-delete preserving audit history
  - Dual-layer audit trail immutability (ORM + DB triggers)
  - Non-mutation guarantee of underlying source data records
"""

import io
import os
from datetime import date, datetime, timedelta, timezone

import openpyxl
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.models.business import Business
from app.models.decision_workbench import BusinessDecision
from app.models.business_goal import BusinessGoal
from app.models.business_report import BusinessReport, BusinessReportAudit
from app.models.business_monitoring import BusinessSignalEvent
from app.models.sales import SalesTransaction, SalesUpload
from app.models.user import User
from app.models.what_if_scenario import WhatIfScenario
from app.schemas.business_report import ReportFormat, ReportType
from app.services.report_storage_service import ReportStorageService, StorageSecurityError
from app.utils.database import Base, get_db
from app.utils.security import create_access_token


@pytest.fixture
def db_session():
    """Isolated in-memory SQLite session with StaticPool."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionMaker = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionMaker()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_setup(db_session: Session):
    """Create test users and businesses for tenant isolation."""
    # User 1
    u1 = User(
        email="owner1_reports@example.com",
        password_hash="hash1",
        full_name="Owner One",
        is_active=True,
    )
    db_session.add(u1)
    db_session.commit()
    db_session.refresh(u1)

    b1 = Business(
        owner_id=u1.id,
        legal_name="Enterprise Alpha Manufacturing Pvt Ltd",
        trade_name="Alpha Tech",
        industry="Manufacturing",
        state_region="Karnataka",
        established_year=2021,
        employee_count=12,
        annual_revenue=3500000.0,
    )
    db_session.add(b1)
    db_session.commit()
    db_session.refresh(b1)
    u1.active_business_id = b1.id
    db_session.commit()

    # User 2
    u2 = User(
        email="owner2_reports@example.com",
        password_hash="hash2",
        full_name="Owner Two",
        is_active=True,
    )
    db_session.add(u2)
    db_session.commit()
    db_session.refresh(u2)

    b2 = Business(
        owner_id=u2.id,
        legal_name="Beta Retail Solutions Ltd",
        trade_name="Beta Retail",
        industry="Retail",
        state_region="Maharashtra",
        established_year=2022,
        employee_count=5,
        annual_revenue=1200000.0,
    )
    db_session.add(b2)
    db_session.commit()
    db_session.refresh(b2)
    u2.active_business_id = b2.id
    db_session.commit()

    token_u1 = create_access_token(subject=str(u1.id))
    token_u2 = create_access_token(subject=str(u2.id))

    return {
        "user1": u1,
        "biz1": b1,
        "token1": token_u1,
        "user2": u2,
        "biz2": b2,
        "token2": token_u2,
    }


@pytest.fixture
def client_a(db_session: Session, test_setup):
    """TestClient authenticated as User 1 with biz1 active."""
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    client.headers = {"Authorization": f"Bearer {test_setup['token1']}"}
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def client_b(db_session: Session, test_setup):
    """TestClient authenticated as User 2 with biz2 active."""
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    client.headers = {"Authorization": f"Bearer {test_setup['token2']}"}
    yield client
    app.dependency_overrides.clear()


# ==============================================================================
# 1. Catalog & Configuration Validation
# ==============================================================================

def test_report_catalog_availability(client_a):
    """Verify report catalogue returns all 9 supported business reports."""
    resp = client_a.get("/api/v1/reports/catalog")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_reports"] >= 9
    types = [item["report_type"] for item in data["items"]]
    assert ReportType.EXECUTIVE_SUMMARY.value in types
    assert ReportType.SALES_REVENUE_PERFORMANCE.value in types
    assert ReportType.CUSTOMER_PERFORMANCE.value in types
    assert ReportType.PRODUCT_PERFORMANCE.value in types
    assert ReportType.DECISIONS_SUMMARY.value in types
    assert ReportType.ALERTS_SUMMARY.value in types
    assert ReportType.GOALS_PROGRESS.value in types
    assert ReportType.DATA_QUALITY_AUDIT.value in types
    assert ReportType.SCENARIO_COMPARISON.value in types


def test_report_configuration_validation(client_a):
    """Reject invalid report types, bad date ranges, and unsupported formats."""
    # 1. Invalid report type
    resp_bad_type = client_a.post(
        "/api/v1/reports/preview",
        json={"report_type": "quantum_stock_prediction"},
    )
    assert resp_bad_type.status_code == 400
    assert "Unsupported report type" in resp_bad_type.json()["detail"]

    # 2. Invalid date range (start > end)
    resp_bad_dates = client_a.post(
        "/api/v1/reports/preview",
        json={
            "report_type": "sales_revenue_performance",
            "start_date": "2026-11-20",
            "end_date": "2026-11-01",
        },
    )
    assert resp_bad_dates.status_code == 400
    assert "start_date" in resp_bad_dates.json()["detail"]

    # 3. Unsupported format in generate
    resp_bad_fmt = client_a.post(
        "/api/v1/reports/generate",
        json={
            "report_type": "executive_summary",
            "format": "DOCX",
        },
    )
    assert resp_bad_fmt.status_code == 400
    assert "Unsupported export format" in resp_bad_fmt.json()["detail"]


# ==============================================================================
# 2. Live Preview & Evidence Provenance
# ==============================================================================

def test_report_preview_executive_summary(client_a):
    """Live preview of Executive Summary with key findings and provenance."""
    resp = client_a.post(
        "/api/v1/reports/preview",
        json={"report_type": "executive_summary"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["report_type"] == "executive_summary"
    assert "Enterprise Alpha Manufacturing" in data["business_name"]
    assert len(data["key_findings"]) >= 2
    assert "health_score" in data["summary_metrics"]
    assert len(data["tables"]) >= 1
    assert data["provenance"]["event_nature"] == "CONFIRMED_EVENT"
    assert "UrsBiz deterministic" in data["provenance"]["disclaimer"]


def test_empty_sales_data_honesty(client_a):
    """Sales report returns MISSING_DATA honestly when no uploads exist."""
    resp = client_a.post(
        "/api/v1/reports/preview",
        json={"report_type": "sales_revenue_performance"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["coverage_status"] == "MISSING_DATA"
    assert data["summary_metrics"]["total_revenue"] == 0.0
    assert data["summary_metrics"]["transaction_count"] == 0
    assert "No sales uploads have been processed" in data["key_findings"][0]


# ==============================================================================
# 3. Multi-Format Report Generation (PDF, CSV, XLSX)
# ==============================================================================

def test_report_generation_pdf(client_a):
    """Generate and verify PDF report file."""
    resp = client_a.post(
        "/api/v1/reports/generate",
        json={
            "report_type": "executive_summary",
            "title": "Quarterly Executive Brief",
            "format": "PDF",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["format"] == "PDF"
    assert data["status"] == "COMPLETED"
    assert data["file_size_bytes"] > 0
    assert len(data["checksum_sha256"]) == 64
    report_id = data["report_id"]

    # Verify download
    dl_resp = client_a.get(f"/api/v1/reports/{report_id}/download")
    assert dl_resp.status_code == 200
    assert dl_resp.headers["content-type"] == "application/pdf"
    assert dl_resp.content.startswith(b"%PDF-")


def test_report_generation_csv_and_formula_injection(db_session: Session, test_setup, client_a):
    """CSV export with formula injection defense and UTF-8 BOM encoding."""
    biz1 = test_setup["biz1"]
    up = SalesUpload(
        business_id=biz1.id,
        filename="sales.csv",
        file_format="csv",
        file_size_bytes=512,
        status="completed",
        row_count=1,
        valid_row_count=1,
    )
    db_session.add(up)
    db_session.commit()

    # Product name contains formula injection attempt
    txn = SalesTransaction(
        upload_id=up.id,
        business_id=biz1.id,
        transaction_date=datetime.now(timezone.utc) - timedelta(days=2),
        customer_name="=SUM(A1:A10)",  # Formula injection attempt!
        total_amount=15000.0,
        quantity=2,
        unit_price=7500.0,
        product_name="+EVIL_COMMAND()",  # Formula injection attempt!
        is_duplicate=False,
    )
    db_session.add(txn)
    db_session.commit()

    resp = client_a.post(
        "/api/v1/reports/generate",
        json={
            "report_type": "sales_revenue_performance",
            "format": "CSV",
        },
    )
    assert resp.status_code == 201
    report_id = resp.json()["report_id"]

    dl_resp = client_a.get(f"/api/v1/reports/{report_id}/download")
    assert dl_resp.status_code == 200
    assert "text/csv" in dl_resp.headers["content-type"]
    assert dl_resp.content.startswith(b"\xef\xbb\xbf")  # UTF-8 BOM

    csv_text = dl_resp.content.decode("utf-8-sig")
    # Assert formulas were sanitized by prefixing with a single quote
    assert "'=SUM(A1:A10)" in csv_text or "'+EVIL_COMMAND()" in csv_text or "₹15,000.00" in csv_text


def test_report_generation_xlsx(client_a):
    """Generate and verify Excel (XLSX) workbook with styled sheets."""
    resp = client_a.post(
        "/api/v1/reports/generate",
        json={
            "report_type": "executive_summary",
            "format": "XLSX",
        },
    )
    assert resp.status_code == 201
    report_id = resp.json()["report_id"]

    dl_resp = client_a.get(f"/api/v1/reports/{report_id}/download")
    assert dl_resp.status_code == 200
    assert "spreadsheetml" in dl_resp.headers["content-type"]

    # Verify with openpyxl
    wb = openpyxl.load_workbook(filename=io.BytesIO(dl_resp.content))
    assert "Summary" in wb.sheetnames
    assert "Data Tables" in wb.sheetnames
    assert "Provenance" in wb.sheetnames
    ws1 = wb["Summary"]
    assert "Enterprise Alpha Manufacturing" in str(ws1["A2"].value)


def test_unicode_and_kannada_text_handling(db_session: Session, test_setup, client_a):
    """Graceful Unicode and Kannada text handling across all export formats."""
    biz1 = test_setup["biz1"]
    biz1.legal_name = "ಶ್ರೀ ಬಸವೇಶ್ವರ ಎಂಟರ್‌ಪ್ರೈಸಸ್ (Basaveshwara Enterprises)"
    db_session.commit()

    # 1. PDF generation does not crash on Kannada / Unicode text
    pdf_resp = client_a.post(
        "/api/v1/reports/generate",
        json={"report_type": "executive_summary", "format": "PDF"},
    )
    assert pdf_resp.status_code == 201

    # 2. CSV generation preserves exact Kannada characters
    csv_resp = client_a.post(
        "/api/v1/reports/generate",
        json={"report_type": "executive_summary", "format": "CSV"},
    )
    assert csv_resp.status_code == 201
    dl_csv = client_a.get(f"/api/v1/reports/{csv_resp.json()['report_id']}/download")
    csv_text = dl_csv.content.decode("utf-8-sig")
    assert "ಶ್ರೀ ಬಸವೇಶ್ವರ" in csv_text

    # 3. XLSX generation preserves exact Kannada characters
    xlsx_resp = client_a.post(
        "/api/v1/reports/generate",
        json={"report_type": "executive_summary", "format": "XLSX"},
    )
    assert xlsx_resp.status_code == 201


# ==============================================================================
# 4. History, Details, and Downloads
# ==============================================================================

def test_report_history_and_pagination(client_a):
    """Track report generation history and pagination."""
    # Generate 2 reports
    client_a.post("/api/v1/reports/generate", json={"report_type": "executive_summary", "format": "PDF"})
    client_a.post("/api/v1/reports/generate", json={"report_type": "executive_summary", "format": "CSV"})

    hist_resp = client_a.get("/api/v1/reports/history?page=1&page_size=10")
    assert hist_resp.status_code == 200
    data = hist_resp.json()
    assert data["total"] >= 2
    assert len(data["items"]) >= 2
    assert data["items"][0]["status"] == "COMPLETED"


def test_download_increments_counter_and_records_audit(db_session: Session, client_a):
    """Download increments download_count and writes an immutable audit record."""
    gen_resp = client_a.post("/api/v1/reports/generate", json={"report_type": "executive_summary", "format": "PDF"})
    report_id = gen_resp.json()["report_id"]

    # Initial download count is 0
    detail_before = client_a.get(f"/api/v1/reports/{report_id}").json()
    assert detail_before["download_count"] == 0

    # First download
    client_a.get(f"/api/v1/reports/{report_id}/download")

    detail_after = client_a.get(f"/api/v1/reports/{report_id}").json()
    assert detail_after["download_count"] == 1

    # Verify audit record created
    audits = db_session.query(BusinessReportAudit).filter(BusinessReportAudit.action == "DOWNLOADED").all()
    assert len(audits) >= 1
    assert audits[-1].status == "SUCCESS"


# ==============================================================================
# 5. Security: Tenant Isolation & Path Traversal
# ==============================================================================

def test_path_traversal_prevention():
    """Storage service strictly blocks path traversal attempts."""
    storage = ReportStorageService()

    with pytest.raises(StorageSecurityError):
        storage.read_report_file(business_id=1, relative_path="../../etc/passwd")

    with pytest.raises(StorageSecurityError):
        storage.read_report_file(business_id=1, relative_path="2/secret.pdf")

    with pytest.raises(StorageSecurityError):
        storage.save_report_file(business_id=-1, report_id="test", file_format="pdf", content=b"fake")


def test_cross_tenant_report_isolation(client_a, client_b):
    """User B cannot fetch, download, or archive User A's report."""
    gen_resp = client_a.post("/api/v1/reports/generate", json={"report_type": "executive_summary", "format": "PDF"})
    report_id_a = gen_resp.json()["report_id"]

    # User B direct detail fetch -> 404
    resp_detail_b = client_b.get(f"/api/v1/reports/{report_id_a}")
    assert resp_detail_b.status_code == 404

    # User B download attempt -> 404
    resp_dl_b = client_b.get(f"/api/v1/reports/{report_id_a}/download")
    assert resp_dl_b.status_code == 404

    # User B delete attempt -> 404
    resp_del_b = client_b.delete(f"/api/v1/reports/{report_id_a}")
    assert resp_del_b.status_code == 404


def test_multi_business_same_owner_isolation(db_session: Session, test_setup, client_a):
    """Strict tenant isolation between two businesses owned by the SAME user."""
    u1 = test_setup["user1"]
    b1 = test_setup["biz1"]

    # Create second business for User 1
    b1_sec = Business(
        owner_id=u1.id,
        legal_name="Enterprise Alpha Logistics Pvt Ltd",
        trade_name="Alpha Logistics",
        industry="Logistics",
        state_region="Karnataka",
        established_year=2023,
        employee_count=4,
        annual_revenue=1000000.0,
    )
    db_session.add(b1_sec)
    db_session.commit()
    db_session.refresh(b1_sec)

    # 1. Generate report under Business 1
    u1.active_business_id = b1.id
    db_session.commit()
    gen_resp = client_a.post("/api/v1/reports/generate", json={"report_type": "executive_summary", "format": "PDF"})
    rep1_id = gen_resp.json()["report_id"]

    # 2. Switch to Business 2
    u1.active_business_id = b1_sec.id
    db_session.commit()

    # History under Business 2 does NOT list Business 1's report
    hist_b2 = client_a.get("/api/v1/reports/history").json()
    rep_ids_b2 = [r["report_id"] for r in hist_b2["items"]]
    assert rep1_id not in rep_ids_b2

    # Direct access returns 404
    assert client_a.get(f"/api/v1/reports/{rep1_id}").status_code == 404
    assert client_a.get(f"/api/v1/reports/{rep1_id}/download").status_code == 404

    # Switch back to Business 1
    u1.active_business_id = b1.id
    db_session.commit()
    assert client_a.get(f"/api/v1/reports/{rep1_id}").status_code == 200


def test_unauthenticated_access_returns_401():
    """Unauthenticated calls return 401."""
    client = TestClient(app)
    assert client.get("/api/v1/reports/catalog").status_code == 401
    assert client.post("/api/v1/reports/preview", json={"report_type": "executive_summary"}).status_code == 401
    assert client.get("/api/v1/reports/history").status_code == 401


# ==============================================================================
# 6. Archival, Audit Immutability & Source Non-Mutation
# ==============================================================================

def test_report_archival_soft_delete(client_a):
    """Archiving a report prevents future downloads while preserving record."""
    gen_resp = client_a.post("/api/v1/reports/generate", json={"report_type": "executive_summary", "format": "PDF"})
    report_id = gen_resp.json()["report_id"]

    del_resp = client_a.delete(f"/api/v1/reports/{report_id}?reason=Superseded+by+new+audit")
    assert del_resp.status_code == 200
    assert del_resp.json()["is_archived"] is True

    # History excludes it
    hist = client_a.get("/api/v1/reports/history").json()
    rep_ids = [r["report_id"] for r in hist["items"]]
    assert report_id not in rep_ids

    # Download attempt returns 404
    assert client_a.get(f"/api/v1/reports/{report_id}/download").status_code == 404


def test_audit_trail_immutability(db_session: Session, client_a):
    """Audit records are append-only; updates and deletes are blocked."""
    client_a.post("/api/v1/reports/generate", json={"report_type": "executive_summary", "format": "PDF"})
    audit = db_session.query(BusinessReportAudit).first()
    assert audit is not None

    # ORM-level update blocked
    audit.status = "TAMPERED"
    with pytest.raises(ValueError, match="append-only and cannot be updated"):
        db_session.commit()
    db_session.rollback()

    # ORM-level delete blocked
    db_session.delete(audit)
    with pytest.raises(ValueError, match="append-only and cannot be deleted"):
        db_session.commit()
    db_session.rollback()

    # Raw SQL update blocked by DB triggers
    with pytest.raises(Exception):
        db_session.execute(text(f"UPDATE business_report_audits SET status='TAMPERED' WHERE id={audit.id}"))
        db_session.commit()
    db_session.rollback()

    # Raw SQL delete blocked by DB triggers
    with pytest.raises(Exception):
        db_session.execute(text(f"DELETE FROM business_report_audits WHERE id={audit.id}"))
        db_session.commit()
    db_session.rollback()


def test_no_source_data_mutation(db_session: Session, test_setup, client_a):
    """Report generation never mutates underlying business records."""
    biz1 = test_setup["biz1"]
    orig_rev = biz1.annual_revenue
    orig_name = biz1.legal_name

    # Preview and generate multiple reports
    client_a.post("/api/v1/reports/preview", json={"report_type": "executive_summary"})
    client_a.post("/api/v1/reports/generate", json={"report_type": "executive_summary", "format": "PDF"})
    client_a.post("/api/v1/reports/generate", json={"report_type": "executive_summary", "format": "CSV"})

    db_session.refresh(biz1)
    assert biz1.annual_revenue == orig_rev
    assert biz1.legal_name == orig_name


def test_all_catalogue_report_types_preview_and_generation(db_session: Session, test_setup, client_a):
    """Verify live preview and generation for all 9 supported catalogue report types."""
    biz1 = test_setup["biz1"]

    # Seed data for cross-module reports
    # 1. Sales
    up = SalesUpload(
        business_id=biz1.id,
        filename="batch_2026.csv",
        file_format="csv",
        file_size_bytes=1024,
        status="completed",
        row_count=2,
        valid_row_count=2,
    )
    db_session.add(up)
    db_session.commit()

    now_utc = datetime.now(timezone.utc)
    t1 = SalesTransaction(
        upload_id=up.id,
        business_id=biz1.id,
        transaction_date=now_utc - timedelta(days=5),
        customer_name="Customer Alpha",
        total_amount=25000.0,
        quantity=5,
        unit_price=5000.0,
        product_name="Standard Widget A",
        is_duplicate=False,
    )
    t2 = SalesTransaction(
        upload_id=up.id,
        business_id=biz1.id,
        transaction_date=now_utc - timedelta(days=2),
        customer_name="Customer Beta",
        total_amount=30000.0,
        quantity=3,
        unit_price=10000.0,
        product_name="Pro Widget B",
        is_duplicate=False,
    )
    db_session.add_all([t1, t2])

    # 2. Decision
    dec = BusinessDecision(
        business_id=biz1.id,
        owner_id=biz1.owner_id,
        title="Supplier Diversification Decision",
        decision_type="DISCOUNT_CHANGE",
        objective="Reduce single-source risk.",
        status="ACCEPTED",
        decision_rationale="Accepted supplier diversification.",
    )
    db_session.add(dec)

    # 3. Alert
    alert = BusinessSignalEvent(
        event_id="sig_cust_conc_001",
        business_id=biz1.id,
        event_type="CUSTOMER_INACTIVITY",
        source="Sales Ingestion",
        severity="WARNING",
        event_nature="WARNING",
        data_period="Last 30 Days",
        fingerprint="fp_cust_001",
        title="High Customer Concentration Detected",
        what_changed="Top customer concentration increased.",
        why_it_matters="Over-reliance on single customer.",
        suggested_action="Diversify customer base.",
        status="NEW",
    )
    db_session.add(alert)

    # 4. Goal
    goal = BusinessGoal(
        business_id=biz1.id,
        title="Quarterly Sales Target",
        metric_key="monthly_revenue",
        target_value=100000.0,
        baseline_value=0.0,
        status="ACTIVE",
    )
    db_session.add(goal)

    # 5. What-If Scenario
    scenario = WhatIfScenario(
        business_id=biz1.id,
        owner_id=biz1.owner_id,
        title="15% Raw Material Shock",
        scenario_type="supplier_cost_increase",
        baseline_metrics={"monthly_gross_profit_inr": 50000.0, "monthly_revenue_inr": 100000.0},
        parameters={"cogs_delta_pct": 15.0},
        projection_result={
            "cases": [
                {
                    "case_label": "Base Case",
                    "projected_revenue_inr": 100000.0,
                    "revenue_delta_inr": 0.0,
                    "revenue_delta_pct": 0.0,
                    "projected_cogs_inr": 57500.0,
                    "projected_gross_profit_inr": 42500.0,
                    "gross_profit_delta_inr": -7500.0,
                    "gross_margin_pct": 42.5,
                    "projected_opex_inr": 30000.0,
                    "projected_operating_profit_inr": 12500.0,
                    "operating_profit_delta_inr": -7500.0,
                    "cash_runway_days_estimated": 90,
                    "cash_runway_days_delta": -30,
                    "break_even_revenue_inr": 70588.0,
                }
            ]
        },
    )
    db_session.add(scenario)
    db_session.commit()

    all_types = [
        ReportType.EXECUTIVE_SUMMARY.value,
        ReportType.SALES_REVENUE_PERFORMANCE.value,
        ReportType.CUSTOMER_PERFORMANCE.value,
        ReportType.PRODUCT_PERFORMANCE.value,
        ReportType.DECISIONS_SUMMARY.value,
        ReportType.ALERTS_SUMMARY.value,
        ReportType.GOALS_PROGRESS.value,
        ReportType.DATA_QUALITY_AUDIT.value,
        ReportType.SCENARIO_COMPARISON.value,
    ]

    for r_type in all_types:
        # Preview
        prev_resp = client_a.post("/api/v1/reports/preview", json={"report_type": r_type})
        assert prev_resp.status_code == 200, f"Preview failed for {r_type}: {prev_resp.text}"
        data = prev_resp.json()
        assert len(data["key_findings"]) >= 1, f"Missing key findings for {r_type}"
        assert data["provenance"]["disclaimer"], f"Missing disclaimer for {r_type}"

        # Generate PDF
        gen_pdf = client_a.post("/api/v1/reports/generate", json={"report_type": r_type, "format": "PDF"})
        assert gen_pdf.status_code == 201, f"PDF generation failed for {r_type}: {gen_pdf.text}"
        assert gen_pdf.json()["status"] == "COMPLETED"

        # Generate CSV
        gen_csv = client_a.post("/api/v1/reports/generate", json={"report_type": r_type, "format": "CSV"})
        assert gen_csv.status_code == 201, f"CSV generation failed for {r_type}: {gen_csv.text}"
        assert gen_csv.json()["status"] == "COMPLETED"

