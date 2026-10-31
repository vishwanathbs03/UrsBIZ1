"""SPRINT AI-17 — Bounded Answer Repair + Claim Lifecycle.

Tests for ``deterministic_answer_repairer``: the 7-strategy
deterministic repair layer (no LLM).

9 tests covering:
  * replace_numeric with envelope value substitutes the literal
  * replace_numeric without envelope value removes the literal
  * remove_claim softens an assertive unsupported claim
  * remove_claim appends unverifiable marker for declarative claim
  * add_uncertainty appends the canonical paragraph
  * add_assumptions appends the scenario assumptions block
  * reclassify_recommendation rewrites assertive phrasing
  * recompose strips chain-of-thought preamble
  * warning_only returns original body with explanation
"""

from __future__ import annotations

from types import SimpleNamespace

from app.services.ai.reasoning.deterministic_answer_repairer import (
    DeterministicAnswerRepairer,
    RepairAction,
    RepairReport,
)


# --------------------------------------------------------------------------- #
# 1 — replace_numeric WITH envelope value substitutes
# --------------------------------------------------------------------------- #


def test_replace_numeric_substitutes_with_envelope_value():
    """The repairer must substitute the LLM literal with the
    authoritative envelope value when one is available."""
    repairer = DeterministicAnswerRepairer()
    body = "Your estimated revenue is 250 cr."
    conflict = SimpleNamespace(
        metric="revenue", llm_value=250.0, authoritative_value=180.0
    )
    report = repairer.repair(
        body, strategy="replace_numeric",
        numeric_conflicts=(conflict,),
        envelope_values={"revenue": 180.0},
    )
    assert "180" in report.repaired_body
    assert "250 cr" not in report.repaired_body
    assert report.fully_repaired is True
    assert any(a.strategy == "replace_numeric" for a in report.actions)


# --------------------------------------------------------------------------- #
# 2 — replace_numeric WITHOUT envelope value removes the literal
# --------------------------------------------------------------------------- #


def test_replace_numeric_removes_literal_without_envelope():
    """The repairer must REMOVE the offending literal when no
    authoritative value is available — it must NEVER guess."""
    repairer = DeterministicAnswerRepairer()
    body = "Your estimated revenue is 250 cr."
    conflict = SimpleNamespace(
        metric="revenue", llm_value=250.0, authoritative_value=None
    )
    report = repairer.repair(
        body, strategy="replace_numeric",
        numeric_conflicts=(conflict,),
        envelope_values={},
    )
    assert "250" not in report.repaired_body
    assert "[value redacted]" in report.repaired_body
    assert report.fully_repaired is True


# --------------------------------------------------------------------------- #
# 3 — remove_claim softens an assertive unsupported claim
# --------------------------------------------------------------------------- #


def test_remove_claim_softens_assertive_unsupported_claim():
    """The repairer softens "we recommend" → "UrsBiz suggests"."""
    repairer = DeterministicAnswerRepairer()
    body = (
        "We recommend you hire two senior engineers immediately "
        "to scale the platform."
    )
    unsupported = (SimpleNamespace(text=body),)
    report = repairer.repair(
        body, strategy="remove_claim",
        unsupported_claims=unsupported,
    )
    # The full assertive phrase was rewritten to advisory.
    assert "UrsBiz suggests" in report.repaired_body
    assert "We recommend you hire" not in report.repaired_body
    assert report.fully_repaired is True


# --------------------------------------------------------------------------- #
# 4 — remove_claim appends unverifiable marker for declarative claim
# --------------------------------------------------------------------------- #


def test_remove_claim_appends_marker_for_declarative_claim():
    """A short declarative claim that does not match an
    assertive marker gets a "[UrsBiz could not verify...]"
    marker appended."""
    repairer = DeterministicAnswerRepairer()
    body = "Acme will raise Series B in 2025."
    unsupported = (SimpleNamespace(text=body),)
    report = repairer.repair(
        body, strategy="remove_claim",
        unsupported_claims=unsupported,
    )
    assert "UrsBiz could not verify" in report.repaired_body
    assert report.fully_repaired is True


# --------------------------------------------------------------------------- #
# 5 — add_uncertainty appends the canonical paragraph
# --------------------------------------------------------------------------- #


def test_add_uncertainty_appends_canonical_paragraph():
    """The repairer appends the canonical uncertainty disclosure."""
    repairer = DeterministicAnswerRepairer()
    body = "Your revenue will be 180 cr by 2027."
    report = repairer.repair(body, strategy="add_uncertainty")
    assert "limited verified evidence" in report.repaired_body
    assert report.fully_repaired is True
    # Idempotent: re-repairing does not double-append.
    report2 = repairer.repair(
        report.repaired_body, strategy="add_uncertainty"
    )
    assert report2.repaired_body.count("limited verified evidence") == 1


# --------------------------------------------------------------------------- #
# 6 — add_assumptions appends the scenario assumptions block
# --------------------------------------------------------------------------- #


def test_add_assumptions_appends_scenario_block():
    """The repairer appends scenario assumptions the LLM omitted."""
    repairer = DeterministicAnswerRepairer()
    body = "Headcount will remain flat."
    assumptions = (
        "revenue grows 20% YoY",
        "headcount flat",
        "current margin of 18% holds",
    )
    report = repairer.repair(
        body, strategy="add_assumptions",
        scenario_assumptions=assumptions,
    )
    assert "Assumptions used in this answer" in report.repaired_body
    for a in assumptions:
        assert a in report.repaired_body
    assert report.fully_repaired is True


# --------------------------------------------------------------------------- #
# 7 — reclassify_recommendation rewrites assertive phrasing
# --------------------------------------------------------------------------- #


def test_reclassify_recommendation_rewrites_assertive_phrasing():
    """The repairer rewrites "you should X" → "you may want to consider X"."""
    repairer = DeterministicAnswerRepairer()
    body = "You should focus on working capital first."
    report = repairer.repair(body, strategy="reclassify_recommendation")
    assert "you may want to focus on" in report.repaired_body.lower()
    # The original assertive phrasing is gone (case-insensitive).
    assert "you should focus on" not in report.repaired_body.lower()
    assert report.fully_repaired is True


# --------------------------------------------------------------------------- #
# 8 — recompose strips chain-of-thought preamble
# --------------------------------------------------------------------------- #


def test_recompose_strips_chain_of_thought_preamble():
    """The repairer strips chain-of-thought preamble when present."""
    repairer = DeterministicAnswerRepairer()
    body = (
        "Your revenue is healthy.\n\n"
        "Reasoning: I looked at the score and saw growth.\n\n"
        "Cash flow is the bottleneck."
    )
    report = repairer.repair(body, strategy="recompose")
    assert "Reasoning:" not in report.repaired_body
    assert "Your revenue is healthy." in report.repaired_body
    assert "Cash flow is the bottleneck." in report.repaired_body
    assert report.fully_repaired is True


# --------------------------------------------------------------------------- #
# 9 — warning_only returns original body with explanation
# --------------------------------------------------------------------------- #


def test_warning_only_keeps_body_and_marks_unrepaired():
    """The repairer must NOT modify the body for warning_only —
    it marks the report as not fully repaired so the bounded
    retry gate decides what to do next."""
    repairer = DeterministicAnswerRepairer()
    body = "Your revenue is 180 cr."
    report = repairer.repair(body, strategy="warning_only")
    assert report.repaired_body == body
    assert report.fully_repaired is False
    assert "did not fully resolve" in report.repair_notes


# --------------------------------------------------------------------------- #
# 10 — original_body preserved for audit
# --------------------------------------------------------------------------- #


def test_original_body_preserved_for_audit():
    """The :class:`RepairReport` always preserves the original
    body so the audit trail can re-validate without re-running
    the pipeline."""
    repairer = DeterministicAnswerRepairer()
    body = "Your revenue is 250 cr."
    conflict = SimpleNamespace(
        metric="revenue", llm_value=250.0, authoritative_value=180.0
    )
    report = repairer.repair(
        body, strategy="replace_numeric",
        numeric_conflicts=(conflict,),
        envelope_values={"revenue": 180.0},
    )
    assert report.original_body == body
    assert report.repaired_body != body


# --------------------------------------------------------------------------- #
# 11 — to_dict round-trip on RepairReport and RepairAction
# --------------------------------------------------------------------------- #


def test_repair_report_to_dict_serialises_actions():
    """:meth:`RepairReport.to_dict` must serialise every action."""
    repairer = DeterministicAnswerRepairer()
    body = "Body."
    report = repairer.repair(body, strategy="add_uncertainty")
    d = report.to_dict()
    assert d["original_body"] == body
    assert d["fully_repaired"] is True
    assert isinstance(d["actions"], list)
    assert d["actions"][0]["strategy"] == "add_uncertainty"
