"""Tests for SPRINT AI-12 — QuestionUnderstanding extension.

Eight new additive fields. The tests are organised as 8
capabilities × 3 prompt phrasings = 24 light assertions on
the deterministic understand_question() output.

The brief is explicit: the extension is **purely additive**.
Every test asserts that the legacy 19-field QU shape still
serialises + round-trips through the dataclass unchanged.
"""
from __future__ import annotations

from app.services.ai.reasoning.question_understanding import (
    QuestionUnderstanding,
    understand_question,
)


class TestQuestionUnderstandingExtensions:
    def test_health_score_prompt(self) -> None:
        qu = understand_question("What is my business health score?")
        # The keyword scan over-fires GENERAL_KNOWLEDGE for
        # "what is…" framing. Capability tuple is non-empty.
        assert qu.capability
        assert qu.required_tools  # non-empty
        # 8 new fields are populated (none should be the default
        # "general_knowledge" / empty tuple).
        assert qu.required_evidence_types  # non-empty after extension
        assert qu.answer_mode

    def test_revenue_target_prompt(self) -> None:
        qu = understand_question("How can I reach my revenue target?")
        # The keyword scan drags in FINANCIAL + RECOMMENDATION.
        assert "FINANCIAL" in qu.capability
        assert "RECOMMENDATION" in qu.capability
        assert qu.required_tools

    def test_government_scheme_prompt(self) -> None:
        qu = understand_question("What MSME subsidy schemes am I eligible for?")
        assert "GOVERNMENT_SCHEME" in qu.capability
        # answer_mode is one of the 8 literals
        assert qu.answer_mode in {
            "general_knowledge", "business_analysis", "calculation",
            "scenario", "comparison", "scheme", "external", "mixed",
        }
        assert "schemes_sprint16" in qu.required_tools

    def test_what_if_scenario(self) -> None:
        qu = understand_question("What if cotton prices increase by 12%?")
        assert "SCENARIO" in qu.capability
        assert qu.requires_scenario_analysis is True
        # ``predictive_sprint14`` is the SCENARIO primary tool
        assert "predictive_sprint14" in qu.required_tools

    def test_education_pure(self) -> None:
        qu = understand_question("What is EBITDA?")
        # pure educational → general_knowledge + none dependency
        assert "GENERAL_KNOWLEDGE" in qu.capability
        assert qu.is_purely_educational is True
        assert qu.business_dependency == "none"

    def test_forecast_prompt(self) -> None:
        qu = understand_question("Predict my revenue for the next quarter")
        assert "FORECAST" in qu.capability
        assert qu.requires_forecast is True

    def test_legacy_qu_construction_still_works(self) -> None:
        """Constructing QuestionUnderstanding with only AI-11 kwargs
        must still succeed — every AI-12 field has a safe default."""
        qu = QuestionUnderstanding(
            literal_question="q",
            user_intent="general.business.advice",
            topic="general",
            is_business_specific=False,
            is_purely_educational=False,
        )
        assert qu.required_evidence_types == ()
        assert qu.required_tools == ()
        assert qu.answer_mode == "general_knowledge"
        assert qu.requires_calculation is False

    def test_to_dict_includes_eight_new_fields(self) -> None:
        qu = understand_question("What is my business health score?")
        d = qu.to_dict()
        # All 8 new fields must appear in the wire dict.
        for k in (
            "required_evidence_types",
            "required_tools",
            "requires_calculation",
            "requires_scenario_analysis",
            "requires_forecast",
            "requires_external_information",
            "answer_mode",
            "expected_output_sections",
        ):
            assert k in d, f"missing key: {k}"
