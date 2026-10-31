"""AI-Powered Recommendation Explanation Service with Deterministic Fallback (Phase 5).

Translates structured evidence and context into plain, actionable language for MSME owners.
Delivers a 9-pillar executive diagnostic brief covering:
  1. What is happening in the business? (Diagnosis)
  2. What is going wrong? (Vulnerability)
  3. Why is it happening? (Root Cause)
  4. What opportunities are being missed? (Missed Opportunity)
  5. What should be done first? (Immediate Next Action)
  6. What could happen if the owner takes action? (Action Outcome Scenario)
  7. What could happen if the owner does nothing? (Cost of Inaction)
  8. How should the owner implement the action? (3-Phase Implementation Roadmap)
  9. How can the owner measure improvement? (KPIs and Metrics)

Gemini may contextualize verified facts but is strictly forbidden from inventing numbers.
Graceful deterministic fallback ensures zero downtime when AI or network is unavailable.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional
import httpx

from app.config.settings import get_settings
from app.schemas.smart_recommendations import (
    RecommendationExplainResponse,
    SmartRecommendationItem,
)
from app.services.ai.resilient_client import ResilientGeminiClient

logger = logging.getLogger(__name__)


def generate_deterministic_explanation(rec: SmartRecommendationItem) -> str:
    """Produce deterministic, evidence-grounded explanation directly from verified attributes."""
    narrative_parts = [
        f"**Why this matters for your business:** {rec.reasoning}",
        f"**Supporting evidence:** {'; '.join(rec.evidence) if rec.evidence else 'Based on your registered business profile and operating industry.'}",
        f"**Expected outcome:** {rec.expected_benefit}",
    ]
    if rec.estimated_impact is not None and rec.impact_unit:
        narrative_parts.append(
            f"**Calculated baseline opportunity:** Up to {rec.estimated_impact:,.2f} {rec.impact_unit} based on historical transactions."
        )

    if rec.cost_of_inaction:
        narrative_parts.append(f"**Cost of inaction:** {rec.cost_of_inaction}")

    if rec.limitations:
        narrative_parts.append(f"**Data considerations:** {rec.limitations[0]}")

    return "\n\n".join(narrative_parts)


def _build_deterministic_brief(rec: SmartRecommendationItem, industry: str) -> dict[str, Any]:
    """Assemble 9-pillar executive diagnostic brief from verified deterministic attributes."""
    phases: list[dict[str, Any]] = []
    if rec.action_plan and rec.action_plan.steps:
        steps = rec.action_plan.steps
        for st in steps:
            phases.append({
                "phase": f"Step {st.step_number}: {st.title}",
                "timeframe": st.timeframe,
                "focus": st.title,
                "steps": [st.description],
                "resources": st.resources_required,
            })
    else:
        actions = rec.recommended_actions or ["Review operational records and align team."]
        phases.append({
            "phase": "Phase 1: Immediate Diagnostic (Days 1-7)",
            "timeframe": "Days 1-7",
            "focus": "Quick Wins & Preparation",
            "steps": actions[:2],
            "resources": "Current business staff and management",
        })
        if len(actions) > 2:
            phases.append({
                "phase": "Phase 2: Execution & Rollout (Days 8-30)",
                "timeframe": "Days 8-30",
                "focus": "Operational Implementation",
                "steps": actions[2:],
                "resources": "Operational channels and customer touchpoints",
            })

    kpis = list(rec.measurement_kpis)
    if not kpis and rec.action_plan and rec.action_plan.success_metric:
        kpis.append(rec.action_plan.success_metric)
    if not kpis:
        kpis = ["Adoption rate", "Revenue stability"]

    return {
        "executive_summary": rec.description,
        "what_is_happening": (
            rec.what_is_happening
            or f"Business is currently operating in {industry} with {len(rec.evidence)} verified data points observed."
        ),
        "what_is_going_wrong": rec.why_it_matters or rec.reasoning,
        "why_is_it_happening": (
            rec.root_cause
            or f"Driven by observed transactional and operational signals: {'; '.join(rec.evidence[:2]) if rec.evidence else rec.business_context}"
        ),
        "missed_opportunity": (
            rec.missed_opportunity
            or f"Strategic upside currently left on the table: {rec.expected_benefit}"
        ),
        "action_outcome": rec.action_scenario or rec.expected_benefit,
        "inaction_cost": (
            rec.cost_of_inaction
            or "Maintaining status quo leaves vulnerabilities unaddressed and compounds operational friction over time."
        ),
        "implementation_phases": phases,
        "measurement_kpis": kpis,
        "confidence_score": rec.confidence,
        "data_quality_label": rec.data_quality,
    }


def explain_recommendation(
    rec: SmartRecommendationItem, business_name: str, industry: str
) -> RecommendationExplainResponse:
    """Generate an AI-powered 9-pillar executive diagnostic brief using Gemini, falling back to deterministic brief on error/timeout."""
    settings = get_settings()
    deterministic_text = generate_deterministic_explanation(rec)
    deterministic_brief = _build_deterministic_brief(rec, industry)

    practical_steps = rec.recommended_actions
    if rec.action_plan and rec.action_plan.steps:
        practical_steps = [f"{s.title}: {s.description} ({s.timeframe})" for s in rec.action_plan.steps]

    # If no AI API key or placeholder, return deterministic explanation directly
    if not settings.ai_api_key or settings.ai_provider == "placeholder":
        return RecommendationExplainResponse(
            recommendation_id=rec.id,
            title=rec.title,
            explanation=deterministic_text,
            is_ai_generated=False,
            practical_steps=practical_steps,
            limitations=rec.limitations,
            executive_summary=deterministic_brief["executive_summary"],
            what_is_happening=deterministic_brief["what_is_happening"],
            what_is_going_wrong=deterministic_brief["what_is_going_wrong"],
            why_is_it_happening=deterministic_brief["why_is_it_happening"],
            missed_opportunity=deterministic_brief["missed_opportunity"],
            action_outcome=deterministic_brief["action_outcome"],
            inaction_cost=deterministic_brief["inaction_cost"],
            implementation_phases=deterministic_brief["implementation_phases"],
            measurement_kpis=deterministic_brief["measurement_kpis"],
            confidence_score=deterministic_brief["confidence_score"],
            data_quality_label=deterministic_brief["data_quality_label"],
        )

    # Attempt bounded outbound call to Gemini
    try:
        system_prompt = (
            "You are an expert MSME business growth consultant for UrsBiz. "
            "Analyze the verified recommendation and explain it clearly across 9 executive pillars:\n"
            "1. Executive Summary\n"
            "2. What is happening in the business?\n"
            "3. What is going wrong?\n"
            "4. Why is it happening? (Root Cause)\n"
            "5. What opportunities are being missed?\n"
            "6. What happens if the owner acts? (Action Scenario)\n"
            "7. What happens if the owner does nothing? (Cost of Inaction)\n"
            "8. Phased Implementation Roadmap\n"
            "9. How to Measure Success (KPIs)\n\n"
            "CRITICAL BOUNDARIES:\n"
            "- NEVER alter, invent, or extrapolate any numbers or currency figures. Use strictly the verified metrics provided.\n"
            "- Avoid academic or MBA jargon. Be encouraging, pragmatic, and direct.\n"
            "- Return clear, grounded text."
        )

        user_content = (
            f"Business: {business_name} ({industry})\n"
            f"Recommendation Title: {rec.title}\n"
            f"Category: {rec.category.value}\n"
            f"Priority: {rec.priority.value} (Score: {rec.priority_score}/100)\n"
            f"Description: {rec.description}\n"
            f"Reasoning: {rec.reasoning}\n"
            f"Evidence: {', '.join(rec.evidence)}\n"
            f"Expected Benefit: {rec.expected_benefit}\n"
            f"Cost of Inaction: {rec.cost_of_inaction or 'Unaddressed vulnerability'}\n"
            f"Limitations: {', '.join(rec.limitations)}\n"
        )

        client = ResilientGeminiClient(timeout_seconds=8.0, max_retries=2, settings=settings)
        content = client.execute_chat_completion(
            system_prompt=system_prompt,
            user_content=user_content,
            max_tokens=600,
            temperature=0.2,
        )

        if content and len(content.strip()) > 30:
            ai_text = content.strip()

            # Attempt structured JSON parse if present
            ai_summary = deterministic_brief["executive_summary"]
            ai_happening = deterministic_brief["what_is_happening"]
            ai_wrong = deterministic_brief["what_is_going_wrong"]
            ai_cause = deterministic_brief["why_is_it_happening"]
            ai_opportunity = deterministic_brief["missed_opportunity"]
            ai_action = deterministic_brief["action_outcome"]
            ai_inaction = deterministic_brief["inaction_cost"]
            ai_phases = deterministic_brief["implementation_phases"]
            ai_kpis = deterministic_brief["measurement_kpis"]

            # If Gemini returned JSON, parse the fields
            try:
                raw_json = ai_text
                if "```json" in raw_json:
                    raw_json = raw_json.split("```json")[1].split("```")[0].strip()
                elif "```" in raw_json:
                    raw_json = raw_json.split("```")[1].split("```")[0].strip()
                parsed = json.loads(raw_json)
                if isinstance(parsed, dict):
                    ai_summary = parsed.get("executive_summary") or ai_summary
                    ai_happening = parsed.get("what_is_happening") or ai_happening
                    ai_wrong = parsed.get("what_is_going_wrong") or ai_wrong
                    ai_cause = parsed.get("why_is_it_happening") or ai_cause
                    ai_opportunity = parsed.get("missed_opportunity") or ai_opportunity
                    ai_action = parsed.get("action_outcome") or ai_action
                    ai_inaction = parsed.get("inaction_cost") or ai_inaction
                    if isinstance(parsed.get("implementation_phases"), list):
                        ai_phases = parsed["implementation_phases"]
                    if isinstance(parsed.get("measurement_kpis"), list):
                        ai_kpis = parsed["measurement_kpis"]
                    ai_text = parsed.get("explanation") or parsed.get("narrative_explanation") or ai_text
            except Exception:
                pass  # Use plain text content as explanation and deterministic attributes for structured keys

            return RecommendationExplainResponse(
                recommendation_id=rec.id,
                title=rec.title,
                explanation=ai_text,
                is_ai_generated=True,
                practical_steps=practical_steps,
                limitations=rec.limitations,
                executive_summary=ai_summary,
                what_is_happening=ai_happening,
                what_is_going_wrong=ai_wrong,
                why_is_it_happening=ai_cause,
                missed_opportunity=ai_opportunity,
                action_outcome=ai_action,
                inaction_cost=ai_inaction,
                implementation_phases=ai_phases,
                measurement_kpis=ai_kpis,
                confidence_score=rec.confidence,
                data_quality_label=rec.data_quality,
            )
    except Exception as e:
        logger.warning(f"Gemini recommendation explanation failed, using deterministic fallback: {e}")

    return RecommendationExplainResponse(
        recommendation_id=rec.id,
        title=rec.title,
        explanation=deterministic_text,
        is_ai_generated=False,
        practical_steps=practical_steps,
        limitations=rec.limitations,
        executive_summary=deterministic_brief["executive_summary"],
        what_is_happening=deterministic_brief["what_is_happening"],
        what_is_going_wrong=deterministic_brief["what_is_going_wrong"],
        why_is_it_happening=deterministic_brief["why_is_it_happening"],
        missed_opportunity=deterministic_brief["missed_opportunity"],
        action_outcome=deterministic_brief["action_outcome"],
        inaction_cost=deterministic_brief["inaction_cost"],
        implementation_phases=deterministic_brief["implementation_phases"],
        measurement_kpis=deterministic_brief["measurement_kpis"],
        confidence_score=deterministic_brief["confidence_score"],
        data_quality_label=deterministic_brief["data_quality_label"],
    )
