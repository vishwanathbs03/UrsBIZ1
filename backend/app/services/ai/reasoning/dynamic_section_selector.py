"""Sprint AI-14 — Universal Answer Intelligence: ``dynamic_section_selector``.

UX contract: every reply starts with one hero-direct-answer line
and follows it with **at most 3 supporting sections**. Complex
prompts that legitimately need more than 3 supports fall back
to the legacy ``expanded`` shell so the renderer returns a
fuller report instead of truncating the answer.

This module reads the :class:`AnswerRequirements` the engine
emitted for the prompt and returns the ordered section list
the composer should render. The selector is a pure function —
same inputs always return the same sections.

Section inventory
----------------

  1. ``direct_answer``     — ALWAYS first; hero conclusion.
  2. ``business_evidence`` — needs_business_evidence.
  3. ``analysis``          — any of (recommendation, risk,
                              scenario, comparison) — generic
                              "analysis" section.
  4. ``calculations``      — needs_calculation.
  5. ``assumptions``       — needs_assumptions.
  6. ``missing_data``      — needs_missing_data OR
                              unsupported_claim_count > 0.
  7. ``sources``           — external info / external sources.
  8. ``confidence``        — always last when contradiction
                              severity is ``"high"`` OR
                              unsupported_claim_count > 0.

Sections that exceed ``MAX_SUPPORTING_SECTIONS`` (=3) after
``direct_answer`` trigger the fallback shell literal. The
fallback shell literal is what the AI-12 / AI-13 ``AdaptiveAnswer``
shell would have rendered (``"expanded"`` by default); the
caller can swap it for any shell the legacy composer supports
(``"scenario"``, ``"comparison"``, ``"scheme"``, ...).
"""
from __future__ import annotations

from typing import Any

from app.services.ai.reasoning.answer_requirements import AnswerRequirements


# Public configuration — single source of truth. Tests assert
# against these values.
MAX_SUPPORTING_SECTIONS: int = 3

ALL_SECTIONS: tuple[str, ...] = (
    "direct_answer",
    "business_evidence",
    "analysis",
    "calculations",
    "assumptions",
    "missing_data",
    "sources",
    "confidence",
)


def select_sections(
    answer_requirements: AnswerRequirements | None,
    *,
    contradiction_severity: str = "none",
    unsupported_claim_count: int = 0,
    fallback_shell: str = "expanded",
) -> tuple[str, ...]:
    """Return the ordered section list the renderer should produce.

    Parameters
    ----------
    answer_requirements
        The frozen dataclass ``derive_answer_requirements``
        produced for this prompt. ``None`` is treated as an
        empty requirements object (legacy callers — the
        selector returns just ``("direct_answer",)``).
    contradiction_severity
        One of ``"none"`` / ``"low"`` / ``"medium"`` /
        ``"high"``. When ``"high"``, ``confidence`` is added.
    unsupported_claim_count
        Number of claims the evidence graph could not support.
        Drives the ``missing_data`` section.
    fallback_shell
        Shell literal the caller should use when the prompt
        needs more than ``MAX_SUPPORTING_SECTIONS`` supporting
        sections. The selector does NOT return the shell
        literal itself; the caller checks
        ``len(sections) > MAX_SUPPORTING_SECTIONS + 1`` and
        uses ``fallback_shell`` accordingly.

    Returns
    -------
    tuple[str, ...]
        Ordered section names. The first element is ALWAYS
        ``"direct_answer"``.
    """
    if answer_requirements is None:
        return ("direct_answer",)

    sections: list[str] = ["direct_answer"]  # ALWAYS first.

    needs_any_analysis = (
        answer_requirements.needs_recommendation
        or answer_requirements.needs_risk_analysis
        or answer_requirements.needs_scenario
        or answer_requirements.needs_comparison
    )
    if needs_any_analysis:
        sections.append("analysis")

    if answer_requirements.needs_business_evidence:
        sections.append("business_evidence")

    if answer_requirements.needs_calculation:
        sections.append("calculations")

    if answer_requirements.needs_assumptions:
        sections.append("assumptions")

    if (
        answer_requirements.needs_missing_data
        or int(unsupported_claim_count or 0) > 0
    ):
        sections.append("missing_data")

    if (
        answer_requirements.needs_external_information
        or len(sections) >= 2
        and answer_requirements.requested_entities
        # External info is implied when the prompt names an
        # entity not in the profile — the renderer surfaces
        # external sources even when the QU flag is off.
        and any("scheme" in e.lower() or "regulation" in e.lower() for e in answer_requirements.requested_entities)
    ):
        sections.append("sources")

    if contradiction_severity == "high" or int(unsupported_claim_count or 0) > 0:
        sections.append("confidence")

    # Enforce the hero-first + max-3-supports UX contract.
    # Truncate to MAX_SUPPORTING_SECTIONS + 1 (direct_answer is
    # not counted as a support); the caller is expected to
    # detect ``len(sections) > MAX_SUPPORTING_SECTIONS + 1``
    # and switch to ``fallback_shell``.
    if len(sections) > MAX_SUPPORTING_SECTIONS + 1:
        sections = sections[: MAX_SUPPORTING_SECTIONS + 1]
        # ``confidence`` MUST stay last when present, so the
        # truncation keeps it if it was originally present.
        if contradiction_severity == "high" and "confidence" not in sections:
            sections.append("confidence")

    return tuple(sections)


def exceeds_max_sections(
    sections: tuple[str, ...] | list[str],
    *,
    max_supports: int = MAX_SUPPORTING_SECTIONS,
) -> bool:
    """True iff the caller should fall back to ``fallback_shell``.

    Counts ``direct_answer`` separately — the UX contract is
    "max 3 supports after the hero".
    """
    if not sections:
        return False
    supports = [s for s in sections if s != "direct_answer"]
    return len(supports) > max_supports


def select_shell(
    answer_requirements: AnswerRequirements | None,
    *,
    sections: tuple[str, ...] | list[str],
    fallback_shell: str = "expanded",
) -> str:
    """Pick the composer shell literal.

    Returns ``fallback_shell`` when the section count exceeds
    the UX contract; otherwise returns the shell that matches
    the most prominent answer-mode directive.
    """
    if exceeds_max_sections(sections):
        return fallback_shell
    if answer_requirements is None:
        return "general_knowledge"
    if answer_requirements.needs_scenario:
        return "scenario"
    if answer_requirements.needs_comparison:
        return "comparison"
    if answer_requirements.needs_external_information:
        return "external"
    if answer_requirements.needs_calculation:
        return "calculation"
    if answer_requirements.needs_business_evidence:
        return "business_analysis"
    return "general_knowledge"