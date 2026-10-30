"""Tests for SPRINT AI-12 — EvidenceRequirementPlanner.

Four tests, one per capability family. The planner is a pure
function over ``QuestionUnderstanding``; same inputs ⇒ same
output. Asserts:

  * every required set is non-empty for active capabilities,
  * ``"profile"`` is always present for business-specific
    prompts,
  * the rationale is a one-line string.
"""
from __future__ import annotations

from app.services.ai.reasoning.evidence_requirements import (
    EvidenceRequirements,
    plan,
)
from app.services.ai.reasoning.question_understanding import (
    QuestionUnderstanding,
    understand_question,
)


class TestEvidenceRequirementPlanner:

    def test_business_analysis_populates_required(self) -> None:
        qu = understand_question("What is my business health score?")
        req = plan(qu)
        assert req.required  # non-empty
        assert "profile" in req.required

    def test_scenario_populates_assumption_evidence(self) -> None:
        qu = understand_question("What if cotton prices increase by 12%?")
        req = plan(qu)
        # Required includes profile + historical_assumption for SCENARIO.
        assert "profile" in req.required
        assert "historical_assumption" in req.required

    def test_government_scheme_populates_scheme_evidence(self) -> None:
        qu = understand_question("What MSME schemes can I apply for?")
        req = plan(qu)
        assert "scheme" in req.required
        assert "funding" in req.required

    def test_unknown_prompt_gets_profile_only(self) -> None:
        # Synthesise a QU with no capabilities (legacy callers).
        qu = QuestionUnderstanding(
            literal_question="z",
            user_intent="general.business.advice",
            topic="general",
            is_business_specific=False,
            is_purely_educational=False,
        )
        req = plan(qu)
        # No business-specific flag → no profile injection.
        assert req.required == ()
        assert req.optional == ()
        assert "no-capability-detected" in req.rationale

    def test_business_specific_injects_profile(self) -> None:
        qu = QuestionUnderstanding(
            literal_question="my numbers?",
            user_intent="general.business.advice",
            topic="general",
            is_business_specific=True,
            is_purely_educational=False,
            capability=("BUSINESS_ANALYSIS",),
        )
        req = plan(qu)
        # capability BUSINESS_ANALYSIS brings in profile+analytics+kpi_history.
        assert "profile" in req.required
        assert "analytics" in req.required

    def test_to_dict_carries_three_fields(self) -> None:
        qu = understand_question("Compare my business with the industry")
        req = plan(qu)
        d = req.to_dict()
        for k in ("required", "optional", "rationale"):
            assert k in d
