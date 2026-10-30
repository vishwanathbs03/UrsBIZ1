"""SPRINT AI-18 — Universal AI Evaluation Harness.

Follow-up conversation scripts.

The brief (PART 2) requires multi-turn evaluation. Each
script is a deterministic tuple of (user, expected_asserts)
turns; the runner feeds the user turns into the production
pipeline one at a time and validates the assistant reply
against the expected asserts after each turn.

A script asserts:

  * context retention (the assistant remembered the prior turn)
  * business-evidence reuse (later turns cite the registry)
  * numeric consistency (the gap-to-target number from turn 2
    is reused in turn 3)
  * graceful hand-off (turn 3 ends with an actionable answer)

Scripts are pure data — no LLM access. The runner is the only
thing that touches the pipeline.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# --------------------------------------------------------------------------- #
# Turn assertion dataclass
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class TurnAssertion:
    """One expected assertion on the assistant's reply.

    The runner evaluates each predicate in order. A failed
    predicate fails the entire script (the runner reports the
    case ID + the failing predicate name).

    Supported predicates
    --------------------
    * ``"body_min_chars"`` — minimum body length
    * ``"body_must_contain_any"`` — at least one of these
      substrings must appear
    * ``"body_must_contain_all"`` — every substring must appear
    * ``"body_must_not_contain"`` — no forbidden substring may
      appear
    * ``"context_retained"`` — the body must contain evidence
      from at least one prior turn (the runner inserts the
      prior turn's body into the regex)
    * ``"evidence_min_count"`` — minimum evidence refs
    * ``"trust_min_score"`` — minimum trust band (0..1)
    """

    body_min_chars: int = 0
    body_must_contain_any: tuple[str, ...] = ()
    body_must_contain_all: tuple[str, ...] = ()
    body_must_not_contain: tuple[str, ...] = ()
    context_retained: bool = False
    evidence_min_count: int = 0
    trust_min_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "body_min_chars": int(self.body_min_chars),
            "body_must_contain_any": list(self.body_must_contain_any),
            "body_must_contain_all": list(self.body_must_contain_all),
            "body_must_not_contain": list(self.body_must_not_contain),
            "context_retained": bool(self.context_retained),
            "evidence_min_count": int(self.evidence_min_count),
            "trust_min_score": float(self.trust_min_score),
        }


# --------------------------------------------------------------------------- #
# Script dataclass
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ScriptTurn:
    """One (user message, expected assertion) pair."""

    user: str
    assertion: TurnAssertion = field(default_factory=TurnAssertion)

    def to_dict(self) -> dict[str, Any]:
        return {"user": self.user, "assertion": self.assertion.to_dict()}


@dataclass(frozen=True)
class FollowUpScript:
    """One multi-turn evaluation script.

    Attributes
    ----------
    script_id:
        Stable identifier (e.g. ``"followup_revenue_gap_action"``).
    title:
        Human-readable title.
    turns:
        Tuple of :class:`ScriptTurn` — the runner feeds them in
        order.
    notes:
        One-line English note about what the script tests.
    """

    script_id: str
    title: str
    turns: tuple[ScriptTurn, ...]
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "script_id": self.script_id,
            "title": self.title,
            "turns": [t.to_dict() for t in self.turns],
            "notes": self.notes,
        }


# --------------------------------------------------------------------------- #
# Scripts
# --------------------------------------------------------------------------- #


# Script 1 — the brief's flagship flow: revenue → gap → action.
FOLLOWUP_REVENUE_GAP_ACTION = FollowUpScript(
    script_id="followup_revenue_gap_action",
    title="Revenue → Gap → Action",
    notes="Brief-mandated flagship flow. Verifies context retention "
    "and business-evidence reuse.",
    turns=(
        ScriptTurn(
            user="What is our revenue?",
            assertion=TurnAssertion(
                body_min_chars=20,
                body_must_contain_any=("revenue", "₹"),
                evidence_min_count=1,
            ),
        ),
        ScriptTurn(
            user="How far are we from ₹3 Cr?",
            assertion=TurnAssertion(
                body_min_chars=30,
                body_must_contain_any=("₹", "crore", "Cr"),
                context_retained=True,
                evidence_min_count=1,
            ),
        ),
        ScriptTurn(
            user="What should we do first?",
            assertion=TurnAssertion(
                body_min_chars=40,
                body_must_contain_any=("recommend", "focus", "next"),
                context_retained=True,
                evidence_min_count=1,
            ),
        ),
    ),
)


# Script 2 — definition → apply-to-business.
FOLLOWUP_DEFINITION_APPLY = FollowUpScript(
    script_id="followup_definition_apply",
    title="Definition → Apply to Our Business",
    notes="General-knowledge follow-up that transitions into a "
    "business analysis.",
    turns=(
        ScriptTurn(
            user="What is working capital?",
            assertion=TurnAssertion(
                body_min_chars=40,
                body_must_contain_any=("working capital",),
                body_must_not_contain=("insufficient data", "could not verify"),
            ),
        ),
        ScriptTurn(
            user="How does that apply to our business?",
            assertion=TurnAssertion(
                body_min_chars=50,
                body_must_contain_any=("working capital",),
                context_retained=True,
                evidence_min_count=1,
            ),
        ),
        ScriptTurn(
            user="What's our biggest working-capital risk?",
            assertion=TurnAssertion(
                body_min_chars=50,
                body_must_contain_any=("working capital", "risk"),
                context_retained=True,
                evidence_min_count=1,
            ),
        ),
    ),
)


# Script 3 — scheme lookup → eligibility check.
FOLLOWUP_SCHEME_ELIGIBILITY = FollowUpScript(
    script_id="followup_scheme_eligibility",
    title="Scheme Lookup → Eligibility Check",
    notes="Government scheme flow with conservative eligibility "
    "language.",
    turns=(
        ScriptTurn(
            user="Are there any government schemes for working capital?",
            assertion=TurnAssertion(
                body_min_chars=30,
                evidence_min_count=1,
            ),
        ),
        ScriptTurn(
            user="Could we qualify for any of those?",
            assertion=TurnAssertion(
                body_min_chars=30,
                body_must_contain_any=(
                    "may", "could", "potential", "depends", "qualify",
                ),
                context_retained=True,
                evidence_min_count=1,
            ),
        ),
    ),
)


# Script 4 — operational diagnosis → action.
FOLLOWUP_DIAGNOSIS_ACTION = FollowUpScript(
    script_id="followup_diagnosis_action",
    title="Operational Diagnosis → Action",
    notes="Operational flow that ties diagnosis to recommendations.",
    turns=(
        ScriptTurn(
            user="Which process is our biggest bottleneck?",
            assertion=TurnAssertion(
                body_min_chars=30,
                evidence_min_count=1,
            ),
        ),
        ScriptTurn(
            user="How do we fix it?",
            assertion=TurnAssertion(
                body_min_chars=40,
                body_must_contain_any=("recommend", "step", "fix", "action"),
                context_retained=True,
                evidence_min_count=1,
            ),
        ),
    ),
)


# Script 5 — context retention across a long gap.
FOLLOWUP_LONG_CONTEXT = FollowUpScript(
    script_id="followup_long_context",
    title="Long Conversation Memory",
    notes="Five turns; the assistant must remember the gap-to-target "
    "from turn 2 when answering turn 5.",
    turns=(
        ScriptTurn(
            user="What is our current revenue?",
            assertion=TurnAssertion(body_min_chars=20, evidence_min_count=1),
        ),
        ScriptTurn(
            user="How much do we need to grow to reach ₹5 Cr?",
            assertion=TurnAssertion(
                body_min_chars=30,
                body_must_contain_any=("₹", "grow", "growth"),
                context_retained=True,
                evidence_min_count=1,
            ),
        ),
        ScriptTurn(
            user="What's our biggest risk?",
            assertion=TurnAssertion(body_min_chars=40, evidence_min_count=1),
        ),
        ScriptTurn(
            user="How long will the gap take to close at current burn?",
            assertion=TurnAssertion(
                body_min_chars=40,
                context_retained=True,
                evidence_min_count=1,
            ),
        ),
        ScriptTurn(
            user="Summarize everything you've told me about our growth gap.",
            assertion=TurnAssertion(
                body_min_chars=80,
                body_must_contain_any=("₹", "gap", "growth"),
                context_retained=True,
                evidence_min_count=1,
            ),
        ),
    ),
)


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #


ALL_SCRIPTS: tuple[FollowUpScript, ...] = (
    FOLLOWUP_REVENUE_GAP_ACTION,
    FOLLOWUP_DEFINITION_APPLY,
    FOLLOWUP_SCHEME_ELIGIBILITY,
    FOLLOWUP_DIAGNOSIS_ACTION,
    FOLLOWUP_LONG_CONTEXT,
)


def all_scripts() -> tuple[FollowUpScript, ...]:
    """Return every follow-up script."""
    return ALL_SCRIPTS


def get_script(script_id: str) -> FollowUpScript | None:
    """Return the script with id ``script_id`` (or ``None``)."""
    for s in ALL_SCRIPTS:
        if s.script_id == script_id:
            return s
    return None


__all__ = [
    "TurnAssertion",
    "ScriptTurn",
    "FollowUpScript",
    "all_scripts",
    "get_script",
]
