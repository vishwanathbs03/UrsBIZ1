"""AI-Powered Recommendation Explanation Service with Deterministic Fallback (Phase 5).

Translates structured evidence and context into plain, actionable language for MSME owners.
Gemini may contextualize verified facts but is strictly forbidden from inventing numbers.
Graceful deterministic fallback ensures zero downtime when AI or network is unavailable.
"""

from __future__ import annotations

import logging
import httpx

from app.config.settings import get_settings
from app.schemas.smart_recommendations import (
    RecommendationExplainResponse,
    SmartRecommendationItem,
)

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

    if rec.limitations:
        narrative_parts.append(f"**Data considerations:** {rec.limitations[0]}")

    return "\n\n".join(narrative_parts)


def explain_recommendation(
    rec: SmartRecommendationItem, business_name: str, industry: str
) -> RecommendationExplainResponse:
    """Generate an AI-powered explanation using Gemini, falling back to deterministic explanation on error/timeout."""
    settings = get_settings()
    deterministic_text = generate_deterministic_explanation(rec)

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
        )

    # Attempt bounded outbound call to Gemini
    try:
        system_prompt = (
            "You are an expert MSME business advisor for UrsBiz. "
            "Explain the following verified recommendation to a small business owner in clear, accessible language.\n"
            "CRITICAL RULES:\n"
            "1. NEVER alter, invent, or extrapolate any numbers, financial figures, customer counts, or metrics. Use only the verified values supplied.\n"
            "2. Do not use complex MBA or financial jargon (e.g. do not say 'synergistic capital allocation').\n"
            "3. State practical next steps in an encouraging, pragmatic tone.\n"
            "4. Mention data limitations and remind the owner that these insights assist decisions rather than guaranteeing outcomes."
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
            f"Limitations: {', '.join(rec.limitations)}\n"
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
            "max_tokens": 300,
            "temperature": 0.2,
        }

        url = f"{settings.ai_base_url.rstrip('/')}/chat/completions"
        with httpx.Client(timeout=8.0) as client:
            resp = client.post(url, headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"]["content"].strip()
                if content and len(content) > 30:
                    return RecommendationExplainResponse(
                        recommendation_id=rec.id,
                        title=rec.title,
                        explanation=content,
                        is_ai_generated=True,
                        practical_steps=practical_steps,
                        limitations=rec.limitations,
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
    )
