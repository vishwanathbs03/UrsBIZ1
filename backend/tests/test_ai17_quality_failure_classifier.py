"""SPRINT AI-17 — Bounded Answer Repair + Claim Lifecycle.

Tests for ``quality_failure_classifier``: the 9-vocabulary
failure taxonomy and the 8-strategy decision tree.

8 tests covering:
  * Numeric conflicts → UNSUPPORTED_NUMERIC strategy "replace_numeric"
  * Unsupported claims → UNSUPPORTED_FACTUAL strategy "remove_claim"
  * Missing uncertainty axis → MISSING_UNCERTAINTY strategy "add_uncertainty"
  * Missing evidence axis → MISSING_EVIDENCE strategy "remove_claim"
  * Completeness + scenario assumptions → MISSING_ASSUMPTION
    strategy "add_assumptions"
  * Actionability + no recommendation entry → UNSUPPORTED_RECOMMENDATION
    strategy "reclassify_recommendation"
  * Format axis below threshold → FORMAT_VIOLATION strategy "recompose"
  * Passing answer → NONE / "none" strategy
"""

from __future__ import annotations

from types import SimpleNamespace

from app.services.ai.reasoning.quality_failure_classifier import (
    QUALITY_AXES,
    QualityFailureClassifier,
    QualityFailureKind,
    QualityFailureReport,
)


def _make_quality(**overrides):
    """Build a SimpleNamespace mimicking AnswerQuality with sane defaults."""
    defaults = {
        "relevance": 7.0,
        "evidence": 7.0,
        "numeric": 7.0,
        "completeness": 7.0,
        "uncertainty": 7.0,
        "actionability": 7.0,
        "consistency": 7.0,
        "format": 7.0,
        "total": 7.0,
        "needs_warning": False,
        "needs_retry": False,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


# --------------------------------------------------------------------------- #
# 1 — Numeric conflicts → replace_numeric
# --------------------------------------------------------------------------- #


def test_numeric_conflict_classifies_as_unsupported_numeric():
    """When the numeric checker reports any conflict the
    classifier must return UNSUPPORTED_NUMERIC with strategy
    ``replace_numeric``."""
    classifier = QualityFailureClassifier()
    quality = _make_quality()
    conflicts = (SimpleNamespace(metric="revenue", llm_value=180.0),)
    report = classifier.classify(
        quality=quality, numeric_conflicts=conflicts
    )
    assert report.failure_kind == QualityFailureKind.UNSUPPORTED_NUMERIC
    assert report.repair_strategy == "replace_numeric"
    assert report.repairable_by_deterministic is True


# --------------------------------------------------------------------------- #
# 2 — Unsupported claims → remove_claim
# --------------------------------------------------------------------------- #


def test_unsupported_claim_classifies_as_unsupported_factual():
    """When the claim auditor flags any unsupported claim the
    classifier must return UNSUPPORTED_FACTUAL with strategy
    ``remove_claim``."""
    classifier = QualityFailureClassifier()
    quality = _make_quality()
    unsupported = (
        SimpleNamespace(text="Acme will raise Series B in 2025"),
    )
    report = classifier.classify(
        quality=quality, unsupported_claims=unsupported
    )
    assert report.failure_kind == QualityFailureKind.UNSUPPORTED_FACTUAL
    assert report.repair_strategy == "remove_claim"
    assert report.repairable_by_deterministic is True


# --------------------------------------------------------------------------- #
# 3 — Uncertainty axis below threshold → add_uncertainty
# --------------------------------------------------------------------------- #


def test_low_uncertainty_classifies_as_missing_uncertainty():
    """Uncertainty axis below 3.0 with no numeric conflicts and
    no unsupported claims → MISSING_UNCERTAINTY / ``add_uncertainty``."""
    classifier = QualityFailureClassifier()
    quality = _make_quality(uncertainty=2.0)
    report = classifier.classify(quality=quality)
    assert report.failure_kind == QualityFailureKind.MISSING_UNCERTAINTY
    assert report.repair_strategy == "add_uncertainty"
    assert report.weakest_axis == "uncertainty"


# --------------------------------------------------------------------------- #
# 4 — Evidence axis below threshold → remove_claim
# --------------------------------------------------------------------------- #


def test_low_evidence_classifies_as_missing_evidence():
    """Evidence axis below 3.0 → MISSING_EVIDENCE / ``remove_claim``."""
    classifier = QualityFailureClassifier()
    quality = _make_quality(uncertainty=6.0, evidence=2.0)
    report = classifier.classify(quality=quality)
    assert report.failure_kind == QualityFailureKind.MISSING_EVIDENCE
    assert report.repair_strategy == "remove_claim"
    assert report.weakest_axis == "evidence"


# --------------------------------------------------------------------------- #
# 5 — Completeness + scenario assumptions → add_assumptions
# --------------------------------------------------------------------------- #


def test_low_completeness_with_scenario_assumptions_classifies_as_missing_assumption():
    """Completeness below 3.5 with scenario assumptions → MISSING_ASSUMPTION."""
    classifier = QualityFailureClassifier()
    quality = _make_quality(uncertainty=6.0, evidence=6.0, completeness=2.0)
    report = classifier.classify(
        quality=quality,
        expected_sections=("summary", "assumptions"),
        scenario_assumptions=("revenue grows 20%", "headcount flat"),
    )
    assert report.failure_kind == QualityFailureKind.MISSING_ASSUMPTION
    assert report.repair_strategy == "add_assumptions"


# --------------------------------------------------------------------------- #
# 6 — Actionability + no recommendation → reclassify_recommendation
# --------------------------------------------------------------------------- #


def test_low_actionability_no_registry_match_classifies_as_unsupported_recommendation():
    """Actionability below 3.0 AND registry_has_recommendation=False
    → UNSUPPORTED_RECOMMENDATION / ``reclassify_recommendation``."""
    classifier = QualityFailureClassifier()
    quality = _make_quality(
        uncertainty=6.0, evidence=6.0, completeness=6.0, actionability=2.0
    )
    report = classifier.classify(
        quality=quality,
        registry_has_recommendation=False,
    )
    assert report.failure_kind == QualityFailureKind.UNSUPPORTED_RECOMMENDATION
    assert report.repair_strategy == "reclassify_recommendation"


# --------------------------------------------------------------------------- #
# 7 — Format axis below threshold → recompose
# --------------------------------------------------------------------------- #


def test_low_format_classifies_as_format_violation():
    """Format axis below 3.0 → FORMAT_VIOLATION / ``recompose``."""
    classifier = QualityFailureClassifier()
    quality = _make_quality(
        uncertainty=6.0, evidence=6.0, completeness=6.0, actionability=6.0,
        format=2.0,
    )
    report = classifier.classify(quality=quality)
    assert report.failure_kind == QualityFailureKind.FORMAT_VIOLATION
    assert report.repair_strategy == "recompose"


# --------------------------------------------------------------------------- #
# 8 — Passing answer → NONE
# --------------------------------------------------------------------------- #


def test_passing_answer_classifies_as_none():
    """A high-quality answer with no conflicts → NONE / ``none``."""
    classifier = QualityFailureClassifier()
    quality = _make_quality(
        relevance=8.0, evidence=8.0, numeric=8.0, completeness=8.0,
        uncertainty=8.0, actionability=8.0, consistency=8.0, format=8.0,
    )
    report = classifier.classify(quality=quality)
    assert report.failure_kind == QualityFailureKind.NONE
    assert report.repair_strategy == "none"
    assert report.repairable_by_deterministic is False
    assert report.is_failing is False


# --------------------------------------------------------------------------- #
# 9 — Weakest axis computation
# --------------------------------------------------------------------------- #


def test_weakest_axis_is_lowest_scoring():
    """The classifier surfaces the lowest-scoring axis name in
    :attr:`QualityFailureReport.weakest_axis`."""
    classifier = QualityFailureClassifier()
    quality = _make_quality(
        relevance=8.0, evidence=8.0, numeric=8.0, completeness=8.0,
        uncertainty=1.0, actionability=8.0, consistency=8.0, format=8.0,
        needs_warning=True,
    )
    report = classifier.classify(quality=quality)
    # Without numeric_conflicts or unsupported_claims, the lowest
    # axis (uncertainty=1.0) drives the MISSING_UNCERTAINTY verdict.
    assert report.weakest_axis == "uncertainty"


# --------------------------------------------------------------------------- #
# 10 — 8-axis vocabulary is exactly the brief's vocabulary
# --------------------------------------------------------------------------- #


def test_quality_axes_vocabulary_matches_brief():
    """The 8-axis vocabulary must match the brief verbatim."""
    assert QUALITY_AXES == (
        "relevance",
        "evidence",
        "numeric",
        "completeness",
        "uncertainty",
        "actionability",
        "consistency",
        "format",
    )


# --------------------------------------------------------------------------- #
# 11 — repair_strategy_for_kind + axes_for_kind helpers
# --------------------------------------------------------------------------- #


def test_helpers_round_trip_kind_to_strategy():
    """Every recognised kind has a canonical strategy."""
    classifier = QualityFailureClassifier()
    assert classifier.repair_strategy_for_kind(
        QualityFailureKind.UNSUPPORTED_NUMERIC
    ) == "replace_numeric"
    assert classifier.repair_strategy_for_kind(
        QualityFailureKind.MISSING_UNCERTAINTY
    ) == "add_uncertainty"
    assert classifier.axes_for_kind(
        QualityFailureKind.UNSUPPORTED_NUMERIC
    ) == ("numeric", "consistency")
