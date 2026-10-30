"""Regression tests for the H7.9R+ intent-aware flagship advisor.

The previous deterministic fallback returned the *same canned
template* for every user prompt. For flagship questions
("How can I reach ₹3 crore turnover?", "What is my biggest
weakness?", "Which government schemes should I apply for?",
"Give me a 12 month roadmap", "Should I expand exports?")
that template is wrong — it doesn't even acknowledge what
the user asked.

These tests lock down the new behaviour:

  (1) Each flagship prompt classifies into the correct
      :class:`QuestionIntent`.
  (2) Each flagship prompt's deterministic fallback body
      contains the question-specific sections the user brief
      demanded.
  (3) The body references the user's *actual* business
      profile values (revenue, target, scheme match scores),
      never invented numbers.
  (4) Every flagship body contains the four-line audit tail:
      Evidence, Assumptions, Limitations, Next actions.
  (5) Grounded mode injects a "Task Framing" block into the
      real-LLM prompt so Gemini/Ollama also stops returning
      generic output.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

import pytest

from app.services.ai.providers.base import (
    AssistantContext,
    AssistantContextDna,
    AssistantContextRecommendation,
    AssistantContextRule,
    AssistantContextScheme,
    AssistantRequest,
    DeterministicFallbackProvider,
)
from app.services.ai.providers.intent_router import (
    QuestionIntent,
    build_intent_frame,
    classify_intent,
)
from app.services.ai.providers.prompt_builder import AssistantPromptBuilder


def _make_context() -> AssistantContext:
    """Build a minimal but realistic Acme-Textiles-like context.

    Annual revenue ₹1.8 Cr, target ₹3 Cr, one recommendation,
    one critical rule, one matched scheme. The exact values
    the flagship-1 test expects to see verbatim.
    """
    return AssistantContext(
        business_id=1,
        overall_business_score=63,
        band="Established",
        dna=AssistantContextDna(
            archetype_key="growth_operator",
            archetype_title="Growth Operator",
            match_score=78,
        ),
        annual_revenue_inr=18_000_000,  # ₹1.80 Cr
        target_revenue_inr=30_000_000,  # ₹3.00 Cr
        industry="Manufacturing",
        sub_industry="Textiles",
        legal_name="Acme Textiles",
        recommendations=(
            AssistantContextRecommendation(
                id="rec_adopt_cloud_accounting",
                title="Adopt a cloud accounting tool",
                category="finance",
                priority="High",
                estimated_score_gain=8,
                estimated_roi=120_000.0,
                estimated_timeline="3 months",
            ),
        ),
        rules=(
            AssistantContextRule(
                id="rule_digital_presence",
                title="Low digital presence",
                category="digital",
                priority="Critical",
                estimated_impact=85,
                reason="No website or social channels recorded.",
            ),
        ),
        schemes=(
            AssistantContextScheme(
                scheme_id="cgtmse",
                title="CGTMSE",
                authority="SIDBI",
                application_url="https://www.cgtmse.in",
                profile_match_score=82,
                last_verified_date="2026-01-15",
            ),
        ),
    )


def _classify_cases() -> list[tuple[str, QuestionIntent]]:
    """The five flagship prompts + the general fallback case."""
    return [
        (
            "How can I reach 3 crore turnover?",
            QuestionIntent.REACH_REVENUE_TARGET,
        ),
        (
            "How can I achieve ₹3 crore revenue?",
            QuestionIntent.REACH_REVENUE_TARGET,
        ),
        (
            "What is my biggest weakness?",
            QuestionIntent.BIGGEST_WEAKNESS,
        ),
        (
            "Which government schemes should I apply for?",
            QuestionIntent.GOVERNMENT_SCHEMES,
        ),
        (
            "Give me a 12 month roadmap",
            QuestionIntent.TWELVE_MONTH_ROADMAP,
        ),
        (
            "Should I expand exports?",
            QuestionIntent.EXPORT_EXPANSION,
        ),
        (
            "Tell me about my business.",
            QuestionIntent.GENERAL,
        ),
    ]


# --------------------------------------------------------------------------- #
# (1) Classifier
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("prompt,expected", _classify_cases())
def test_classify_intent_routes_each_flagship_prompt(prompt, expected):
    """Each flagship prompt classifies into the right intent."""
    assert classify_intent(prompt) == expected


def test_classify_intent_handles_empty_prompt():
    """Empty / whitespace prompts fall back to GENERAL, never crash."""
    assert classify_intent("") == QuestionIntent.GENERAL
    assert classify_intent("   ") == QuestionIntent.GENERAL


# --------------------------------------------------------------------------- #
# (2) Section coverage — every flagship body carries the right headers
# --------------------------------------------------------------------------- #


def _body_for(prompt: str, ctx: AssistantContext) -> str:
    provider = DeterministicFallbackProvider()
    return provider.complete(
        AssistantRequest(user_prompt=prompt, context=ctx, mode="grounded")
    ).body


def test_reach_target_body_includes_revenue_gap_math():
    """Flagship 1: revenue / gap / growth multiple / strategies."""
    ctx = _make_context()
    body = _body_for("How can I reach 3 crore turnover?", ctx)
    # Required sections from the brief
    assert "REVENUE GAP MATH" in body, body
    assert "₹1.80 Cr" in body, body  # current revenue
    assert "₹3.00 Cr" in body, body  # target revenue
    assert "₹1.20 Cr" in body, body  # gap math
    assert "1.67x" in body, body  # growth multiple
    # Required downstream sections
    assert "GROWTH STRATEGY" in body
    assert "QUARTER-WISE ROADMAP" in body
    assert "FUNDING" in body or "FINANCIAL PROJECTIONS" in body
    assert "KEY RISKS" in body
    assert "KPIs" in body or "KPIS" in body


def test_biggest_weakness_body_identifies_highest_risk():
    """Flagship 2: highest risk, evidence, business impact, recommended."""
    ctx = _make_context()
    body = _body_for("What is my biggest weakness?", ctx)
    assert "HIGHEST RISK" in body, body
    assert "Low digital presence" in body, body  # from rules
    assert "Critical" in body  # priority


def test_schemes_body_ranks_and_links_schemes():
    """Flagship 3: ranked top schemes, eligibility framing, application link."""
    ctx = _make_context()
    body = _body_for("Which government schemes should I apply for?", ctx)
    assert "ELIGIBLE SCHEMES" in body, body
    assert "CGTMSE" in body
    assert "82" in body  # profile_match_score 82
    assert "https://www.cgtmse.in" in body  # application link
    # Eligibility framing — never claim eligibility
    assert "eligibility" in body.lower()
    assert "match" in body.lower()


def test_twelve_month_roadmap_body_groups_quarters():
    """Flagship 4: quarter-wise plan, milestones, KPIs."""
    ctx = _make_context()
    body = _body_for("Give me a 12 month roadmap", ctx)
    assert "QUARTER-WISE ROADMAP" in body
    assert "Q1" in body
    assert "Q2" in body
    assert "Q3" in body
    assert "Q4" in body
    assert "MILESTONES" in body
    assert "KPIs" in body or "KPIS" in body


def test_export_body_analyses_readiness():
    """Flagship 5: readiness, evidence, pros, risks, markets, recommendation."""
    ctx = _make_context()
    body = _body_for("Should I expand exports?", ctx)
    assert "EXPORT READINESS" in body
    assert "PROS" in body
    assert "RISKS" in body or "KEY RISKS" in body
    assert "TARGET MARKETS" in body
    assert "RECOMMENDATION" in body


# --------------------------------------------------------------------------- #
# (3) The four-line audit tail is always present
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("prompt", [p for p, _ in _classify_cases() if _ is not QuestionIntent.GENERAL])
def test_flagship_body_contains_evidence_assumptions_limitations_actions(prompt):
    """Every flagship body has Evidence / Assumptions / Limitations / Next actions."""
    ctx = _make_context()
    body = _body_for(prompt, ctx)
    assert "### EVIDENCE" in body, body
    assert "### ASSUMPTIONS" in body
    assert "### LIMITATIONS" in body
    assert "### NEXT ACTIONS" in body


def test_general_intent_falls_back_to_consultant_framing():
    """GENERAL intent preserves the original 4-section consultant body."""
    ctx = _make_context()
    body = _body_for("Tell me about my business.", ctx)
    # Original general framing markers
    assert "BUSINESS FACTS & SITUATION ASSESSMENT" in body
    assert "DIAGNOSTIC REASONING & ROOT CAUSES" in body
    assert "Overall business score: 63/100" in body
    assert "Growth Operator" in body
    assert "Adopt a cloud accounting tool" in body


# --------------------------------------------------------------------------- #
# (4) No invented numbers — only profile values appear
# --------------------------------------------------------------------------- #


def test_no_invented_revenue_in_reach_target_body():
    """The flagship-1 body must NOT invent numbers beyond the profile.

    The Acme-Textiles-like context has revenue ₹1.8 Cr and
    target ₹3 Cr. The body should quote these exactly. It
    must NOT invent e.g. "₹2.5 Cr" or "₹5 Cr" as plan steps.
    """
    ctx = _make_context()
    body = _body_for("How can I reach 3 crore turnover?", ctx)
    # Allow the genuine values + standard qualifiers.
    forbidden = ["₹2.50 Cr", "₹5 Cr", "₹10 Cr", "100% growth", "doubled revenue"]
    for f in forbidden:
        assert f not in body, f"forbidden invented figure in body: {f!r}"


def test_schemes_body_does_not_claim_eligibility():
    """The flagship-3 body must NEVER claim 'eligible' or 'approved' as fact."""
    ctx = _make_context()
    body = _body_for("Which government schemes should I apply for?", ctx)
    # The body uses "eligibility" in framing — never "you are eligible".
    forbidden_phrases = ["you are eligible", "you qualify", "guaranteed approval"]
    for f in forbidden_phrases:
        assert f.lower() not in body.lower(), (
            f"forbidden eligibility claim in body: {f!r}"
        )


# --------------------------------------------------------------------------- #
# (5) Grounded-mode prompt includes Task Framing
# --------------------------------------------------------------------------- #


def test_grounded_prompt_includes_task_framing_for_flagship():
    """Real-LLM grounded prompt gets the Task Framing block."""
    ctx = _make_context()
    req = AssistantRequest(
        user_prompt="How can I reach 3 crore turnover?",
        context=ctx,
        history=(),
        mode="grounded",
    )
    rendered = AssistantPromptBuilder.render_user_message(req)
    assert "TASK FRAMING" in rendered, rendered[:500]
    assert "REVENUE GAP MATH" in rendered
    assert "GROWTH STRATEGY" in rendered
    assert "QUARTER-WISE ROADMAP" in rendered


def test_open_mode_prompt_includes_task_framing_for_flagship():
    """Open mode also gets the framing when the question is flagship."""
    ctx = _make_context()
    req = AssistantRequest(
        user_prompt="Which government schemes should I apply for?",
        context=ctx,
        history=(),
        mode="open",
    )
    rendered = AssistantPromptBuilder.render_user_message(req)
    assert "TASK FRAMING" in rendered
    assert "GOVERNMENT_SCHEMES" in rendered


def test_general_prompt_omits_task_framing():
    """GENERAL intent must NOT inject a Task Framing block — it preserves
    the existing prompt shape."""
    ctx = _make_context()
    req = AssistantRequest(
        user_prompt="Tell me about my business.",
        context=ctx,
        history=(),
        mode="grounded",
    )
    rendered = AssistantPromptBuilder.render_user_message(req)
    assert "TASK FRAMING" not in rendered