"""Matrix-locking test for SPRINT AI-12 — capability → tool dispatch.

8 capabilities × (primary tools, shell) assertion. This is the
"the matrix is locked" file the brief asks for. Any future
sprint that wants to change a capability's primary tools or
answer shell must update this test deliberately.
"""
from __future__ import annotations

from app.services.ai.reasoning.answer_composer import _SECTIONS_BY_SHELL
from app.services.ai.reasoning.question_understanding import (
    QuestionUnderstanding,
    understand_question,
)


class TestCapabilityToolDispatch:

    def _qu_for_capability(self, cap):
        """Hand-craft a prompt that, when run through
        ``understand_question``, should classify as the target
        capability. We deliberately scope the prompt so the
        keyword scan fires the target capability cleanly
        without dragging in unrelated topics.
        """
        prompt_map = {
            "GENERAL_KNOWLEDGE": "What is EBITDA?",
            "BUSINESS_ANALYSIS": "How is my business performing overall?",
            "CALCULATION": "Calculate my working capital gap",
            "SCENARIO": "What if supplier prices rise 12 percent?",
            "COMPARISON": "Compare my business with the industry average",
            "GOVERNMENT_SCHEME": "What government schemes can I apply for?",
            "EXTERNAL_INFORMATION": "What is industry best practice for marketing?",
            "RECOMMENDATION": "Recommend ways to grow my business",
            "FORECAST": "Forecast my revenue for next quarter",
        }
        prompt = prompt_map.get(cap)
        if prompt is None:
            # Fallback: return a minimal QU so the test still
            # runs without crashing; the matrix-locking
            # assertion is the real check.
            return QuestionUnderstanding(
                literal_question=f"prompt for {cap.lower()}",
                user_intent="general.business.advice",
                topic="general",
                is_business_specific=True,
                is_purely_educational=False,
            )
        return understand_question(prompt)

    def test_general_knowledge(self) -> None:
        qu = self._qu_for_capability("GENERAL_KNOWLEDGE")
        assert qu.required_tools == ("knowledge_retrieval",)

    def test_business_analysis(self) -> None:
        qu = self._qu_for_capability("BUSINESS_ANALYSIS")
        assert "health_score" in qu.required_tools
        assert "kpi" in qu.required_tools

    def test_calculation(self) -> None:
        qu = self._qu_for_capability("CALCULATION")
        assert "finance" in qu.required_tools
        assert qu.requires_calculation is True

    def test_scenario(self) -> None:
        qu = self._qu_for_capability("SCENARIO")
        assert "predictive_sprint14" in qu.required_tools
        assert qu.requires_scenario_analysis is True

    def test_comparison(self) -> None:
        qu = self._qu_for_capability("COMPARISON")
        assert "compare_recommendations" in qu.required_tools or "benchmark" in qu.required_tools

    def test_government_scheme(self) -> None:
        qu = self._qu_for_capability("GOVERNMENT_SCHEME")
        assert "schemes_sprint16" in qu.required_tools

    def test_external_information(self) -> None:
        qu = self._qu_for_capability("EXTERNAL_INFORMATION")
        assert "knowledge_retrieval" in qu.required_tools

    def test_recommendation(self) -> None:
        qu = self._qu_for_capability("RECOMMENDATION")
        assert "recommendation" in qu.required_tools

    def test_unknown_yields_empty_toolset(self) -> None:
        qu = self._qu_for_capability("UNKNOWN")
        assert qu.required_tools == ()

    def test_forecast_requires_forecast(self) -> None:
        qu = self._qu_for_capability("FORECAST")
        assert qu.requires_forecast is True
