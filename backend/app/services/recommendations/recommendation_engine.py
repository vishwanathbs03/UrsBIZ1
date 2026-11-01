"""Context-Aware Business Recommendation Engine (Phase 5 Advanced Intelligence).

Orchestrates the 4-tier recommendation architecture:
  Tier 1: Verified Business Data via RecommendationContextService
  Tier 2: Deterministic Rules & Prioritization via RecommendationRuleRegistry & RecommendationPrioritizationService
          Advanced Multi-Signal, Root Cause, Opportunity, and Scenario Engines
  Tier 3: Explainability & 3-Horizon Strategy via ExplanationService & GrowthStrategyEngine
  Tier 4: Lifecycle Tracking & Feedback Persistence via RecommendationLifecycleRepository & RecommendationFeedbackRepository

Enforces strict inventory and revenue boundaries:
  - Phase 3 has no inventory balances, supplier lead times, or stockout dates:
    recommends operational review of demand trends only; never calculates reorder
    quantities, safety stock, or liquidation targets.
  - Historical inactive-customer spend is historical evidence only:
    never claimed as guaranteed or calculated recoverable revenue.
  - Composite ID schema: rec_{rule_id}_{business_id}_{entity_id}_v{version}
    ensuring idempotent lifecycle tracking across data refreshes.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from typing import Any, Optional
from sqlalchemy.orm import Session

from app.models.business import Business
from app.repositories.recommendation_feedback_repository import (
    RecommendationFeedbackRepository,
)
from app.repositories.recommendation_lifecycle_repository import (
    RecommendationLifecycleRepository,
)
from app.schemas.advanced_recommendations import (
    AdvancedRecommendationsOverviewResponse,
    PersonalizedGrowthStrategy,
    RecommendationAskRequest,
    RecommendationAskResponse,
    RecommendationFeedbackCreate,
    RecommendationFeedbackResponse,
    ScenarioSimulationRequest,
    ScenarioSimulationResponse,
)
from app.schemas.smart_recommendations import (
    RecommendationCategory,
    RecommendationPriority,
    RecommendationStatus,
    SmartRecommendationItem,
    SmartRecommendationsResponse,
)
from app.services.recommendations.context_service import RecommendationContextService
from app.services.recommendations.conversational_advisor import (
    ConversationalRecommendationAdvisor,
)
from app.services.recommendations.growth_strategy_engine import GrowthStrategyEngine
from app.services.recommendations.multi_signal_engine import MultiSignalEngine
from app.services.recommendations.next_best_action_engine import NextBestActionEngine
from app.services.recommendations.opportunity_discovery_engine import (
    OpportunityDiscoveryEngine,
)
from app.services.recommendations.prioritization_service import (
    RecommendationPrioritizationService,
)
from app.services.recommendations.quality_engine import RecommendationQualityEngine
from app.services.recommendations.root_cause_engine import RootCauseEngine
from app.services.recommendations.rule_registry import RecommendationRuleRegistry
from app.services.recommendations.scenario_engine import ScenarioSimulationEngine
from app.repositories.personalization_repository import PersonalizationRepository
from app.services.recommendations.personalization_engine import PersonalizationEngine
from app.services.recommendations.portfolio_engine import RecommendationPortfolioEngine
from app.schemas.personalization import (
    BusinessConstraintType,
    BusinessGoalType,
    BusinessMaturityLevel,
    PersonalizationSettingsUpdate,
    RecommendationPersonalizationProfile,
)
from app.schemas.portfolio import RecommendationPortfolioResponse
from app.repositories.recommendation_outcome_repository import (
    RecommendationOutcomeRepository,
)
from app.services.recommendations.outcome_measurement_engine import (
    BeforeAfterMeasurementEngine,
)
from app.services.recommendations.outcome_learning_engine import (
    RecommendationOutcomeLearningEngine,
)
from app.schemas.recommendation_outcomes import (
    BeforeAfterMeasurementResponse,
    CompleteHistoryResponse,
    OutcomeRecordingRequest,
    OutcomeTrackingResponse,
    RecommendationAuditEventItem,
    RecommendationEffectivenessResponse,
    RecommendationHistoryResponse,
)
from app.schemas.business_monitoring import (
    BusinessSignalsFeedResponse,
    MonitoringEvaluationResponse,
    MonitoringPreferencesSchema,
    MonitoringPreferencesUpdate,
)
from app.services.recommendations.proactive_monitoring_service import (
    ProactiveMonitoringService,
)

logger = logging.getLogger(__name__)


class SmartRecommendationEngine:
    """Core recommendation generation and deterministic prioritization orchestrator."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.context_service = RecommendationContextService(db)
        self.rule_registry = RecommendationRuleRegistry()
        self.prioritizer = RecommendationPrioritizationService()
        self.lifecycle_repo = RecommendationLifecycleRepository(db)
        self.feedback_repo = RecommendationFeedbackRepository(db)
        self.personalization_repo = PersonalizationRepository(db)
        self.personalization_engine = PersonalizationEngine()
        self.portfolio_engine = RecommendationPortfolioEngine()
        self.outcome_repo = RecommendationOutcomeRepository(db)
        self.measurement_engine = BeforeAfterMeasurementEngine(db)
        self.outcome_learning_engine = RecommendationOutcomeLearningEngine(db)
        self.quality_engine = RecommendationQualityEngine()
        self.multi_signal_engine = MultiSignalEngine()
        self.root_cause_engine = RootCauseEngine()
        self.opportunity_engine = OpportunityDiscoveryEngine()
        self.next_best_action_engine = NextBestActionEngine()
        self.scenario_engine = ScenarioSimulationEngine()
        self.growth_strategy_engine = GrowthStrategyEngine()
        self.conversational_advisor = ConversationalRecommendationAdvisor()
        self.monitoring_service = ProactiveMonitoringService(db)

    def generate_recommendations(
        self,
        business: Business,
        category_filter: Optional[str] = None,
        priority_filter: Optional[str] = None,
        status_filter: Optional[str] = None,
    ) -> SmartRecommendationsResponse:
        """Generate context-grounded recommendations for a business with lifecycle state tracking."""
        now_iso = datetime.now(timezone.utc).isoformat()

        # Tier 1: Aggregate verified context from all subsystems
        ctx = self.context_service.build_context(business)

        # Tier 2: Evaluate modular rules against verified context
        raw_candidates = self.rule_registry.evaluate_all(ctx)

        # Tier 4: Fetch persisted lifecycle states and record first views
        persisted_states = self.lifecycle_repo.get_states_for_business(business.id)

        # Tier 2b: Autonomous Opportunity Discovery (Beyond Predefined Rules)
        active_candidate_ids = set(c["id"] for c in raw_candidates)
        completed_ids = set(
            rec_id for rec_id, s in persisted_states.items()
            if s.status in (RecommendationStatus.COMPLETED.value, RecommendationStatus.DISMISSED.value)
        )
        opp_candidates = self.opportunity_engine.generate_opportunity_recommendation_candidates(
            ctx=ctx,
            active_rec_ids=active_candidate_ids,
            completed_rec_ids=completed_ids,
        )
        raw_candidates.extend(opp_candidates)

        candidate_ids = [c["id"] for c in raw_candidates]
        self.lifecycle_repo.record_first_views(business.id, candidate_ids)

        # Get feedback suppressions
        suppressed_ids = self.feedback_repo.get_suppressed_recommendation_ids(business.id)

        # Tier 2c: Personalization & Business DNA Adaptation Profile
        pers_settings = self.personalization_repo.get_or_create_settings(business.id, business=business)
        try:
            active_goals = json.loads(pers_settings.goals)
        except Exception:
            active_goals = []
        try:
            active_constraints = json.loads(pers_settings.constraints)
        except Exception:
            active_constraints = []
        try:
            focus_areas = json.loads(pers_settings.focus_areas)
        except Exception:
            focus_areas = []

        recent_feedback = self.personalization_repo.get_recent_feedback(business.id)
        maturity, maturity_drivers = self.personalization_engine.evaluate_maturity(
            business=business,
            sales_total_revenue=ctx.sales.total_revenue,
            sales_tx_count=ctx.sales.total_transactions,
        )

        # Tier 2: Deterministic Prioritization Scoring with Personalization Adaptation
        scored_items: list[SmartRecommendationItem] = []
        for cand in raw_candidates:
            u = cand.get("urgency", 50)
            imp = cand.get("impact", 50)
            ev = cand.get("evidence_strength", 50)
            conf = cand.get("confidence", 70.0)
            feas = cand.get("feasibility", 60)

            # Personalization Sub-scores
            goal_align = self.personalization_engine.calculate_goal_alignment(
                category=cand["category"],
                title=cand["title"],
                description=cand["description"],
                active_goals=active_goals,
            )
            mat_fit = self.personalization_engine.calculate_maturity_fit(
                category=cand["category"],
                maturity=maturity,
                difficulty=cand.get("implementation_difficulty", "Tactical"),
            )
            const_pen, const_warns = self.personalization_engine.evaluate_constraints(
                category=cand["category"],
                title=cand["title"],
                description=cand["description"],
                active_constraints=active_constraints,
                preferred_investment=pers_settings.preferred_investment_level,
                preferred_effort=pers_settings.preferred_effort_level,
            )
            pref_score = self.personalization_engine.calculate_preference_score(
                category=cand["category"],
                recent_feedback=recent_feedback,
                focus_areas=focus_areas,
            )

            p_score, p_level, pers_comp, adj_feas = (
                self.personalization_engine.compute_personalized_priority(
                    base_urgency=u,
                    base_impact=imp,
                    evidence_strength=ev,
                    confidence=conf,
                    base_feasibility=feas,
                    goal_alignment_score=goal_align,
                    maturity_fit_score=mat_fit,
                    preference_score=pref_score,
                    constraint_penalty=const_pen,
                )
            )

            pers_expl = self.personalization_engine.build_personalization_explanation(
                business=business,
                category=cand["category"],
                title=cand["title"],
                maturity=maturity,
                maturity_drivers=maturity_drivers,
                active_goals=active_goals,
                active_constraints=active_constraints,
                constraint_warnings=const_warns,
                missing_data=ctx.data_limitations,
                goal_score=goal_align,
                maturity_score=mat_fit,
                pref_score=pref_score,
                constraint_pen=const_pen,
                priority_rank=1,
                is_critical_risk=(u >= 80.0),
            )

            state_record = persisted_states.get(cand["id"])
            if state_record:
                curr_status = RecommendationStatus(state_record.status)
                status_updated = (
                    state_record.status_updated_at.isoformat()
                    if state_record.status_updated_at
                    else None
                )
                rec_notes = state_record.notes
            else:
                curr_status = RecommendationStatus.NEW
                status_updated = now_iso
                rec_notes = None

            item = SmartRecommendationItem(
                id=cand["id"],
                title=cand["title"],
                category=cand["category"],
                priority=p_level,
                priority_score=p_score,
                description=cand["description"],
                business_context=cand["business_context"],
                evidence=cand.get("evidence", []),
                reasoning=cand["reasoning"],
                recommended_actions=cand.get("recommended_actions", []),
                action_plan=cand.get("action_plan"),
                expected_benefit=cand["expected_benefit"],
                estimated_impact=cand.get("estimated_impact"),
                impact_unit=cand.get("impact_unit"),
                confidence=float(conf),
                data_quality=cand.get("data_quality", "Moderate"),
                limitations=cand.get("limitations", []),
                source_modules=cand.get("source_modules", []),
                source_module_link=cand.get("source_module_link"),
                created_at=now_iso,
                status=curr_status,
                status_updated_at=status_updated,
                notes=rec_notes,
                what_is_happening=cand.get("what_is_happening"),
                why_it_matters=cand.get("why_it_matters"),
                root_cause=cand.get("root_cause"),
                missed_opportunity=cand.get("missed_opportunity"),
                action_scenario=cand.get("action_scenario"),
                cost_of_inaction=cand.get("cost_of_inaction"),
                measurement_kpis=cand.get("measurement_kpis", []),
                implementation_difficulty=cand.get("implementation_difficulty", "Tactical"),
                prerequisites_and_tradeoffs=cand.get("prerequisites_and_tradeoffs", []),
                is_autonomous_opportunity=cand.get("is_autonomous_opportunity", False),
                opportunity_quality_status=cand.get("opportunity_quality_status"),
                opportunity_hypothesis_id=cand.get("opportunity_hypothesis_id"),
                personalization_explanation=pers_expl.model_dump(),
                personalization_score=pers_comp,
                goal_alignment_score=goal_align,
                maturity_fit_score=mat_fit,
                constraint_adjusted_feasibility=adj_feas,
            )
            scored_items.append(item)

        # Apply Quality Gate
        filtered_items = self.quality_engine.filter_actionable(scored_items)

        # Sort by deterministic priority score descending
        filtered_items.sort(key=lambda r: r.priority_score, reverse=True)

        # Update ranking rationale numbers post-sort
        for rank_idx, item in enumerate(filtered_items, start=1):
            if item.personalization_explanation and "ranking_rationale" in item.personalization_explanation:
                item.personalization_explanation["ranking_rationale"] = (
                    item.personalization_explanation["ranking_rationale"].replace("Ranked #1", f"Ranked #{rank_idx}")
                )

        # Apply Suppression & Filters
        if not status_filter or status_filter.lower() != "all":
            # Suppress items dismissed by user feedback
            filtered_items = [i for i in filtered_items if i.id not in suppressed_ids]
            # Apply closed-loop learning & repeated suppression with critical risk protection
            filtered_items = self.outcome_learning_engine.apply_learning_to_recommendations(
                filtered_items, business.id
            )

        if category_filter and category_filter != "all":
            filtered_items = [
                i
                for i in filtered_items
                if i.category.value.lower() == category_filter.lower()
            ]

        if priority_filter and priority_filter != "all":
            filtered_items = [
                i
                for i in filtered_items
                if i.priority.value.lower() == priority_filter.lower()
            ]

        if status_filter and status_filter != "all":
            filtered_items = [
                i
                for i in filtered_items
                if i.status.value.lower() == status_filter.lower()
            ]
        elif not status_filter:
            filtered_items = [
                i for i in filtered_items if i.status != RecommendationStatus.DISMISSED
            ]

        crit_count = sum(
            1 for i in filtered_items if i.priority == RecommendationPriority.CRITICAL
        )
        high_count = sum(
            1 for i in filtered_items if i.priority == RecommendationPriority.HIGH
        )
        med_count = sum(
            1 for i in filtered_items if i.priority == RecommendationPriority.MEDIUM
        )
        low_count = sum(
            1 for i in filtered_items if i.priority == RecommendationPriority.LOW
        )

        status_counts: dict[str, int] = {}
        for i in filtered_items:
            status_counts[i.status.value] = status_counts.get(i.status.value, 0) + 1

        category_counts: dict[str, int] = {}
        for i in filtered_items:
            category_counts[i.category.value] = (
                category_counts.get(i.category.value, 0) + 1
            )

        return SmartRecommendationsResponse(
            generated_at=now_iso,
            business_id=business.id,
            business_name=business.legal_name,
            total_count=len(filtered_items),
            critical_count=crit_count,
            high_count=high_count,
            medium_count=med_count,
            low_count=low_count,
            status_counts=status_counts,
            category_counts=category_counts,
            recommendations=filtered_items,
        )

    def get_advanced_overview(
        self, business: Business
    ) -> AdvancedRecommendationsOverviewResponse:
        """Construct full advanced intelligence overview for the executive dashboard."""
        now_iso = datetime.now(timezone.utc).isoformat()
        ctx = self.context_service.build_context(business)

        # Generate base recommendations
        rec_response = self.generate_recommendations(business=business, status_filter="all")
        suppressed_ids = self.feedback_repo.get_suppressed_recommendation_ids(business.id)

        # 1. Next Best Business Action Engine
        next_best = self.next_best_action_engine.rank_actions(
            recommendations=rec_response.recommendations,
            suppressed_ids=suppressed_ids,
        )

        # 2. Multi-Signal Engine
        multi_signal = self.multi_signal_engine.analyze(ctx)

        # 3. Root Cause Engine
        root_causes = self.root_cause_engine.diagnose(ctx)

        # 4. Opportunity Discovery Engine
        active_ids = set(r.id for r in rec_response.recommendations)
        persisted_states = self.lifecycle_repo.get_states_for_business(business.id)
        completed_ids = set(
            rec_id for rec_id, s in persisted_states.items()
            if s.status in (RecommendationStatus.COMPLETED.value, RecommendationStatus.DISMISSED.value)
        )
        hypotheses = self.opportunity_engine.discover_hypotheses(
            ctx=ctx,
            active_rec_ids=active_ids,
            completed_rec_ids=completed_ids,
        )
        opportunities = self.opportunity_engine.hypotheses_to_opportunity_items(hypotheses)

        evidence_summary: dict[str, Any] = {
            "sources_verified": ctx.data_sources_present,
            "has_sales_ledger": ctx.sales.has_sales_data,
            "total_revenue": ctx.sales.total_revenue,
            "has_forecast_intelligence": ctx.forecast.has_forecast_data,
            "schemes_matched": len(ctx.schemes.recommended_schemes),
            "business_health_score": ctx.health.overall_score,
            "data_limitations_count": len(ctx.data_limitations),
        }

        return AdvancedRecommendationsOverviewResponse(
            business_id=business.id,
            business_name=business.legal_name,
            generated_at=now_iso,
            next_best_action=next_best,
            multi_signal_insights=multi_signal,
            root_cause_analyses=root_causes,
            opportunities=opportunities,
            opportunity_hypotheses=hypotheses,
            evidence_summary=evidence_summary,
        )

    def get_growth_strategy(self, business: Business) -> PersonalizedGrowthStrategy:
        """Generate personalized 3-horizon growth strategy for the business."""
        ctx = self.context_service.build_context(business)
        rec_response = self.generate_recommendations(business=business)
        return self.growth_strategy_engine.generate_strategy(
            ctx=ctx, recommendations=rec_response.recommendations
        )

    def get_recommendation_portfolio(
        self, business: Business
    ) -> RecommendationPortfolioResponse:
        """Construct a coherent, optimized recommendation portfolio with dependencies and conflicts."""
        ctx = self.context_service.build_context(business)
        rec_response = self.generate_recommendations(business=business, status_filter="all")
        persisted_states = self.lifecycle_repo.get_states_for_business(business.id)
        return self.portfolio_engine.build_portfolio(
            business=business,
            recommendations=rec_response.recommendations,
            ctx=ctx,
            persisted_states=persisted_states,
        )

    def simulate_scenario(
        self, business: Business, req: ScenarioSimulationRequest
    ) -> ScenarioSimulationResponse:
        """Run deterministic What-If scenario simulation."""
        ctx = self.context_service.build_context(business)
        return self.scenario_engine.simulate(ctx=ctx, req=req)

    def record_feedback(
        self, business: Business, req: RecommendationFeedbackCreate
    ) -> RecommendationFeedbackResponse:
        """Record owner feedback on a recommendation and apply automatic suppression if appropriate."""
        # Check if recommendation is an enterprise risk alert
        is_risk = any(
            k in req.recommendation_id.lower()
            for k in ("risk", "churn", "concentration", "solvency", "runway")
        )

        # Do not permanently suppress critical risk alerts merely because owner dismissed them
        suppress_flag = False if is_risk else None

        feedback = self.feedback_repo.record_feedback(
            business_id=business.id,
            recommendation_id=req.recommendation_id,
            feedback_type=req.feedback_type,
            outcome_notes=req.outcome_notes,
            suppress=suppress_flag,
        )

        # If suppressed or already implemented, update lifecycle status
        if req.feedback_type in ("Already implemented", "Implemented"):
            self.lifecycle_repo.update_status(
                business_id=business.id,
                recommendation_id=req.recommendation_id,
                status="Completed",
                notes=req.outcome_notes or "Marked as already implemented by owner",
            )
        elif req.feedback_type in (
            "Not relevant",
            "Not relevant to my business",
            "Incorrect information",
            "Not feasible",
            "Too expensive",
            "Not aligned with my current goal",
        ):
            if is_risk:
                self.lifecycle_repo.update_status(
                    business_id=business.id,
                    recommendation_id=req.recommendation_id,
                    status="Viewed",
                    notes="Critical risk alert retained for business safety despite dismissal.",
                )
            else:
                self.lifecycle_repo.update_status(
                    business_id=business.id,
                    recommendation_id=req.recommendation_id,
                    status="Dismissed",
                    notes=req.outcome_notes or f"Marked as {req.feedback_type} by owner",
                )

        return RecommendationFeedbackResponse(
            id=feedback.id,
            business_id=feedback.business_id,
            recommendation_id=feedback.recommendation_id,
            feedback_type=feedback.feedback_type,
            suppress_recommendation=feedback.suppress_recommendation,
            outcome_notes=feedback.outcome_notes,
            created_at=feedback.created_at.isoformat() if feedback.created_at else "",
        )

    def get_personalization_profile(
        self, business: Business
    ) -> RecommendationPersonalizationProfile:
        """Construct structured Recommendation Personalization Profile."""
        ctx = self.context_service.build_context(business)
        pers_settings = self.personalization_repo.get_or_create_settings(business.id, business=business)
        try:
            active_goals = json.loads(pers_settings.goals)
        except Exception:
            active_goals = []
        try:
            active_constraints = json.loads(pers_settings.constraints)
        except Exception:
            active_constraints = []
        try:
            focus_areas = json.loads(pers_settings.focus_areas)
        except Exception:
            focus_areas = []

        maturity, maturity_drivers = self.personalization_engine.evaluate_maturity(
            business=business,
            sales_total_revenue=ctx.sales.total_revenue,
            sales_tx_count=ctx.sales.total_transactions,
        )
        feedback_summary = self.personalization_repo.get_feedback_summary(business.id)

        now_iso = datetime.now(timezone.utc).isoformat()
        updated_iso = (
            pers_settings.updated_at.isoformat()
            if pers_settings.updated_at
            else now_iso
        )

        return RecommendationPersonalizationProfile(
            business_id=business.id,
            business_name=business.legal_name or "Your Business",
            industry=business.industry or "General MSME",
            sub_industry=business.sub_industry,
            business_type=business.business_type,
            dna_archetype="Pragmatic Operator",
            dna_stage=maturity.value,
            evaluated_maturity=maturity,
            maturity_drivers=maturity_drivers,
            active_goals=active_goals,
            active_constraints=active_constraints,
            preferred_effort_level=pers_settings.preferred_effort_level,
            preferred_investment_level=pers_settings.preferred_investment_level,
            focus_areas=focus_areas,
            feedback_summary=feedback_summary,
            source=pers_settings.source,
            updated_at=updated_iso,
        )

    def update_personalization_settings(
        self, business: Business, payload: PersonalizationSettingsUpdate
    ) -> RecommendationPersonalizationProfile:
        """Update owner personalization preferences and constraints."""
        self.personalization_repo.update_settings(business.id, payload)
        return self.get_personalization_profile(business)

    def ask_recommendation_question(
        self, business: Business, req: RecommendationAskRequest
    ) -> RecommendationAskResponse:
        """Answer natural language business questions using cross-signal intelligence, calculations, and boundaries."""
        ctx = self.context_service.build_context(business)
        return self.conversational_advisor.answer_question(ctx=ctx, req=req)

    # ----------------------------------------------------------------------- #
    # Closed-Loop Outcome Tracking & Business Measurement                     #
    # ----------------------------------------------------------------------- #

    def record_outcome(
        self,
        business: Business,
        recommendation_id: str,
        req: OutcomeRecordingRequest,
    ) -> OutcomeTrackingResponse:
        """Record implementation outcome, evaluate empirical before/after metrics, and append audit event."""
        started_dt: Optional[datetime] = None
        if req.started_at:
            try:
                started_dt = datetime.fromisoformat(req.started_at)
            except Exception:
                pass

        completed_dt: Optional[datetime] = None
        if req.completed_at:
            try:
                completed_dt = datetime.fromisoformat(req.completed_at)
            except Exception:
                pass

        # 1. Persist outcome
        outcome = self.outcome_repo.record_outcome(
            business_id=business.id,
            recommendation_id=recommendation_id,
            is_started=req.is_started,
            is_completed=req.is_completed,
            is_abandoned=req.is_abandoned,
            started_at=started_dt,
            completed_at=completed_dt,
            actual_effort=req.actual_effort,
            owner_rating=req.owner_rating,
            qualitative_feedback=req.qualitative_feedback,
            perceived_utility=req.perceived_utility,
            non_completion_reason=req.non_completion_reason,
            still_relevant=req.still_relevant,
            notes=req.notes,
        )

        # 2. Before-and-after business measurement
        measurement: Optional[BeforeAfterMeasurementResponse] = None
        if outcome.is_completed and outcome.completed_at:
            measurement = self.measurement_engine.measure_outcome(
                business_id=business.id,
                recommendation_id=recommendation_id,
                recommendation_title=recommendation_id.replace("_", " ").title(),
                completed_at=outcome.completed_at,
                window_days=30,
            )
            # Update measured outcome summary
            rev_metric = next((m for m in measurement.metrics if m.metric_name == "Total Revenue"), None)
            summary_txt = rev_metric.observation_statement if rev_metric else "Empirical before-and-after metrics calculated."
            outcome.measured_outcome_summary = summary_txt
            self.db.commit()

        # 3. Append immutable audit event
        event_type = "OUTCOME_RECORDED"
        if req.is_completed:
            event_type = "COMPLETED"
        elif req.is_abandoned:
            event_type = "DISMISSED"
        elif req.is_started:
            event_type = "IN_PROGRESS"

        self.outcome_repo.record_audit_event(
            business_id=business.id,
            recommendation_id=recommendation_id,
            title=recommendation_id.replace("_", " ").title(),
            category="Recommendation Implementation",
            priority="Medium",
            priority_score=70,
            event_type=event_type,
            event_notes=req.notes or req.qualitative_feedback or f"Outcome status: {event_type}",
            metrics_snapshot={"actual_effort": req.actual_effort, "rating": req.owner_rating},
        )

        now_iso = datetime.now(timezone.utc).isoformat()
        return OutcomeTrackingResponse(
            id=outcome.id,
            business_id=outcome.business_id,
            recommendation_id=outcome.recommendation_id,
            is_started=outcome.is_started,
            is_completed=outcome.is_completed,
            is_abandoned=outcome.is_abandoned,
            started_at=outcome.started_at.isoformat() if outcome.started_at else None,
            completed_at=outcome.completed_at.isoformat() if outcome.completed_at else None,
            actual_effort=outcome.actual_effort,
            owner_rating=outcome.owner_rating,
            qualitative_feedback=outcome.qualitative_feedback,
            perceived_utility=outcome.perceived_utility,
            non_completion_reason=outcome.non_completion_reason,
            still_relevant=outcome.still_relevant,
            measured_outcome_summary=outcome.measured_outcome_summary,
            measurement=measurement,
            created_at=outcome.created_at.isoformat() if outcome.created_at else now_iso,
            updated_at=outcome.updated_at.isoformat() if outcome.updated_at else now_iso,
        )

    def get_outcome(
        self,
        business: Business,
        recommendation_id: str,
        window_days: int = 30,
    ) -> OutcomeTrackingResponse:
        """Fetch outcome record and calculate empirical before/after measurement."""
        outcome = self.outcome_repo.get_outcome(business.id, recommendation_id)
        now_iso = datetime.now(timezone.utc).isoformat()

        if outcome is None:
            measurement = self.measurement_engine.measure_outcome(
                business_id=business.id,
                recommendation_id=recommendation_id,
                recommendation_title=recommendation_id.replace("_", " ").title(),
                completed_at=None,
                window_days=window_days,
            )
            return OutcomeTrackingResponse(
                id=0,
                business_id=business.id,
                recommendation_id=recommendation_id,
                is_started=False,
                is_completed=False,
                is_abandoned=False,
                still_relevant=True,
                measurement=measurement,
                created_at=now_iso,
                updated_at=now_iso,
            )

        measurement = None
        if outcome.is_completed and outcome.completed_at:
            measurement = self.measurement_engine.measure_outcome(
                business_id=business.id,
                recommendation_id=recommendation_id,
                recommendation_title=recommendation_id.replace("_", " ").title(),
                completed_at=outcome.completed_at,
                window_days=window_days,
            )

        return OutcomeTrackingResponse(
            id=outcome.id,
            business_id=outcome.business_id,
            recommendation_id=outcome.recommendation_id,
            is_started=outcome.is_started,
            is_completed=outcome.is_completed,
            is_abandoned=outcome.is_abandoned,
            started_at=outcome.started_at.isoformat() if outcome.started_at else None,
            completed_at=outcome.completed_at.isoformat() if outcome.completed_at else None,
            actual_effort=outcome.actual_effort,
            owner_rating=outcome.owner_rating,
            qualitative_feedback=outcome.qualitative_feedback,
            perceived_utility=outcome.perceived_utility,
            non_completion_reason=outcome.non_completion_reason,
            still_relevant=outcome.still_relevant,
            measured_outcome_summary=outcome.measured_outcome_summary,
            measurement=measurement,
            created_at=outcome.created_at.isoformat() if outcome.created_at else now_iso,
            updated_at=outcome.updated_at.isoformat() if outcome.updated_at else now_iso,
        )

    def get_effectiveness_analytics(
        self, business: Business
    ) -> RecommendationEffectivenessResponse:
        """Compute portfolio-wide and category-level recommendation effectiveness with small-sample safeguards."""
        return self.outcome_learning_engine.compute_effectiveness_intelligence(business.id)

    def get_recommendation_history(
        self, business: Business, recommendation_id: str
    ) -> RecommendationHistoryResponse:
        """Retrieve complete immutable version and decision audit history for a recommendation."""
        records = self.outcome_repo.get_history_for_recommendation(business.id, recommendation_id)
        current_v = max((r.version for r in records), default=1)
        items = [
            RecommendationAuditEventItem(
                id=r.id,
                recommendation_id=r.recommendation_id,
                version=r.version,
                title=r.title,
                category=r.category,
                priority=r.priority,
                priority_score=r.priority_score,
                evidence_version=r.evidence_version,
                evidence_summary=r.evidence_summary,
                event_type=r.event_type,
                event_notes=r.event_notes,
                metrics_snapshot=r.metrics_snapshot,
                created_at=r.created_at.isoformat() if r.created_at else "",
            )
            for r in records
        ]
        return RecommendationHistoryResponse(
            recommendation_id=recommendation_id,
            current_version=current_v,
            events=items,
        )

    def get_complete_history(
        self, business: Business, limit: int = 100
    ) -> CompleteHistoryResponse:
        """Retrieve recent immutable version and decision audit history across all recommendations."""
        records = self.outcome_repo.get_complete_history(business.id, limit=limit)
        items = [
            RecommendationAuditEventItem(
                id=r.id,
                recommendation_id=r.recommendation_id,
                version=r.version,
                title=r.title,
                category=r.category,
                priority=r.priority,
                priority_score=r.priority_score,
                evidence_version=r.evidence_version,
                evidence_summary=r.evidence_summary,
                event_type=r.event_type,
                event_notes=r.event_notes,
                metrics_snapshot=r.metrics_snapshot,
                created_at=r.created_at.isoformat() if r.created_at else "",
            )
            for r in records
        ]
        return CompleteHistoryResponse(
            business_id=business.id,
            total_events=len(items),
            events=items,
        )

    # ----------------------------------------------------------------------- #
    # Proactive AI Business Monitoring & Event Intelligence (Phase 5)         #
    # ----------------------------------------------------------------------- #

    def evaluate_monitoring(self, business: Business) -> MonitoringEvaluationResponse:
        """Run incremental proactive monitoring scan to detect business changes."""
        return self.monitoring_service.evaluate_business_changes(business)

    def get_signals_feed(
        self, business: Business, min_severity: Optional[str] = None
    ) -> BusinessSignalsFeedResponse:
        """Fetch proactive business signals and opportunities feed for owner dashboard."""
        return self.monitoring_service.get_signals_feed(business, min_severity=min_severity)

    def get_monitoring_preferences(self, business: Business) -> MonitoringPreferencesSchema:
        """Retrieve business monitoring settings and preferences."""
        return self.monitoring_service.get_monitoring_preferences(business)

    def update_monitoring_preferences(
        self, business: Business, payload: MonitoringPreferencesUpdate
    ) -> MonitoringPreferencesSchema:
        """Update owner monitoring preferences with critical safety preservation."""
        return self.monitoring_service.update_monitoring_preferences(business, payload)

    def dismiss_signal(self, business: Business, event_id: str) -> dict[str, Any]:
        """Acknowledge or dismiss an individual signal."""
        return self.monitoring_service.dismiss_signal(business, event_id)
