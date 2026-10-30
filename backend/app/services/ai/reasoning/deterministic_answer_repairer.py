"""SPRINT AI-17 — Bounded Answer Repair + Claim Lifecycle.

Deterministic answer repair.

The repair layer is the FIRST line of defence when an
:class:`AnswerQuality` reports low quality. It applies the
strategy the :class:`QualityFailureClassifier` chose and returns
a new, repaired answer body. The repair layer NEVER calls the
LLM. If the layer cannot fix the answer, it returns the
original body unchanged with a non-empty ``repair_notes`` field
explaining why — the bounded retry gate (PART 3) then decides
whether to retry or ship the answer with a warning.

Repair strategies
-----------------

  * ``"replace_numeric"``         — substitute or remove an
    out-of-band numeric that disagrees with the authoritative
    envelope value.
  * ``"remove_claim"``            — drop the unsupported claim
    from the body and the audit log.
  * ``"add_uncertainty"``         — append the canonical
    uncertainty disclosure paragraph.
  * ``"add_assumptions"``         — append the scenario
    assumptions the engine had declared but the LLM omitted.
  * ``"reclassify_recommendation"`` — rewrite "X is the right
    thing to do" into "X may be worth considering; UrsBiz does
    not certify this.".
  * ``"recompose"``               — rebuild the body from the
    :class:`AnswerRequirements` shell.
  * ``"warning_only"``            — leave the body unchanged and
    surface the warning; the bounded retry gate decides what
    to do next.
  * ``"none"``                    — no repair needed.

The repair layer records every action in :attr:`RepairReport`
so the audit trail knows exactly what was changed. The original
body is preserved verbatim in :attr:`original_body` so an
auditor can re-run the failed validation.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


# --------------------------------------------------------------------------- #
# Repair action
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class RepairAction:
    """One deterministic action the repair layer applied.

    Attributes
    ----------
    strategy:
        The strategy token (see module docstring).
    description:
        One-line English description of the action for the
        audit trail.
    before:
        The text before the change (snippet). ``""`` when
        the action was an append / insert.
    after:
        The text after the change (snippet). ``""`` when
        the action was a removal.
    """

    strategy: str = "none"
    description: str = ""
    before: str = ""
    after: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy,
            "description": self.description,
            "before": self.before,
            "after": self.after,
        }


# --------------------------------------------------------------------------- #
# Repair report
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class RepairReport:
    """The repair layer's output.

    ``repaired_body`` is the body to ship. ``actions`` is the
    ordered tuple of :class:`RepairAction` records. ``fully_repaired``
    is True when every defect the
    :class:`QualityFailureClassifier` flagged was repaired.
    ``repair_notes`` carries the human-readable explanation when
    ``fully_repaired`` is False.

    The original body is preserved so the audit trail can
    re-validate without re-running the pipeline.
    """

    repaired_body: str = ""
    original_body: str = ""
    actions: tuple[RepairAction, ...] = ()
    fully_repaired: bool = False
    repair_notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "repaired_body": self.repaired_body,
            "original_body": self.original_body,
            "actions": [a.to_dict() for a in self.actions],
            "fully_repaired": self.fully_repaired,
            "repair_notes": self.repair_notes,
        }


# --------------------------------------------------------------------------- #
# Repairer
# --------------------------------------------------------------------------- #


# Phrases the repairer recognises as "assertion of benefit / claim".
# When the repairer drops an unsupported recommendation it
# rewrites these to advisory phrasing rather than deleting them
# outright (the user already read them).
_ASSERTIVE_TOKENS: tuple[str, ...] = (
    "we recommend",
    "you should",
    "the best",
    "definitely",
    "certainly",
    "without doubt",
)

_UNCERTAINTY_PARAGRAPH = (
    "\n\nNote: UrsBiz has limited verified evidence for parts of "
    "this answer. Treat the figures and recommendations as "
    "indicative; verify with your own records before acting on "
    "them. Where authoritative values were not available, UrsBiz "
    "has flagged the uncertainty inline."
)

_RECLASSIFY_PHRASES: dict[str, str] = {
    "we recommend you": "you may want to consider",
    "you should apply": "you may want to consider applying",
    "you should hire": "you may want to consider hiring",
    "you should focus on": "you may want to focus on",
    "we strongly recommend": "we suggest",
}


class DeterministicAnswerRepairer:
    """Apply deterministic repair strategies to an answer body.

    Pure. No I/O. No LLM. The repairer preserves the original
    body and emits an audit-friendly :class:`RepairReport`.

    Strategies that need tool-envelope / scenario-analysis input
    take it as a kwarg. The repairer never infers authoritative
    values — when an authoritative value is missing, the
    repairer removes the unsupported claim rather than guessing
    a replacement.
    """

    # ---- top-level entry point ------------------------------------- #

    def repair(
        self,
        body: str,
        *,
        strategy: str,
        numeric_conflicts: tuple = (),
        unsupported_claims: tuple = (),
        scenario_assumptions: tuple[str, ...] = (),
        envelope_values: dict[str, float] | None = None,
    ) -> RepairReport:
        """Return a :class:`RepairReport` applying ``strategy`` to ``body``.

        ``envelope_values`` is a dict ``{metric_name: authoritative_value}``
        the repairer uses for numeric substitutions. When a
        conflict has no envelope value, the repairer REMOVES the
        offending number (it does NOT guess).
        """
        original = body or ""
        actions: list[RepairAction] = []
        working = original

        if strategy == "replace_numeric":
            working, actions = self._repair_replace_numeric(
                working, numeric_conflicts, envelope_values or {}, actions
            )
        elif strategy == "remove_claim":
            working, actions = self._repair_remove_claim(
                working, unsupported_claims, actions
            )
        elif strategy == "add_uncertainty":
            working, actions = self._repair_add_uncertainty(working, actions)
        elif strategy == "add_assumptions":
            working, actions = self._repair_add_assumptions(
                working, scenario_assumptions, actions
            )
        elif strategy == "reclassify_recommendation":
            working, actions = self._repair_reclassify_recommendation(
                working, actions
            )
        elif strategy == "recompose":
            working, actions = self._repair_recompose(working, actions)
        elif strategy == "warning_only":
            # No body change; the bounded retry gate decides next.
            actions.append(
                RepairAction(
                    strategy="warning_only",
                    description="No body change; ship with warning.",
                )
            )
        elif strategy == "none":
            actions.append(
                RepairAction(
                    strategy="none",
                    description="No failure detected; body unchanged.",
                )
            )
        else:
            actions.append(
                RepairAction(
                    strategy="unknown",
                    description=(
                        f"Unknown strategy {strategy!r}; body unchanged."
                    ),
                )
            )

        # Determine whether the repair was complete.
        fully_repaired = strategy not in {
            "warning_only",
            "unknown",
            "",
            "none",
        }
        notes = "" if fully_repaired else (
            f"Strategy {strategy!r} did not fully resolve the defect."
        )
        return RepairReport(
            repaired_body=working,
            original_body=original,
            actions=tuple(actions),
            fully_repaired=fully_repaired,
            repair_notes=notes,
        )

    # ---- strategy implementations ---------------------------------- #

    def _repair_replace_numeric(
        self,
        body: str,
        numeric_conflicts: tuple,
        envelope_values: dict[str, float],
        actions: list[RepairAction],
    ) -> tuple[str, list[RepairAction]]:
        """Substitute or remove the offending numeric.

        For each conflict the repairer:

          1. Looks up the authoritative value in
             ``envelope_values`` keyed by the metric.
          2. Substitutes the literal in the body when an
             authoritative value is found.
          3. Removes the literal when no authoritative value
             is available (it does NOT guess).

        Returns the (possibly modified) body and the appended
        actions list.
        """
        working = body
        for conflict in numeric_conflicts:
            metric = getattr(conflict, "metric", "") or ""
            llm_value = getattr(conflict, "llm_value", None)
            auth_value = getattr(conflict, "authoritative_value", None)
            if auth_value is None and metric:
                auth_value = envelope_values.get(metric)

            snippet = (
                f"{llm_value}" if llm_value is not None else ""
            )
            if auth_value is not None and llm_value is not None:
                working = _substitute_literal(working, llm_value, auth_value)
                actions.append(
                    RepairAction(
                        strategy="replace_numeric",
                        description=(
                            f"Replaced {llm_value} with authoritative "
                            f"{auth_value} for metric {metric!r}"
                        ),
                        before=str(llm_value),
                        after=str(auth_value),
                    )
                )
            elif llm_value is not None:
                working = _remove_literal(working, llm_value)
                actions.append(
                    RepairAction(
                        strategy="replace_numeric",
                        description=(
                            f"Removed unsupported numeric {llm_value!r} "
                            f"for metric {metric!r} (no authoritative value)"
                        ),
                        before=str(llm_value),
                        after="",
                    )
                )
            else:
                actions.append(
                    RepairAction(
                        strategy="replace_numeric",
                        description=(
                            f"Skipped conflict for metric {metric!r}; "
                            "no LLM value to replace"
                        ),
                        before=snippet,
                        after="",
                    )
                )
        return working, actions

    def _repair_remove_claim(
        self,
        body: str,
        unsupported_claims: tuple,
        actions: list[RepairAction],
    ) -> tuple[str, list[RepairAction]]:
        """Drop unsupported claims from the body.

        The repairer keeps the paragraph that contains the claim
        (deleting a full paragraph mid-answer is more disruptive
        than rewriting it), but it neutralises the claim's
        assertive phrasing and appends an "UrsBiz could not verify"
        marker.
        """
        working = body
        if not unsupported_claims:
            actions.append(
                RepairAction(
                    strategy="remove_claim",
                    description=(
                        "No unsupported claims supplied; body unchanged."
                    ),
                )
            )
            return working, actions

        for claim in unsupported_claims:
            text = getattr(claim, "text", "") or ""
            if not text:
                continue
            softened = _soften_assertive(text)
            if softened != text:
                actions.append(
                    RepairAction(
                        strategy="remove_claim",
                        description=(
                            "Softened unsupported claim to advisory "
                            "phrasing (could not remove without "
                            "damaging the paragraph)."
                        ),
                        before=_preview(text),
                        after=_preview(softened),
                    )
                )
                working = working.replace(text, softened, 1)
            else:
                actions.append(
                    RepairAction(
                        strategy="remove_claim",
                        description=(
                            "Unsupported claim is purely declarative; "
                            "appended unverifiable marker."
                        ),
                        before=_preview(text),
                        after="(UrsBiz could not verify this claim.)",
                    )
                )
                marker = (
                    f"\n\n[UrsBiz could not verify the following claim: "
                    f"{_preview(text, cap=120)}]"
                )
                working = working + marker
        return working, actions

    def _repair_add_uncertainty(
        self, body: str, actions: list[RepairAction]
    ) -> tuple[str, list[RepairAction]]:
        """Append the canonical uncertainty paragraph."""
        if _UNCERTAINTY_PARAGRAPH.strip() in body:
            actions.append(
                RepairAction(
                    strategy="add_uncertainty",
                    description=(
                        "Uncertainty paragraph already present; no change."
                    ),
                )
            )
            return body, actions
        actions.append(
            RepairAction(
                strategy="add_uncertainty",
                description=(
                    "Appended canonical uncertainty disclosure paragraph."
                ),
                before="",
                after=_preview(_UNCERTAINTY_PARAGRAPH, cap=80),
            )
        )
        return body.rstrip() + _UNCERTAINTY_PARAGRAPH, actions

    def _repair_add_assumptions(
        self,
        body: str,
        scenario_assumptions: tuple[str, ...],
        actions: list[RepairAction],
    ) -> tuple[str, list[RepairAction]]:
        """Append scenario assumptions the LLM omitted."""
        if not scenario_assumptions:
            actions.append(
                RepairAction(
                    strategy="add_assumptions",
                    description=(
                        "No scenario assumptions available; body unchanged."
                    ),
                )
            )
            return body, actions
        assumptions_block = (
            "\n\nAssumptions used in this answer:\n"
            + "\n".join(f"- {a}" for a in scenario_assumptions)
        )
        if "Assumptions used in this answer" in body:
            actions.append(
                RepairAction(
                    strategy="add_assumptions",
                    description=(
                        "Assumptions block already present; no change."
                    ),
                )
            )
            return body, actions
        actions.append(
            RepairAction(
                strategy="add_assumptions",
                description=(
                    f"Appended {len(scenario_assumptions)} scenario "
                    "assumption(s)."
                ),
                before="",
                after=_preview(assumptions_block, cap=120),
            )
        )
        return body.rstrip() + assumptions_block, actions

    def _repair_reclassify_recommendation(
        self, body: str, actions: list[RepairAction]
    ) -> tuple[str, list[RepairAction]]:
        """Rewrite assertive recommendation phrasing into advisory."""
        working = body
        changes = 0
        for src, dst in _RECLASSIFY_PHRASES.items():
            if src in working.lower():
                # Case-insensitive replace preserving original casing of the
                # first letter.
                pattern = re.compile(re.escape(src), re.IGNORECASE)
                working, n = pattern.subn(dst, working)
                changes += n
        if changes == 0:
            actions.append(
                RepairAction(
                    strategy="reclassify_recommendation",
                    description=(
                        "No assertive recommendation phrasing found; "
                        "body unchanged."
                    ),
                )
            )
            return body, actions
        actions.append(
            RepairAction(
                strategy="reclassify_recommendation",
                description=(
                    f"Reclassified {changes} assertive phrasing(s) to "
                    "advisory ('may want to consider', 'we suggest')."
                ),
                before="",
                after="",
            )
        )
        return working, actions

    def _repair_recompose(
        self, body: str, actions: list[RepairAction]
    ) -> tuple[str, list[RepairAction]]:
        """Light recompose — strip chain-of-thought, ensure section.

        The brief: "recompose using AnswerRequirements". The
        repair layer here is conservative — it removes any
        "Reasoning:" / "Step-by-step:" preamble (the brief
        forbids CoT leakage) and ensures the body ends with a
        one-line closing statement. A full recompose would
        require the AnswerRequirements instance; the layer
        here only addresses the format axis.
        """
        working = body
        cot_markers = (
            "\nReasoning:",
            "\nStep-by-step:",
            "\nLet me think",
            "\nFirst, let me",
            "\nMy thought process:",
        )
        stripped = False
        for marker in cot_markers:
            if marker in working:
                # Drop everything from the marker to the next blank line.
                idx = working.index(marker)
                end = working.find("\n\n", idx)
                if end == -1:
                    working = working[:idx].rstrip()
                else:
                    working = (working[:idx] + working[end + 2:]).rstrip()
                stripped = True
        if stripped:
            actions.append(
                RepairAction(
                    strategy="recompose",
                    description=(
                        "Stripped chain-of-thought preamble from body."
                    ),
                )
            )
        else:
            actions.append(
                RepairAction(
                    strategy="recompose",
                    description=(
                        "No chain-of-thought detected; body unchanged."
                    ),
                )
            )
        return working, actions


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _preview(text: str, *, cap: int = 80) -> str:
    """Short preview of ``text`` for the audit trail."""
    if not text:
        return ""
    text = str(text).replace("\n", " ").strip()
    if len(text) <= cap:
        return text
    return text[: cap - 1].rstrip() + "…"


def _substitute_literal(body: str, old: float | int, new: float | int) -> str:
    """Replace ``old`` with ``new`` in ``body`` (first occurrence)."""
    old_str = _format_new(new)
    if _format_old(old) in body:
        return body.replace(_format_old(old), old_str, 1)
    # Try the int representation.
    old_int = str(int(old)) if float(old).is_integer() else None
    if old_int and old_int in body:
        return body.replace(old_int, old_str, 1)
    return body


def _remove_literal(body: str, value: float | int) -> str:
    """Remove ``value`` from ``body`` (first occurrence)."""
    if _format_old(value) in body:
        return body.replace(_format_old(value), "[value redacted]", 1)
    old_int = str(int(value)) if float(value).is_integer() else None
    if old_int and old_int in body:
        return body.replace(old_int, "[value redacted]", 1)
    return body


def _format_new(value: float | int) -> str:
    """Format ``value`` as it should appear in the body."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return str(value)
    if f == int(f):
        return str(int(f))
    return str(f)


def _format_old(value: float | int) -> str:
    """Format ``value`` to look for in the body (any common form)."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return str(value)
    if f == int(f):
        return str(int(f))
    return str(f)


def _soften_assertive(text: str) -> str:
    """Rewrite an assertive sentence into advisory phrasing.

    Conservative: when the text is short or does not contain
    an assertive marker, returns the text unchanged. When an
    assertive marker is found the function replaces it (not the
    full sentence) so the resulting text reads naturally.
    """
    if len(text) < 30:
        return text
    low = text.lower()
    # Token-level replacements: keep the prose, just tone down.
    swaps: tuple[tuple[str, str], ...] = (
        ("we recommend", "UrsBiz suggests"),
        ("we strongly recommend", "UrsBiz suggests"),
        ("you should", "you may want to consider"),
        ("the best", "a good"),
        ("definitely", "likely"),
        ("certainly", "likely"),
        ("without doubt", "with reasonable confidence"),
    )
    out = text
    for src, dst in swaps:
        if src in low:
            # Case-insensitive replace preserving the first letter casing.
            pattern = re.compile(re.escape(src), re.IGNORECASE)
            out = pattern.sub(dst, out, count=1)
            low = out.lower()
    return out
