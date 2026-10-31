"""Centralized Business Data Provenance Service (Phase 5 Data Integrity).

Maintains verifiable provenance metadata, lineage chains, and source references
for every important business metric across UrsBiz.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from typing import Any, Optional
from sqlalchemy.orm import Session

from app.models.data_provenance import BusinessDataProvenance, BusinessDataQualityAudit
from app.schemas.data_provenance import (
    DataProvenanceRecord,
    DataQualityAuditReport,
    DataQualityStatus,
    FreshnessStatus,
    MetricNature,
    ModuleDomain,
)
from app.schemas.recommendation_context import UnifiedRecommendationContext
from app.services.data_integrity.freshness_engine import DataFreshnessEngine

logger = logging.getLogger("ursbiz.provenance_service")


class ProvenanceService:
    """Manages creation, retrieval, and database persistence of metric provenance records."""

    def __init__(
        self,
        db: Optional[Session] = None,
        freshness_engine: Optional[DataFreshnessEngine] = None,
    ) -> None:
        self.db = db
        self.freshness_engine = freshness_engine or DataFreshnessEngine()
        # Thread-safe in-memory cache for fast lookups: (business_id, metric_name) -> DataProvenanceRecord
        self._in_memory_registry: dict[tuple[int, str], DataProvenanceRecord] = {}

    def register_metric(
        self,
        record: DataProvenanceRecord,
        persist: bool = True,
    ) -> DataProvenanceRecord:
        """Register metric provenance in-memory and optionally persist to database."""
        key = (record.business_id, record.metric_name)
        self._in_memory_registry[key] = record

        if persist and self.db:
            try:
                db_record = BusinessDataProvenance(
                    business_id=record.business_id,
                    metric_name=record.metric_name,
                    metric_value=record.metric_value,
                    source_module=record.source_module.value,
                    source_record_ref=record.source_record_ref,
                    measurement_period=record.measurement_period,
                    unit=record.unit,
                    currency=record.currency,
                    calculation_methodology=record.calculation_methodology,
                    data_quality_status=record.data_quality_status.value,
                    nature=record.nature.value,
                    freshness_status=record.freshness_status.value,
                    freshness_as_of=(
                        datetime.fromisoformat(record.freshness_as_of.replace("Z", "+00:00"))
                        if record.freshness_as_of
                        else None
                    ),
                    confidence_score=record.confidence_score,
                )
                self.db.add(db_record)
                self.db.commit()
            except Exception as e:
                logger.warning(f"Failed to persist provenance record to DB (continuing in-memory): {e}")
                if self.db:
                    self.db.rollback()

        return record

    def get_provenance(
        self, business_id: int, metric_name: str
    ) -> Optional[DataProvenanceRecord]:
        """Fetch provenance for a specific business metric."""
        key = (business_id, metric_name)
        if key in self._in_memory_registry:
            return self._in_memory_registry[key]

        if self.db:
            try:
                row = (
                    self.db.query(BusinessDataProvenance)
                    .filter(
                        BusinessDataProvenance.business_id == business_id,
                        BusinessDataProvenance.metric_name == metric_name,
                    )
                    .order_by(BusinessDataProvenance.created_at.desc())
                    .first()
                )
                if row:
                    rec = DataProvenanceRecord(
                        metric_name=row.metric_name,
                        metric_value=row.metric_value,
                        business_id=row.business_id,
                        source_module=ModuleDomain(row.source_module),
                        source_record_ref=row.source_record_ref,
                        measurement_period=row.measurement_period,
                        unit=row.unit,
                        currency=row.currency,
                        calculation_methodology=row.calculation_methodology,
                        last_updated_at=row.updated_at.isoformat() if row.updated_at else datetime.now(timezone.utc).isoformat(),
                        data_quality_status=DataQualityStatus(row.data_quality_status),
                        nature=MetricNature(row.nature),
                        freshness_status=FreshnessStatus(row.freshness_status),
                        freshness_as_of=row.freshness_as_of.isoformat() if row.freshness_as_of else None,
                        confidence_score=row.confidence_score,
                    )
                    self._in_memory_registry[key] = rec
                    return rec
            except Exception as e:
                logger.warning(f"Error querying provenance record from DB: {e}")

        return None

    def build_provenance_registry_from_context(
        self,
        ctx: UnifiedRecommendationContext,
        persist: bool = False,
    ) -> dict[str, DataProvenanceRecord]:
        """Extract and register complete provenance lineage from UnifiedRecommendationContext."""
        now_iso = datetime.now(timezone.utc).isoformat()
        records: dict[str, DataProvenanceRecord] = {}
        biz_id = ctx.business_id

        # 1. Total Revenue Metric
        if ctx.sales.has_sales_data and ctx.sales.total_revenue > 0:
            tx_period = (
                f"{ctx.sales.first_transaction_date or 'Start'} to {ctx.sales.latest_transaction_date or 'Latest'}"
            )
            fresh_status, age_days, _ = self.freshness_engine.evaluate_freshness(
                ModuleDomain.SALES, ctx.sales.latest_transaction_date
            )
            rec = DataProvenanceRecord(
                metric_name="total_revenue",
                metric_value=ctx.sales.total_revenue,
                business_id=biz_id,
                source_module=ModuleDomain.SALES,
                source_record_ref=f"sales_transactions:business_{biz_id}:non_duplicate_rows",
                measurement_period=tx_period,
                unit="INR",
                currency="INR",
                calculation_methodology="Sum of non-duplicate sales transaction total_amount records",
                last_updated_at=now_iso,
                data_quality_status=DataQualityStatus.VERIFIED,
                nature=MetricNature.ACTUAL,
                freshness_status=fresh_status,
                freshness_as_of=ctx.sales.latest_transaction_date,
                confidence_score=100.0,
            )
            records["total_revenue"] = self.register_metric(rec, persist=persist)

        # 2. Top Customer Concentration Ratio
        if ctx.customers.top_customers_by_revenue and ctx.sales.total_revenue > 0:
            top1 = ctx.customers.top_customers_by_revenue[0]
            top_rev = float(top1.get("revenue", 0.0))
            pct = (top_rev / ctx.sales.total_revenue) * 100.0
            cust_name = top1.get("customer_name") or "Primary Customer"

            fresh_status, _, _ = self.freshness_engine.evaluate_freshness(
                ModuleDomain.CUSTOMERS, ctx.sales.latest_transaction_date
            )
            rec = DataProvenanceRecord(
                metric_name="top_customer_concentration_pct",
                metric_value=round(pct, 2),
                business_id=biz_id,
                source_module=ModuleDomain.CUSTOMERS,
                source_record_ref=f"customer_ledgers:top_client_{cust_name.lower().replace(' ', '_')}",
                measurement_period="Recorded Historical Horizon",
                unit="percentage",
                currency=None,
                calculation_methodology="Top-1 customer aggregate turnover divided by total business sales turnover",
                last_updated_at=now_iso,
                data_quality_status=DataQualityStatus.VERIFIED,
                nature=MetricNature.CALCULATED,
                freshness_status=fresh_status,
                freshness_as_of=ctx.sales.latest_transaction_date,
                confidence_score=95.0,
            )
            records["top_customer_concentration_pct"] = self.register_metric(rec, persist=persist)

        # 3. Phase 4 Demand Forecast
        if ctx.forecast and ctx.forecast.product_forecasts:
            top_fc = ctx.forecast.product_forecasts[0]
            sku = getattr(top_fc, "product_name", "Top Product")
            fc_units = getattr(top_fc, "forecasted_units_total", 0.0)
            model_name = getattr(top_fc, "selected_model", "croston")

            rec = DataProvenanceRecord(
                metric_name="forecasted_demand_30d",
                metric_value=fc_units,
                business_id=biz_id,
                source_module=ModuleDomain.DEMAND_FORECAST,
                source_record_ref=f"phase4_forecasting:sku_{sku.lower().replace(' ', '_')}:model_{model_name}",
                measurement_period=f"Next {ctx.forecast.forecast_horizon} Months",
                unit="units",
                currency=None,
                calculation_methodology=f"Phase 4 Tournament Selected Model ({model_name}) with unconfirmed gap isolation",
                last_updated_at=now_iso,
                data_quality_status=DataQualityStatus.PROVISIONAL,
                nature=MetricNature.FORECASTED,
                freshness_status=FreshnessStatus.FRESH,
                freshness_as_of=now_iso,
                confidence_score=85.0,
            )
            records["forecasted_demand_30d"] = self.register_metric(rec, persist=persist)

        # 4. Business Health Score
        if ctx.health.overall_score is not None:
            rec = DataProvenanceRecord(
                metric_name="business_health_score",
                metric_value=ctx.health.overall_score,
                business_id=biz_id,
                source_module=ModuleDomain.HEALTH_SCORE,
                source_record_ref="health_score_engine:v2_diagnostic",
                measurement_period="Current Assessment",
                unit="score",
                currency=None,
                calculation_methodology="Multi-facet weighted scoring across financial, operational, and market completeness",
                last_updated_at=now_iso,
                data_quality_status=DataQualityStatus.VERIFIED,
                nature=MetricNature.CALCULATED,
                freshness_status=FreshnessStatus.FRESH,
                freshness_as_of=now_iso,
                confidence_score=95.0,
            )
            records["business_health_score"] = self.register_metric(rec, persist=persist)

        return records

    def record_audit_report(self, report: DataQualityAuditReport) -> None:
        """Persist data quality audit execution to database."""
        if not self.db:
            return

        try:
            audit_row = BusinessDataQualityAudit(
                business_id=report.business_id,
                audit_type="comprehensive",
                quality_score=report.quality_score,
                overall_quality_status=report.overall_quality_status.value,
                anomalies=[a.model_dump() for a in report.anomalies_detected],
                cross_module_discrepancies=[d.model_dump() for d in report.cross_module_discrepancies],
                freshness_summary={k: v.value for k, v in report.freshness_summary.items()},
                unconfirmed_gaps_count=report.unconfirmed_gaps_count,
                duplicate_records_count=report.duplicate_records_count,
            )
            self.db.add(audit_row)
            self.db.commit()
        except Exception as e:
            logger.warning(f"Failed to persist quality audit report to DB: {e}")
            if self.db:
                self.db.rollback()
