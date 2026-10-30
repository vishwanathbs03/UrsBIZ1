"""Sprint AI-15 — quality warning tests.

4 tests covering the low-quality warning flag (distinct from
retry), threshold behaviour, and message content safety.
"""

from __future__ import annotations

from app.services.ai.reasoning.answer_quality_validator import (
    AnswerQualityValidator,
)


class _StubEnv:
    def __init__(self, **kw):
        self.tool_name = kw.get("tool_name", "finance")
        self.metric = kw.get("metric", "amount")
        self.value = kw.get("value", 1.0)
        self.unit = kw.get("unit", "INR")
        self.confidence = kw.get("confidence", 1.0)


class _StubPlan:
    def __init__(self, **kw):
        self.required_evidence_ids = kw.get("required_evidence_ids", ())
        self.missing_evidence_ids = kw.get("missing_evidence_ids", ())


def _validator() -> AnswerQualityValidator:
    return AnswerQualityValidator()


# --------------------------------------------------------------------------- #
# 1 — high-quality answer ⇒ no warning
# --------------------------------------------------------------------------- #


def test_high_quality_no_warning():
    """A response with all the canonical trust signals should
    pass the warning threshold."""
    body = (
        "Revenue is ₹1.8 Cr. Based on the finance.amount envelope, "
        "we recommend scheduling a follow-up next step. The formula is value. "
        "Approximately 18,000,000 INR may be available. "
        "According to industry benchmarks, this is reasonable. "
        "Apply for working capital next. Consider registering with MUDRA. "
        "Follow the compliance checklist. You should also review the "
        "seasonality risk which could affect next quarter's revenue. "
        "We assume cotton prices remain stable. Subject to availability "
        "of working capital lines, the company may pursue export orders. "
        "Depending on demand, capacity could be expanded next year. "
        "Evidence: finance.amount source. Recommendation: apply for MUDRA loan."
    )
    plan = _StubPlan(required_evidence_ids=("e1",), missing_evidence_ids=())
    env = _StubEnv(value=1.8e7)
    quality = _validator().validate(answer=body, plan=plan, envelopes=(env,))
    assert quality.total >= 6.5, (
        f"total={quality.total} below threshold"
    )
    assert quality.needs_warning is False
    assert quality.warning_message == ""


# --------------------------------------------------------------------------- #
# 2 — low-total answer ⇒ warning fires with non-empty message
# --------------------------------------------------------------------------- #


def test_low_total_fires_warning():
    """A very short body with no trust signals should fall below
    the total threshold and emit the warning."""
    body = "Maybe. Or not."
    plan = _StubPlan()
    env = _StubEnv()
    quality = _validator().validate(answer=body, plan=plan, envelopes=(env,))
    assert quality.total < 6.5
    assert quality.needs_warning is True
    assert quality.warning_message
    assert "limited" in quality.warning_message.lower() or "review" in quality.warning_message.lower()


# --------------------------------------------------------------------------- #
# 3 — any-axis-low ⇒ warning fires
# --------------------------------------------------------------------------- #


def test_single_weak_axis_fires_warning():
    """Even when total is decent, a single weak axis should fire
    the warning."""
    # Body with 0 uncertainty tokens → uncertainty = 0
    body = (
        "Revenue is ₹1.8 Cr. Based on the finance.amount envelope, "
        "we recommend scheduling a follow-up. The formula is value. "
        "Apply for working capital next."
    )
    plan = _StubPlan(required_evidence_ids=("e1",), missing_evidence_ids=())
    env = _StubEnv(value=1.8e7)
    quality = _validator().validate(answer=body, plan=plan, envelopes=(env,))
    assert quality.uncertainty < 4.0, (
        f"uncertainty={quality.uncertainty} should be weak"
    )
    assert quality.needs_warning is True


# --------------------------------------------------------------------------- #
# 4 — warning message never exposes internal scoring labels
# --------------------------------------------------------------------------- #


def test_warning_message_has_no_internal_labels():
    """The user-facing warning must never expose axis names or
    scoring labels."""
    body = ""
    plan = _StubPlan()
    quality = _validator().validate(answer=body, plan=plan, envelopes=())
    msg = quality.warning_message.lower()
    for forbidden in (
        "relevance=",
        "evidence=",
        "numeric=",
        "completeness=",
        "uncertainty=",
        "actionability=",
        "consistency=",
        "format=",
        "axis",
        "weakest",
    ):
        assert forbidden not in msg, f"warning leaked internal label: {forbidden}"