"""SPRINT AI-18 — Universal AI Evaluation Harness.

Golden set — 11 immutable demo cases covering every
mandatory category from PART 7 of the brief:

  1. general knowledge
  2. business fact
  3. calculation
  4. risk
  5. recommendation
  6. scenario
  7. comparison
  8. scheme
  9. export
 10. missing-data
 11. mixed question

Each case is a :class:`GoldenCase` with:

  * expected capability (one or more labels the
    :class:`QuestionUnderstanding` should produce)
  * expected required evidence (the evidence kinds the
    answer must reference)
  * expected tool category (the deterministic engine the
    ToolDispatcher should call)
  * forbidden tool categories (engines that MUST NOT be
    called)
  * expected answer characteristics (semantic assertions
    the runner checks with regex / substring / numeric checks
    — never exact prose matching)
  * expected trust state (the trust-summary headline +
    confidence band)

Golden set is immutable; adding a case is non-breaking,
removing one IS.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# --------------------------------------------------------------------------- #
# Case dataclass
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class GoldenCase:
    """One immutable evaluation case.

    Attributes
    ----------
    case_id:
        Stable identifier (e.g. ``"golden_general_001"``).
    prompt:
        The literal user message.
    category:
        One of the brief's 16 categories.
    expected_capabilities:
        Tuple of capability labels the AI-1
        :class:`QuestionUnderstanding` should set on the
        understanding. Empty when general.
    expected_required_evidence:
        Tuple of evidence kinds (SCORE / RECOMMENDATION /
        SCHEME / FORECAST / INSIGHT / RULE / DNA / ACTION)
        the answer must reference. Empty when no specific
        evidence is required.
    expected_tool_categories:
        Tuple of tool-category names the dispatcher should
        invoke (e.g. ``("recommendation",)``). Empty when
        no tool call is required.
    forbidden_tool_categories:
        Tuple of tool-category names that MUST NOT fire
        on this prompt. The runner fails the case when any
        forbidden tool ran.
    expected_characteristics:
        Dict of semantic assertions the runner evaluates.
        Supported keys:

          * ``"body_min_chars"`` — minimum body length
          * ``"body_must_contain"`` — tuple of substrings
            the body must contain
          * ``"body_must_not_contain"`` — tuple of forbidden
            substrings
          * ``"body_must_match_regex"`` — tuple of regex
            patterns the body must satisfy
          * ``"trust_min_score"`` — minimum trust band
            (0..1) the trust summary should report
          * ``"evidence_min_count"`` — minimum evidence_refs
            count
    expected_trust_state:
        Dict the runner keys off to verify the trust
        envelope. Supported keys:

          * ``"mode"`` — expected answer_mode string
            (e.g. ``"general_knowledge"``)
          * ``"confidence_band"`` — one of ``"high"``
            (≥70), ``"medium"`` (50-69), ``"low"`` (<50)
          * ``"fallback_expected"`` — True when the
            deterministic fallback is acceptable
          * ``"warning_expected"`` — True when the
            answer should carry a low-quality warning
    notes:
        One-line English note about what the case
        demonstrates.
    """

    case_id: str
    prompt: str
    category: str
    expected_capabilities: tuple[str, ...] = ()
    expected_required_evidence: tuple[str, ...] = ()
    expected_tool_categories: tuple[str, ...] = ()
    forbidden_tool_categories: tuple[str, ...] = ()
    expected_characteristics: dict[str, Any] = field(default_factory=dict)
    expected_trust_state: dict[str, Any] = field(default_factory=dict)
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "prompt": self.prompt,
            "category": self.category,
            "expected_capabilities": list(self.expected_capabilities),
            "expected_required_evidence": list(self.expected_required_evidence),
            "expected_tool_categories": list(self.expected_tool_categories),
            "forbidden_tool_categories": list(self.forbidden_tool_categories),
            "expected_characteristics": dict(self.expected_characteristics),
            "expected_trust_state": dict(self.expected_trust_state),
            "notes": self.notes,
        }


# --------------------------------------------------------------------------- #
# The 11-case golden set
# --------------------------------------------------------------------------- #


# Tool-category vocabulary the runner + cases share.
class GoldenTool(str):
    """Plain-string vocabulary for the golden tool categories.

    Mirrors the values the AI-12 tool selector emits. Kept as
    string subclass (not enum) for JSON-serialisability.
    """

    SCORE = "score"
    RECOMMENDATION = "recommendation"
    SCHEME = "scheme"
    FORECAST = "forecast"
    INSIGHT = "insight"
    RULE = "rule"
    RISK = "risk"
    DNA = "dna"
    ACTION = "action"
    FINANCE = "finance"
    HEALTH = "health_score"
    KNOWLEDGE = "knowledge_retrieval"
    SCHEMES_SPRINT16 = "schemes_sprint16"


GOLDEN_CASES: tuple[GoldenCase, ...] = (
    # ---- 1 — general knowledge ------------------------------------ #
    GoldenCase(
        case_id="golden_general_001",
        prompt="What is EBITDA?",
        category="general_knowledge",
        expected_capabilities=("general_knowledge",),
        expected_required_evidence=(),
        expected_tool_categories=(),
        forbidden_tool_categories=(
            GoldenTool.SCORE, GoldenTool.RECOMMENDATION, GoldenTool.SCHEME,
            GoldenTool.FORECAST, GoldenTool.FINANCE, GoldenTool.RISK,
        ),
        expected_characteristics={
            "body_min_chars": 40,
            "body_must_contain": ("EBITDA",),
        },
        expected_trust_state={
            "mode": "general_knowledge",
            "confidence_band": "high",
            "fallback_expected": True,
        },
        notes="General-knowledge prompt must NOT invoke any business tool.",
    ),
    # ---- 2 — business fact ---------------------------------------- #
    GoldenCase(
        case_id="golden_business_fact_001",
        prompt="What is our current revenue?",
        category="business_fact",
        expected_capabilities=("business_fact",),
        expected_required_evidence=("SCORE",),
        expected_tool_categories=(GoldenTool.SCORE,),
        forbidden_tool_categories=(
            GoldenTool.SCHEME, GoldenTool.FORECAST,
        ),
        expected_characteristics={
            "body_min_chars": 30,
            "evidence_min_count": 1,
        },
        expected_trust_state={
            "mode": "business_analysis",
            "confidence_band": "high",
        },
        notes="Business-fact must cite score evidence.",
    ),
    # ---- 3 — calculation ------------------------------------------ #
    GoldenCase(
        case_id="golden_calculation_001",
        prompt="How much revenue do we need to hit ₹3 Cr?",
        category="calculation",
        expected_capabilities=("calculation", "business_fact"),
        expected_required_evidence=("SCORE",),
        expected_tool_categories=(GoldenTool.SCORE, GoldenTool.FINANCE),
        forbidden_tool_categories=(
            GoldenTool.SCHEME, GoldenTool.RISK,
        ),
        expected_characteristics={
            "body_min_chars": 50,
            "evidence_min_count": 1,
            "body_must_contain": ("₹",),
        },
        expected_trust_state={
            "mode": "calculation",
            "confidence_band": "high",
        },
        notes="Calculation must invoke finance and surface a numeric.",
    ),
    # ---- 4 — risk ------------------------------------------------- #
    GoldenCase(
        case_id="golden_risk_001",
        prompt="What is our biggest business risk?",
        category="risk",
        expected_capabilities=("risk", "business_fact"),
        expected_required_evidence=("RULE", "INSIGHT"),
        expected_tool_categories=(GoldenTool.RISK, GoldenTool.INSIGHT, GoldenTool.RULE),
        forbidden_tool_categories=(GoldenTool.SCHEME,),
        expected_characteristics={
            "body_min_chars": 50,
            "evidence_min_count": 1,
        },
        expected_trust_state={
            "mode": "business_analysis",
            "confidence_band": "medium",
        },
        notes="Risk must surface the risk engine output.",
    ),
    # ---- 5 — recommendation --------------------------------------- #
    GoldenCase(
        case_id="golden_recommendation_001",
        prompt="What should we focus on first this quarter?",
        category="recommendation",
        expected_capabilities=("recommendation", "business_fact"),
        expected_required_evidence=("RECOMMENDATION",),
        expected_tool_categories=(GoldenTool.RECOMMENDATION,),
        forbidden_tool_categories=(GoldenTool.SCHEME,),
        expected_characteristics={
            "body_min_chars": 50,
            "evidence_min_count": 1,
        },
        expected_trust_state={
            "mode": "business_analysis",
            "confidence_band": "high",
        },
        notes="Recommendation must cite a rec_id.",
    ),
    # ---- 6 — scenario -------------------------------------------- #
    GoldenCase(
        case_id="golden_scenario_001",
        prompt="What happens if revenue grows 20% next year?",
        category="scenario",
        expected_capabilities=("scenario", "calculation"),
        expected_required_evidence=("FORECAST",),
        expected_tool_categories=(GoldenTool.FORECAST, GoldenTool.FINANCE),
        forbidden_tool_categories=(GoldenTool.SCHEME,),
        expected_characteristics={
            "body_min_chars": 80,
            "evidence_min_count": 1,
        },
        expected_trust_state={
            "mode": "scenario",
            "confidence_band": "medium",
        },
        notes="Scenario must expose assumptions and use forecast engine.",
    ),
    # ---- 7 — comparison ------------------------------------------ #
    GoldenCase(
        case_id="golden_comparison_001",
        prompt="How do we compare to a typical MSME in Tirupur?",
        category="comparison",
        expected_capabilities=("comparison", "business_fact"),
        expected_required_evidence=("SCORE", "INSIGHT"),
        expected_tool_categories=(GoldenTool.SCORE, GoldenTool.INSIGHT),
        forbidden_tool_categories=(GoldenTool.SCHEME, GoldenTool.FORECAST),
        expected_characteristics={
            "body_min_chars": 60,
            "evidence_min_count": 1,
        },
        expected_trust_state={
            "mode": "comparison",
            "confidence_band": "medium",
        },
        notes="Comparison must contrast current vs peer / industry.",
    ),
    # ---- 8 — scheme ---------------------------------------------- #
    GoldenCase(
        case_id="golden_scheme_001",
        prompt="Are there any government schemes we should apply to?",
        category="government_scheme",
        expected_capabilities=("scheme", "business_fact"),
        expected_required_evidence=("SCHEME",),
        expected_tool_categories=(GoldenTool.SCHEME, GoldenTool.SCHEMES_SPRINT16),
        forbidden_tool_categories=(GoldenTool.FORECAST,),
        expected_characteristics={
            "body_min_chars": 50,
            "evidence_min_count": 1,
        },
        expected_trust_state={
            "mode": "scheme",
            "confidence_band": "medium",
        },
        notes="Scheme answer must invoke schemes_sprint16 and cite scheme_id.",
    ),
    # ---- 9 — export ---------------------------------------------- #
    GoldenCase(
        case_id="golden_export_001",
        prompt="What export markets are best for our products?",
        category="export",
        expected_capabilities=("export", "business_fact"),
        expected_required_evidence=("INSIGHT", "RECOMMENDATION"),
        expected_tool_categories=(GoldenTool.INSIGHT, GoldenTool.RECOMMENDATION),
        forbidden_tool_categories=(GoldenTool.SCHEME,),
        expected_characteristics={
            "body_min_chars": 50,
            "evidence_min_count": 1,
        },
        expected_trust_state={
            "mode": "business_analysis",
            "confidence_band": "medium",
        },
        notes="Export answer must surface insight / recommendation engines.",
    ),
    # ---- 10 — missing-data --------------------------------------- #
    GoldenCase(
        case_id="golden_missing_data_001",
        prompt="What is our cash position for the next 6 months?",
        category="financial",
        expected_capabilities=("calculation", "business_fact"),
        expected_required_evidence=("SCORE",),
        expected_tool_categories=(GoldenTool.FINANCE, GoldenTool.SCORE),
        forbidden_tool_categories=(),
        expected_characteristics={
            "body_min_chars": 50,
            "evidence_min_count": 0,
        },
        expected_trust_state={
            "mode": "calculation",
            "confidence_band": "low",
            "warning_expected": True,
        },
        notes="Missing data: profile lacks the inputs; warning expected.",
    ),
    # ---- 11 — mixed question ------------------------------------- #
    GoldenCase(
        case_id="golden_mixed_001",
        prompt="What is the GST rate on textiles and how will it impact us?",
        category="mixed",
        expected_capabilities=("general_knowledge", "business_fact"),
        expected_required_evidence=("EXTERNAL_FACT", "SCORE"),
        expected_tool_categories=(GoldenTool.SCORE, GoldenTool.KNOWLEDGE),
        forbidden_tool_categories=(),
        expected_characteristics={
            "body_min_chars": 80,
            "evidence_min_count": 1,
        },
        expected_trust_state={
            "mode": "mixed",
            "confidence_band": "medium",
        },
        notes="Mixed question must separate external from business block.",
    ),
)


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #


def all_golden_cases() -> tuple[GoldenCase, ...]:
    """Return the immutable 11-case golden set."""
    return GOLDEN_CASES


def get_case(case_id: str) -> GoldenCase | None:
    """Return the case with id ``case_id`` (or ``None``)."""
    for c in GOLDEN_CASES:
        if c.case_id == case_id:
            return c
    return None


__all__ = [
    "GoldenCase",
    "GoldenTool",
    "GOLDEN_CASES",
    "all_golden_cases",
    "get_case",
]
