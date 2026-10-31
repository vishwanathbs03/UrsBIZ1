"""AdaptiveAnswer — SPRINT AI-1 Stage 8 + AI-12 Universal Reasoning.

The legacy assistant renders the same 10-section consultant
framing for every prompt. AI-1 keeps that as the default
(``"expanded"`` shell) but adds three more shells:

  * ``"executive"`` — short, 3-section shell for simple
    questions. Saves tokens on trivial lookups.
  * ``"scenario"`` — Assumptions / Estimated outcome / Risks /
    What would change the result. Used for "what if" prompts.
  * ``"missing_info"`` — What I can determine / What is
    missing / Why it matters / What to provide next. Used when
    the context is missing fields the answer requires.

SPRINT AI-12 grows the catalogue to eight shells:

  * ``"comparison"`` — side-by-side table shell for
    "compare X vs Y" prompts.
  * ``"scheme"`` — Schemes / Eligibility / How to apply /
    Documents shell for government-scheme prompts.
  * ``"external"`` — Source / Claim / Confidence / Source
    authority shell for external-information prompts.
  * ``"table_checklist"`` — flat table + checklist shell for
    "give me a list of X" prompts.

The composer does NOT overwrite the LLM's prose. It returns
metadata only (``AdaptiveAnswer``) — the service uses it to
stamp ``GenerationMeta.possible_answer_structure`` and to
enrich the audit trail.

Backward compatibility
-----------------------

The composer is invoked AFTER the LLM has produced its
response. The LLM prose stays unchanged. Only the metadata
envelope changes. The fallback path (no LLM) returns a
default :class:`AdaptiveAnswer` with
``mode_used="expanded"`` so the deterministic path's audit
trail is also uniformly tagged. The AI-12 shells are
additive — every legacy ``possible_answer_structure``
value (``"executive"``, ``"expanded"``, ``"scenario"``,
``"missing_info"``) keeps its existing rendering.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


# SPRINT AI-12 — expanded AnswerShell. Legacy 4 values stay
# in place; ``"general_knowledge"`` and ``"business_analysis"``
# are also valid because the question_understanding's
# ``answer_mode`` carries those literals for capability-aware
# rendering. Eight literals total.
AnswerShell = Literal[
    "executive",
    "expanded",
    "scenario",
    "missing_info",
    "comparison",
    "scheme",
    "external",
    "general_knowledge",
    "business_analysis",
    "calculation",
    "table_checklist",
]


@dataclass(frozen=True)
class AdaptiveAnswer:
    """The structured shell the answer composer picks.

    Attributes
    ----------
    mode_used
        One of the :data:`AnswerShell` literals. Records which
        shell the composer selected for the audit trail.
    sections
        Ordered list of section titles the chosen shell uses.
        The renderer surfaces these in the response envelope.
    executive_summary
        A one-paragraph summary derived from the parsed
        response (the legacy ``ExecutiveSummary.text`` for the
        grounded path, the first paragraph of the raw body for
        the open path). Empty when no LLM response was
        available.
    key_findings
        Top-N bullets the composer extracted from the parsed
        response. Empty when the parsed response has none.
    recommendations
        Recommendation titles the composer surfaced. Empty
        when none.
    assumptions
        Assumptions declared by the composer shell. Three max.
    limitations
        Limitations declared by the composer shell. Three max.
    """

    mode_used: AnswerShell = "expanded"
    sections: tuple[str, ...] = field(default_factory=tuple)
    executive_summary: str = ""
    key_findings: tuple[str, ...] = field(default_factory=tuple)
    recommendations: tuple[str, ...] = field(default_factory=tuple)
    assumptions: tuple[str, ...] = field(default_factory=tuple)
    limitations: tuple[str, ...] = field(default_factory=tuple)


# --------------------------------------------------------------------------- #
# Shell templates
# --------------------------------------------------------------------------- #


_SHELL_EXECUTIVE: tuple[str, ...] = (
    "1. EXECUTIVE SUMMARY",
    "2. KEY FINDINGS",
    "3. NEXT ACTION",
)

_SHELL_EXPANDED: tuple[str, ...] = (
    "1. EXECUTIVE SUMMARY",
    "2. KEY FINDINGS",
    "3. GROWTH STRATEGY",
    "4. QUARTER-WISE ROADMAP",
    "5. FUNDING & PROJECTIONS",
    "6. KEY RISKS",
    "7. SCHEMES",
    "8. KPIs TO TRACK",
    "9. NEXT ACTIONS",
    "10. ASSUMPTIONS / LIMITATIONS",
)

_SHELL_SCENARIO: tuple[str, ...] = (
    "1. SCENARIO ASSUMPTIONS",
    "2. ESTIMATED OUTCOME",
    "3. KEY RISKS UNDER THIS SCENARIO",
    "4. WHAT WOULD CHANGE THE RESULT",
)

_SHELL_MISSING_INFO: tuple[str, ...] = (
    "1. WHAT I CAN DETERMINE",
    "2. WHAT IS MISSING",
    "3. WHY IT MATTERS",
    "4. WHAT TO PROVIDE NEXT",
)

# SPRINT AI-12 — 4 new shells + 3 capability-mode aliases.
# The aliases reuse the existing 4 shells' section lists so the
# renderer doesn't need new branches — capability-aware
# rendering is a frontend follow-up.

_SHELL_COMPARISON: tuple[str, ...] = (
    "1. COMPARISON OVERVIEW",
    "2. SIDE-BY-SIDE TABLE",
    "3. KEY DIFFERENCES",
    "4. RECOMMENDATION",
)

_SHELL_SCHEME: tuple[str, ...] = (
    "1. ELIGIBLE SCHEMES",
    "2. ELIGIBILITY CRITERIA",
    "3. HOW TO APPLY",
    "4. REQUIRED DOCUMENTS",
    "5. NEXT STEPS",
)

_SHELL_EXTERNAL: tuple[str, ...] = (
    "1. SOURCE",
    "2. CLAIM",
    "3. CONFIDENCE",
    "4. SOURCE AUTHORITY",
    "5. LIMITATIONS",
)

_SHELL_TABLE_CHECKLIST: tuple[str, ...] = (
    "1. TABLE",
    "2. CHECKLIST",
    "3. NEXT STEPS",
)

# Aliases — capability answer_mode → legacy shell. The
# renderer doesn't need to know the difference; the composer
# just selects the right shell for the chosen mode.
_SHELL_GENERAL_KNOWLEDGE: tuple[str, ...] = _SHELL_EXECUTIVE
_SHELL_BUSINESS_ANALYSIS: tuple[str, ...] = _SHELL_EXPANDED
_SHELL_CALCULATION: tuple[str, ...] = _SHELL_EXPANDED


# --------------------------------------------------------------------------- #
# Composer
# --------------------------------------------------------------------------- #


def compose_adaptive_answer(
    *,
    parsed: Any,
    question_understanding: Any,
    reasoning_plan: Any,
    tool_results: tuple[Any, ...] = (),
    context: Any = None,
) -> AdaptiveAnswer:
    """Return an :class:`AdaptiveAnswer` describing the chosen shell.

    Parameters
    ----------
    parsed
        The parsed response (e.g. ``GroundedResponse`` for the
        grounded path, ``OpenResponse`` for the open path).
        May be ``None`` when the deterministic fallback
        produced the body — the composer then uses the plan's
        ``possible_answer_structure`` field.
    question_understanding
        The :class:`QuestionUnderstanding` from Stage 1.
    reasoning_plan
        The :class:`ReasoningPlan` from Stage 4. The plan's
        :attr:`possible_answer_structure` field is the
        primary driver of the shell choice.
    tool_results
        The :class:`ToolResult` tuple from Stage 5.
        Currently informational only — the composer never
        emits a tool-specific shell.
    context
        The :class:`AssistantContext`. Informational only.
    """
    # 1. Pick the shell.
    shell = _pick_shell(parsed, question_understanding, reasoning_plan)

    # 2. Map the shell to its section list.
    sections = _SECTIONS_BY_SHELL[shell]

    # 3. Pull findings / recommendations from the parsed response.
    executive_summary, key_findings, recommendations = _extract_summary(
        parsed
    )

    # 4. Add shell-specific assumptions / limitations.
    assumptions, limitations = _assumptions_for_shell(
        shell, question_understanding, reasoning_plan, tool_results
    )

    return AdaptiveAnswer(
        mode_used=shell,
        sections=sections,
        executive_summary=executive_summary,
        key_findings=key_findings,
        recommendations=recommendations,
        assumptions=assumptions,
        limitations=limitations,
    )


_SECTIONS_BY_SHELL: dict[str, tuple[str, ...]] = {
    "executive": _SHELL_EXECUTIVE,
    "expanded": _SHELL_EXPANDED,
    "scenario": _SHELL_SCENARIO,
    "missing_info": _SHELL_MISSING_INFO,
    # SPRINT AI-12 — 4 new shells.
    "comparison": _SHELL_COMPARISON,
    "scheme": _SHELL_SCHEME,
    "external": _SHELL_EXTERNAL,
    "table_checklist": _SHELL_TABLE_CHECKLIST,
    # Aliases — capability answer_mode → legacy shell.
    "general_knowledge": _SHELL_GENERAL_KNOWLEDGE,
    "business_analysis": _SHELL_BUSINESS_ANALYSIS,
    "calculation": _SHELL_CALCULATION,
}


def _pick_shell(
    parsed: Any,
    question_understanding: Any,
    reasoning_plan: Any,
) -> AnswerShell:
    """Pick the answer shell.

    Priority order:

      1. Plan's ``possible_answer_structure`` (when set) wins.
      2. Understanding's ``answer_mode`` (AI-12) — the
         capability-aware answer rendering hint.
      3. Understanding's ``unknowns`` (when non-empty) flips
         to ``"missing_info"``.
      4. Understanding's ``complexity``:

         * ``"simple"`` → ``"executive"``
         * ``"scenario"`` → ``"scenario"``
         * ``"moderate"`` / ``"strategic"`` → ``"expanded"``

      5. Default ``"expanded"``.
    """
    plan_value = getattr(reasoning_plan, "possible_answer_structure", "") or ""
    if plan_value in _SECTIONS_BY_SHELL:
        return plan_value  # type: ignore[return-value]

    # SPRINT AI-12 — fall back to the answer_mode before the
    # complexity walk. The QU's answer_mode carries the
    # capability-aware shape signal (e.g. ``"scenario"`` for
    # "what if" prompts, ``"comparison"`` for "compare X vs Y").
    answer_mode = (
        getattr(question_understanding, "answer_mode", "") or ""
    )
    if answer_mode in _SECTIONS_BY_SHELL:
        return answer_mode  # type: ignore[return-value]

    unknowns = getattr(question_understanding, "unknowns", ()) or ()
    if unknowns:
        return "missing_info"

    complexity = getattr(question_understanding, "complexity", "moderate")
    if complexity == "scenario":
        return "scenario"
    if complexity == "simple":
        return "executive"
    return "expanded"


def _extract_summary(parsed: Any) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
    """Pull summary text + findings + recommendations from ``parsed``."""
    if parsed is None:
        return "", (), ()
    # ``GroundedResponse`` has a string executive_summary.
    if isinstance(getattr(parsed, "executive_summary", None), str):
        exec_sum = parsed.executive_summary
    else:
        exec_sum = (
            getattr(getattr(parsed, "executive_summary", None), "text", "") or ""
        )
    findings: list[str] = []
    for kf in getattr(parsed, "key_findings", ()) or ():
        if isinstance(kf, str):
            findings.append(kf)
        else:
            text = (
                getattr(kf, "statement", "") or getattr(kf, "text", "") or ""
            )
            if text:
                findings.append(text)
    recs: list[str] = []
    for rec in getattr(parsed, "recommendations", ()) or ():
        if isinstance(rec, str):
            recs.append(rec)
        else:
            title = (
                getattr(rec, "title", "") or getattr(rec, "action", "") or ""
            )
            if title:
                recs.append(title)
    return exec_sum, tuple(findings[:5]), tuple(recs[:3])


def _assumptions_for_shell(
    shell: AnswerShell,
    question_understanding: Any,
    reasoning_plan: Any,
    tool_results: tuple[Any, ...],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return (assumptions, limitations) for the chosen shell."""
    if shell == "scenario":
        return (
            (
                "Scenario outputs are estimates, not predictions.",
                "Confidence reflects data completeness, not outcome certainty.",
            ),
            (
                "Sensitivities to cost / demand changes may be larger than shown.",
            ),
        )
    if shell == "missing_info":
        unknowns = getattr(question_understanding, "unknowns", ()) or ()
        limitations = tuple(
            f"Missing: {u}" for u in unknowns[:3]
        ) or ("Add profile data to unlock a fuller answer.",)
        return (
            (
                "Answer is partial because the context is missing fields.",
            ),
            limitations,
        )
    if shell == "executive":
        return (
            ("Answer is a short summary; ask a follow-up for depth.",),
            (),
        )
    # expanded (default)
    return (
        (
            "Every fact in the response traces back to an evidence registry entry.",
        ),
        (
            "Detailed numbers depend on the freshness of your business profile.",
        ),
    )


# --------------------------------------------------------------------------- #
# SPRINT AI-14 — Dynamic Answer Composer
# --------------------------------------------------------------------------- #
#
# ``compose_dynamic`` is the AI-14 thin shim layer the service.py
# hookups call when ``AnswerRequirements`` are available. It keeps
# the existing ``compose_adaptive_answer`` behaviour untouched (legacy
# callers keep working) and reuses the 11-shell inventory
# (``executive`` / ``expanded`` / ``scenario`` / ``comparison`` /
# etc.) as layout strategies keyed on ``AnswerRequirements.needs_*``
# flags. The actual section-order selection is delegated to
# :func:`app.services.ai.reasoning.dynamic_section_selector
# .select_sections` so the UX contract — hero direct-answer + max
# 3 supports + fallback to ``expanded`` when exceeded — lives in
# one place.
# --------------------------------------------------------------------------- #


def compose_dynamic(
    *,
    parsed: Any,
    question_understanding: Any,
    reasoning_plan: Any,
    answer_requirements: Any | None = None,
    contradiction_severity: str = "none",
    unsupported_claim_count: int = 0,
    tool_results: tuple = (),
    context: Any | None = None,
) -> tuple[str, tuple[str, ...]]:
    """SPRINT AI-14 — return ``(shell, sections)`` for the renderer.

    Behaviour
    ---------

    * ``shell`` is the legacy ``AdaptiveAnswer`` shell literal
      (``executive`` / ``expanded`` / ``scenario`` / ``comparison``
      / etc.). Selected by :func:`select_shell` with the
      ``AnswerRequirements`` flags as input; falls back to
      ``expanded`` when the section list exceeds ``MAX_SUPPORTING_SECTIONS``.
    * ``sections`` is the ordered section list
      (:func:`select_sections`) the composer + renderer should
      iterate. ``direct_answer`` is always first (hero conclusion).

    Legacy fallback
    ---------------

    When ``answer_requirements`` is ``None`` (no engine run,
    or legacy caller), this function delegates to
    :func:`compose_adaptive_answer` and returns its shell +
    sections. The existing ``compose_adaptive_answer`` body is
    NOT rewritten — only reused through this single seam.
    """
    try:
        from app.services.ai.reasoning.dynamic_section_selector import (
            select_sections,
            select_shell,
        )
    except Exception:  # pragma: no cover — defensive
        select_sections = None  # type: ignore[assignment]
        select_shell = None  # type: ignore[assignment]

    if select_sections is None or select_shell is None or answer_requirements is None:
        # Legacy path — reuse the AI-12 composer. We can't read
        # ``AdaptiveAnswer.sections`` without constructing one,
        # so just call ``compose_adaptive_answer`` and use its
        # ``shell`` literal; the renderer falls back to the
        # legacy "expanded" layout.
        legacy = compose_adaptive_answer(
            parsed=parsed,
            question_understanding=question_understanding,
            reasoning_plan=reasoning_plan,
            tool_results=tool_results,
            context=context,
        )
        try:
            sections = tuple(legacy.sections or ())
        except Exception:
            sections = ()
        return legacy.shell, sections

    sections = select_sections(
        answer_requirements,
        contradiction_severity=contradiction_severity,
        unsupported_claim_count=unsupported_claim_count,
    )
    shell = select_shell(
        answer_requirements,
        sections=sections,
        fallback_shell="expanded",
    )
    return shell, sections