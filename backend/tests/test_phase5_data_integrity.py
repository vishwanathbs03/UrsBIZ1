"""Enterprise-Grade Business Data Integrity and Provenance Test Suite (Phase 5).

Covers:
  1. Centralized Data Provenance (lineage, methodology, nature, quality status)
  2. Source-Specific Freshness Policies (7 distinct module rules, fresh vs stale vs expired)
  3. Data Quality Validation (missing fields, duplicates, invalid dates, negative amounts, outliers)
  4. Cross-Module Consistency & Reconciliation (sales vs products vs customers vs profile)
  5. Safe Forecast Data Consumption (unconfirmed gap isolation, minimum 6 periods, no actual sales claims)
  6. Typed Data Contracts (Pydantic v2 validation, strict bounds, currency checks)
  7. Cross-Business Tenant Isolation (foreign tenant transaction rejection)
  8. Database Persistence & Rollback Safety (Alembic migration tables)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import math
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.business import Business
from app.models.data_provenance import BusinessDataProvenance, BusinessDataQualityAudit
from app.models.sales import SalesTransaction
from app.schemas.data_contracts import (
    DataIntegrityEnvelope,
    ValidatedBusinessProfileContract,
    ValidatedCustomerAnalyticsContract,
    ValidatedDemandForecastContract,
    ValidatedSalesMetricsContract,
)
from app.schemas.data_provenance import (
    CrossModuleDiscrepancy,
    DataProvenanceRecord,
    DataQualityAnomaly,
    DataQualityAuditReport,
    DataQualityStatus,
    FreshnessStatus,
    MetricNature,
    ModuleDomain,
)
from app.schemas.recommendation_context import (
    BusinessProfileContext,
    CustomerAnalyticsContext,
    DemandForecastContext,
    HealthScoreContext,
    OperationalReadinessContext,
    ProductForecastItemContext,
    ProductPerformanceContext,
    SalesIntelligenceContext,
    SchemeMatchingContext,
    UnifiedRecommendationContext,
)
from app.services.data_integrity.cross_module_consistency import CrossModuleConsistencyEngine
from app.services.data_integrity.forecast_safety import SafeForecastConsumer
from app.services.data_integrity.freshness_engine import (
    DEFAULT_FRESHNESS_POLICIES,
    DataFreshnessEngine,
)
from app.services.data_integrity.provenance_service import ProvenanceService
from app.services.data_integrity.quality_validator import DataQualityValidator
from app.utils.database import Base


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #

@pytest.fixture
def mock_business() -> Business:
    b = Business()
    b.id = 501
    b.legal_name = "Zenith Dynamics Precision Tools Pvt Ltd"
    b.trade_name = "Zenith Tools"
    b.industry = "Precision Engineering"
    b.city = "Pune"
    b.state_region = "Maharashtra"
    b.country = "India"
    b.annual_revenue = 18000000.0
    b.revenue_currency = "INR"
    b.established_year = 2018
    b.employee_count = 45
    b.created_at = datetime.now(timezone.utc) - timedelta(days=200)
    b.updated_at = datetime.now(timezone.utc) - timedelta(days=20)
    return b


@pytest.fixture
def sample_transactions(mock_business) -> list[SalesTransaction]:
    now = datetime.now(timezone.utc)
    txs: list[SalesTransaction] = []
    # 10 valid transactions over past 90 days
    for i in range(10):
        t = SalesTransaction()
        t.id = 1000 + i
        t.upload_id = 10
        t.business_id = mock_business.id
        t.transaction_date = now - timedelta(days=(90 - i * 8))
        t.invoice_id = f"INV-2025-{100 + i}"
        t.customer_id = f"CUST-{1 if i < 6 else 2}"
        t.customer_name = "Bharat Aerospace Corp" if i < 6 else "Tata Advanced Motors"
        t.product_id = f"SKU-{1 if i % 2 == 0 else 2}"
        t.product_name = "Tungsten Carbide Nozzle" if i % 2 == 0 else "Alloy Valve Guide"
        t.quantity = 10.0 + i
        t.unit_price = 10000.0
        t.total_amount = t.quantity * t.unit_price
        t.is_duplicate = False
        txs.append(t)
    return txs


# --------------------------------------------------------------------------- #
# 1. Centralized Data Provenance Tests
# --------------------------------------------------------------------------- #

def test_provenance_registration_and_retrieval():
    service = ProvenanceService(db=None)

    rec = DataProvenanceRecord(
        metric_name="total_revenue",
        metric_value=12500000.0,
        business_id=501,
        source_module=ModuleDomain.SALES,
        source_record_ref="sales_transactions:batch_101:rows_1_150",
        measurement_period="2025-01-01 to 2025-09-30",
        unit="INR",
        currency="INR",
        calculation_methodology="Sum of non-duplicate transaction total_amount records",
        last_updated_at=datetime.now(timezone.utc).isoformat(),
        data_quality_status=DataQualityStatus.VERIFIED,
        nature=MetricNature.ACTUAL,
        freshness_status=FreshnessStatus.FRESH,
        confidence_score=100.0,
    )

    registered = service.register_metric(rec, persist=False)
    assert registered.metric_name == "total_revenue"

    fetched = service.get_provenance(business_id=501, metric_name="total_revenue")
    assert fetched is not None
    assert fetched.metric_value == 12500000.0
    assert fetched.nature == MetricNature.ACTUAL
    assert fetched.source_record_ref == "sales_transactions:batch_101:rows_1_150"

    # Verify no fake provenance when not registered
    missing = service.get_provenance(business_id=501, metric_name="unrecorded_metric")
    assert missing is None


# --------------------------------------------------------------------------- #
# 2. Source-Specific Freshness Policy Tests
# --------------------------------------------------------------------------- #

def test_source_specific_freshness_policies():
    engine = DataFreshnessEngine()
    now = datetime.now(timezone.utc)

    # 1. Sales: 30d fresh, 90d stale, >90d expired
    fresh_sales_dt = now - timedelta(days=15)
    st_fresh, age_fresh, _ = engine.evaluate_freshness(ModuleDomain.SALES, fresh_sales_dt, now)
    assert st_fresh == FreshnessStatus.FRESH
    assert age_fresh == 15

    stale_sales_dt = now - timedelta(days=45)
    st_stale, age_stale, _ = engine.evaluate_freshness(ModuleDomain.SALES, stale_sales_dt, now)
    assert st_stale == FreshnessStatus.POTENTIALLY_STALE
    assert age_stale == 45

    expired_sales_dt = now - timedelta(days=100)
    st_exp, age_exp, _ = engine.evaluate_freshness(ModuleDomain.SALES, expired_sales_dt, now)
    assert st_exp == FreshnessStatus.EXPIRED_OR_UNAVAILABLE

    # 2. Demand Forecast: 14d fresh, 45d stale
    fresh_fc_dt = now - timedelta(days=10)
    st_fc_fresh, _, _ = engine.evaluate_freshness(ModuleDomain.DEMAND_FORECAST, fresh_fc_dt, now)
    assert st_fc_fresh == FreshnessStatus.FRESH

    stale_fc_dt = now - timedelta(days=20)
    st_fc_stale, _, _ = engine.evaluate_freshness(ModuleDomain.DEMAND_FORECAST, stale_fc_dt, now)
    assert st_fc_stale == FreshnessStatus.POTENTIALLY_STALE

    # 3. Business Profile: 180d fresh (semi-annual)
    profile_dt = now - timedelta(days=120)
    st_prof, _, _ = engine.evaluate_freshness(ModuleDomain.BUSINESS_PROFILE, profile_dt, now)
    assert st_prof == FreshnessStatus.FRESH

    # Disclaimer generation
    disclaimer = engine.generate_freshness_disclaimer(ModuleDomain.SALES, st_stale, age_stale, "2025-09-15")
    assert disclaimer is not None
    assert "Temporal Caution" in disclaimer
    assert "45 days ago" in disclaimer


# --------------------------------------------------------------------------- #
# 3. Data Quality Validation Tests
# --------------------------------------------------------------------------- #

def test_data_quality_missing_fields_and_negative_amounts(mock_business):
    validator = DataQualityValidator()

    # Corrupt business with missing legal name and negative revenue
    bad_biz = Business()
    bad_biz.id = 999
    bad_biz.legal_name = ""
    bad_biz.industry = "Manufacturing"
    bad_biz.annual_revenue = -500000.0

    report = validator.audit_business_dataset(bad_biz, [])
    assert report.overall_quality_status == DataQualityStatus.SUSPECT
    assert any(a.anomaly_type == "missing_field" and a.field_name == "legal_name" for a in report.anomalies_detected)
    assert any(a.anomaly_type == "negative_number" and a.field_name == "annual_revenue" for a in report.anomalies_detected)


def test_data_quality_duplicate_transaction_exclusion(mock_business, sample_transactions):
    validator = DataQualityValidator()

    # Introduce a duplicate transaction
    dup = SalesTransaction()
    dup.id = 9999
    dup.upload_id = 10
    dup.business_id = mock_business.id
    dup.transaction_date = sample_transactions[0].transaction_date
    dup.invoice_id = sample_transactions[0].invoice_id
    dup.product_name = sample_transactions[0].product_name
    dup.total_amount = sample_transactions[0].total_amount
    dup.quantity = sample_transactions[0].quantity
    dup.unit_price = sample_transactions[0].unit_price
    dup.is_duplicate = False

    txs_with_dup = sample_transactions + [dup]
    report = validator.audit_business_dataset(mock_business, txs_with_dup)

    assert report.duplicate_records_count == 1
    assert any(a.anomaly_type == "duplicate_record" for a in report.anomalies_detected)


def test_data_quality_invalid_dates_and_future_timestamps(mock_business):
    validator = DataQualityValidator()
    now = datetime.now(timezone.utc)

    # Future transaction date
    future_tx = SalesTransaction()
    future_tx.id = 8888
    future_tx.upload_id = 10
    future_tx.business_id = mock_business.id
    future_tx.transaction_date = now + timedelta(days=10)
    future_tx.invoice_id = "INV-FUTURE"
    future_tx.product_name = "Turbine Ring"
    future_tx.quantity = 5.0
    future_tx.unit_price = 1000.0
    future_tx.total_amount = 5000.0
    future_tx.is_duplicate = False

    report = validator.audit_business_dataset(mock_business, [future_tx])
    assert any(a.anomaly_type == "invalid_date" for a in report.anomalies_detected)


def test_data_quality_outlier_surge_detection(mock_business, sample_transactions):
    validator = DataQualityValidator()

    # Outlier transaction: ₹50,000,000 (normal mean is ~₹150,000)
    outlier_tx = SalesTransaction()
    outlier_tx.id = 7777
    outlier_tx.upload_id = 10
    outlier_tx.business_id = mock_business.id
    outlier_tx.transaction_date = datetime.now(timezone.utc) - timedelta(days=2)
    outlier_tx.invoice_id = "INV-SPIKE"
    outlier_tx.product_name = "Industrial Extrusion Machine"
    outlier_tx.quantity = 1.0
    outlier_tx.unit_price = 50000000.0
    outlier_tx.total_amount = 50000000.0
    outlier_tx.is_duplicate = False

    txs_with_outlier = sample_transactions + [outlier_tx]
    report = validator.audit_business_dataset(mock_business, txs_with_outlier)

    assert any(a.anomaly_type == "outlier_surge" for a in report.anomalies_detected)


def test_data_quality_unconfirmed_gap_isolation(mock_business):
    validator = DataQualityValidator()
    now = datetime.now(timezone.utc)

    # Two transactions separated by 120 days (unconfirmed gap)
    t1 = SalesTransaction()
    t1.id = 1
    t1.upload_id = 10
    t1.business_id = mock_business.id
    t1.transaction_date = now - timedelta(days=150)
    t1.invoice_id = "INV-1"
    t1.product_name = "SKU-A"
    t1.quantity = 5.0
    t1.unit_price = 1000.0
    t1.total_amount = 5000.0
    t1.is_duplicate = False

    t2 = SalesTransaction()
    t2.id = 2
    t2.upload_id = 10
    t2.business_id = mock_business.id
    t2.transaction_date = now - timedelta(days=20)
    t2.invoice_id = "INV-2"
    t2.product_name = "SKU-A"
    t2.quantity = 8.0
    t2.unit_price = 1000.0
    t2.total_amount = 8000.0
    t2.is_duplicate = False

    report = validator.audit_business_dataset(mock_business, [t1, t2])
    assert report.unconfirmed_gaps_count >= 1
    gap_anomaly = next(a for a in report.anomalies_detected if a.anomaly_type == "unconfirmed_gap")
    assert "NOT confirmed zero demand" in gap_anomaly.description


# --------------------------------------------------------------------------- #
# 4. Cross-Module Consistency Tests
# --------------------------------------------------------------------------- #

def test_cross_module_consistency_product_overflow():
    engine = CrossModuleConsistencyEngine()

    # Context where sum of products (₹20,000,000) exceeds total revenue (₹12,000,000)
    ctx = UnifiedRecommendationContext(
        business_id=501,
        gathered_at="2026-11-01T00:00:00Z",
        profile=BusinessProfileContext(
            business_id=501, legal_name="Zenith Tools", industry="Precision Tools"
        ),
        health=HealthScoreContext(overall_score=80, grade="A"),
        sales=SalesIntelligenceContext(has_sales_data=True, total_revenue=12000000.0),
        customers=CustomerAnalyticsContext(),
        products=ProductPerformanceContext(
            total_products=2,
            top_products_by_revenue=[
                {"product_name": "Nozzle A", "revenue": 14000000.0},
                {"product_name": "Nozzle B", "revenue": 6000000.0},
            ],
        ),
        forecast=DemandForecastContext(),
        schemes=SchemeMatchingContext(),
        readiness=OperationalReadinessContext(),
    )

    discrepancies = engine.reconcile_context(ctx)
    assert len(discrepancies) >= 1
    overflow = next(d for d in discrepancies if d.discrepancy_type == "product_revenue_overflow")
    assert overflow.divergence_pct is not None and overflow.divergence_pct > 50.0


def test_cross_module_consistency_customer_overflow():
    engine = CrossModuleConsistencyEngine()

    # Context where top customer revenue (₹15,000,000) exceeds total sales turnover (₹10,000,000)
    ctx = UnifiedRecommendationContext(
        business_id=501,
        gathered_at="2026-11-01T00:00:00Z",
        profile=BusinessProfileContext(
            business_id=501, legal_name="Zenith Tools", industry="Precision Tools"
        ),
        health=HealthScoreContext(overall_score=80, grade="A"),
        sales=SalesIntelligenceContext(has_sales_data=True, total_revenue=10000000.0),
        customers=CustomerAnalyticsContext(
            top_customers_by_revenue=[
                {"customer_name": "Acme Aerospace", "revenue": 15000000.0}
            ]
        ),
        products=ProductPerformanceContext(),
        forecast=DemandForecastContext(),
        schemes=SchemeMatchingContext(),
        readiness=OperationalReadinessContext(),
    )

    discrepancies = engine.reconcile_context(ctx)
    assert any(d.discrepancy_type == "customer_revenue_overflow" for d in discrepancies)


# --------------------------------------------------------------------------- #
# 5. Safe Forecast Data Consumption Tests
# --------------------------------------------------------------------------- #

def test_safe_forecast_consumption_minimum_history_and_boundaries():
    consumer = SafeForecastConsumer()

    fc_ctx = DemandForecastContext(
        has_forecast_data=True,
        product_forecasts=[
            ProductForecastItemContext(
                product_id="SKU-01",
                product_name="CNC Nozzle",
                demand_trend="increasing",
                forecasted_units_total=300.0,
                forecast_horizon_periods=3,
                selected_model="croston",
                reliability="High",
                limitation_notes=[],
            )
        ],
    )

    # Case 1: Insufficient history (< 6 periods)
    is_safe, disclaimers, sanitized = consumer.audit_forecast_consumption(
        forecast_ctx=fc_ctx,
        total_historical_periods=4,
        unconfirmed_gaps_present=True,
    )

    assert is_safe is True
    assert any("minimum 6 required" in d for d in disclaimers)
    assert any("Unconfirmed Data Gap Guard" in d for d in disclaimers)
    # Warehouse stock limitation must be enforced
    assert any("warehouse" in lim.lower() for lim in sanitized[0].limitation_notes)


# --------------------------------------------------------------------------- #
# 6. Typed Data Contracts Validation Tests
# --------------------------------------------------------------------------- #

def test_typed_data_contracts_validation():
    # 1. Valid Profile Contract
    prof = ValidatedBusinessProfileContract(
        business_id=501,
        legal_name="Zenith Tools Pvt Ltd",
        industry="Manufacturing",
        revenue_currency="INR",
        annual_revenue=15000000.0,
    )
    assert prof.business_id == 501

    # 2. Reject negative business_id
    with pytest.raises(Exception):
        ValidatedBusinessProfileContract(
            business_id=-1,
            legal_name="Bad Co",
            industry="Manufacturing",
        )

    # 3. Reject unsupported currency
    with pytest.raises(Exception):
        ValidatedBusinessProfileContract(
            business_id=501,
            legal_name="Bad Co",
            industry="Manufacturing",
            revenue_currency="INVALID_CURRENCY",
        )

    # 4. Sales metrics contract: reject NaN
    with pytest.raises(Exception):
        ValidatedSalesMetricsContract(
            business_id=501,
            has_sales_data=True,
            total_revenue=float("nan"),
        )


# --------------------------------------------------------------------------- #
# 7. Multi-Tenant Cross-Business Data Access Containment
# --------------------------------------------------------------------------- #

def test_cross_tenant_data_access_containment(mock_business):
    validator = DataQualityValidator()

    # Foreign transaction with business_id 999 instead of 501
    foreign_tx = SalesTransaction()
    foreign_tx.id = 1234
    foreign_tx.upload_id = 10
    foreign_tx.business_id = 999  # Foreign tenant
    foreign_tx.transaction_date = datetime.now(timezone.utc)
    foreign_tx.invoice_id = "INV-FOREIGN"
    foreign_tx.product_name = "Leaked SKU"
    foreign_tx.quantity = 1.0
    foreign_tx.unit_price = 1000.0
    foreign_tx.total_amount = 1000.0
    foreign_tx.is_duplicate = False

    report = validator.audit_business_dataset(mock_business, [foreign_tx])
    assert any(a.anomaly_type == "cross_tenant_violation" for a in report.anomalies_detected)
    assert report.overall_quality_status == DataQualityStatus.SUSPECT


# --------------------------------------------------------------------------- #
# 8. Database Persistence Integration Tests
# --------------------------------------------------------------------------- #

def test_database_provenance_and_audit_persistence(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/test_integrity.db")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    # Create dummy business in DB
    biz = Business()
    biz.id = 601
    biz.owner_id = 1
    biz.legal_name = "Aero Machining Ltd"
    biz.industry = "Aerospace"
    biz.established_year = 2020
    db.add(biz)
    db.commit()

    service = ProvenanceService(db=db)

    # Register metric with persistence
    now_iso = datetime.now(timezone.utc).isoformat()
    rec = DataProvenanceRecord(
        metric_name="total_revenue",
        metric_value=25000000.0,
        business_id=601,
        source_module=ModuleDomain.SALES,
        source_record_ref="sales_transactions:batch_1:1-200",
        measurement_period="2025-01-01 to 2025-09-30",
        unit="INR",
        currency="INR",
        calculation_methodology="Sum of non-duplicate sales transaction rows",
        last_updated_at=now_iso,
        data_quality_status=DataQualityStatus.VERIFIED,
        nature=MetricNature.ACTUAL,
        freshness_status=FreshnessStatus.FRESH,
        confidence_score=100.0,
    )
    service.register_metric(rec, persist=True)

    # Fetch from DB
    retrieved = service.get_provenance(business_id=601, metric_name="total_revenue")
    assert retrieved is not None
    assert retrieved.metric_value == 25000000.0
    assert retrieved.source_record_ref == "sales_transactions:batch_1:1-200"

    # Persist audit report
    audit_report = DataQualityAuditReport(
        business_id=601,
        audit_timestamp=now_iso,
        overall_quality_status=DataQualityStatus.VERIFIED,
        quality_score=95.0,
        anomalies_detected=[],
        cross_module_discrepancies=[],
        freshness_summary={"sales": FreshnessStatus.FRESH},
        unconfirmed_gaps_count=0,
        duplicate_records_count=0,
        data_limitations=[],
    )
    service.record_audit_report(audit_report)

    # Verify audit row exists in DB
    db_audit = db.query(BusinessDataQualityAudit).filter(BusinessDataQualityAudit.business_id == 601).first()
    assert db_audit is not None
    assert db_audit.quality_score == 95.0
    assert db_audit.overall_quality_status == "VERIFIED"

    db.close()
