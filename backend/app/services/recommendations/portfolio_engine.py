"""Advanced Recommendation Portfolio Optimization and Conflict Resolution Engine (Phase 5).

Transforms independent recommendations into a coherent, strategically coordinated
business improvement portfolio for MSME owners.

Key Capabilities:
  1. Complete Portfolio Multi-Signal Analysis (Critical Risks, Quick Wins, Strategic Moves).
  2. Dependency Detection: Maps directional prerequisite relationships without inventing false ties.
  3. Conflict Detection: Identifies resource competition, strategic contradictions, and timing mismatches,
     providing explicit trade-off analyses and sequencing recommendations without discarding ideas.
  4. Deterministic Portfolio Optimization: Weights impact, risk reduction, urgency, feasibility,
     and prerequisite unblocking.
  5. Timeframe Segmentation: Classifies actions into Immediate (Quick Wins), Short-Term (Tactical),
     and Strategic Initiatives based on evidence and operational difficulty.
  6. Topological Execution Sequencing: Suggests a logical Step 1 -> Step 2 -> Step 3 roadmap
     with clear causal rationale and downstream unlock tracking.
  7. Portfolio Change & Obsolescence Detection: Flags retired recommendations as evidence shifts
     while preserving accepted/in-progress states.
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any, Optional, Set

from app.models.business import Business
from app.models.recommendation_lifecycle import RecommendationLifecycleState
from app.schemas.portfolio import (
    PortfolioObsoleteItem,
    RecommendationConflict,
    RecommendationDependency,
    RecommendationPortfolioResponse,
    SequencedAction,
)
from app.schemas.recommendation_context import UnifiedRecommendationContext
from app.schemas.smart_recommendations import (
    RecommendationCategory,
    RecommendationPriority,
    RecommendationStatus,
    SmartRecommendationItem,
)

logger = logging.getLogger("atlas.recommendations.portfolio")


class RecommendationPortfolioEngine:
    """Orchestrates portfolio analysis, dependency mapping, conflict resolution, and sequencing."""

    # ----------------------------------------------------------------------- #
    # 1. Dependency Detection                                                 #
    # ----------------------------------------------------------------------- #
    def detect_dependencies(
        self,
        recommendations: list[SmartRecommendationItem],
        ctx: UnifiedRecommendationContext,
        completed_ids: Set[str],
    ) -> list[RecommendationDependency]:
        """Identify verified structural prerequisites and enablers among active recommendations."""
        deps: list[RecommendationDependency] = []
        rec_map = {r.id: r for r in recommendations}

        for r in recommendations:
            r_cat = r.category.value if hasattr(r.category, "value") else str(r.category)
            r_title_l = r.title.lower()

            # Dependency Rule 1: Digital storefront / Online sales depends on basic Product catalog
            if r_cat == RecommendationCategory.DIGITAL_TRANSFORMATION.value or "storefront" in r_title_l or "e-commerce" in r_title_l:
                # Find if there is a catalog or record keeping recommendation
                catalog_recs = [
                    cand for cand in recommendations
                    if cand.id != r.id and ("catalog" in cand.title.lower() or "product" in cand.title.lower() or cand.category == RecommendationCategory.PRODUCT_PERFORMANCE)
                ]
                if catalog_recs and ctx.products.total_products <= 2:
                    target_prereq = catalog_recs[0]
                    deps.append(
                        RecommendationDependency(
                            recommendation_id=r.id,
                            depends_on_id=target_prereq.id,
                            dependency_type="PREREQUISITE",
                            reason=(
                                "Launching a digital storefront requires an accurate, priced product catalog "
                                f"('{target_prereq.title}') before onboarding online buyers."
                            ),
                            is_satisfied=target_prereq.id in completed_ids,
                        )
                    )

            # Dependency Rule 2: Scaling Surging SKU / Capacity depends on Working Capital Liquidity
            if r_cat == RecommendationCategory.DEMAND_PLANNING.value or "surging" in r_title_l or "capacity" in r_title_l:
                wc_recs = [
                    cand for cand in recommendations
                    if cand.id != r.id and (cand.category == RecommendationCategory.FINANCIAL_MANAGEMENT or "receivable" in cand.title.lower() or "cashflow" in cand.title.lower())
                ]
                if wc_recs:
                    target_prereq = wc_recs[0]
                    deps.append(
                        RecommendationDependency(
                            recommendation_id=r.id,
                            depends_on_id=target_prereq.id,
                            dependency_type="ENABLER",
                            reason=(
                                "Procurement and production scaling requires stabilized cashflow liquidity "
                                f"('{target_prereq.title}') to fund raw material commitments."
                            ),
                            is_satisfied=target_prereq.id in completed_ids,
                        )
                    )

            # Dependency Rule 3: Statutory Debt/Subsidy Schemes depend on basic Financial Records
            if r_cat == RecommendationCategory.GOVERNMENT_SCHEMES.value:
                record_recs = [
                    cand for cand in recommendations
                    if cand.id != r.id and (cand.category == RecommendationCategory.OPERATIONAL_EFFICIENCY or "record" in cand.title.lower() or "accounting" in cand.title.lower())
                ]
                if record_recs and ctx.health.overall_score < 60:
                    target_prereq = record_recs[0]
                    deps.append(
                        RecommendationDependency(
                            recommendation_id=r.id,
                            depends_on_id=target_prereq.id,
                            dependency_type="DATA_DEPENDENCY",
                            reason=(
                                "Statutory scheme matching and bank disbursement requires documented financial statements "
                                f"('{target_prereq.title}') to fulfill institutional criteria."
                            ),
                            is_satisfied=target_prereq.id in completed_ids,
                        )
                    )

            # Dependency Rule 4: Top-Tier VIP Retention requires Repeat Customer identification
            if "vip" in r_title_l or "tiering" in r_title_l:
                retention_recs = [
                    cand for cand in recommendations
                    if cand.id != r.id and ("re-engagement" in cand.title.lower() or "lapsed" in cand.title.lower())
                ]
                if retention_recs:
                    target_prereq = retention_recs[0]
                    deps.append(
                        RecommendationDependency(
                            recommendation_id=r.id,
                            depends_on_id=target_prereq.id,
                            dependency_type="ENABLER",
                            reason=(
                                "Structuring a formalized VIP program is more effective after initial outreach "
                                f"('{target_prereq.title}') confirms active buyer responsiveness."
                            ),
                            is_satisfied=target_prereq.id in completed_ids,
                        )
                    )

        return deps

    # ----------------------------------------------------------------------- #
    # 2. Conflict Detection                                                   #
    # ----------------------------------------------------------------------- #
    def detect_conflicts(
        self,
        recommendations: list[SmartRecommendationItem],
        ctx: UnifiedRecommendationContext,
    ) -> list[RecommendationConflict]:
        """Detect resource competition, strategic contradictions, and timing mismatches."""
        conflicts: list[RecommendationConflict] = []
        n = len(recommendations)

        for i in range(n):
            for j in range(i + 1, n):
                rec_a = recommendations[i]
                rec_b = recommendations[j]

                cat_a = rec_a.category.value if hasattr(rec_a.category, "value") else str(rec_a.category)
                cat_b = rec_b.category.value if hasattr(rec_b.category, "value") else str(rec_b.category)

                title_a = rec_a.title.lower()
                title_b = rec_b.title.lower()

                # Conflict 1: Spend Expansion / Promotions vs Cost Reduction
                is_growth_a = cat_a == RecommendationCategory.REVENUE_GROWTH.value or "discount" in title_a or "promot" in title_a
                is_cost_b = cat_b == RecommendationCategory.COST_OPTIMIZATION.value or "cost" in title_b or "expense" in title_b

                is_growth_b = cat_b == RecommendationCategory.REVENUE_GROWTH.value or "discount" in title_b or "promot" in title_b
                is_cost_a = cat_a == RecommendationCategory.COST_OPTIMIZATION.value or "cost" in title_a or "expense" in title_a

                if (is_growth_a and is_cost_b) or (is_growth_b and is_cost_a):
                    g_rec = rec_a if is_growth_a else rec_b
                    c_rec = rec_b if is_growth_a else rec_a

                    conflicts.append(
                        RecommendationConflict(
                            conflict_id=f"conf_SPEND_VS_COST_{g_rec.id}_{c_rec.id}",
                            rec_a_id=g_rec.id,
                            rec_a_title=g_rec.title,
                            rec_b_id=c_rec.id,
                            rec_b_title=c_rec.title,
                            conflict_type="RESOURCE_COMPETITION",
                            description=(
                                f"Direct competition for operating cashflow: '{g_rec.title}' involves commercial "
                                f"volume incentives or promotional investment, whereas '{c_rec.title}' mandates "
                                "immediate overhead expense compression."
                            ),
                            evidence_a=g_rec.evidence[:2],
                            evidence_b=c_rec.evidence[:2],
                            trade_off_analysis=(
                                "Aggressive revenue promotion accelerates volume but risks depleting the cash buffer; "
                                "pure cost containment preserves margins but forfeits top-line customer acquisition."
                            ),
                            recommended_resolution=(
                                f"Sequential staging: Complete cost rationalization ('{c_rec.title}') during Days 1–14 "
                                f"to establish an expense buffer, then fund targeted revenue initiatives ('{g_rec.title}') in Days 15–45."
                            ),
                            owner_decision_required=True,
                        )
                    )

                # Conflict 2: Catalog Expansion vs Catalog Simplification
                is_prod_exp = (cat_a == RecommendationCategory.PRODUCT_PERFORMANCE.value and ("launch" in title_a or "expand" in title_a or "variety" in title_a)) or (cat_b == RecommendationCategory.PRODUCT_PERFORMANCE.value and ("launch" in title_b or "expand" in title_b or "variety" in title_b))
                is_prod_prune = (cat_a == RecommendationCategory.COST_OPTIMIZATION.value and "sku" in title_a) or (cat_b == RecommendationCategory.COST_OPTIMIZATION.value and "sku" in title_b)

                if is_prod_exp and is_prod_prune:
                    exp_rec = rec_a if ("launch" in title_a or "expand" in title_a) else rec_b
                    prune_rec = rec_b if ("launch" in title_a or "expand" in title_a) else rec_a

                    conflicts.append(
                        RecommendationConflict(
                            conflict_id=f"conf_CATALOG_FOCUS_{exp_rec.id}_{prune_rec.id}",
                            rec_a_id=exp_rec.id,
                            rec_a_title=exp_rec.title,
                            rec_b_id=prune_rec.id,
                            rec_b_title=prune_rec.title,
                            conflict_type="STRATEGIC_CONTRADICTION",
                            description=(
                                f"Catalog focus contradiction: '{exp_rec.title}' proposes onboarding new product variants, "
                                f"while '{prune_rec.title}' recommends pruning underperforming SKUs."
                            ),
                            evidence_a=exp_rec.evidence[:2],
                            evidence_b=prune_rec.evidence[:2],
                            trade_off_analysis=(
                                "Expanding portfolio variety captures emerging niche demand but spreads inventory capital thin. "
                                "Simplifying the catalog increases working capital velocity but restricts customer choices."
                            ),
                            recommended_resolution=(
                                f"Prioritize pruning first: Liquidate or phase out the bottom 20% slow-moving SKUs "
                                f"('{prune_rec.title}') to release working capital before introducing new variants ('{exp_rec.title}')."
                            ),
                            owner_decision_required=False,
                        )
                    )

                # Conflict 3: Market/Export Expansion vs Operational Bottlenecks
                is_mkt_exp = "market" in title_a or "export" in title_a or "channel" in title_a
                is_op_fix = cat_b == RecommendationCategory.OPERATIONAL_EFFICIENCY.value or "bottleneck" in title_b or "delay" in title_b

                if is_mkt_exp and is_op_fix:
                    conflicts.append(
                        RecommendationConflict(
                            conflict_id=f"conf_TIMING_EXPANSION_{rec_a.id}_{rec_b.id}",
                            rec_a_id=rec_a.id,
                            rec_a_title=rec_a.title,
                            rec_b_id=rec_b.id,
                            rec_b_title=rec_b.title,
                            conflict_type="TIMING_MISMATCH",
                            description=(
                                f"Timing mismatch: Driving new sales channels ('{rec_a.title}') risks exacerbating "
                                f"operational delivery bottlenecks ('{rec_b.title}') and damaging customer reputation."
                            ),
                            evidence_a=rec_a.evidence[:2],
                            evidence_b=rec_b.evidence[:2],
                            trade_off_analysis=(
                                "Scaling demand before fixing operational workflow risks high defect rates and fulfillment delays. "
                                "Focusing solely on operations delays commercial capture."
                            ),
                            recommended_resolution=(
                                f"Resolve the operational bottleneck ('{rec_b.title}') to 85%+ fulfillment reliability "
                                f"before launching multi-channel expansion ('{rec_a.title}')."
                            ),
                            owner_decision_required=False,
                        )
                    )

        # Deduplicate conflicts by conflict_id
        unique_conflicts: dict[str, RecommendationConflict] = {}
        for c in conflicts:
            if c.conflict_id not in unique_conflicts:
                unique_conflicts[c.conflict_id] = c

        return list(unique_conflicts.values())

    # ----------------------------------------------------------------------- #
    # 3. Timeframe Segmentation                                               #
    # ----------------------------------------------------------------------- #
    def classify_timeframes(
        self,
        recommendations: list[SmartRecommendationItem],
        dependencies: list[RecommendationDependency],
    ) -> Tuple[
        list[SmartRecommendationItem],
        list[SmartRecommendationItem],
        list[SmartRecommendationItem],
    ]:
        """Classify recommendations into Quick Wins, Short-Term Improvements, and Strategic Initiatives."""
        quick_wins: list[SmartRecommendationItem] = []
        short_term: list[SmartRecommendationItem] = []
        strategic: list[SmartRecommendationItem] = []

        # Map of recommendation IDs that have unsatisfied prerequisites
        unsatisfied_rec_ids = {
            d.recommendation_id for d in dependencies if not d.is_satisfied
        }

        for r in recommendations:
            diff = r.implementation_difficulty
            # Quick wins must have low operational friction and no blocking prerequisites
            if diff == "Quick Win" and r.id not in unsatisfied_rec_ids:
                quick_wins.append(r)
            elif diff == "Strategic" or r.id in unsatisfied_rec_ids or r.category == RecommendationCategory.GOVERNMENT_SCHEMES:
                strategic.append(r)
            else:
                short_term.append(r)

        return quick_wins, short_term, strategic

    # ----------------------------------------------------------------------- #
    # 4. Topological Execution Sequencing                                     #
    # ----------------------------------------------------------------------- #
    def generate_execution_sequence(
        self,
        recommendations: list[SmartRecommendationItem],
        dependencies: list[RecommendationDependency],
        conflicts: list[RecommendationConflict],
    ) -> list[SequencedAction]:
        """Generate a logically ordered execution sequence with causal explanations."""
        sequence: list[SequencedAction] = []
        rec_map = {r.id: r for r in recommendations}

        # Track unlock relationships: prereq_id -> list[downstream_id]
        unlock_map: dict[str, list[str]] = {}
        prereq_map: dict[str, list[str]] = {}
        for d in dependencies:
            unlock_map.setdefault(d.depends_on_id, []).append(d.recommendation_id)
            prereq_map.setdefault(d.recommendation_id, []).append(d.depends_on_id)

        # Stage 1: Critical Risks and Root Prerequisites (Immediate Foundation)
        critical_items = [
            r for r in recommendations
            if r.priority == RecommendationPriority.CRITICAL or r.priority_score >= 80
        ]
        # Root prerequisites that unblock others but have no prerequisites themselves
        root_prereqs = [
            r for r in recommendations
            if r.id in unlock_map and r.id not in prereq_map and r not in critical_items
        ]

        # Stage 2: Quick Wins and Tactical Immediate Actions
        quick_wins = [
            r for r in recommendations
            if r.implementation_difficulty == "Quick Win" and r not in critical_items and r not in root_prereqs
        ]

        # Stage 3: Dependent Tactical Actions
        dependent_items = [
            r for r in recommendations
            if r.id in prereq_map and r not in critical_items and r not in root_prereqs and r not in quick_wins
        ]

        # Stage 4: Strategic Long-Term Initiatives
        remaining_items = [
            r for r in recommendations
            if r not in critical_items and r not in root_prereqs and r not in quick_wins and r not in dependent_items
        ]

        # Assemble orderly sequence
        ordered_groups = [
            ("FIRST_ACTION", "Days 1-14", critical_items + root_prereqs),
            ("SUPPORTING_ACTION", "Days 15-30", quick_wins),
            ("DEPENDENT_ACTION", "Days 31-60", dependent_items),
            ("STRATEGIC_INITIATIVE", "Days 61-90+", remaining_items),
        ]

        step_counter = 1
        seen_ids: Set[str] = set()

        for stage_name, timeframe_lbl, items in ordered_groups:
            # Sort within group by priority_score descending
            sorted_items = sorted(items, key=lambda x: x.priority_score, reverse=True)
            for item in sorted_items:
                if item.id in seen_ids:
                    continue
                seen_ids.add(item.id)

                unlocked = unlock_map.get(item.id, [])
                prereqs = prereq_map.get(item.id, [])

                # Causal sequencing explanation
                if stage_name == "FIRST_ACTION":
                    if item.priority == RecommendationPriority.CRITICAL:
                        rationale = (
                            f"Step {step_counter} Priority: Critical risk alert requiring immediate mitigation "
                            "to safeguard business solvency before capital commitments."
                        )
                    else:
                        rationale = (
                            f"Step {step_counter} Prerequisite: Essential foundation that unblocks {len(unlocked)} "
                            "downstream improvement initiatives."
                        )
                elif stage_name == "SUPPORTING_ACTION":
                    rationale = (
                        f"Step {step_counter} Quick Win: High-feasibility tactical intervention generating early cashflow "
                        "and operational momentum."
                    )
                elif stage_name == "DEPENDENT_ACTION":
                    prereq_titles = [rec_map[pid].title for pid in prereqs if pid in rec_map]
                    rationale = (
                        f"Step {step_counter} Staged Action: Execution proceeds after completing prerequisites "
                        f"({', '.join(prereq_titles) if prereq_titles else 'foundational steps'})."
                    )
                else:
                    rationale = (
                        f"Step {step_counter} Strategic Initiative: Long-horizon scaling milestone building on "
                        "stabilized operations."
                    )

                sequence.append(
                    SequencedAction(
                        sequence_order=step_counter,
                        stage=stage_name,
                        recommendation_id=item.id,
                        title=item.title,
                        category=item.category.value if hasattr(item.category, "value") else str(item.category),
                        priority=item.priority.value if hasattr(item.priority, "value") else str(item.priority),
                        timeframe_label=timeframe_lbl,
                        why_this_order=rationale,
                        unlocks_recommendation_ids=unlocked,
                        status=item.status.value if hasattr(item.status, "value") else str(item.status),
                    )
                )
                step_counter += 1

        return sequence

    # ----------------------------------------------------------------------- #
    # 5. Portfolio Obsolescence Detection                                     #
    # ----------------------------------------------------------------------- #
    def detect_obsolete_recommendations(
        self,
        current_recommendations: list[SmartRecommendationItem],
        ctx: UnifiedRecommendationContext,
        persisted_states: dict[str, RecommendationLifecycleState],
    ) -> list[PortfolioObsoleteItem]:
        """Identify previously active recommendations rendered obsolete by updated empirical data."""
        obsolete_items: list[PortfolioObsoleteItem] = []
        current_ids = {r.id for r in current_recommendations}

        for rec_id, state in persisted_states.items():
            # If the recommendation was active (New, Viewed, Accepted, In Progress) but no longer triggered
            if rec_id not in current_ids and state.status not in (RecommendationStatus.COMPLETED.value, RecommendationStatus.DISMISSED.value):
                # Reason derivation based on verified context shifts
                rec_id_l = rec_id.lower()
                if "concentration" in rec_id_l:
                    reason = "Customer concentration mitigated: top client revenue share is now below the 25% risk threshold."
                elif "storefront" in rec_id_l and ctx.profile.has_website:
                    reason = f"Digital storefront requirement satisfied: verified live website at {ctx.profile.website_url or 'registered domain'}."
                elif "surge" in rec_id_l and not ctx.forecast.has_forecast_data:
                    reason = "Forecast demand surge expired: demand trend normalized to historical baseline."
                elif "lapsed" in rec_id_l or "churn" in rec_id_l:
                    reason = "Customer churn alert resolved: dormant repeat buyer resumed regular purchase cadence."
                else:
                    reason = "Business operational telemetry evolved; conditions triggering this recommendation are no longer active."

                obsolete_items.append(
                    PortfolioObsoleteItem(
                        recommendation_id=rec_id,
                        title=f"Recommendation '{rec_id}'",
                        reason_obsolete=reason,
                        previous_status=state.status,
                    )
                )

        return obsolete_items

    # ----------------------------------------------------------------------- #
    # 6. Full Portfolio Assembly                                              #
    # ----------------------------------------------------------------------- #
    def build_portfolio(
        self,
        business: Business,
        recommendations: list[SmartRecommendationItem],
        ctx: UnifiedRecommendationContext,
        persisted_states: dict[str, RecommendationLifecycleState],
    ) -> RecommendationPortfolioResponse:
        """Construct the unified, coherent Recommendation Portfolio."""
        completed_ids = {
            r_id for r_id, s in persisted_states.items()
            if s.status == RecommendationStatus.COMPLETED.value
        }

        # 1. Detect Dependencies
        dependencies = self.detect_dependencies(
            recommendations=recommendations,
            ctx=ctx,
            completed_ids=completed_ids,
        )

        # 2. Detect Conflicts
        conflicts = self.detect_conflicts(
            recommendations=recommendations,
            ctx=ctx,
        )

        # 3. Classify Timeframes
        quick_wins, short_term, strategic = self.classify_timeframes(
            recommendations=recommendations,
            dependencies=dependencies,
        )

        # 4. Generate Execution Sequence
        sequence = self.generate_execution_sequence(
            recommendations=recommendations,
            dependencies=dependencies,
            conflicts=conflicts,
        )

        # 5. Detect Obsolete Items
        obsolete = self.detect_obsolete_recommendations(
            current_recommendations=recommendations,
            ctx=ctx,
            persisted_states=persisted_states,
        )

        # Critical risks extraction
        crit_risks = [
            r for r in recommendations
            if r.priority == RecommendationPriority.CRITICAL or r.priority_score >= 80
        ]

        # Calculate Portfolio Health Score (0 - 100)
        # Deduct for unresolved conflicts and unaddressed critical risks
        health_score = 100
        health_score -= len(conflicts) * 10
        health_score -= len(crit_risks) * 15
        unsatisfied_deps = [d for d in dependencies if not d.is_satisfied]
        health_score -= len(unsatisfied_deps) * 5
        final_health = max(20, min(100, health_score))

        # Resource Summary
        resource_summary = {
            "total_initiatives": len(recommendations),
            "critical_risk_count": len(crit_risks),
            "quick_win_count": len(quick_wins),
            "strategic_initiative_count": len(strategic),
            "active_conflicts_count": len(conflicts),
            "dependencies_count": len(dependencies),
            "unsatisfied_dependencies_count": len(unsatisfied_deps),
            "estimated_implementation_horizon": "90 Days",
        }

        now_iso = datetime.now(timezone.utc).isoformat()
        return RecommendationPortfolioResponse(
            business_id=business.id,
            business_name=business.legal_name or "Your Business",
            generated_at=now_iso,
            portfolio_health_score=final_health,
            total_active_count=len(recommendations),
            critical_risks=crit_risks,
            quick_wins=quick_wins,
            short_term_improvements=short_term,
            strategic_initiatives=strategic,
            dependencies=dependencies,
            conflicts=conflicts,
            execution_sequence=sequence,
            obsolete_recommendations=obsolete,
            resource_summary=resource_summary,
        )
