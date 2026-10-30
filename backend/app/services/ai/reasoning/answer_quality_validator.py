"""AnswerQualityValidator — SPRINT AI-12.

Post-LLM scoring of the assembled answer on eight axes:

  * ``relevance`` — does the answer address the user's question?
  * ``evidence`` — does it cite evidence (calc IDs, evidence
    IDs, "based on…")?
  * ``numeric`` — are the numbers in the answer internally
    consistent with the tool envelopes?
  * ``completeness`` — does it cover the sections the
    :class:`QuestionUnderstanding.expected_output_sections`
    declared?
  * ``uncertainty`` — does it disclose uncertainty when the
    data is sparse or the confidence is low?
  * ``actionability`` — does it include actionable next
    steps when the question is operational/strategic?
  * ``consistency`` — does it avoid contradicting itself
    (or the envelopes)?
  * ``format`` — does it match the chosen shell template
    (headings, bullets, table)?

Each axis is scored ``0..10``. The ``total`` is the unweighted
mean (in ``0..10``). When ``total < 5.5`` the validator sets
``needs_retry=True`` so the conversation service can trigger
one regeneration pass with a "Tighten weakest axis: X" hint.

The validator is **pure** — same inputs ⇒ same output. No
LLM access, no I/O.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from app.services.ai.reasoning.structured_envelope import StructuredToolEnvelope


# Below this total the answer is "needs retry". Tuned so that
# a passing answer scores 6+ — generous because the LLM is
# noisy and we only have one retry budget.
_NEEDS_RETRY_BELOW = 5.5

# SPRINT AI-15 — low-quality warning thresholds. The brief
# requires a concise warning (NOT a retry) when the answer has
# limited support. Total < 6.5 OR any axis < 4.0 triggers the
# warning. These are deliberately stricter than the retry
# threshold — a "retry" requires a really bad answer; a warning
# is shown on a "thin" one.
_NEEDS_WARNING_BELOW_TOTAL = 6.5
_NEEDS_WARNING_BELOW_AXIS = 4.0

# Soft caps for axis scoring. The validator uses regex / set
# membership heuristics; these caps clamp the heuristic score
# into the 0..10 range so the dataclass never holds a
# "100 % match" out-of-band number.
_AXIS_CAP = 10


@dataclass(frozen=True)
class AnswerQuality:
    """The eight-axis quality report.

    Attributes
    ----------
    relevance, evidence, numeric, completeness,
    uncertainty, actionability, consistency, format:
        Per-axis scores in ``0..10``. ``0`` means the axis
        is fully missing; ``10`` means the axis is fully
        satisfied.
    total:
        Unweighted mean of the eight axes, in ``0..10``.
    weakest_axis:
        Name of the lowest-scoring axis (one of the eight
        field names above). ``""`` when ``total`` is
        already at the cap.
    needs_retry:
        ``True`` when ``total < 5.5``. The conversation
        service treats this as a one-shot regeneration
        request with a "tighten weakest axis" hint.
    rationale:
        One-line explanation for the audit trail.
    needs_warning:
        SPRINT AI-15 — ``True`` when ``total < 6.5`` OR any
        axis is below ``4.0``. Distinct from ``needs_retry``
        (which requires a really bad answer) — the warning
        surfaces honest "limited support" disclosure on a thin
        answer without triggering a second LLM call.
    warning_message:
        SPRINT AI-15 — server-authored one-liner the renderer
        shows when ``needs_warning`` is ``True``. Deliberately
        never exposes internal scoring axis names.
    """

    relevance: float = 0.0
    evidence: float = 0.0
    numeric: float = 0.0
    completeness: float = 0.0
    uncertainty: float = 0.0
    actionability: float = 0.0
    consistency: float = 0.0
    format: float = 0.0
    total: float = 0.0
    weakest_axis: str = ""
    needs_retry: bool = False
    rationale: str = ""
    # SPRINT AI-15 — low-quality warning fields.
    needs_warning: bool = False
    warning_message: str = ""

    def to_dict(self) -> dict:
        return {
            "relevance": self.relevance,
            "evidence": self.evidence,
            "numeric": self.numeric,
            "completeness": self.completeness,
            "uncertainty": self.uncertainty,
            "actionability": self.actionability,
            "consistency": self.consistency,
            "format": self.format,
            "total": self.total,
            "weakest_axis": self.weakest_axis,
            "needs_retry": self.needs_retry,
            "rationale": self.rationale,
            # SPRINT AI-15 — wire mirror for the renderer.
            "needs_warning": self.needs_warning,
            "warning_message": self.warning_message,
        }


# Heuristic regexes used by the per-axis scorers. The set is
# deliberately permissive — the validator scores on shape, not
# on semantic correctness.
_BULLET_RX = r"(?:^|\n)\s*(?:[-*•]|\d+\.)"
_HEADING_RX = r"(?:^|\n)\s*#{1,6}\s|\n\n[A-Z][^\n]{2,60}\n"
_TABLE_RX = r"\|.+\|"
_EVIDENCE_TOKENS = (
    "based on",
    "calc_",
    "rec_",
    "insight_",
    "evidence_id",
    "source:",
    "according to",
    "we recommend",
    "growth multiple",
    "scenario delta",
)
_UNCERTAINTY_TOKENS = (
    "may",
    "could",
    "approximately",
    "estimated",
    "depends on",
    "subject to",
    "assuming",
    "we assume",
)
_ACTION_TOKENS = (
    "next step",
    "you should",
    "recommend",
    "apply for",
    "consider",
    "follow",
    "schedule",
    "register",
    "start by",
)


class AnswerQualityValidator:
    """Eight-axis post-LLM quality scorer."""

    def validate(
        self,
        answer: Any,
        plan: Any = None,
        envelopes: tuple["StructuredToolEnvelope", ...] = (),
    ) -> AnswerQuality:
        """Score ``answer`` and return an :class:`AnswerQuality`.

        ``answer`` may be ``str`` (the raw response body) or
        a dataclass / object with a ``.body`` attribute.
        ``plan`` is the :class:`ReasoningPlan` the engine
        produced (used for completeness scoring). ``envelopes``
        is the dispatcher outcome (used for numeric scoring).
        """
        body = _extract_body(answer)
        body_low = body.lower()

        relevance = self._score_relevance(plan, body)
        evidence = self._score_evidence(body_low)
        numeric = self._score_numeric(body, envelopes)
        completeness = self._score_completeness(plan, body)
        uncertainty = self._score_uncertainty(body_low)
        actionability = self._score_actionability(body_low)
        consistency = self._score_consistency(body, envelopes)
        format_score = self._score_format(body)

        scores = {
            "relevance": relevance,
            "evidence": evidence,
            "numeric": numeric,
            "completeness": completeness,
            "uncertainty": uncertainty,
            "actionability": actionability,
            "consistency": consistency,
            "format": format_score,
        }
        total = sum(scores.values()) / float(len(scores))
        weakest = min(scores, key=lambda k: scores[k])
        needs_retry = total < _NEEDS_RETRY_BELOW
        # SPRINT AI-15 — low-quality warning. Distinct from
        # retry: warning fires on a "thin" answer (low total OR
        # a single weak axis), retry fires on a really bad one.
        # The warning never triggers a second LLM call (the
        # brief is explicit on this).
        any_axis_low = any(
            v < _NEEDS_WARNING_BELOW_AXIS for v in scores.values()
        )
        needs_warning = (
            total < _NEEDS_WARNING_BELOW_TOTAL or any_axis_low
        )
        warning_message = (
            "Some parts of this answer have limited support. "
            "Review the evidence before acting."
            if needs_warning
            else ""
        )
        rationale_bits = [
            f"total={total:.1f}",
            f"weakest={weakest}",
            "retry=yes" if needs_retry else "retry=no",
            "warning=yes" if needs_warning else "warning=no",
        ]
        return AnswerQuality(
            relevance=relevance,
            evidence=evidence,
            numeric=numeric,
            completeness=completeness,
            uncertainty=uncertainty,
            actionability=actionability,
            consistency=consistency,
            format=format_score,
            total=total,
            weakest_axis=weakest if needs_retry else "",
            needs_retry=needs_retry,
            rationale="answer quality: " + " | ".join(rationale_bits),
            # SPRINT AI-15 — low-quality warning.
            needs_warning=needs_warning,
            warning_message=warning_message,
        )

    # ---- per-axis scorers ------------------------------------------ #
    @staticmethod
    def _score_relevance(plan: Any, body: str) -> float:
        """Return 0..10. Rewards the answer being non-empty and non-trivial."""
        if not body or not body.strip():
            return 0.0
        length = len(body.strip())
        if length < 30:
            return 2.0
        if length < 120:
            return 6.0
        return min(10.0, 5.0 + length / 400.0)

    @staticmethod
    def _score_evidence(body_low: str) -> float:
        """Return 0..10. Counts evidence-token matches."""
        hits = sum(1 for tok in _EVIDENCE_TOKENS if tok in body_low)
        return min(_AXIS_CAP, float(hits) * 2.5)

    @staticmethod
    def _score_numeric(
        body: str, envelopes: tuple["StructuredToolEnvelope", ...]
    ) -> float:
        """Return 0..10. Counts numbers in the body that match envelope values."""
        envelope_values = {
            env.value for env in envelopes if env.value is not None
        }
        if not envelope_values:
            # No envelopes — neutral score; no penalty.
            return 6.0
        body_nums = _extract_numbers(body)
        if not body_nums:
            return 3.0
        overlap = 0
        for n in body_nums:
            for env_v in envelope_values:
                try:
                    f_env = float(env_v)
                except (TypeError, ValueError):
                    continue
                if abs(f_env - n) < 0.5:
                    overlap += 1
                    break
        return min(_AXIS_CAP, 4.0 + overlap * 2.0)

    @staticmethod
    def _score_completeness(plan: Any, body: str) -> float:
        """Return 0..10. Checks the body's sections vs ``expected_output_sections``."""
        expected = tuple(
            getattr(plan, "expected_output_sections", ()) or ()
        )
        if not expected:
            return 6.0  # neutral default
        body_low = body.lower()
        hits = 0
        for section in expected:
            if section.lower() in body_low:
                hits += 1
        return min(_AXIS_CAP, float(hits) / float(len(expected)) * 10.0)

    @staticmethod
    def _score_uncertainty(body_low: str) -> float:
        """Return 0..10. Disclosure language is rewarded up to a cap."""
        hits = sum(1 for tok in _UNCERTAINTY_TOKENS if tok in body_low)
        return min(_AXIS_CAP, float(hits) * 3.0)

    @staticmethod
    def _score_actionability(body_low: str) -> float:
        """Return 0..10. Action verbs earn points."""
        hits = sum(1 for tok in _ACTION_TOKENS if tok in body_low)
        return min(_AXIS_CAP, float(hits) * 2.5)

    @staticmethod
    def _score_consistency(
        body: str, envelopes: tuple["StructuredToolEnvelope", ...]
    ) -> float:
        """Return 0..10. Penalises body claims that disagree with envelope values."""
        envelope_values = [
            float(env.value)
            for env in envelopes
            if env.value is not None and isinstance(env.value, (int, float))
        ]
        if not envelope_values:
            return 7.0
        body_nums = _extract_numbers(body)
        if not body_nums:
            return 7.0
        # Count how many body numbers sit within 5% of any envelope value.
        match = 0
        for n in body_nums:
            for ev in envelope_values:
                if ev == 0:
                    continue
                if abs(n - ev) / abs(ev) < 0.05:
                    match += 1
                    break
        return min(_AXIS_CAP, 4.0 + match * 2.0)

    @staticmethod
    def _score_format(body: str) -> float:
        """Return 0..10. Counts structural elements (headings, bullets, table)."""
        if not body:
            return 0.0
        score = 4.0
        if _HEADING_RX and _regex_search(_HEADING_RX, body):
            score += 3.0
        if _regex_search(_BULLET_RX, body):
            score += 2.0
        if _regex_search(_TABLE_RX, body):
            score += 1.0
        return min(_AXIS_CAP, score)


# ---- helpers -------------------------------------------------------- #


def _extract_body(answer: Any) -> str:
    """Extract the response body from ``answer`` (str | object)."""
    if answer is None:
        return ""
    if isinstance(answer, str):
        return answer
    for attr in ("body", "text", "content", "response"):
        v = getattr(answer, attr, None)
        if isinstance(v, str):
            return v
    return str(answer)


def _extract_numbers(body: str) -> list[float]:
    """Return the numeric literals in ``body`` (best-effort)."""
    import re

    out: list[float] = []
    for m in re.finditer(r"-?\d{1,3}(?:,\d{3})*(?:\.\d+)?|-?\d+\.\d+|-?\d+", body):
        try:
            out.append(float(m.group(0).replace(",", "")))
        except ValueError:
            continue
    return out


def _regex_search(pattern: str, body: str) -> bool:
    """Light wrapper so the import isn't at module top level."""
    import re

    return bool(re.search(pattern, body))