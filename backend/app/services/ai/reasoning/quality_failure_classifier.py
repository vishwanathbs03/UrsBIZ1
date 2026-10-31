"""SPRINT AI-17 — Bounded Answer Repair + Claim Lifecycle.

Quality-failure classification.

The :class:`AnswerQualityValidator` reports eight axis scores
plus a ``needs_retry`` flag. AI-17 needs a finer-grained view of
*why* the answer failed so the deterministic repair layer can
pick the right repair strategy.

The :class:`QualityFailureClassifier` reads an :class:`AnswerQuality`
plus the per-axis contributing diagnostics and returns a
:class:`QualityFailureReport` whose :attr:`failure_kind` is one of:

  * ``"unsupported_numeric"``  — the answer states a number
    that disagrees with the authoritative tool envelopes (the
    ``numeric`` axis is the weakest and the body carries an
    out-of-band numeric).
  * ``"unsupported_factual"``  — the answer states a fact the
    evidence registry cannot ground (the ``evidence`` axis is
    the weakest and the registry reports an unsupported claim).
  * ``"unsupported_recommendation"`` — the answer recommends
    something the registry has no recommendation entry for.
  * ``"missing_uncertainty"``  — the answer does not disclose
    uncertainty on a question that requires it.
  * ``"missing_evidence"``     — the answer cites no evidence
    IDs / calc IDs on a business-analysis prompt.
  * ``"missing_assumption"``   — the answer does not declare
    the assumptions a scenario / forecast requires.
  * ``"low_quality_generic"``  — the total is below the
    warning threshold but no specific axis pinned the cause.
  * ``"format_violation"``     — the body does not follow the
    chosen answer shell's structural contract.
  * ``"none"``                 — the answer passes.

The classifier never calls the LLM. It is a pure function over
the inputs and is deterministic.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# --------------------------------------------------------------------------- #
# QualityFailureKind vocabulary
# --------------------------------------------------------------------------- #


# Eight brief-mandated axis names. Kept as a module-level tuple
# so the :class:`AnswerQuality` dataclass and the classifier
# agree on the vocabulary.
QUALITY_AXES: tuple[str, ...] = (
    "relevance",
    "evidence",
    "numeric",
    "completeness",
    "uncertainty",
    "actionability",
    "consistency",
    "format",
)


class QualityFailureKind(str):
    """Plain-string enum of failure kinds.

    Using a string subclass (not :class:`enum.Enum`) keeps the
    classifier JSON-serialisable without bespoke to_dict code.
    """

    UNSUPPORTED_NUMERIC = "unsupported_numeric"
    UNSUPPORTED_FACTUAL = "unsupported_factual"
    UNSUPPORTED_RECOMMENDATION = "unsupported_recommendation"
    MISSING_UNCERTAINTY = "missing_uncertainty"
    MISSING_EVIDENCE = "missing_evidence"
    MISSING_ASSUMPTION = "missing_assumption"
    LOW_QUALITY_GENERIC = "low_quality_generic"
    FORMAT_VIOLATION = "format_violation"
    NONE = "none"


# Axis names that pair with each failure kind. The classifier
# uses these to map an axis weakness to a specific repair
# strategy. Multiple failure kinds can map to the same axis
# (e.g. ``unsupported_numeric`` + ``unsupported_factual`` both
# touch ``numeric`` / ``evidence``).
_KIND_TO_AXES: dict[str, tuple[str, ...]] = {
    QualityFailureKind.UNSUPPORTED_NUMERIC: ("numeric", "consistency"),
    QualityFailureKind.UNSUPPORTED_FACTUAL: ("evidence",),
    QualityFailureKind.UNSUPPORTED_RECOMMENDATION: ("evidence", "actionability"),
    QualityFailureKind.MISSING_UNCERTAINTY: ("uncertainty",),
    QualityFailureKind.MISSING_EVIDENCE: ("evidence",),
    QualityFailureKind.MISSING_ASSUMPTION: ("completeness",),
    QualityFailureKind.FORMAT_VIOLATION: ("format", "completeness"),
    QualityFailureKind.LOW_QUALITY_GENERIC: (),
}


# --------------------------------------------------------------------------- #
# Report
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class QualityFailureReport:
    """The classifier's output.

    ``failure_kind`` is one of :class:`QualityFailureKind`. The
    dataclass carries enough metadata for the deterministic
    repair layer to pick the right strategy without re-walking
    the original :class:`AnswerQuality`.

    Attributes
    ----------
    failure_kind:
        One of the nine :class:`QualityFailureKind` values.
    weakest_axis:
        The lowest-scoring axis from the :class:`AnswerQuality`.
        ``""`` when the answer passes.
    weakest_axis_score:
        The 0..10 score of the weakest axis.
    repairable_by_deterministic:
        ``True`` when the failure kind has a deterministic
        repair strategy (PART 2). ``False`` when the answer
        needs an LLM retry or has to ship with a warning.
    repair_strategy:
        One short token the repair layer keys off
        (``"replace_numeric"``, ``"add_uncertainty"``,
        ``"remove_claim"``, ``"reclassify_recommendation"``,
        ``"add_assumptions"``, ``"recompose"``, ``"warning_only"``,
        ``"none"``).
    rationale:
        One-line English summary for the audit trail.
    """

    failure_kind: str = QualityFailureKind.NONE
    weakest_axis: str = ""
    weakest_axis_score: float = 0.0
    repairable_by_deterministic: bool = False
    repair_strategy: str = "none"
    rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "failure_kind": self.failure_kind,
            "weakest_axis": self.weakest_axis,
            "weakest_axis_score": self.weakest_axis_score,
            "repairable_by_deterministic": self.repairable_by_deterministic,
            "repair_strategy": self.repair_strategy,
            "rationale": self.rationale,
        }

    @property
    def is_failing(self) -> bool:
        """True when the answer needs some form of repair / retry / warning."""
        return self.failure_kind != QualityFailureKind.NONE


# --------------------------------------------------------------------------- #
# Classifier
# --------------------------------------------------------------------------- #


# Axis → token mapping the classifier uses to pick the strategy.
# The classifier picks the FIRST strategy whose predicate
# fires; predicates are ordered most-specific to most-generic.
_AXIS_STRATEGY_ORDER: tuple[tuple[str, str], ...] = (
    ("numeric", "replace_numeric"),
    ("evidence", "remove_claim"),
    ("uncertainty", "add_uncertainty"),
    ("completeness", "add_assumptions"),
    ("actionability", "reclassify_recommendation"),
    ("format", "recompose"),
    ("consistency", "replace_numeric"),
    ("relevance", "warning_only"),
)


# Per-axis thresholds the classifier uses to decide "this axis
# is failing badly enough to trigger a specific repair". The
# thresholds are below the validator's warning threshold (4.0)
# so a "thin" axis (e.g. evidence = 3.5) still triggers a
# specific repair when other signals fire.
_AXIS_FAILURE_THRESHOLD: dict[str, float] = {
    "relevance": 3.0,
    "evidence": 3.5,
    "numeric": 4.0,
    "completeness": 3.5,
    "uncertainty": 3.0,
    "actionability": 3.0,
    "consistency": 4.0,
    "format": 3.0,
}


class QualityFailureClassifier:
    """Map an :class:`AnswerQuality` + diagnostics to a repair plan.

    The classifier accepts:

      * :attr:`quality` — the :class:`AnswerQuality` the validator
        produced.
      * :attr:`numeric_conflicts` — the :class:`NumericConflict`
        tuple the numeric checker produced. Empty when there is
        none.
      * :attr:`unsupported_claims` — the tuple of
        ``ClaimAuditRecord`` the claim auditor flagged with
        ``validation_status == "unsupported"``.
      * :attr:`expected_sections` — the sections the
        :class:`AnswerRequirements` declared (drives
        "completeness" repair).
      * :attr:`scenario_assumptions` — the tuple of
        assumptions the :class:`ScenarioAnalysis` produced.
        When ``completeness`` is the weakest axis and the
        scenario has assumptions, the classifier triggers
        ``add_assumptions``.
      * :attr:`registry_has_recommendation` — bool indicating
        whether the registry carries a recommendation entry
        for the LLM's primary rec. Drives
        ``unsupported_recommendation``.

    Pure function. Same inputs ⇒ same output. No LLM access.
    """

    def classify(
        self,
        *,
        quality: Any,
        numeric_conflicts: tuple = (),
        unsupported_claims: tuple = (),
        expected_sections: tuple[str, ...] = (),
        scenario_assumptions: tuple[str, ...] = (),
        registry_has_recommendation: bool = True,
    ) -> QualityFailureReport:
        """Return the :class:`QualityFailureReport`."""
        # Fast path: passing answer.
        if quality is None:
            return QualityFailureReport(rationale="no quality report")

        # Pull the weakest axis and its score.
        scores = {
            axis: float(getattr(quality, axis, 0.0) or 0.0)
            for axis in QUALITY_AXES
        }
        weakest = min(scores, key=lambda k: scores[k])
        weakest_score = scores[weakest]

        # Strategy 1: numeric conflict present → unsupported_numeric.
        if numeric_conflicts:
            return QualityFailureReport(
                failure_kind=QualityFailureKind.UNSUPPORTED_NUMERIC,
                weakest_axis=weakest,
                weakest_axis_score=weakest_score,
                repairable_by_deterministic=True,
                repair_strategy="replace_numeric",
                rationale=(
                    f"{len(numeric_conflicts)} numeric conflict(s) "
                    f"between body and authoritative envelopes"
                ),
            )

        # Strategy 2: unsupported claims present → unsupported_factual.
        if unsupported_claims:
            return QualityFailureReport(
                failure_kind=QualityFailureKind.UNSUPPORTED_FACTUAL,
                weakest_axis=weakest,
                weakest_axis_score=weakest_score,
                repairable_by_deterministic=True,
                repair_strategy="remove_claim",
                rationale=(
                    f"{len(unsupported_claims)} unsupported claim(s) "
                    f"the registry cannot ground"
                ),
            )

        # Strategy 3: missing uncertainty (axis < threshold AND prompt
        # needs disclosure). The classifier conservatively treats any
        # uncertainty axis below 4.0 as missing.
        if scores["uncertainty"] < 3.0:
            return QualityFailureReport(
                failure_kind=QualityFailureKind.MISSING_UNCERTAINTY,
                weakest_axis="uncertainty",
                weakest_axis_score=scores["uncertainty"],
                repairable_by_deterministic=True,
                repair_strategy="add_uncertainty",
                rationale=(
                    "uncertainty axis below 3.0; "
                    "answer does not disclose caveats"
                ),
            )

        # Strategy 4: missing evidence (axis < threshold AND no
        # cited IDs at all).
        if scores["evidence"] < 3.0:
            return QualityFailureReport(
                failure_kind=QualityFailureKind.MISSING_EVIDENCE,
                weakest_axis="evidence",
                weakest_axis_score=scores["evidence"],
                repairable_by_deterministic=True,
                repair_strategy="remove_claim",
                rationale=(
                    "evidence axis below 3.0; "
                    "answer cites no evidence IDs"
                ),
            )

        # Strategy 5: missing assumptions (completeness below
        # threshold AND scenario assumptions exist that the
        # answer did not surface).
        if (
            scores["completeness"] < 3.5
            and expected_sections
            and scenario_assumptions
        ):
            return QualityFailureReport(
                failure_kind=QualityFailureKind.MISSING_ASSUMPTION,
                weakest_axis="completeness",
                weakest_axis_score=scores["completeness"],
                repairable_by_deterministic=True,
                repair_strategy="add_assumptions",
                rationale=(
                    "completeness below 3.5 and scenario has "
                    f"{len(scenario_assumptions)} unstated assumption(s)"
                ),
            )

        # Strategy 6: unsupported recommendation (actionability below
        # threshold AND registry has no matching recommendation).
        if (
            scores["actionability"] < 3.0
            and not registry_has_recommendation
        ):
            return QualityFailureReport(
                failure_kind=QualityFailureKind.UNSUPPORTED_RECOMMENDATION,
                weakest_axis="actionability",
                weakest_axis_score=scores["actionability"],
                repairable_by_deterministic=True,
                repair_strategy="reclassify_recommendation",
                rationale=(
                    "recommendation has no registry match; "
                    "reclassify as inference / assumption"
                ),
            )

        # Strategy 7: format violation (format axis below threshold).
        if scores["format"] < 3.0:
            return QualityFailureReport(
                failure_kind=QualityFailureKind.FORMAT_VIOLATION,
                weakest_axis="format",
                weakest_axis_score=scores["format"],
                repairable_by_deterministic=True,
                repair_strategy="recompose",
                rationale="format axis below 3.0; recompose with shell",
            )

        # Strategy 8: low-quality generic (warning threshold but
        # no specific kind pinned).
        needs_warning = bool(getattr(quality, "needs_warning", False))
        if needs_warning:
            return QualityFailureReport(
                failure_kind=QualityFailureKind.LOW_QUALITY_GENERIC,
                weakest_axis=weakest,
                weakest_axis_score=weakest_score,
                repairable_by_deterministic=False,
                repair_strategy="warning_only",
                rationale=(
                    f"answer quality thin (total<warning threshold); "
                    f"weakest axis={weakest} ({weakest_score:.1f})"
                ),
            )

        # No failure.
        return QualityFailureReport(
            failure_kind=QualityFailureKind.NONE,
            weakest_axis="",
            weakest_axis_score=10.0,
            repairable_by_deterministic=False,
            repair_strategy="none",
            rationale="answer passes all thresholds",
        )

    def repair_strategy_for_kind(self, kind: str) -> str:
        """Return the canonical repair strategy token for a failure kind."""
        _KIND_TO_STRATEGY: dict[str, str] = {
            QualityFailureKind.UNSUPPORTED_NUMERIC: "replace_numeric",
            QualityFailureKind.UNSUPPORTED_FACTUAL: "remove_claim",
            QualityFailureKind.UNSUPPORTED_RECOMMENDATION: "reclassify_recommendation",
            QualityFailureKind.MISSING_UNCERTAINTY: "add_uncertainty",
            QualityFailureKind.MISSING_EVIDENCE: "remove_claim",
            QualityFailureKind.MISSING_ASSUMPTION: "add_assumptions",
            QualityFailureKind.FORMAT_VIOLATION: "recompose",
            QualityFailureKind.LOW_QUALITY_GENERIC: "warning_only",
            QualityFailureKind.NONE: "none",
        }
        return _KIND_TO_STRATEGY.get(kind, "warning_only")

    def axes_for_kind(self, kind: str) -> tuple[str, ...]:
        """Return the axes a failure kind cares about (for traceability)."""
        return _KIND_TO_AXES.get(kind, ())
