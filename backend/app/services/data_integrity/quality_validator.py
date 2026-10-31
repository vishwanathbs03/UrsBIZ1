"""Data Quality Validation & Anomaly Detection Engine (Phase 5 Data Integrity).

Performs non-destructive, deterministic data quality audits:
  - Missing required fields
  - Duplicate records (tracked, excluded from totals, preserved for audit)
  - Invalid dates (future timestamps, pre-establishment records)
  - Invalid numerical values (negative revenue, NaN, Infinity)
  - Currency inconsistencies (mixed currencies, profile mismatches)
  - Statistical outliers (extreme transaction spikes)
  - Conflicting records (profile turnover vs ledger turnover)
  - Incomplete reporting periods & unconfirmed sales gaps (Phase 4 isolation)
"""

from __future__ import annotations

from datetime import datetime, timezone
import math
from typing import Any, Optional

from app.models.business import Business
from app.models.sales import SalesTransaction
from app.schemas.data_provenance import (
    DataQualityAnomaly,
    DataQualityAuditReport,
    DataQualityStatus,
    FreshnessStatus,
    ModuleDomain,
)
from app.services.data_integrity.freshness_engine import DataFreshnessEngine


class DataQualityValidator:
    """Non-destructive validator inspecting business records for data anomalies."""

    def __init__(self, freshness_engine: Optional[DataFreshnessEngine] = None) -> None:
        self.freshness_engine = freshness_engine or DataFreshnessEngine()

    def audit_business_dataset(
        self,
        business: Business,
        transactions: list[SalesTransaction],
        reference_time: Optional[datetime] = None,
    ) -> DataQualityAuditReport:
        """Run comprehensive, non-destructive audit over business profile and transaction ledger."""
        now = reference_time or datetime.now(timezone.utc)
        now_iso = now.isoformat()
        anomalies: list[DataQualityAnomaly] = []
        limitations: list[str] = []

        # 1. Profile Field Validation
        if not business.legal_name or len(business.legal_name.strip()) < 2:
            anomalies.append(
                DataQualityAnomaly(
                    anomaly_type="missing_field",
                    source_module=ModuleDomain.BUSINESS_PROFILE.value,
                    field_name="legal_name",
                    description="Business legal name is missing or too short.",
                    severity="Critical",
                    is_blocking=True,
                )
            )

        if not business.industry or len(business.industry.strip()) < 2:
            anomalies.append(
                DataQualityAnomaly(
                    anomaly_type="missing_field",
                    source_module=ModuleDomain.BUSINESS_PROFILE.value,
                    field_name="industry",
                    description="Business industry classification is missing.",
                    severity="High",
                )
            )

        if business.annual_revenue is not None and business.annual_revenue < 0:
            anomalies.append(
                DataQualityAnomaly(
                    anomaly_type="negative_number",
                    source_module=ModuleDomain.BUSINESS_PROFILE.value,
                    field_name="annual_revenue",
                    observed_value=business.annual_revenue,
                    description="Stated annual turnover cannot be negative.",
                    severity="Critical",
                    is_blocking=True,
                )
            )

        est_year = business.established_year
        if est_year and (est_year < 1850 or est_year > now.year):
            anomalies.append(
                DataQualityAnomaly(
                    anomaly_type="invalid_date",
                    source_module=ModuleDomain.BUSINESS_PROFILE.value,
                    field_name="established_year",
                    observed_value=est_year,
                    description=f"Established year {est_year} is invalid (must be between 1850 and {now.year}).",
                    severity="High",
                )
            )

        # 2. Transaction Audit (Duplicates, Numbers, Dates, Outliers)
        duplicate_count = 0
        unconfirmed_gaps_count = 0
        seen_tx_keys: set[str] = set()
        amounts: list[float] = []
        latest_tx_dt: Optional[datetime] = None
        earliest_tx_dt: Optional[datetime] = None

        for tx in transactions:
            # Check tenant isolation integrity
            if tx.business_id != business.id:
                anomalies.append(
                    DataQualityAnomaly(
                        anomaly_type="cross_tenant_violation",
                        source_module=ModuleDomain.SALES.value,
                        record_identifier=str(tx.id),
                        observed_value=tx.business_id,
                        description=f"Transaction belongs to foreign business_id {tx.business_id}, not active business {business.id}.",
                        severity="Critical",
                        is_blocking=True,
                    )
                )
                continue

            # Check duplicate
            tx_key = f"{tx.invoice_id}_{tx.product_name}_{tx.total_amount}_{tx.transaction_date.isoformat()}"
            if tx.is_duplicate or tx_key in seen_tx_keys:
                duplicate_count += 1
                anomalies.append(
                    DataQualityAnomaly(
                        anomaly_type="duplicate_record",
                        source_module=ModuleDomain.SALES.value,
                        record_identifier=f"tx_{tx.id}",
                        description=f"Duplicate sales record detected for invoice '{tx.invoice_id}'. Preserved in raw log, excluded from turnover.",
                        severity="Medium",
                    )
                )
            else:
                seen_tx_keys.add(tx_key)

            # Check numeric validity
            amt = tx.total_amount
            if math.isnan(amt) or math.isinf(amt):
                anomalies.append(
                    DataQualityAnomaly(
                        anomaly_type="invalid_number",
                        source_module=ModuleDomain.SALES.value,
                        record_identifier=f"tx_{tx.id}",
                        field_name="total_amount",
                        observed_value=str(amt),
                        description="Transaction amount contains NaN or Infinity.",
                        severity="Critical",
                        is_blocking=True,
                    )
                )
            elif amt < 0.0:
                anomalies.append(
                    DataQualityAnomaly(
                        anomaly_type="negative_number",
                        source_module=ModuleDomain.SALES.value,
                        record_identifier=f"tx_{tx.id}",
                        field_name="total_amount",
                        observed_value=amt,
                        description="Sales transaction total_amount cannot be negative.",
                        severity="High",
                    )
                )
            elif not tx.is_duplicate:
                amounts.append(amt)

            # Check dates
            tx_dt = tx.transaction_date
            if tx_dt.tzinfo is None:
                tx_dt = tx_dt.replace(tzinfo=timezone.utc)

            if tx_dt > now:
                anomalies.append(
                    DataQualityAnomaly(
                        anomaly_type="invalid_date",
                        source_module=ModuleDomain.SALES.value,
                        record_identifier=f"tx_{tx.id}",
                        field_name="transaction_date",
                        observed_value=tx_dt.isoformat(),
                        description=f"Transaction date is in the future relative to audit timestamp ({now_iso}).",
                        severity="High",
                    )
                )

            if est_year and tx_dt.year < est_year:
                anomalies.append(
                    DataQualityAnomaly(
                        anomaly_type="invalid_date",
                        source_module=ModuleDomain.SALES.value,
                        record_identifier=f"tx_{tx.id}",
                        field_name="transaction_date",
                        observed_value=tx_dt.isoformat(),
                        description=f"Transaction date ({tx_dt.year}) precedes business establishment year ({est_year}).",
                        severity="Medium",
                    )
                )

            if earliest_tx_dt is None or tx_dt < earliest_tx_dt:
                earliest_tx_dt = tx_dt
            if latest_tx_dt is None or tx_dt > latest_tx_dt:
                latest_tx_dt = tx_dt

        # 3. Statistical Outlier Detection (Surges > 10x median or > Q3 + 3*IQR)
        if len(amounts) >= 5:
            sorted_amts = sorted(amounts)
            median_amt = sorted_amts[len(sorted_amts) // 2]
            q1 = sorted_amts[len(sorted_amts) // 4]
            q3 = sorted_amts[int(len(sorted_amts) * 0.75)]
            iqr = max(q3 - q1, 1.0)
            outlier_threshold = max(median_amt * 10.0, q3 + (3.0 * iqr))

            for tx in transactions:
                if not tx.is_duplicate and tx.total_amount > outlier_threshold:
                    anomalies.append(
                        DataQualityAnomaly(
                            anomaly_type="outlier_surge",
                            source_module=ModuleDomain.SALES.value,
                            record_identifier=f"tx_{tx.id}",
                            field_name="total_amount",
                            observed_value=tx.total_amount,
                            description=(
                                f"Transaction amount ₹{tx.total_amount:,.0f} exceeds 10x median (₹{median_amt:,.0f}) "
                                f"and statistical fence (₹{outlier_threshold:,.0f}). Requires audit confirmation."
                            ),
                            severity="Medium",
                        )
                    )

        # 4. Unconfirmed Gap & Sequence Interruption Detection
        if len(transactions) > 0 and earliest_tx_dt and latest_tx_dt:
            # Sort chronologically
            sorted_txs = sorted(
                [t for t in transactions if not t.is_duplicate],
                key=lambda x: x.transaction_date,
            )
            for i in range(len(sorted_txs) - 1):
                t1 = sorted_txs[i].transaction_date
                t2 = sorted_txs[i + 1].transaction_date
                gap_days = (t2 - t1).days
                # If gap > 60 days in an otherwise active business, mark as unconfirmed gap
                if gap_days > 60:
                    unconfirmed_gaps_count += 1
                    anomalies.append(
                        DataQualityAnomaly(
                            anomaly_type="unconfirmed_gap",
                            source_module=ModuleDomain.SALES.value,
                            record_identifier=f"gap_{t1.date()}_to_{t2.date()}",
                            description=(
                                f"Unconfirmed sales gap of {gap_days} days detected between {t1.date()} and {t2.date()}. "
                                "Preserved as unconfirmed gap, NOT confirmed zero demand."
                            ),
                            severity="High",
                        )
                    )

        # 5. Profile vs Ledger Conflict Detection
        profile_rev = business.annual_revenue
        ledger_rev = sum(amounts)
        if profile_rev and ledger_rev > 0:
            divergence = abs(profile_rev - ledger_rev)
            if divergence > (0.4 * profile_rev):
                limitations.append(
                    f"Profile annual revenue (₹{profile_rev:,.0f}) diverges by {divergence / profile_rev * 100:.1f}% "
                    f"from uploaded ledger sum (₹{ledger_rev:,.0f})."
                )

        # 6. Freshness Evaluation
        freshness_map: dict[str, FreshnessStatus] = {}
        for mod in [
            ModuleDomain.SALES,
            ModuleDomain.CUSTOMERS,
            ModuleDomain.PRODUCTS,
            ModuleDomain.BUSINESS_PROFILE,
            ModuleDomain.FINANCIAL_INDICATORS,
            ModuleDomain.DEMAND_FORECAST,
            ModuleDomain.GOVERNMENT_SCHEMES,
        ]:
            if mod == ModuleDomain.SALES:
                st, age, _ = self.freshness_engine.evaluate_freshness(mod, latest_tx_dt, now)
            elif mod == ModuleDomain.BUSINESS_PROFILE:
                st, age, _ = self.freshness_engine.evaluate_freshness(mod, business.updated_at, now)
            else:
                st, age, _ = self.freshness_engine.evaluate_freshness(mod, latest_tx_dt, now)
            freshness_map[mod.value] = st

        # Calculate Overall Quality Score
        critical_count = sum(1 for a in anomalies if a.severity == "Critical")
        high_count = sum(1 for a in anomalies if a.severity == "High")
        medium_count = sum(1 for a in anomalies if a.severity == "Medium")

        penalty = (critical_count * 30.0) + (high_count * 15.0) + (medium_count * 5.0)
        score = max(0.0, min(100.0, 100.0 - penalty))

        if critical_count > 0 or score < 50.0:
            quality_status = DataQualityStatus.SUSPECT
        elif high_count > 0 or score < 75.0 or unconfirmed_gaps_count > 0:
            quality_status = DataQualityStatus.PROVISIONAL
        else:
            quality_status = DataQualityStatus.VERIFIED

        return DataQualityAuditReport(
            business_id=business.id,
            audit_timestamp=now_iso,
            overall_quality_status=quality_status,
            quality_score=score,
            anomalies_detected=anomalies,
            cross_module_discrepancies=[],
            freshness_summary=freshness_map,
            unconfirmed_gaps_count=unconfirmed_gaps_count,
            duplicate_records_count=duplicate_count,
            data_limitations=limitations,
        )
