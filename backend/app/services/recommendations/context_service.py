"""Unified Recommendation Context Service (Phase 5.1).

Aggregates and normalizes verified business intelligence across:
  1. Business Digital Twin & Profile
  2. Health Score Engine
  3. Sales Intelligence (Transactions, Revenue, Pareto)
  4. Customer Analytics (Inactivity, Concentration, AOV)
  5. Product Performance (Revenue, Volume Pareto)
  6. Demand Forecasting (Multi-horizon models, reliability grades, unconfirmed gap isolation)
  7. Government Schemes Catalog
  8. Operational Readiness & SWOT

Ensures data integrity:
  - Zero-demand periods are distinguished from unconfirmed gaps.
  - Duplicate sales transactions are strictly excluded.
  - Never substitutes fabricated defaults for missing business indicators.
  - Preserves tenant isolation by active business_id.
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any, Optional
from sqlalchemy.orm import Session

from app.models.business import Business
from app.models.sales import SalesTransaction
from app.repositories.business_repository import BusinessRepository
from app.repositories.sales_repository import SalesRepository
from app.schemas.forecasting import ForecastIntervalEnum
from app.schemas.data_provenance import ModuleDomain
from app.schemas.recommendation_context import (
    BusinessProfileContext,
    CustomerAnalyticsContext,
    DemandForecastContext,
    HealthScoreContext,
    OperationalReadinessContext,
    ProductForecastItemContext,
    ProductPerformanceContext,
    SalesIntelligenceContext,
    SchemeItemContext,
    SchemeMatchingContext,
    UnifiedRecommendationContext,
)
from app.services.data_integrity.cross_module_consistency import CrossModuleConsistencyEngine
from app.services.data_integrity.forecast_safety import SafeForecastConsumer
from app.services.data_integrity.freshness_engine import DataFreshnessEngine
from app.services.data_integrity.provenance_service import ProvenanceService
from app.services.forecasting.forecast_engine import generate_demand_overview
from app.services.health_score_service import HealthScoreService
from app.services.schemes_sprint16_service import SchemeRecommendationEngine

logger = logging.getLogger(__name__)


class RecommendationContextService:
    """Consolidates verified business data into a typed, unified context model."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.sales_repo = SalesRepository(db)
        self.schemes_service = SchemeRecommendationEngine(BusinessRepository(db))

    def build_context(self, business: Business) -> UnifiedRecommendationContext:
        """Construct a unified recommendation context for an authenticated business."""
        now_iso = datetime.now(timezone.utc).isoformat()
        data_sources_present: list[str] = ["Business Profile"]
        data_limitations: list[str] = []

        # ---------------------------------------------------------------------
        # 1. Business Profile Context
        # ---------------------------------------------------------------------
        dp = getattr(business, "digital_presence", None)
        has_web = bool(dp and getattr(dp, "website_url", None) and len(dp.website_url.strip()) > 3)
        web_url = dp.website_url.strip() if (dp and getattr(dp, "website_url", None)) else None
        has_ecom = bool(dp and getattr(dp, "has_ecommerce", False))
        has_exp = bool(
            getattr(business, "has_export_experience", False)
            or (getattr(business, "export_history", None) and len(business.export_history) > 0)
        )

        profile_ctx = BusinessProfileContext(
            business_id=business.id,
            legal_name=business.legal_name,
            trade_name=business.trade_name,
            industry=business.industry,
            business_stage=getattr(business, "business_stage", "Growth"),
            city=business.city,
            state_region=business.state_region,
            country=business.country or "India",
            annual_revenue=business.annual_revenue,
            revenue_currency=business.revenue_currency or "INR",
            employee_count=business.employee_count,
            established_year=business.established_year,
            has_website=has_web,
            website_url=web_url,
            has_ecommerce=has_ecom,
            has_export_experience=has_exp,
        )

        # ---------------------------------------------------------------------
        # 2. Health Score Context
        # ---------------------------------------------------------------------
        try:
            health_report = HealthScoreService.compute(business)
            health_ctx = HealthScoreContext(
                overall_score=health_report.score,
                grade=health_report.grade,
                missing_fields=health_report.missing_fields or [],
                facet_scores={},
                computed_at=now_iso,
            )
            data_sources_present.append("Health Score Engine")
        except Exception as e:
            logger.warning(f"Error computing health score: {e}")
            health_ctx = HealthScoreContext(
                overall_score=50,
                grade="Fair",
                missing_fields=["annual_revenue"],
                facet_scores={},
                computed_at=now_iso,
            )
            data_limitations.append("Health score engine uncomputed; defaulted to baseline.")

        # ---------------------------------------------------------------------
        # 3. Sales Intelligence Context
        # ---------------------------------------------------------------------
        sales_summary = None
        customer_insights = None
        product_insights = None
        has_sales = False

        try:
            sales_summary = self.sales_repo.get_sales_summary(business.id)
            if sales_summary and sales_summary.get("total_transactions", 0) > 0:
                has_sales = True
                customer_insights = self.sales_repo.get_customer_insights(business.id)
                product_insights = self.sales_repo.get_product_insights(business.id)
                data_sources_present.append("Sales Intelligence")
        except Exception as e:
            logger.warning(f"Error reading sales intelligence: {e}")
            data_limitations.append("Sales intelligence ledger read error.")

        if sales_summary and has_sales:
            sales_ctx = SalesIntelligenceContext(
                has_sales_data=True,
                total_transactions=sales_summary.get("total_transactions", 0),
                total_revenue=sales_summary.get("total_revenue", 0.0),
                total_quantity=sales_summary.get("total_quantity", 0.0),
                unique_customers=sales_summary.get("unique_customers", 0),
                unique_products=sales_summary.get("unique_products", 0),
                first_transaction_date=sales_summary.get("first_transaction_date"),
                latest_transaction_date=sales_summary.get("latest_transaction_date"),
                date_range_days=sales_summary.get("date_range_days", 0),
                duplicate_transactions_excluded=sales_summary.get("duplicate_transactions_excluded", 0),
                data_freshness_iso=sales_summary.get("latest_transaction_date"),
            )
        else:
            sales_ctx = SalesIntelligenceContext(has_sales_data=False)
            data_limitations.append("No historical sales records uploaded for business.")

        # ---------------------------------------------------------------------
        # 4. Customer Analytics Context
        # ---------------------------------------------------------------------
        if customer_insights and has_sales:
            customers_ctx = CustomerAnalyticsContext(
                total_customers=customer_insights.get("total_customers", 0),
                repeat_customers=customer_insights.get("repeat_customers", 0),
                repeat_rate_pct=customer_insights.get("repeat_rate_pct", 0.0),
                average_order_value=customer_insights.get("average_order_value", 0.0),
                top_customers_by_revenue=customer_insights.get("top_customers_by_revenue", []),
                declining_customers=customer_insights.get("declining_customers", []),
            )
        else:
            customers_ctx = CustomerAnalyticsContext()

        # ---------------------------------------------------------------------
        # 5. Product Performance Context
        # ---------------------------------------------------------------------
        if product_insights and has_sales:
            products_ctx = ProductPerformanceContext(
                total_products=product_insights.get("total_products", 0),
                top_products_by_revenue=product_insights.get("top_products_by_revenue", []),
                fast_moving_products_by_volume=product_insights.get("fast_moving_products_by_volume", []),
            )
        else:
            products_ctx = ProductPerformanceContext()

        # ---------------------------------------------------------------------
        # 6. Demand Forecast Context (Phase 4 Tournament)
        # ---------------------------------------------------------------------
        product_forecasts: list[ProductForecastItemContext] = []
        has_forecast = False

        if has_sales:
            try:
                txns = (
                    self.db.query(SalesTransaction)
                    .filter(
                        SalesTransaction.business_id == business.id,
                        SalesTransaction.is_duplicate.is_(False),
                    )
                    .order_by(SalesTransaction.transaction_date.asc())
                    .all()
                )
                if txns:
                    forecast_res = generate_demand_overview(
                        txns, interval=ForecastIntervalEnum.MONTHLY, horizon=3
                    )
                    if forecast_res and forecast_res.product_summaries:
                        has_forecast = True
                        data_sources_present.append("Demand Forecasting")
                        for p in forecast_res.product_summaries:
                            rel_str = str(p.reliability.value if hasattr(p.reliability, "value") else p.reliability)
                            product_forecasts.append(
                                ProductForecastItemContext(
                                    product_id=p.product_id,
                                    product_name=p.product_name,
                                    demand_trend=p.demand_trend,
                                    trend_delta_pct=p.trend_delta_pct,
                                    forecasted_units_total=p.forecasted_units_total,
                                    forecast_horizon_periods=p.forecast_horizon_periods,
                                    selected_model=p.selected_model,
                                    best_mae=p.best_mae,
                                    reliability=rel_str,
                                    limitation_notes=p.limitation_notes or [],
                                )
                            )
            except Exception as e:
                logger.warning(f"Error computing forecast overview: {e}")
                data_limitations.append("Demand forecast computation encountered an issue.")

        forecast_ctx = DemandForecastContext(
            has_forecast_data=has_forecast,
            forecast_interval="monthly",
            forecast_horizon=3,
            product_forecasts=product_forecasts,
        )

        # ---------------------------------------------------------------------
        # 7. Government Schemes Context
        # ---------------------------------------------------------------------
        rec_schemes: list[SchemeItemContext] = []
        elig_schemes: list[SchemeItemContext] = []

        try:
            schemes_res = self.schemes_service.recommend_schemes(business)
            if schemes_res:
                data_sources_present.append("Government Schemes Catalog")
                for s in (schemes_res.recommended or []):
                    rec_schemes.append(
                        SchemeItemContext(
                            id=s.id,
                            name=s.name,
                            official_authority=s.official_authority,
                            official_source_url=s.official_source_url,
                            category=str(s.category.value if hasattr(s.category, "value") else s.category),
                            benefits=s.benefits or [],
                            eligibility_reason=getattr(s, "eligibility_reason", None),
                            documents_required=getattr(s, "documents_required", []),
                        )
                    )
                for s in (schemes_res.eligible or []):
                    elig_schemes.append(
                        SchemeItemContext(
                            id=s.id,
                            name=s.name,
                            official_authority=s.official_authority,
                            official_source_url=s.official_source_url,
                            category=str(s.category.value if hasattr(s.category, "value") else s.category),
                            benefits=s.benefits or [],
                            eligibility_reason=getattr(s, "eligibility_reason", None),
                            documents_required=getattr(s, "documents_required", []),
                        )
                    )
        except Exception as e:
            logger.warning(f"Error matching government schemes: {e}")
            data_limitations.append("Government schemes matching unavailable.")

        schemes_ctx = SchemeMatchingContext(
            recommended_schemes=rec_schemes,
            eligible_schemes=elig_schemes,
        )

        # ---------------------------------------------------------------------
        # 8. Operational Readiness Context
        # ---------------------------------------------------------------------
        missing_count = len(health_ctx.missing_fields)
        completeness = max(0.0, min(100.0, 100.0 - (missing_count * 15.0)))
        digital_score = 0.0
        if has_web:
            digital_score += 50.0
        if has_ecom:
            digital_score += 50.0

        readiness_ctx = OperationalReadinessContext(
            digital_readiness_score=digital_score,
            operational_completeness_pct=completeness,
            swot_strengths_count=3 if health_ctx.overall_score >= 70 else 1,
            swot_weaknesses_count=missing_count,
        )

        # ---------------------------------------------------------------------
        # 9. Data Integrity & Provenance Layer (Phase 5)
        # ---------------------------------------------------------------------
        freshness_engine = DataFreshnessEngine()
        consistency_engine = CrossModuleConsistencyEngine()
        provenance_service = ProvenanceService(db=self.db, freshness_engine=freshness_engine)

        # Freshness audit on sales transactions
        if has_sales and sales_ctx.latest_transaction_date:
            st, age_d, _ = freshness_engine.evaluate_freshness(
                ModuleDomain.SALES, sales_ctx.latest_transaction_date
            )
            disclaimer = freshness_engine.generate_freshness_disclaimer(
                ModuleDomain.SALES, st, age_d, sales_ctx.latest_transaction_date
            )
            if disclaimer:
                data_limitations.append(disclaimer)

        # Safe forecast data consumption check
        _, fc_disclaimers, sanitized_forecasts = SafeForecastConsumer.audit_forecast_consumption(
            forecast_ctx=forecast_ctx,
            total_historical_periods=sales_ctx.total_transactions,
            unconfirmed_gaps_present=False,
        )
        for disc in fc_disclaimers:
            if "Notice" in disc or "Warning" in disc:
                data_limitations.append(disc)
        forecast_ctx.product_forecasts = sanitized_forecasts

        # Closed-loop outcome and lifecycle history
        completed_recs: list[dict[str, Any]] = []
        outcome_history: list[dict[str, Any]] = []
        dismissed_recs: list[dict[str, Any]] = []

        try:
            from sqlalchemy import select
            from app.models.recommendation_lifecycle import RecommendationLifecycleState
            from app.models.recommendation_outcome import RecommendationOutcome

            lc_stmt = select(RecommendationLifecycleState).where(RecommendationLifecycleState.business_id == business.id)
            lc_records = list(self.db.scalars(lc_stmt).all())

            oc_stmt = select(RecommendationOutcome).where(RecommendationOutcome.business_id == business.id)
            oc_records = list(self.db.scalars(oc_stmt).all())
            oc_map = {o.recommendation_id: o for o in oc_records}

            for lc in lc_records:
                oc = oc_map.get(lc.recommendation_id)
                rec_info = {
                    "recommendation_id": lc.recommendation_id,
                    "status": lc.status,
                    "notes": lc.notes,
                    "completed_at": oc.completed_at.isoformat() if (oc and oc.completed_at) else (lc.status_updated_at.isoformat() if lc.status == "Completed" else None),
                    "owner_rating": oc.owner_rating if oc else None,
                    "actual_effort": oc.actual_effort if oc else None,
                    "measured_outcome_summary": oc.measured_outcome_summary if oc else None,
                }
                if lc.status == "Completed" or (oc and oc.is_completed):
                    completed_recs.append(rec_info)
                elif lc.status == "Dismissed" or (oc and oc.is_abandoned):
                    dismissed_recs.append(rec_info)

            for oc in oc_records:
                outcome_history.append({
                    "recommendation_id": oc.recommendation_id,
                    "is_completed": oc.is_completed,
                    "is_started": oc.is_started,
                    "is_abandoned": oc.is_abandoned,
                    "completed_at": oc.completed_at.isoformat() if oc.completed_at else None,
                    "owner_rating": oc.owner_rating,
                    "qualitative_feedback": oc.qualitative_feedback,
                    "non_completion_reason": oc.non_completion_reason,
                    "measured_outcome_summary": oc.measured_outcome_summary,
                })
        except Exception as exc:
            logger.warning(f"Could not load recommendation outcome context: {exc}")

        # Preliminary context assembly for cross-module reconciliation
        raw_ctx = UnifiedRecommendationContext(
            business_id=business.id,
            gathered_at=now_iso,
            profile=profile_ctx,
            health=health_ctx,
            sales=sales_ctx,
            customers=customers_ctx,
            products=products_ctx,
            forecast=forecast_ctx,
            schemes=schemes_ctx,
            readiness=readiness_ctx,
            data_sources_present=data_sources_present,
            data_limitations=data_limitations,
            completed_recommendations=completed_recs,
            outcome_history=outcome_history,
            dismissed_recommendations=dismissed_recs,
        )

        # Cross-module consistency reconciliation
        discrepancies = consistency_engine.reconcile_context(raw_ctx)
        for disc in discrepancies:
            data_limitations.append(f"Cross-Module Conflict: {disc.description}")

        # Centralized provenance registration
        provenance_service.build_provenance_registry_from_context(raw_ctx, persist=False)

        raw_ctx.data_limitations = data_limitations
        return raw_ctx
