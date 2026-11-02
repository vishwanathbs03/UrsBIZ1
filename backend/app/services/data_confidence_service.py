"""Data Quality and Business Data Confidence Centre Service (Phase 6.20 Extension).

Provides authoritative, non-destructive audit and confidence assessment for MSME owners:
  - Ingestion reconciliation: gross uploaded vs. duplicate-excluded analytical basis
  - Valid-row rate and rejected-row audit
  - Observation window calculation (calendar span and unconfirmed gaps)
  - Insight Confidence Matrix mapping data sufficiency to each business module
  - Actionable improvement checklist to guide data enhancement
  - Persistent audit log creation
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.business import Business
from app.models.data_provenance import BusinessDataQualityAudit
from app.models.sales import SalesTransaction, SalesUpload
from app.schemas.data_confidence import (
    DataAnomalySummary,
    DataConfidenceCentreResponse,
    DataImprovementAction,
    IngestionReconciliationSummary,
    InsightReadinessItem,
    ObservationWindowSummary,
)
from app.services.data_integrity.freshness_engine import DataFreshnessEngine
from app.services.data_integrity.quality_validator import DataQualityValidator

logger = logging.getLogger(__name__)


class DataConfidenceService:
    """Evaluates business data sufficiency, integrity, and insight confidence."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.freshness_engine = DataFreshnessEngine()
        self.quality_validator = DataQualityValidator(freshness_engine=self.freshness_engine)

    def evaluate_business_confidence(
        self,
        business_id: int,
        owner_id: int,
        persist_audit: bool = True,
    ) -> DataConfidenceCentreResponse:
        """Runs a complete data quality audit and returns the confidence matrix."""
        # 1. Fetch business and verify ownership
        business = self.db.execute(
            select(Business).where(
                Business.id == business_id,
                Business.owner_id == owner_id,
            )
        ).scalar_one_or_none()

        if not business:
            raise ValueError(f"Business {business_id} not found or not owned by user {owner_id}")

        now = datetime.now(timezone.utc)

        # 2. Ingestion & Uploads Audit
        uploads = list(
            self.db.execute(
                select(SalesUpload)
                .where(SalesUpload.business_id == business_id)
                .order_by(SalesUpload.created_at.desc())
            ).scalars().all()
        )

        total_uploads = len(uploads)
        total_rows_imported = sum(u.row_count for u in uploads)
        valid_rows_ingested = sum(u.valid_row_count for u in uploads)
        rejected_rows_count = sum(u.invalid_row_count for u in uploads)

        # 3. Transaction Ledger & Duplicate Reconciliation
        transactions = list(
            self.db.execute(
                select(SalesTransaction)
                .where(SalesTransaction.business_id == business_id)
                .order_by(SalesTransaction.transaction_date.asc())
            ).scalars().all()
        )

        duplicate_txs = [t for t in transactions if t.is_duplicate]
        duplicate_rows_count = len(duplicate_txs)

        valid_row_rate_pct = (
            round((valid_rows_ingested / total_rows_imported) * 100.0, 2)
            if total_rows_imported > 0
            else 100.0
        )
        duplicate_row_rate_pct = (
            round((duplicate_rows_count / total_rows_imported) * 100.0, 2)
            if total_rows_imported > 0
            else 0.0
        )

        gross_uploaded_rev = sum(float(t.total_amount) for t in transactions)
        duplicate_rev = sum(float(t.total_amount) for t in duplicate_txs)
        analytical_rev = gross_uploaded_rev - duplicate_rev

        reconciliation_note = (
            f"Gross uploaded revenue reflects all {len(transactions)} rows committed via upload files (₹{gross_uploaded_rev:,.0f}). "
            f"Duplicate-excluded analytical revenue (₹{analytical_rev:,.0f}) removes {duplicate_rows_count} duplicate rows (₹{duplicate_rev:,.0f}) "
            "to prevent double-counting in forecasting and business intelligence."
        )

        ingestion_summary = IngestionReconciliationSummary(
            total_uploads_count=total_uploads,
            total_rows_imported=total_rows_imported,
            valid_rows_ingested=valid_rows_ingested,
            duplicate_rows_excluded=duplicate_rows_count,
            rejected_rows_count=rejected_rows_count,
            valid_row_rate_pct=valid_row_rate_pct,
            duplicate_row_rate_pct=duplicate_row_rate_pct,
            gross_uploaded_revenue_inr=round(gross_uploaded_rev, 2),
            duplicate_revenue_excluded_inr=round(duplicate_rev, 2),
            analytical_revenue_inr=round(analytical_rev, 2),
            reconciliation_basis_note=reconciliation_note,
        )

        # 4. Observation Window & Unconfirmed Gaps
        valid_txs = [t for t in transactions if not t.is_duplicate]
        unconfirmed_gaps: list[dict[str, Any]] = []

        if valid_txs:
            earliest_dt = valid_txs[0].transaction_date
            latest_dt = valid_txs[-1].transaction_date
            # Calendar day span inclusive
            observation_days = (latest_dt.date() - earliest_dt.date()).days + 1
            earliest_str = earliest_dt.strftime("%Y-%m-%d")
            latest_str = latest_dt.strftime("%Y-%m-%d")

            # Days since latest transaction relative to now
            latest_aware = latest_dt if latest_dt.tzinfo else latest_dt.replace(tzinfo=timezone.utc)
            days_since_last = max(0, (now - latest_aware).days)

            # Detect unconfirmed gaps (> 14 days between consecutive transactions)
            sorted_by_date = sorted(valid_txs, key=lambda x: x.transaction_date)
            for i in range(len(sorted_by_date) - 1):
                t1 = sorted_by_date[i].transaction_date
                t2 = sorted_by_date[i + 1].transaction_date
                gap = (t2.date() - t1.date()).days
                if gap > 14:
                    unconfirmed_gaps.append({
                        "start_date": t1.strftime("%Y-%m-%d"),
                        "end_date": t2.strftime("%Y-%m-%d"),
                        "gap_days": gap,
                        "classification": "Unconfirmed Sales Gap",
                        "note": (
                            f"{gap} consecutive days with zero recorded transactions. "
                            "Preserved as an unconfirmed reporting gap, not confirmed zero demand."
                        ),
                    })
        else:
            earliest_str = None
            latest_str = None
            observation_days = 0
            days_since_last = None

        last_upload_time = uploads[0].created_at.isoformat() if uploads else None

        # Freshness status
        if not valid_txs:
            freshness_status = "EXPIRED_OR_UNAVAILABLE"
            freshness_desc = "No sales transactions recorded. Ingestion required."
        elif days_since_last is not None and days_since_last <= 14:
            freshness_status = "FRESH"
            freshness_desc = f"Latest transaction recorded {days_since_last} days ago. Highly current."
        elif days_since_last is not None and days_since_last <= 45:
            freshness_status = "POTENTIALLY_STALE"
            freshness_desc = f"Latest transaction is {days_since_last} days old. Fresh sales upload recommended."
        else:
            freshness_status = "EXPIRED_OR_UNAVAILABLE"
            freshness_desc = f"Dataset is {days_since_last} days old. Stale data limits predictive accuracy."

        observation_window = ObservationWindowSummary(
            earliest_transaction_date=earliest_str,
            latest_transaction_date=latest_str,
            observation_window_days=observation_days,
            days_since_last_transaction=days_since_last,
            last_upload_timestamp=last_upload_time,
            freshness_status=freshness_status,  # type: ignore
            freshness_description=freshness_desc,
            unconfirmed_gaps_count=len(unconfirmed_gaps),
            unconfirmed_gaps=unconfirmed_gaps,
        )

        # 5. Run Non-Destructive Quality Audit
        audit_report = self.quality_validator.audit_business_dataset(
            business=business,
            transactions=transactions,
            reference_time=now,
        )

        anomalies_summary: list[DataAnomalySummary] = [
            DataAnomalySummary(
                anomaly_type=a.anomaly_type,
                source_module=a.source_module,
                record_identifier=a.record_identifier,
                description=a.description,
                severity=a.severity,  # type: ignore
                is_blocking=a.is_blocking,
            )
            for a in audit_report.anomalies_detected
        ]

        # 6. Insight Confidence Matrix
        matrix: list[InsightReadinessItem] = []

        # A. Sales Intelligence
        if len(valid_txs) >= 30:
            matrix.append(
                InsightReadinessItem(
                    module_key="sales_intelligence",
                    module_name="Sales Intelligence & Trends",
                    confidence_level="High",
                    confidence_score=95.0,
                    readiness_status="Ready",
                    impact_explanation=f"Full analytical confidence based on {len(valid_txs)} verified transactions across {observation_days} days.",
                    missing_prerequisites=[],
                )
            )
        elif len(valid_txs) >= 5:
            matrix.append(
                InsightReadinessItem(
                    module_key="sales_intelligence",
                    module_name="Sales Intelligence & Trends",
                    confidence_level="Medium",
                    confidence_score=70.0,
                    readiness_status="Degraded with Disclosures",
                    impact_explanation=f"Provisional confidence: {len(valid_txs)} transactions provide initial signal, but a 30+ transaction history is required for robust trendlines.",
                    missing_prerequisites=["Minimum 30 transactions for statistically confident baselines."],
                )
            )
        else:
            matrix.append(
                InsightReadinessItem(
                    module_key="sales_intelligence",
                    module_name="Sales Intelligence & Trends",
                    confidence_level="Insufficient",
                    confidence_score=20.0,
                    readiness_status="Blocked by Missing Data",
                    impact_explanation="Insufficient sales data. Ingest an order or invoice CSV to unlock sales intelligence.",
                    missing_prerequisites=["Initial sales upload with order dates, amounts, and items."],
                )
            )

        # B. Demand Forecasting
        if observation_days >= 60 and len(unconfirmed_gaps) == 0:
            matrix.append(
                InsightReadinessItem(
                    module_key="demand_forecasting",
                    module_name="30-Day Predictive Demand Forecasting",
                    confidence_level="High",
                    confidence_score=90.0,
                    readiness_status="Ready",
                    impact_explanation=f"Continuous {observation_days}-day observation window supports confident moving-average and seasonal projection.",
                    missing_prerequisites=[],
                )
            )
        elif observation_days >= 30:
            missing_items = []
            if len(unconfirmed_gaps) > 0:
                missing_items.append(f"{len(unconfirmed_gaps)} unconfirmed sales gaps exist in the timeline.")
            if observation_days < 60:
                missing_items.append("History span is under 60 days (forecast confidence is bounded).")

            matrix.append(
                InsightReadinessItem(
                    module_key="demand_forecasting",
                    module_name="30-Day Predictive Demand Forecasting",
                    confidence_level="Medium" if len(unconfirmed_gaps) == 0 else "Degraded",
                    confidence_score=65.0 if len(unconfirmed_gaps) == 0 else 45.0,
                    readiness_status="Degraded with Disclosures",
                    impact_explanation="Forecast runs under conservative fallback smoothing due to limited duration or sequence gaps.",
                    missing_prerequisites=missing_items,
                )
            )
        else:
            matrix.append(
                InsightReadinessItem(
                    module_key="demand_forecasting",
                    module_name="30-Day Predictive Demand Forecasting",
                    confidence_level="Insufficient",
                    confidence_score=15.0,
                    readiness_status="Blocked by Missing Data",
                    impact_explanation="Predictive forecasting requires at least 30 continuous calendar days of transaction history.",
                    missing_prerequisites=["30+ calendar days of transaction history."],
                )
            )

        # C. Customer Concentration & Churn
        has_customers = any(bool(t.customer_name or t.customer_id) for t in valid_txs)
        if has_customers:
            matrix.append(
                InsightReadinessItem(
                    module_key="customer_concentration",
                    module_name="Customer Concentration & Churn Analytics",
                    confidence_level="High",
                    confidence_score=88.0,
                    readiness_status="Ready",
                    impact_explanation="Customer identifiers mapped across transaction ledger. Retention, AOV, and top client share are verifiable.",
                    missing_prerequisites=[],
                )
            )
        else:
            matrix.append(
                InsightReadinessItem(
                    module_key="customer_concentration",
                    module_name="Customer Concentration & Churn Analytics",
                    confidence_level="Low",
                    confidence_score=35.0,
                    readiness_status="Degraded with Disclosures",
                    impact_explanation="Sales data does not identify individual customers. Top customer concentration is estimated via industry benchmark (25%).",
                    missing_prerequisites=["Include 'Customer Name' or 'Customer ID' column in uploaded CSV."],
                )
            )

        # D. Product Profitability & Unit Economics
        has_products = any(bool(t.product_name) for t in valid_txs)
        if has_products:
            matrix.append(
                InsightReadinessItem(
                    module_key="product_profitability",
                    module_name="Product Revenue & Velocity Analytics",
                    confidence_level="High",
                    confidence_score=85.0,
                    readiness_status="Ready",
                    impact_explanation="Products mapped with transaction quantities and revenue shares.",
                    missing_prerequisites=[],
                )
            )
        else:
            matrix.append(
                InsightReadinessItem(
                    module_key="product_profitability",
                    module_name="Product Revenue & Velocity Analytics",
                    confidence_level="Low",
                    confidence_score=30.0,
                    readiness_status="Blocked by Missing Data",
                    impact_explanation="Item names missing in uploaded sales records. Catalog-level breakdown unavailable.",
                    missing_prerequisites=["Map 'Item Name' or 'Product' column during CSV ingestion."],
                )
            )

        # E. Digital Twin Health Score
        health_confidence = 90.0 if business.annual_revenue and len(valid_txs) > 10 else 60.0
        matrix.append(
            InsightReadinessItem(
                module_key="health_score",
                module_name="Digital Twin Business Health Score",
                confidence_level="High" if health_confidence >= 80.0 else "Medium",
                confidence_score=health_confidence,
                readiness_status="Ready" if health_confidence >= 80.0 else "Degraded with Disclosures",
                impact_explanation="Health score calculated by deterministic engine across financial, digital, and operational dimensions.",
                missing_prerequisites=[] if health_confidence >= 80.0 else ["Complete all Digital Twin wizard sections."],
            )
        )

        # F. Financial Runway & Working Capital
        matrix.append(
            InsightReadinessItem(
                module_key="runway_analysis",
                module_name="Cash Runway & Working Capital Simulation",
                confidence_level="Medium",
                confidence_score=60.0,
                readiness_status="Degraded with Disclosures",
                impact_explanation="Benchmarked against industry gross margin and 1.5x OpEx cash cushion. Override in What-If Simulator for custom precision.",
                missing_prerequisites=["Explicit monthly expense ledger and verified live bank balance."],
            )
        )

        # 7. Actionable Improvement Checklist
        checklist: list[DataImprovementAction] = []
        if len(valid_txs) < 30:
            checklist.append(
                DataImprovementAction(
                    priority="High",
                    title="Upload Remaining Historical Transactions",
                    description=f"Currently {len(valid_txs)} transactions recorded. Upload sales files spanning 30+ days to unlock full statistical forecasting.",
                    impact_on_insights="Transitions Demand Forecasting and Sales Intelligence from Degraded to High Confidence.",
                    action_type="upload_sales",
                )
            )

        if unconfirmed_gaps:
            gap = unconfirmed_gaps[0]
            checklist.append(
                DataImprovementAction(
                    priority="High",
                    title=f"Reconcile Sales Gap ({gap['start_date']} to {gap['end_date']})",
                    description=f"A {gap['gap_days']}-day gap exists without recorded sales. If the business was operating, upload missing ledger entries.",
                    impact_on_insights="Removes unconfirmed gap penalty, raising forecast confidence by 25%.",
                    action_type="fill_gaps",
                )
            )

        if not has_customers:
            checklist.append(
                DataImprovementAction(
                    priority="Medium",
                    title="Map Customer Identifiers in Next Upload",
                    description="Include buyer names or account codes in future sales CSVs to unlock repeat buyer retention and churn early-warning.",
                    impact_on_insights="Upgrades Customer Concentration from 35% benchmark to 90% verified analytics.",
                    action_type="map_customers",
                )
            )

        if any(a.anomaly_type == "outlier_surge" for a in audit_report.anomalies_detected):
            checklist.append(
                DataImprovementAction(
                    priority="Low",
                    title="Verify Statistical Outlier Transactions",
                    description="Certain transactions exceed 10x median order size. Confirm whether they represent bulk orders or typographical errors.",
                    impact_on_insights="Ensures average order value (AOV) and revenue trendlines reflect true operational rhythm.",
                    action_type="review_outliers",
                )
            )

        # 8. Overall Confidence Score & Grade
        matrix_avg = sum(m.confidence_score for m in matrix) / len(matrix)
        audit_score = audit_report.quality_score
        overall_score = round((matrix_avg * 0.5) + (audit_score * 0.5), 1)

        if overall_score >= 80.0 and len(unconfirmed_gaps) == 0:
            quality_status = "VERIFIED"
            badge = "Verified Data Quality"
        elif overall_score >= 55.0:
            quality_status = "PROVISIONAL"
            badge = "Provisional — Usable with Disclosures"
        elif len(valid_txs) > 0:
            quality_status = "SUSPECT"
            badge = "Suspect — Data Inconsistencies Detected"
        else:
            quality_status = "INSUFFICIENT"
            badge = "Insufficient Data"

        # 9. Persist audit to database
        if persist_audit:
            try:
                db_audit = BusinessDataQualityAudit(
                    business_id=business_id,
                    audit_type="confidence_centre",
                    quality_score=overall_score,
                    overall_quality_status=quality_status,
                    anomalies=[a.model_dump() for a in anomalies_summary],
                    cross_module_discrepancies=[],
                    freshness_summary={k: v.value for k, v in audit_report.freshness_summary.items()},
                    unconfirmed_gaps_count=len(unconfirmed_gaps),
                    duplicate_records_count=duplicate_rows_count,
                )
                self.db.add(db_audit)
                self.db.commit()
            except Exception as exc:
                logger.warning("Failed to persist data quality audit record: %s", exc)

        return DataConfidenceCentreResponse(
            business_id=business_id,
            audit_timestamp=now.isoformat(),
            overall_confidence_score=overall_score,
            overall_quality_status=quality_status,  # type: ignore
            quality_status_badge=badge,
            ingestion_summary=ingestion_summary,
            observation_window=observation_window,
            insight_confidence_matrix=matrix,
            anomalies_detected=anomalies_summary,
            actionable_improvement_checklist=checklist,
            data_limitations=audit_report.data_limitations,
        )
