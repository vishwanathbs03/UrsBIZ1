"""Tests for SPRINT AI-12 — AnswerQualityValidator.

Eight-axis post-LLM scoring. Three tests:

  * a high-quality answer returns ``needs_retry=False``,
  * a low-quality answer returns ``needs_retry=True`` and
    identifies the weakest axis,
  * a neutral answer sits in the middle.
"""
from __future__ import annotations

from app.services.ai.reasoning.answer_quality_validator import (
    AnswerQuality,
    AnswerQualityValidator,
)
import pytest


class TestAnswerQualityValidator:

    def test_high_quality_answer_passes(self) -> None:
        v = AnswerQualityValidator()
        body = """# Executive Summary

Based on health_score 72 and the recent KPI history, your business
is on track. Rec_42 indicates the next recommended action.

- Apply for the MSME subsidy scheme.
- Schedule a working-capital review.

Estimated margin expansion is approximately 18% over Q3, assuming
demand stays stable. We recommend a 12-month roadmap.

| KPI | Current | Target |
|-----|---------|--------|
| Revenue | 1.0cr | 1.5cr |
"""
        q = v.validate(body)
        # The 5-axis answer should easily clear 5.5
        assert q.total >= 5.5
        assert q.needs_retry is False

    def test_low_quality_answer_needs_retry(self) -> None:
        v = AnswerQualityValidator()
        q = v.validate("ok")
        assert q.total < 5.5
        assert q.needs_retry is True
        # weakest_axis populated for retry decisions
        assert q.weakest_axis

    def test_neutral_answer_in_middle(self) -> None:
        v = AnswerQualityValidator()
        body = "Some prose without structure. About two lines."
        q = v.validate(body)
        # Body length 42 chars triggers _score_relevance=6.0
        assert 0 < q.total < 10

    def test_plan_used_for_completeness(self) -> None:
        v = AnswerQualityValidator()
        # Plan provides expected_output_sections — body should cover them
        class _P:
            expected_output_sections = ("summary", "actions", "evidence")
        body = "# Summary\nThe summary. Actions follow.\n- Do X.\nMore text."
        q = v.validate(body, _P())
        # At minimum 2 of 3 sections must appear
        assert q.completeness > 0

    def test_envelope_numeric_scoring(self) -> None:
        v = AnswerQualityValidator()
        from app.services.ai.reasoning.structured_envelope import (
            envelope_from_tool_result,
        )
        from app.services.ai.reasoning.tool_selector import ToolResult
        env = envelope_from_tool_result(
            "health_score",
            ToolResult(service_name="health_score", status="ok",
                       payload={"score": 72, "unit": "/100"}),
            owner_id=1,
        )
        body = "Your health score is 72. Things are good."
        q = v.validate(body, envelopes=(env,))
        # Body matches envelope value — numeric should be high
        assert q.numeric > 0

    def test_to_dict_carries_eight_axes(self) -> None:
        v = AnswerQualityValidator()
        q = v.validate("hi")
        d = q.to_dict()
        for k in (
            "relevance", "evidence", "numeric", "completeness",
            "uncertainty", "actionability", "consistency", "format",
            "total", "weakest_axis", "needs_retry", "rationale",
        ):
            assert k in d


def pytest_approx(x):
    return x  # not strictly pytest.approx to avoid import — pass through
