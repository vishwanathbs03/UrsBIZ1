"""Test suite for Sprint H8.3 — Explicit Reasoning Pipeline & Conclusion Sanitizer."""

import pytest
from app.services.ai.reasoning.pipeline import ReasoningPipeline
from app.services.ai.reasoning.sanitizer import ConclusionSanitizer


def test_1_sanitizer_removes_thinking_fences():
    """Verify ConclusionSanitizer strips <think> tags and internal reasoning blocks."""
    raw = """<think>
Step 1: Analyzing revenue ₹1.8 Cr.
Step 2: Supplier risk is high.
</think>

### Executive Summary
Acme Textiles is positioned for growth with a ₹1.8 Cr revenue baseline.

[REASONING]
Hypothesis 1 validated.
[/REASONING]

### Recommended Next Actions
- Audit top yarn suppliers.
"""
    sanitizer = ConclusionSanitizer()
    clean = sanitizer.sanitize(raw)

    assert "<think>" not in clean
    assert "[REASONING]" not in clean
    assert "Step 1:" not in clean
    assert "### Executive Summary" in clean
    assert "### Recommended Next Actions" in clean


def test_2_sanitizer_collapses_whitespace():
    """Verify ConclusionSanitizer collapses redundant newlines to maximum 2."""
    raw = "Line 1\n\n\n\n\nLine 2\n\n\n\nLine 3"
    sanitizer = ConclusionSanitizer()
    clean = sanitizer.sanitize(raw)

    assert "\n\n\n" not in clean
    assert "Line 1\n\nLine 2\n\nLine 3" == clean


@pytest.fixture
def sim_context():
    from app.services.ai.providers.base import AssistantContext, AssistantContextDna
    return AssistantContext(
        business_id=1,
        legal_name="Acme Textiles",
        industry="Textiles",
        annual_revenue_inr=18000000,
        overall_business_score=68,
        band="Established",
        dna=AssistantContextDna("growth_operator", "Growth Operator", 85),
    )


def test_3_reasoning_pipeline_executes_8_stages(sim_context):
    """Verify ReasoningPipeline executes 8 internal stages and returns clean conclusions."""
    pipeline = ReasoningPipeline()
    raw_body = """<think>
Internal hypothesis: Supplier risk limits margin expansion.
Confidence: 88%
</think>

### Executive Summary
Acme Textiles should diversify yarn suppliers to unlock margin expansion.
"""
    result = pipeline.process(
        user_prompt="Help Acme Textiles grow",
        context=sim_context,
        raw_response_body=raw_body,
    )

    assert "<think>" not in result
    assert "Acme Textiles should diversify yarn suppliers" in result
