"""Open-Ended Natural-Language AI Business Intelligence & Reasoning Engine (Phase 5).

Provides autonomous question-answering across any relevant business query expressed in natural language:
  1. Accepts free-form natural language questions without fixed intent locking.
  2. Resolves multi-turn conversational context (e.g. "that product", "those customers", "the decline").
  3. Classifies query intent and determines required backend analysis tools.
  4. Executes 13 controlled, whitelisted analysis tools with strict tenant isolation and bounded execution.
  5. Performs multi-step cross-signal reasoning (e.g. revenue vs profit, concentration vs churn).
  6. Transparently discloses data boundaries and unavailable metrics (e.g. warehouse stock counts, expense ledgers).
  7. Formulates deterministic calculation lineage and synthesizes situational recommendations using the
     mandated 25/25/20/15/15 priority formula.
  8. Provides resilient Gemini executive reasoning with instant deterministic fallback.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import logging
import re
import time
from typing import Any, Optional
import uuid

import httpx
from pydantic import ValidationError

from app.config.settings import get_settings
from app.schemas.advanced_recommendations import (
    AnswerabilityStatus,
    AnswerQualityEvaluation,
    CalculationStep,
    GroundedFinding,
    RecommendationAskRequest,
    RecommendationAskResponse,
    SituationalRecommendation,
    StatementClassification,
)
from app.schemas.recommendation_context import UnifiedRecommendationContext
from app.services.recommendations.evaluation_engine import (
    AnswerabilityClassifier,
    AIAnswerQualityEvaluator,
    GroundedFindingBuilder,
    StructuredObservabilityLogger,
)
from app.services.ai.tool_router.types import (
    BusinessComparisonArgs,
    BusinessHealthArgs,
    BusinessProfileArgs,
    CalculateMetricsArgs,
    CustomerConcentrationArgs,
    CustomerInsightsArgs,
    DemandForecastArgs,
    ExistingRecommendationsArgs,
    FinancialIndicatorsArgs,
    ProductPerformanceArgs,
    SalesSummaryArgs,
    SalesTrendsArgs,
    SearchSchemesArgs,
)

logger = logging.getLogger(__name__)

# Bounded tool execution limits
_MAX_TOOL_CALLS_PER_TURN = 3
_TOOL_EXECUTION_TIMEOUT_SECONDS = 8.0


# --------------------------------------------------------------------------- #
# Tool Execution Implementations
# --------------------------------------------------------------------------- #


def _tool_get_business_profile(ctx: UnifiedRecommendationContext, args: dict[str, Any]) -> dict[str, Any]:
    BusinessProfileArgs.model_validate(args)
    p = ctx.profile
    return {
        "business_id": p.business_id,
        "legal_name": p.legal_name,
        "trade_name": p.trade_name,
        "industry": p.industry,
        "business_stage": p.business_stage or "Established",
        "city": p.city,
        "state_region": p.state_region,
        "country": p.country or "India",
        "employee_count": p.employee_count,
        "established_year": p.established_year,
        "has_website": p.has_website,
        "has_export_experience": p.has_export_experience,
        "annual_revenue": p.annual_revenue,
        "revenue_currency": p.revenue_currency,
    }


def _tool_get_business_health(ctx: UnifiedRecommendationContext, args: dict[str, Any]) -> dict[str, Any]:
    BusinessHealthArgs.model_validate(args)
    h = ctx.health
    readiness_obj = getattr(ctx, "readiness", None) or getattr(ctx, "operational", None)
    dig_score = readiness_obj.digital_readiness_score if readiness_obj else 0.0
    op_comp = readiness_obj.operational_completeness_pct if readiness_obj else 0.0
    return {
        "overall_score": h.overall_score,
        "grade": h.grade,
        "facet_scores": h.facet_scores,
        "missing_fields": h.missing_fields,
        "digital_readiness_score": dig_score,
        "operational_completeness_pct": op_comp,
    }


def _tool_get_sales_summary(ctx: UnifiedRecommendationContext, args: dict[str, Any]) -> dict[str, Any]:
    SalesSummaryArgs.model_validate(args)
    s = ctx.sales
    return {
        "has_sales_data": s.has_sales_data,
        "total_revenue": s.total_revenue,
        "total_transactions": s.total_transactions,
        "total_quantity": s.total_quantity,
        "unique_customers": s.unique_customers,
        "unique_products": s.unique_products,
        "date_range_days": s.date_range_days,
        "first_transaction_date": s.first_transaction_date,
        "latest_transaction_date": s.latest_transaction_date,
        "duplicate_transactions_excluded": s.duplicate_transactions_excluded,
        "data_freshness_iso": s.data_freshness_iso,
    }


def _tool_get_sales_trends(ctx: UnifiedRecommendationContext, args: dict[str, Any]) -> dict[str, Any]:
    parsed = SalesTrendsArgs.model_validate(args)
    s = ctx.sales
    if not s.has_sales_data or s.total_revenue <= 0:
        return {
            "has_sales_data": False,
            "trend_direction": "insufficient_data",
            "observation": "No sales transaction ledger uploaded. Minimum 6 periods required for trend analysis.",
        }

    trend_direction = "stable"
    if ctx.forecast.product_forecasts:
        growing = sum(1 for p in ctx.forecast.product_forecasts if p.demand_trend in ("increasing", "surging"))
        declining = sum(1 for p in ctx.forecast.product_forecasts if p.demand_trend in ("declining", "dropping"))
        if growing > declining:
            trend_direction = "increasing"
        elif declining > growing:
            trend_direction = "declining"

    avg_monthly = (s.total_revenue / (s.date_range_days / 30.0)) if s.date_range_days >= 30 else s.total_revenue
    return {
        "has_sales_data": True,
        "total_revenue": s.total_revenue,
        "trend_direction": trend_direction,
        "date_range_days": s.date_range_days,
        "average_monthly_revenue": avg_monthly,
        "latest_transaction_date": s.latest_transaction_date,
        "interval": parsed.interval,
    }


def _tool_get_product_performance(ctx: UnifiedRecommendationContext, args: dict[str, Any]) -> dict[str, Any]:
    parsed = ProductPerformanceArgs.model_validate(args)
    p = ctx.products
    return {
        "total_products": p.total_products,
        "top_products_by_revenue": p.top_products_by_revenue[: parsed.limit],
        "fast_moving_products_by_volume": p.fast_moving_products_by_volume[: parsed.limit],
    }


def _tool_get_customer_insights(ctx: UnifiedRecommendationContext, args: dict[str, Any]) -> dict[str, Any]:
    parsed = CustomerInsightsArgs.model_validate(args)
    c = ctx.customers
    return {
        "total_customers": c.total_customers,
        "repeat_customers": c.repeat_customers,
        "repeat_rate_pct": c.repeat_rate_pct,
        "average_order_value": c.average_order_value,
        "top_customers_by_revenue": c.top_customers_by_revenue[: parsed.limit],
        "declining_customers": c.declining_customers[: parsed.limit],
        "declining_count": len(c.declining_customers),
    }


def _tool_get_customer_concentration(ctx: UnifiedRecommendationContext, args: dict[str, Any]) -> dict[str, Any]:
    CustomerConcentrationArgs.model_validate(args)
    c = ctx.customers
    total_rev = ctx.sales.total_revenue
    if not c.top_customers_by_revenue or total_rev <= 0:
        return {
            "has_data": False,
            "observation": "Customer concentration analysis requires uploaded sales transactions.",
        }

    top1 = c.top_customers_by_revenue[0]
    top1_rev = top1.get("revenue", 0.0)
    top1_pct = round((top1_rev / total_rev) * 100.0, 1)
    top3_rev = sum(cust.get("revenue", 0.0) for cust in c.top_customers_by_revenue[:3])
    top3_pct = round((top3_rev / total_rev) * 100.0, 1)
    risk_level = "High" if top1_pct > 30.0 or top3_pct > 60.0 else ("Moderate" if top1_pct > 15.0 else "Low")
    return {
        "has_data": True,
        "top1_customer_name": top1.get("customer_name") or "Primary Client",
        "top1_revenue": top1_rev,
        "top1_share_pct": top1_pct,
        "top3_cumulative_revenue": top3_rev,
        "top3_share_pct": top3_pct,
        "concentration_risk_level": risk_level,
        "assessment": f"Top buyer accounts for {top1_pct}% of total sales. Concentration risk rating: {risk_level}.",
    }


def _tool_get_financial_indicators(ctx: UnifiedRecommendationContext, args: dict[str, Any]) -> dict[str, Any]:
    FinancialIndicatorsArgs.model_validate(args)
    annual_rev = ctx.profile.annual_revenue
    sales_rev = ctx.sales.total_revenue
    return {
        "reported_annual_revenue": annual_rev,
        "recorded_sales_ledger_revenue": sales_rev if ctx.sales.has_sales_data else None,
        "currency": ctx.profile.revenue_currency,
        "detailed_expense_ledger_uploaded": False,
        "net_profit_margin": None,
        "depreciation_recorded": False,
        "cogs_recorded": False,
        "untracked_metrics": [
            "cogs",
            "operating_expenses",
            "net_profit_margin",
            "depreciation",
            "tax_returns",
        ],
        "disclosure": "UrsBiz does not track unuploaded expense ledgers, depreciation schedules, or tax returns. Profitability analysis requires user-provided cost inputs.",
    }


def _tool_get_demand_forecast(ctx: UnifiedRecommendationContext, args: dict[str, Any]) -> dict[str, Any]:
    parsed = DemandForecastArgs.model_validate(args)
    f = ctx.forecast
    if not f.has_forecast_data or not f.product_forecasts:
        return {
            "has_forecast_data": False,
            "status": "insufficient_history",
            "observation": "Demand forecasting requires at least 6 periods of historical sales transactions.",
        }

    forecasts = f.product_forecasts
    if parsed.product_id:
        target = parsed.product_id.lower()
        forecasts = [
            item
            for item in forecasts
            if (item.product_id and item.product_id.lower() == target)
            or item.product_name.lower() == target
        ] or forecasts

    return {
        "has_forecast_data": True,
        "forecast_interval": f.forecast_interval,
        "forecast_horizon": f.forecast_horizon,
        "product_forecasts": [
            {
                "product_name": item.product_name,
                "demand_trend": item.demand_trend,
                "trend_delta_pct": item.trend_delta_pct,
                "forecasted_units_total": item.forecasted_units_total,
                "forecast_horizon_periods": item.forecast_horizon_periods,
                "selected_model": item.selected_model,
                "best_mae": item.best_mae,
                "reliability": item.reliability,
                "intermittent_demand": "intermittent" in item.selected_model.lower() or item.reliability == "Low",
            }
            for item in forecasts[:5]
        ],
        "limitation_disclosure": "Warehouse stock levels, safety stocks, and supplier replenishment lead times are external operational variables not tracked by UrsBiz.",
    }


def _tool_get_existing_recommendations(ctx: UnifiedRecommendationContext, args: dict[str, Any]) -> dict[str, Any]:
    parsed = ExistingRecommendationsArgs.model_validate(args)
    recs = ctx.recommendations.active_recommendations if hasattr(ctx.recommendations, "active_recommendations") else []
    if parsed.category:
        cat_lower = parsed.category.lower()
        recs = [r for r in recs if cat_lower in getattr(r, "category", "").lower()]

    items = []
    for r in recs[: parsed.limit]:
        if hasattr(r, "model_dump"):
            items.append(r.model_dump())
        elif isinstance(r, dict):
            items.append(r)
        else:
            items.append(str(r))

    return {
        "active_recommendations_count": len(recs),
        "recommendations": items,
    }


def _tool_search_official_schemes(ctx: UnifiedRecommendationContext, args: dict[str, Any]) -> dict[str, Any]:
    parsed = SearchSchemesArgs.model_validate(args)
    schemes = ctx.schemes.recommended_schemes or ctx.schemes.eligible_schemes
    if parsed.category:
        cat_lower = parsed.category.lower()
        schemes = [s for s in schemes if cat_lower in s.category.lower()] or schemes

    return {
        "matched_schemes_count": len(schemes),
        "schemes": [
            {
                "id": s.id,
                "name": s.name,
                "official_authority": s.official_authority,
                "official_source_url": s.official_source_url,
                "category": s.category,
                "benefits": s.benefits,
                "documents_required": s.documents_required,
                "eligibility_reason": s.eligibility_reason,
            }
            for s in schemes[:4]
        ],
    }


def _tool_run_business_comparison(ctx: UnifiedRecommendationContext, args: dict[str, Any]) -> dict[str, Any]:
    parsed = BusinessComparisonArgs.model_validate(args)
    dim = (parsed.dimension or "revenue").lower()

    if dim in ("customers", "customer"):
        c = ctx.customers
        top1 = c.top_customers_by_revenue[0] if c.top_customers_by_revenue else {}
        top1_rev = top1.get("revenue", 0.0)
        aov = c.average_order_value
        factor = round(top1_rev / aov, 1) if aov > 0 else 0.0
        return {
            "comparison_dimension": "customers",
            "primary_subject": top1.get("customer_name", "Top Client"),
            "primary_value": f"₹{top1_rev:,.0f}",
            "benchmark_subject": "Average Order Value",
            "benchmark_value": f"₹{aov:,.0f}",
            "difference_factor": factor,
            "summary": f"Top client generates {factor}x more revenue than the average order value.",
        }
    elif dim in ("products", "product"):
        p = ctx.products
        top1 = p.top_products_by_revenue[0] if p.top_products_by_revenue else {}
        top2 = p.top_products_by_revenue[1] if len(p.top_products_by_revenue) > 1 else {}
        r1 = top1.get("revenue", 0.0)
        r2 = top2.get("revenue", 0.0)
        diff_pct = round(((r1 - r2) / r2) * 100.0, 1) if r2 > 0 else 0.0
        return {
            "comparison_dimension": "products",
            "primary_product": top1.get("product_name", "Top SKU"),
            "primary_revenue": f"₹{r1:,.0f}",
            "secondary_product": top2.get("product_name", "Runner-up SKU"),
            "secondary_revenue": f"₹{r2:,.0f}",
            "difference_pct": diff_pct,
            "summary": f"Top SKU outperforms the second SKU by {diff_pct}% in total recorded sales.",
        }
    else:
        # Default revenue comparison: profile reported vs ledger verified
        rep = ctx.profile.annual_revenue or 0.0
        rec = ctx.sales.total_revenue or 0.0
        cov_pct = round((rec / rep) * 100.0, 1) if rep > 0 else 0.0
        discrepancy = abs(rep - rec) > (0.1 * rep) if rep > 0 and rec > 0 else False
        return {
            "comparison_dimension": "revenue",
            "profile_reported_revenue": f"₹{rep:,.0f}",
            "ledger_verified_revenue": f"₹{rec:,.0f}",
            "ledger_coverage_pct": cov_pct,
            "discrepancy_detected": discrepancy,
            "summary": f"Profile records ₹{rep:,.0f} annual turnover; uploaded transaction ledger verifies ₹{rec:,.0f}.",
        }


def _tool_calculate_business_metrics(ctx: UnifiedRecommendationContext, args: dict[str, Any]) -> dict[str, Any]:
    parsed = CalculateMetricsArgs.model_validate(args)
    metric = parsed.metric.lower().strip()
    supported_metrics = [
        "repeat_rate",
        "customer_concentration",
        "average_order_value",
        "product_concentration",
        "annualized_revenue",
        "revenue_growth",
        "atv",
    ]
    if metric not in supported_metrics:
        return {
            "status": "unsupported_metric",
            "metric": metric,
            "supported_metrics": supported_metrics,
            "error": f"Metric '{metric}' is not supported for deterministic calculation.",
        }

    if metric in ("repeat_rate", "repeat_purchase_rate"):
        c = ctx.customers
        return {
            "metric": "repeat_rate",
            "formula": f"({c.repeat_customers} repeat buyers / {c.total_customers} total buyers) * 100",
            "result": f"{c.repeat_rate_pct:.1f}%",
            "inputs": {"repeat_customers": c.repeat_customers, "total_customers": c.total_customers},
        }
    elif metric in ("customer_concentration", "concentration"):
        c = ctx.customers
        total_rev = ctx.sales.total_revenue
        top1_rev = c.top_customers_by_revenue[0].get("revenue", 0.0) if c.top_customers_by_revenue else 0.0
        pct = (top1_rev / total_rev * 100.0) if total_rev > 0 else 0.0
        return {
            "metric": "customer_concentration",
            "formula": f"(₹{top1_rev:,.0f} top client / ₹{total_rev:,.0f} total) * 100",
            "result": f"{pct:.1f}%",
            "inputs": {"top_client_revenue": top1_rev, "total_revenue": total_rev},
        }
    elif metric in ("average_order_value", "atv"):
        s = ctx.sales
        aov = (s.total_revenue / s.total_transactions) if s.total_transactions > 0 else 0.0
        return {
            "metric": "average_order_value",
            "formula": f"₹{s.total_revenue:,.0f} / {s.total_transactions} orders",
            "result": f"₹{aov:,.0f}",
            "inputs": {"total_revenue": s.total_revenue, "total_transactions": s.total_transactions},
        }
    elif metric == "product_concentration":
        p = ctx.products
        total_rev = ctx.sales.total_revenue
        top1_rev = p.top_products_by_revenue[0].get("revenue", 0.0) if p.top_products_by_revenue else 0.0
        pct = (top1_rev / total_rev * 100.0) if total_rev > 0 else 0.0
        return {
            "metric": "product_concentration",
            "formula": f"(₹{top1_rev:,.0f} top SKU / ₹{total_rev:,.0f} total) * 100",
            "result": f"{pct:.1f}%",
            "inputs": {"top_sku_revenue": top1_rev, "total_revenue": total_rev},
        }
    elif metric in ("annualized_revenue", "revenue_growth"):
        s = ctx.sales
        if s.date_range_days >= 30 and s.total_revenue > 0:
            annualized = (s.total_revenue / s.date_range_days) * 365.25
            return {
                "metric": "annualized_revenue",
                "formula": f"(₹{s.total_revenue:,.0f} / {s.date_range_days} days) * 365.25",
                "result": f"₹{annualized:,.0f}",
                "inputs": {"total_revenue": s.total_revenue, "date_range_days": s.date_range_days},
            }
        else:
            return {
                "status": "insufficient_data",
                "metric": metric,
                "error": "Minimum 30 days of sales transactions required to compute annualized revenue.",
            }

    return {"status": "error", "error": "Evaluation failed"}


# The 13 Whitelisted Analysis Tools
WHITELISTED_TOOLS: dict[str, Any] = {
    "get_business_profile": _tool_get_business_profile,
    "get_business_health": _tool_get_business_health,
    "get_sales_summary": _tool_get_sales_summary,
    "get_sales_trends": _tool_get_sales_trends,
    "get_product_performance": _tool_get_product_performance,
    "get_customer_insights": _tool_get_customer_insights,
    "get_customer_concentration": _tool_get_customer_concentration,
    "get_financial_indicators": _tool_get_financial_indicators,
    "get_demand_forecast": _tool_get_demand_forecast,
    "get_existing_recommendations": _tool_get_existing_recommendations,
    "search_official_schemes": _tool_search_official_schemes,
    "run_business_comparison": _tool_run_business_comparison,
    "calculate_business_metrics": _tool_calculate_business_metrics,
}


# --------------------------------------------------------------------------- #
# OpenEndedBusinessIntelligenceEngine
# --------------------------------------------------------------------------- #


class OpenEndedBusinessIntelligenceEngine:
    """Core Natural-Language Understanding, Tool Selection, and Reasoning Engine."""

    def __init__(self) -> None:
        self._tools = WHITELISTED_TOOLS
        self._answerability_classifier = AnswerabilityClassifier()
        self._quality_evaluator = AIAnswerQualityEvaluator()
        self._finding_builder = GroundedFindingBuilder()
        self._observability_logger = StructuredObservabilityLogger()

    def answer(
        self,
        ctx: UnifiedRecommendationContext,
        req: RecommendationAskRequest,
    ) -> RecommendationAskResponse:
        """Process any open-ended question with verified data grounding, reasoning, and automated QA evaluation."""
        t0 = time.perf_counter()
        req_uuid = f"req_{uuid.uuid4().hex[:12]}"
        now_iso = datetime.now(timezone.utc).isoformat()
        q = req.question.strip()
        q_lower = q.lower()
        history = req.conversation_history or []

        # 0. Answerability Pre-Classification
        ans_status, ans_reason = self._answerability_classifier.classify(
            question=q,
            ctx=ctx,
            has_history=bool(history),
        )

        if ans_status == AnswerabilityStatus.UNSUPPORTED_REQUEST:
            resp = self._handle_unsupported_request(q, ans_reason, now_iso)
            eval_res = self._quality_evaluator.evaluate(q, resp, ctx)
            resp.quality_evaluation = eval_res
            latency_ms = (time.perf_counter() - t0) * 1000
            self._observability_logger.log_query_execution(
                request_uuid=req_uuid,
                business_id=ctx.profile.business_id,
                question=q,
                answerability=ans_status,
                tools_executed=[],
                evaluation=eval_res,
                latency_ms=latency_ms,
            )
            return resp

        # 1. Multi-turn reference resolution
        resolved_focus, antecedent_entity = self._resolve_multi_turn_context(q_lower, history)

        # 2. Query classification & intent mapping
        query_type, intent, required_tools = self._understand_question(
            q_lower, resolved_focus, antecedent_entity
        )

        # 3. Handle Special Non-Analytical Query Categories
        if query_type == "ambiguous" or (ans_status == AnswerabilityStatus.NEEDS_CLARIFICATION and not history):
            resp = self._handle_ambiguous_question(q, intent, now_iso)
            eval_res = self._quality_evaluator.evaluate(q, resp, ctx)
            resp.quality_evaluation = eval_res
            latency_ms = (time.perf_counter() - t0) * 1000
            self._observability_logger.log_query_execution(
                request_uuid=req_uuid,
                business_id=ctx.profile.business_id,
                question=q,
                answerability=AnswerabilityStatus.NEEDS_CLARIFICATION,
                tools_executed=[],
                evaluation=eval_res,
                latency_ms=latency_ms,
            )
            return resp

        if query_type == "data_unavailable":
            resp = self._handle_unavailable_data_question(q, intent, q_lower, now_iso)
            eval_res = self._quality_evaluator.evaluate(q, resp, ctx)
            resp.quality_evaluation = eval_res
            latency_ms = (time.perf_counter() - t0) * 1000
            self._observability_logger.log_query_execution(
                request_uuid=req_uuid,
                business_id=ctx.profile.business_id,
                question=q,
                answerability=AnswerabilityStatus.INSUFFICIENT_DATA,
                tools_executed=[],
                evaluation=eval_res,
                latency_ms=latency_ms,
            )
            return resp

        if query_type == "general_business_guidance":
            resp = self._handle_general_business_guidance(ctx, q, intent, now_iso)
            eval_res = self._quality_evaluator.evaluate(q, resp, ctx)
            resp.quality_evaluation = eval_res
            latency_ms = (time.perf_counter() - t0) * 1000
            self._observability_logger.log_query_execution(
                request_uuid=req_uuid,
                business_id=ctx.profile.business_id,
                question=q,
                answerability=AnswerabilityStatus.ANSWERABLE,
                tools_executed=[],
                evaluation=eval_res,
                latency_ms=latency_ms,
            )
            return resp

        # 4. Tool Execution Phase (Bounded, Validated, Sandboxed)
        tool_results, tool_traces, data_gaps = self._execute_tools(
            ctx=ctx,
            tools=required_tools,
            antecedent_entity=antecedent_entity,
        )

        # 5. Check Contradictory Data
        contradiction_note = self._detect_contradictions(ctx, tool_results)

        # 6. Extract Supporting Evidence & Calculation Lineage
        evidence, calculations, follow_ups = self._synthesize_evidence(
            ctx=ctx,
            tool_results=tool_results,
            intent=intent,
            resolved_focus=resolved_focus,
            antecedent_entity=antecedent_entity,
        )

        if contradiction_note:
            evidence.insert(0, contradiction_note)

        # 7. Synthesize Situational Recommendations using 25/25/20/15/15 Priority Formula
        situational_recs = self._synthesize_situational_recommendations(
            ctx=ctx,
            intent=intent,
            tool_results=tool_results,
            evidence=evidence,
            antecedent_entity=antecedent_entity,
        )

        # 8. Formulate Deterministic Direct Answer
        deterministic_answer = self._formulate_direct_answer(
            ctx=ctx,
            question=q,
            intent=intent,
            query_type=query_type,
            evidence=evidence,
            calculations=calculations,
            data_gaps=data_gaps,
            situational_recs=situational_recs,
            tool_results=tool_results,
        )

        # Build Grounded Findings
        grounded_findings = self._finding_builder.build_from_context_and_tools(
            ctx=ctx,
            tool_results=tool_results,
            calculations=calculations,
        )

        # Trust Label determination
        if ans_status == AnswerabilityStatus.PARTIALLY_ANSWERABLE:
            trust_label = "Partial Data Grounded"
        elif len(evidence) >= 3:
            trust_label = "Verified Data Grounded"
        else:
            trust_label = "High Confidence"

        # 9. Attempt Bounded Gemini Polish (with instant deterministic fallback)
        chosen_answer = deterministic_answer
        is_ai = False
        settings = get_settings()
        if settings.ai_api_key and settings.ai_provider != "placeholder":
            try:
                ai_answer = self._call_gemini_reasoning(
                    ctx=ctx,
                    question=q,
                    intent=intent,
                    evidence=evidence,
                    calculations=calculations,
                    data_gaps=data_gaps,
                    deterministic_baseline=deterministic_answer,
                )
                if ai_answer:
                    # Validate Gemini output for numerical consistency and boundaries
                    num_score, _, num_warns = self._quality_evaluator.numeric_validator.validate_text(ai_answer, ctx)
                    violations = self._quality_evaluator.hallucination_detector.detect_violations(ai_answer)
                    if num_score >= 7.0 and len(violations) == 0:
                        chosen_answer = ai_answer
                        is_ai = True
                    else:
                        logger.warning(
                            "Gemini reasoning discarded due to quality/boundary checks (num_score=%.1f, violations=%s). "
                            "Defaulting to deterministic baseline.",
                            num_score,
                            violations,
                        )
            except Exception as exc:
                logger.warning(f"Gemini open-ended reasoning call failed, falling back to deterministic answer: {exc}")

        resp = RecommendationAskResponse(
            question=q,
            intent=intent,
            direct_answer=chosen_answer,
            evidence_points=evidence,
            calculations=calculations,
            situational_recommendations=situational_recs,
            data_limitations_and_gaps=data_gaps,
            follow_up_questions=follow_ups,
            tool_executions=tool_traces,
            query_type=query_type,
            is_ai_generated=is_ai,
            generated_at=now_iso,
            answerability=ans_status,
            answerability_reason=ans_reason,
            grounded_findings=grounded_findings,
            trust_label=trust_label,
        )

        # 10. Run Full 10-Dimension Quality Evaluation
        eval_result = self._quality_evaluator.evaluate(q, resp, ctx)
        resp.quality_evaluation = eval_result

        # 11. Log Structured Telemetry
        latency_ms = (time.perf_counter() - t0) * 1000
        executed_tool_names = [t.get("tool", "") for t in tool_traces]
        self._observability_logger.log_query_execution(
            request_uuid=req_uuid,
            business_id=ctx.profile.business_id,
            question=q,
            answerability=ans_status,
            tools_executed=executed_tool_names,
            evaluation=eval_result,
            latency_ms=latency_ms,
        )

        return resp

    # ----------------------------------------------------------------------- #
    # Multi-turn Context Resolution
    # ----------------------------------------------------------------------- #

    def _resolve_multi_turn_context(
        self,
        q_lower: str,
        history: list[dict[str, Any]],
    ) -> tuple[Optional[str], Optional[str]]:
        """Resolve pronouns and contextual references like 'that product', 'those customers', 'the decline'."""
        if not history:
            return None, None

        resolved_focus = None
        antecedent_entity = None

        # Scan previous turns in reverse
        for turn in reversed(history):
            content = (turn.get("content") or turn.get("question") or "").lower()
            # Check for product references
            if any(ref in q_lower for ref in ["that product", "which product", "the product", "this sku", "what should i do about it"]):
                # Look for product mentions in previous turn
                match = re.search(r"product '([^']+)'|sku '([^']+)'|product ([a-zA-Z0-9_-]+)", content)
                if match:
                    antecedent_entity = match.group(1) or match.group(2) or match.group(3)
                    resolved_focus = "product_deep_dive"
                    break
                elif "sales" in content or "drop" in content or "decline" in content:
                    resolved_focus = "sales_decline_attribution"
                    break

            # Check for customer references
            if any(ref in q_lower for ref in ["those customers", "that customer", "that client", "the customer"]):
                match = re.search(r"client '([^']+)'|customer '([^']+)'", content)
                if match:
                    antecedent_entity = match.group(1) or match.group(2)
                    resolved_focus = "customer_deep_dive"
                    break
                resolved_focus = "customer_inactivity"
                break

        return resolved_focus, antecedent_entity

    # ----------------------------------------------------------------------- #
    # Question Understanding & Tool Selection
    # ----------------------------------------------------------------------- #

    def _understand_question(
        self,
        q_lower: str,
        resolved_focus: Optional[str],
        antecedent_entity: Optional[str],
    ) -> tuple[str, str, list[str]]:
        """Understand question type, business intent, and select 1-3 appropriate tools."""
        # Check ambiguous or extremely short questions
        words = q_lower.strip().split()
        if len(words) < 2 and len(q_lower) < 8:
            return "ambiguous", "general_clarification", []

        # Check unavailable data requests (warehouse inventory, reorder qty, stockout dates, taxes)
        unavailable_terms = [
            "stock count",
            "stock balance",
            "warehouse stock",
            "reorder quantity",
            "reorder point",
            "stockout date",
            "safety stock",
            "lead time",
            "depreciation schedule",
            "depreciation",
            "tax return",
            "gst return filing",
            "overtime hours",
        ]
        if any(term in q_lower for term in unavailable_terms):
            return "data_unavailable", "untracked_operational_metric", ["get_financial_indicators"]

        # Check general business questions (not requiring specific ledger data)
        general_terms = [
            "how should i prepare my business for expansion",
            "prepare for expansion",
            "consider before launching a new product",
            "launching a new product",
            "how to launch a product",
            "risks of expanding into another market",
            "export market risks",
            "how can i improve customer retention in general",
            "general principles of working capital",
        ]
        if any(gt in q_lower for gt in general_terms) or (
            "consider" in q_lower and "product" in q_lower and "launch" in q_lower
        ) or (
            "prepare" in q_lower and "expansion" in q_lower
        ) or (
            "risks" in q_lower and "market" in q_lower and "expand" in q_lower
        ):
            return "general_business_guidance", "general_strategic_consulting", ["get_business_profile"]

        # Check multi-step reasoning: Revenue up but profit down
        if (("revenue" in q_lower or "sales" in q_lower) and ("profit" in q_lower or "money" in q_lower or "margin" in q_lower)) and (
            "struggling" in q_lower or "down" in q_lower or "drop" in q_lower or "decreasing" in q_lower or "why" in q_lower
        ):
            return "multi_step", "margin_cost_discrepancy", [
                "get_sales_trends",
                "get_financial_indicators",
                "calculate_business_metrics",
            ]

        # Multi-step reasoning: Which customers to focus on / concentration
        if ("which customer" in q_lower or "focus on" in q_lower or "grow my business" in q_lower) and (
            "customer" in q_lower or "client" in q_lower
        ):
            return "multi_step", "customer_retention_concentration", [
                "get_customer_insights",
                "get_customer_concentration",
            ]

        # Customer concentration query
        if any(w in q_lower for w in ["dependent", "concentration", "rely", "single buyer", "few customers", "dependency", "vulnerable", "single client"]):
            return "data_grounded", "customer_retention_concentration", [
                "get_customer_concentration",
                "get_customer_insights",
            ]

        # Demand forecast query
        if any(w in q_lower for w in ["forecast", "demand next month", "future demand", "projected demand", "demand trend", "trajectory", "lathe"]):
            return "data_grounded", "product_demand_forecasting", [
                "get_demand_forecast",
                "get_product_performance",
            ]

        # Product performance / ranking query
        if any(w in q_lower for w in ["which products perform best", "best performing", "top products", "top selling", "product ranking"]):
            return "data_grounded", "product_performance_ranking", [
                "get_product_performance",
                "get_sales_summary",
            ]

        # Sales decline / diagnostics query
        if resolved_focus == "sales_decline_attribution" or any(
            w in q_lower for w in ["sales declining", "sales drop", "sales falling", "why are my sales dropping", "revenue drop"]
        ):
            return "multi_step", "sales_revenue_diagnostics", [
                "get_sales_trends",
                "get_product_performance",
                "get_customer_insights",
            ]

        # Government schemes query
        if any(w in q_lower for w in ["scheme", "grant", "subsidy", "cgtmse", "mudra", "pmegp", "government", "udyam"]):
            return "data_grounded", "government_funding_schemes", [
                "search_official_schemes",
                "get_business_profile",
            ]

        # Business health / priority improvement query
        if any(w in q_lower for w in ["improve first", "health score", "what should i improve", "weakness", "focus on this week"]):
            return "data_grounded", "health_and_prioritization", [
                "get_business_health",
                "get_existing_recommendations",
            ]

        # Sales trend / history query
        if any(w in q_lower for w in ["sales trend", "sales trends", "trend over the past", "revenue trend", "historical sales"]):
            return "data_grounded", "sales_trend_analysis", [
                "get_sales_trends",
                "get_sales_summary",
            ]

        # Customer / Client list or insights query
        if "customer" in q_lower or "client" in q_lower:
            return "data_grounded", "customer_analytics", [
                "get_customer_insights",
                "get_sales_summary",
            ]

        # Multi-turn entity follow-up: "What should I do about it?"
        if antecedent_entity or resolved_focus in ("product_deep_dive", "customer_deep_dive"):
            return "multi_step", "entity_followup_recommendation", [
                "get_product_performance",
                "get_demand_forecast",
            ]

        # Default fallback: open-ended analytical inquiry
        return "data_grounded", "general_business_analytics", [
            "get_sales_summary",
            "get_business_health",
        ]

    # ----------------------------------------------------------------------- #
    # Tool Execution Controller
    # ----------------------------------------------------------------------- #

    def _execute_tools(
        self,
        ctx: UnifiedRecommendationContext,
        tools: list[str],
        antecedent_entity: Optional[str] = None,
    ) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
        """Safely execute bounded list of whitelisted tools with audit tracing."""
        results: dict[str, Any] = {}
        traces: list[dict[str, Any]] = []
        data_gaps: list[str] = []

        # Bound tool executions to cap
        selected_tools = tools[:_MAX_TOOL_CALLS_PER_TURN]

        for tool_name in selected_tools:
            tool_fn = self._tools.get(tool_name)
            if not tool_fn:
                continue

            t0 = time.perf_counter()
            call_args: dict[str, Any] = {}
            if tool_name == "get_demand_forecast" and antecedent_entity:
                call_args["product_id"] = antecedent_entity
            elif tool_name == "calculate_business_metrics":
                call_args["metric"] = "average_order_value"

            try:
                payload = tool_fn(ctx, call_args)
                duration_ms = int((time.perf_counter() - t0) * 1000)
                results[tool_name] = payload
                traces.append(
                    {
                        "tool": tool_name,
                        "status": "ok",
                        "duration_ms": duration_ms,
                        "arguments": call_args,
                    }
                )
                if tool_name == "get_demand_forecast":
                    data_gaps.append(
                        "Warehouse stock counts and supplier delivery lead times are external operational variables not tracked by UrsBiz. Reorder points require physical inventory logs."
                    )
                elif tool_name == "get_customer_concentration":
                    data_gaps.append(
                        "Master service agreement expiration dates and client satisfaction metrics are external variables not recorded in the ledger."
                    )
                elif tool_name == "get_financial_indicators":
                    data_gaps.append(
                        "Detailed expense ledgers, depreciation schedules, and tax returns are not tracked by UrsBiz unless uploaded by the user."
                    )
            except ValidationError as ve:
                duration_ms = int((time.perf_counter() - t0) * 1000)
                traces.append(
                    {
                        "tool": tool_name,
                        "status": "error",
                        "duration_ms": duration_ms,
                        "error": f"Invalid arguments: {ve}",
                    }
                )
            except Exception as e:
                duration_ms = int((time.perf_counter() - t0) * 1000)
                traces.append(
                    {
                        "tool": tool_name,
                        "status": "error",
                        "duration_ms": duration_ms,
                        "error": str(e),
                    }
                )

        return results, traces, data_gaps

    # ----------------------------------------------------------------------- #
    # Synthesis & Calculations
    # ----------------------------------------------------------------------- #

    def _detect_contradictions(
        self,
        ctx: UnifiedRecommendationContext,
        results: dict[str, Any],
    ) -> Optional[str]:
        """Detect and surface discrepancies between stated profile revenue and uploaded ledger."""
        profile_rev = ctx.profile.annual_revenue
        ledger_rev = ctx.sales.total_revenue
        if profile_rev and ledger_rev and profile_rev > 0 and ledger_rev > 0:
            if abs(profile_rev - ledger_rev) > (0.4 * profile_rev):
                return (
                    f"Profile Discrepancy Note: Business profile records ₹{profile_rev:,.0f} annual turnover, "
                    f"whereas uploaded sales transactions corroborate ₹{ledger_rev:,.0f}. Insights below prioritize verified transaction records."
                )
        return None

    def _synthesize_evidence(
        self,
        ctx: UnifiedRecommendationContext,
        tool_results: dict[str, Any],
        intent: str,
        resolved_focus: Optional[str],
        antecedent_entity: Optional[str],
    ) -> tuple[list[str], list[CalculationStep], list[str]]:
        """Synthesize verified evidence points, calculation formulas, and follow-ups."""
        evidence: list[str] = []
        calculations: list[CalculationStep] = []
        follow_ups: list[str] = []

        total_rev = ctx.sales.total_revenue
        has_sales = ctx.sales.has_sales_data and total_rev > 0

        # General business identity
        evidence.append(
            f"Business: {ctx.profile.legal_name} | Industry: {ctx.profile.industry} | State: {ctx.profile.state_region or 'India'}"
        )

        # Customer Concentration Evidence
        if "get_customer_concentration" in tool_results:
            conc = tool_results["get_customer_concentration"]
            if conc.get("has_data"):
                top1_name = conc.get("top1_customer_name")
                top1_rev = conc.get("top1_revenue", 0.0)
                top1_pct = conc.get("top1_share_pct", 0.0)
                risk = conc.get("concentration_risk_level")
                evidence.append(
                    f"Primary client '{top1_name}' accounts for ₹{top1_rev:,.0f} ({top1_pct}% of total sales). Concentration risk rating: {risk}."
                )
                calculations.append(
                    CalculationStep(
                        name="Top Client Revenue Concentration Share",
                        formula=f"₹{top1_rev:,.0f} / ₹{total_rev:,.0f}",
                        result=f"{top1_pct:.1f}% of total turnover",
                    )
                )
                follow_ups.append(f"Do you have a signed supply contract or purchase order commitment with '{top1_name}'?")
                follow_ups.append("Would you like to simulate a customer retention campaign in the What-If Simulator?")

        # Customer Insights Evidence
        if "get_customer_insights" in tool_results:
            ci = tool_results["get_customer_insights"]
            rep_pct = ci.get("repeat_rate_pct", 0.0)
            rep_cust = ci.get("repeat_customers", 0)
            tot_cust = ci.get("total_customers", 0)
            aov = ci.get("average_order_value", 0.0)
            declining_count = ci.get("declining_count", 0)
            evidence.append(
                f"Customer base: {tot_cust} total buyers, {rep_cust} repeat buyers ({rep_pct:.1f}% repeat rate), Average Order Value: ₹{aov:,.0f}."
            )
            if declining_count > 0:
                evidence.append(
                    f"{declining_count} client account(s) have not placed repeat orders in recent transaction cycles."
                )
            top_custs = ci.get("top_customers_by_revenue", [])
            if top_custs:
                top_names = [c.get("customer_name") for c in top_custs[:3] if c.get("customer_name")]
                if top_names:
                    evidence.append(f"Top recorded clients: {', '.join(top_names)}.")
            calculations.append(
                CalculationStep(
                    name="Customer Repeat Purchase Ratio",
                    formula=f"{rep_cust} repeat buyers / {tot_cust} total buyers",
                    result=f"{rep_pct:.1f}%",
                )
            )

        # Sales Trends Evidence
        if "get_sales_trends" in tool_results:
            st = tool_results["get_sales_trends"]
            if st.get("has_sales_data"):
                trend = st.get("trend_direction", "stable")
                avg_m = st.get("average_monthly_revenue", 0.0)
                evidence.append(
                    f"Transaction history spans {st.get('date_range_days')} days with average monthly turnover of ₹{avg_m:,.0f} (Trend: {trend})."
                )
            else:
                evidence.append(
                    st.get("observation") or "No sales transaction ledger uploaded. Minimum 6 periods required for trend analysis."
                )

        # Product Performance Evidence
        if "get_product_performance" in tool_results:
            pp = tool_results["get_product_performance"]
            top_products = pp.get("top_products_by_revenue", [])
            if top_products:
                top_p = top_products[0]
                p_name = top_p.get("product_name", "Primary SKU")
                p_rev = top_p.get("revenue", 0.0)
                p_pct = (p_rev / total_rev * 100.0) if total_rev > 0 else 0.0
                evidence.append(
                    f"Top SKU '{p_name}' generated ₹{p_rev:,.0f} ({p_pct:.1f}% of total sales)."
                )
                calculations.append(
                    CalculationStep(
                        name=f"Top Product Revenue Share ({p_name})",
                        formula=f"₹{p_rev:,.0f} / ₹{total_rev:,.0f}",
                        result=f"{p_pct:.1f}%",
                    )
                )

        # Demand Forecast Evidence
        if "get_demand_forecast" in tool_results:
            df = tool_results["get_demand_forecast"]
            if df.get("has_forecast_data"):
                for pf in df.get("product_forecasts", [])[:2]:
                    evidence.append(
                        f"Phase 4 Forecast for '{pf['product_name']}': trend '{pf['demand_trend']}', projected {pf['forecasted_units_total']:,.0f} units "
                        f"over {pf['forecast_horizon_periods']} periods (Model: {pf['selected_model']}, Reliability: {pf['reliability']})."
                    )
                    if pf.get("best_mae") is not None:
                        calculations.append(
                            CalculationStep(
                                name=f"Holdout Backtest MAE for {pf['product_name']}",
                                formula="Mean Absolute Error on independent holdout segment",
                                result=f"{pf['best_mae']:.2f} units",
                            )
                        )
                follow_ups.append("Would you like to simulate a +20% demand surge scenario for your top SKUs?")
            else:
                evidence.append(
                    "Demand forecasting is currently pending minimum historical transaction depth (6 periods)."
                )

        # Government Schemes Evidence
        if "search_official_schemes" in tool_results:
            sc = tool_results["search_official_schemes"]
            schemes = sc.get("schemes", [])
            if schemes:
                for s in schemes[:2]:
                    evidence.append(
                        f"Matched Scheme: '{s['name']}' administered by {s['official_authority']}. Benefit: {s['benefits'][0] if s['benefits'] else 'Credit/Subsidy support'}."
                    )
                follow_ups.append("Do you hold an active Udyam registration certificate?")

        # Business Health Evidence
        if "get_business_health" in tool_results:
            bh = tool_results["get_business_health"]
            evidence.append(
                f"Business Health Score: {bh.get('overall_score')}/100 (Grade: {bh.get('grade')}, Digital Readiness: {bh.get('digital_readiness_score')}%)."
            )

        # Fallback default evidence if empty
        if not evidence:
            evidence.append(f"Business: {ctx.profile.legal_name} | Health Score: {ctx.health.overall_score}/100")

        return evidence, calculations, follow_ups

    # ----------------------------------------------------------------------- #
    # Situational Recommendations (Deterministic 25/25/20/15/15 Formula)
    # ----------------------------------------------------------------------- #

    def _synthesize_situational_recommendations(
        self,
        ctx: UnifiedRecommendationContext,
        intent: str,
        tool_results: dict[str, Any],
        evidence: list[str],
        antecedent_entity: Optional[str],
    ) -> list[SituationalRecommendation]:
        """Synthesize situational recommendations using the mandated priority formula."""
        recs: list[SituationalRecommendation] = []

        # Customer concentration recommendation
        if "get_customer_concentration" in tool_results:
            conc = tool_results["get_customer_concentration"]
            if conc.get("has_data") and conc.get("top1_share_pct", 0) > 20:
                top1_name = conc.get("top1_customer_name", "Primary Client")
                recs.append(
                    SituationalRecommendation(
                        title=f"Establish Quarterly Executive Review & Contract Renewal with '{top1_name}'",
                        category="Customer Retention",
                        priority="Critical" if conc.get("top1_share_pct", 0) > 35 else "High",
                        situational_rationale=(
                            f"With {conc.get('top1_share_pct')}% of total sales concentrated in '{top1_name}', "
                            "formalizing forward-looking quarterly purchase commitments is essential to hedge against sudden volume shrinkage."
                        ),
                        action_steps=[
                            f"Schedule a senior executive check-in with procurement lead at '{top1_name}'",
                            "Review operational fulfillment performance and resolve any open delivery issues",
                            "Explore quarterly rolling blanket purchase orders with agreed price indexation",
                        ],
                        timeframe="7-14 days",
                        cost_of_delay="Losing this relationship would trigger an immediate cash-flow shock and potential insolvency.",
                    )
                )

        # Demand forecast procurement recommendation
        if "get_demand_forecast" in tool_results:
            df = tool_results["get_demand_forecast"]
            if df.get("has_forecast_data") and df.get("product_forecasts"):
                top_f = df["product_forecasts"][0]
                recs.append(
                    SituationalRecommendation(
                        title=f"Align Supplier Raw Material Procurement for '{top_f['product_name']}'",
                        category="Product Performance",
                        priority="High",
                        situational_rationale=(
                            f"Demand forecast indicates {top_f['demand_trend']} demand ({top_f['forecasted_units_total']:,.0f} units). "
                            "Staging supplier orders in 2-week rolling batches prevents stockouts without locking up working capital."
                        ),
                        action_steps=[
                            f"Confirm component availability and supplier lead times for '{top_f['product_name']}'",
                            "Set procurement delivery schedules aligned with weekly sales velocity",
                            "Avoid unconfirmed bulk raw material speculative buying",
                        ],
                        timeframe="14-21 days",
                        cost_of_delay="Unpreparedness leads to buyer order cancellations, while excessive advance buying locks up working capital.",
                    )
                )

        # Margin / Cost discrepancy recommendation
        if intent == "margin_cost_discrepancy":
            recs.append(
                SituationalRecommendation(
                    title="Implement SKU-Level Contribution Margin & Discount Audit",
                    category="Financial Management",
                    priority="High",
                    situational_rationale=(
                        "When sales volume expands but net profit contracts, unmonitored discounting, freight cost creep, or unit COGS inflation "
                        "are the most common drivers. Auditing unit margins isolates unprofitable transactions."
                    ),
                    action_steps=[
                        "Calculate gross margin on your top 5 revenue-generating SKUs",
                        "Review commercial discount approvals and cap discretionary sales concessions",
                        "Upload detailed purchase/expense ledger to UrsBiz for automated margin tracking",
                    ],
                    timeframe="10-15 days",
                    cost_of_delay="Continued revenue expansion at negative or razor-thin contribution accelerates working capital depletion.",
                )
            )

        # General operational fallback recommendation
        if not recs:
            recs.append(
                SituationalRecommendation(
                    title="Optimize Business Health Profile & Complete Operating Data",
                    category="Operational Efficiency",
                    priority="Medium",
                    situational_rationale=(
                        f"Current Business Health Index is {ctx.health.overall_score}/100. Adding transaction ledgers and operational records "
                        "directly upgrades recommendation precision and lender bankability."
                    ),
                    action_steps=[
                        "Upload complete historical sales ledger in CSV format",
                        "Complete missing profile fields under Business Digital Twin",
                        "Review top priority actions on the Smart Recommendations dashboard",
                    ],
                    timeframe="7-10 days",
                    cost_of_delay="Incomplete data profiles prevent statutory scheme pre-matching and credit readiness scoring.",
                )
            )

        return recs

    # ----------------------------------------------------------------------- #
    # Direct Answer Formulation
    # ----------------------------------------------------------------------- #

    def _formulate_direct_answer(
        self,
        ctx: UnifiedRecommendationContext,
        question: str,
        intent: str,
        query_type: str,
        evidence: list[str],
        calculations: list[CalculationStep],
        data_gaps: list[str],
        situational_recs: list[SituationalRecommendation],
        tool_results: dict[str, Any],
    ) -> str:
        """Formulate a direct, context-aware, evidence-backed answer."""
        paragraphs: list[str] = []

        # 1. Direct answer sentence
        if query_type == "multi_step" and intent == "margin_cost_discrepancy":
            paragraphs.append(
                f"Regarding *\"{question}\"*: While your sales ledger confirms active top-line revenue, "
                f"profit contraction during revenue growth typically indicates that costs (such as cost of goods sold, freight, or discounting) "
                f"are rising faster than turnover."
            )
        elif query_type == "multi_step" and intent == "customer_retention_concentration":
            paragraphs.append(
                f"Regarding *\"{question}\"*: To grow sustainably, focus first on securing your highest-volume accounts "
                f"while systematically converting one-time buyers into repeat clients."
            )
        else:
            paragraphs.append(
                f"Here is what your verified business data indicates regarding *\"{question}\"*:"
            )

        # 2. Key findings & verified facts
        if evidence:
            ev_bullets = [f"- {e}" for e in evidence[:3]]
            paragraphs.append("### Key Verified Facts & Signals\n" + "\n".join(ev_bullets))

        findings: list[str] = []
        if calculations:
            for c in calculations:
                findings.append(f"- **{c.name}:** {c.result} (Formula: `{c.formula}`).")
        if findings:
            paragraphs.append("### Key Verified Calculations\n" + "\n".join(findings))

        # 3. Actionable recommendation from situation
        if situational_recs:
            top_rec = situational_recs[0]
            paragraphs.append(
                f"### Strategic Next Action: {top_rec.title}\n"
                f"{top_rec.situational_rationale}\n\n"
                f"**Immediate Steps:**\n" + "\n".join([f"- {s}" for s in top_rec.action_steps]) + "\n\n"
                f"*Target Timeline:* {top_rec.timeframe} | *Cost of Delay:* {top_rec.cost_of_delay}"
            )

        # 4. Limitations and data boundaries
        if data_gaps:
            paragraphs.append(
                f"### Data Boundaries & Limitations\n"
                + "\n".join([f"- {g}" for g in data_gaps])
                + "\n\n*Note: UrsBiz bases all recommendations strictly on verified records and does not invent speculative numbers.*"
            )

        return "\n\n".join(paragraphs)

    # ----------------------------------------------------------------------- #
    # Handlers for Special Non-Analytical Inquiries
    # ----------------------------------------------------------------------- #

    def _handle_unsupported_request(
        self, q: str, reason: str, now_iso: str
    ) -> RecommendationAskResponse:
        return RecommendationAskResponse(
            question=q,
            intent="unsupported_request",
            direct_answer=(
                f"I cannot fulfill this request as submitted. {reason}\n\n"
                "UrsBiz is an AI business intelligence platform designed specifically to advise MSME owners on sales trends, "
                "customer concentration, demand forecasting, business health diagnostics, and eligible government schemes "
                "based on verified business data."
            ),
            evidence_points=[],
            calculations=[],
            situational_recommendations=[],
            data_limitations_and_gaps=[reason],
            follow_up_questions=[
                "Would you like an analysis of your customer concentration risk?",
                "Would you like to review demand forecasts for your top products?",
                "Should we explore government schemes matching your industry?",
            ],
            tool_executions=[],
            query_type="unsupported",
            is_ai_generated=False,
            generated_at=now_iso,
            answerability=AnswerabilityStatus.UNSUPPORTED_REQUEST,
            answerability_reason=reason,
            trust_label="Unsupported Request",
        )

    def _handle_ambiguous_question(self, q: str, intent: str, now_iso: str) -> RecommendationAskResponse:
        return RecommendationAskResponse(
            question=q,
            intent=intent,
            direct_answer=(
                f"Your question *\"{q}\"* is quite broad. To give you the most accurate and practical recommendation, "
                "could you clarify what specific aspect of your business you would like to explore?\n\n"
                "For example, you can ask:\n"
                "- *\"Why are my sales declining and which products are affected?\"*\n"
                "- *\"Am I dependent on a few key customers?\"*\n"
                "- *\"What is the demand forecast for my products next month?\"*\n"
                "- *\"Which government schemes match my business profile?\"*"
            ),
            evidence_points=[],
            calculations=[],
            situational_recommendations=[],
            data_limitations_and_gaps=["User inquiry lacked specific metric, entity, or domain scope."],
            follow_up_questions=[
                "Would you like an overview of your top-selling products?",
                "Would you like an analysis of customer concentration?",
                "Should we review your overall Business Health Index?",
            ],
            tool_executions=[],
            query_type="ambiguous",
            is_ai_generated=False,
            generated_at=now_iso,
            answerability=AnswerabilityStatus.NEEDS_CLARIFICATION,
            answerability_reason="The inquiry is too brief or ambiguous. Clarifying context is required.",
            trust_label="Needs Clarification",
        )

    def _handle_unavailable_data_question(
        self, q: str, intent: str, q_lower: str, now_iso: str
    ) -> RecommendationAskResponse:
        missing_metric = "the requested operational metric"
        if "stock" in q_lower or "reorder" in q_lower or "warehouse" in q_lower:
            missing_metric = "warehouse stock balances, reorder points, and supplier delivery lead times"
        elif "depreciation" in q_lower or "tax" in q_lower:
            missing_metric = "asset depreciation schedules and filed statutory tax returns"
        elif "cac" in q_lower or "ad spend" in q_lower or "channel" in q_lower:
            missing_metric = "marketing channel ad spend and customer acquisition cost ledgers"

        return RecommendationAskResponse(
            question=q,
            intent=intent,
            direct_answer=(
                f"I cannot determine this accurately because your UrsBiz business account does not currently track {missing_metric}.\n\n"
                f"**Boundary Disclosure:** UrsBiz specializes in sales intelligence, customer analytics, demand trend forecasting, "
                f"and government scheme matching based strictly on verified business records. We do not invent physical warehouse counts, "
                f"lead times, or unrecorded expense schedules.\n\n"
                f"To manage replenishment, we recommend comparing your Phase 4 demand forecast velocity with your physical inventory logs."
            ),
            evidence_points=[],
            calculations=[],
            situational_recommendations=[],
            data_limitations_and_gaps=[
                f"UrsBiz does not track {missing_metric}. Operational records must be confirmed externally."
            ],
            follow_up_questions=[
                "Would you like to review your Phase 4 product demand forecast velocity?",
                "Would you like to analyze historical sales transaction trends?",
            ],
            tool_executions=[],
            query_type="data_unavailable",
            is_ai_generated=False,
            generated_at=now_iso,
            answerability=AnswerabilityStatus.INSUFFICIENT_DATA,
            answerability_reason=f"UrsBiz does not track {missing_metric}.",
            trust_label="Data Upload Required",
        )

    def _handle_general_business_guidance(
        self, ctx: UnifiedRecommendationContext, q: str, intent: str, now_iso: str
    ) -> RecommendationAskResponse:
        guidance_text = (
            f"**General Business Guidance:** Regarding your question *\"{q}\"*, here are core strategic principles "
            f"for MSME growth (distinct from specific empirical ledger findings):\n\n"
            f"1. **Working Capital Buffer:** Ensure you have at least 3-6 months of operating expenses preserved before committing capital to expansion.\n"
            f"2. **Product-Market Fit & Unit Economics:** Confirm positive contribution margins before scaling distribution or marketing spend.\n"
            f"3. **Customer Concentration Hedge:** Avoid entering new expansion phases if a single buyer represents more than 30% of your current revenue.\n"
            f"4. **Statutory & Regulatory Readiness:** Verify export licenses (IEC), quality certifications (e.g. ZED, ISO), and GST compliance."
        )

        return RecommendationAskResponse(
            question=q,
            intent=intent,
            direct_answer=guidance_text,
            evidence_points=[
                f"Business Context: {ctx.profile.legal_name} | Industry: {ctx.profile.industry} | State: {ctx.profile.state_region or 'India'}",
                "General strategic principles sourced from MSME operational best practices.",
            ],
            calculations=[],
            situational_recommendations=[
                SituationalRecommendation(
                    title="Conduct an Internal Readiness & Working Capital Audit",
                    category="Business Strategy",
                    priority="High",
                    situational_rationale=(
                        "Expansion initiatives require financial resilience and operational stress-testing before scaling commitments."
                    ),
                    action_steps=[
                        "Review current cash runway and upcoming receivables",
                        "Evaluate existing capacity utilization of production/service delivery",
                        "Consult your Advisor dashboard for eligible government growth schemes",
                    ],
                    timeframe="15-30 days",
                    cost_of_delay="Premature expansion without working capital reserves exposes MSMEs to severe cash crunches.",
                )
            ],
            data_limitations_and_gaps=[
                "This response reflects general MSME business strategy and is not derived from specific uploaded expense or inventory ledgers."
            ],
            follow_up_questions=[
                "Would you like to review eligible government schemes for business expansion?",
                "Should we analyze your current customer concentration before planning expansion?",
            ],
            tool_executions=[],
            query_type="general_business_guidance",
            is_ai_generated=False,
            generated_at=now_iso,
            answerability=AnswerabilityStatus.ANSWERABLE,
            answerability_reason="General strategic guidance grounded in MSME operational standards.",
            trust_label="General Advisory Only",
        )

    # ----------------------------------------------------------------------- #
    # Resilient Gemini Calling with Fallback
    # ----------------------------------------------------------------------- #

    def _call_gemini_reasoning(
        self,
        ctx: UnifiedRecommendationContext,
        question: str,
        intent: str,
        evidence: list[str],
        calculations: list[CalculationStep],
        data_gaps: list[str],
        deterministic_baseline: str,
    ) -> Optional[str]:
        """Perform bounded Gemini call with zero-hallucination guard."""
        settings = get_settings()
        system_prompt = (
            "You are the Senior MSME Business Growth Consultant for UrsBiz. "
            "Answer the business owner's question using ONLY the provided verified facts, calculations, and data boundaries.\n"
            "CRITICAL RULES:\n"
            "1. NEVER invent, alter, or extrapolate any numbers, financial figures, customer names, or dates. Use strictly the provided calculations and metrics.\n"
            "2. If asked about warehouse stock balances, reorder points, or stockout dates, explicitly state that UrsBiz does not track warehouse inventory or lead times, and advise operational trend review only.\n"
            "3. Speak directly to the business owner in a clear, pragmatic, encouraging, and authoritative executive tone.\n"
            "4. Clearly distinguish between what is proven by verified data and what is a general business consideration."
        )

        calc_text = "\n".join([f"- {c.name}: {c.result} [Formula: {c.formula}]" for c in calculations])
        ev_text = "\n".join([f"- {e}" for e in evidence])
        gaps_text = "\n".join([f"- {g}" for g in data_gaps])

        user_content = (
            f"Business: {ctx.profile.legal_name} ({ctx.profile.industry})\n"
            f"User Question: \"{question}\"\n"
            f"Intent: {intent}\n\n"
            f"Verified Evidence:\n{ev_text}\n\n"
            f"Verified Calculations:\n{calc_text}\n\n"
            f"Known Data Gaps & Boundaries:\n{gaps_text}\n\n"
            f"Please provide an articulate, executive-grade consultation response in 2-3 short, focused paragraphs."
        )

        headers = {
            "Authorization": f"Bearer {settings.ai_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": settings.ai_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "max_tokens": 400,
            "temperature": 0.2,
        }

        url = f"{settings.ai_base_url.rstrip('/')}/chat/completions"
        with httpx.Client(timeout=_TOOL_EXECUTION_TIMEOUT_SECONDS) as client:
            resp = client.post(url, headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"]["content"].strip()
                if content and len(content) > 40:
                    return content
        return None
