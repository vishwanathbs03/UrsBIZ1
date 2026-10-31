"""SPRINT AI-17 — Bounded Answer Repair + Claim Lifecycle.

Tests for ``numeric_correction_auditor``: the post-repair
server-side enforcement that incorrect numbers NEVER reach
the trusted payload.

7 tests covering:
  * audit_body with no envelope values → safe_to_ship=True
  * audit_body with matching envelope value → safe_to_ship=True
  * audit_body with residual conflicting literal → safe_to_ship=False
  * audit_pair flags unrepaired conflict
  * audit_pair passes when conflict is redacted
  * audit_pair passes when conflict is substituted
  * Redaction marker counts as resolution
"""

from __future__ import annotations

from types import SimpleNamespace

from app.services.ai.reasoning.numeric_correction_auditor import (
    NumericAuditIssue,
    NumericAuditReport,
    NumericCorrectionAuditor,
)


def _conflict(metric: str, llm_value, authoritative_value):
    return SimpleNamespace(
        metric=metric,
        llm_value=llm_value,
        authoritative_value=authoritative_value,
        location=f"claim[{metric}]",
    )


# --------------------------------------------------------------------------- #
# 1 — empty body, no envelope → safe
# --------------------------------------------------------------------------- #


def test_audit_body_empty_envelope_is_safe():
    """When no envelope values are supplied the auditor has
    nothing to compare against and the body is safe by default."""
    auditor = NumericCorrectionAuditor()
    report = auditor.audit_body("Your revenue is 250 cr.")
    assert report.safe_to_ship is True
    assert report.issues == ()


# --------------------------------------------------------------------------- #
# 2 — body matches envelope value → safe
# --------------------------------------------------------------------------- #


def test_audit_body_matching_envelope_is_safe():
    """When the body's numeric agrees with the envelope value
    the auditor marks it safe."""
    auditor = NumericCorrectionAuditor()
    report = auditor.audit_body(
        "Your revenue is 180 cr.",
        envelope_values={"revenue": 180.0},
        tolerance=0.5,
    )
    assert report.safe_to_ship is True


# --------------------------------------------------------------------------- #
# 3 — body disagrees with envelope → unsafe
# --------------------------------------------------------------------------- #


def test_audit_body_residual_conflict_unsafe():
    """When the body carries a numeric that disagrees with the
    envelope value the auditor flags it as unsafe."""
    auditor = NumericCorrectionAuditor()
    report = auditor.audit_body(
        "Your revenue is 250 cr.",
        envelope_values={"revenue": 180.0},
        tolerance=0.5,
    )
    assert report.safe_to_ship is False
    assert any(
        i.kind == "residual_conflict" and i.metric == "revenue"
        for i in report.issues
    )


# --------------------------------------------------------------------------- #
# 4 — audit_pair flags unrepaired conflict
# --------------------------------------------------------------------------- #


def test_audit_pair_flags_unrepaired_conflict():
    """When the original conflict still appears in the repaired
    body the auditor raises ``missing_redaction`` (the body
    still carries the LLM literal with no resolution)."""
    auditor = NumericCorrectionAuditor()
    original = "Your revenue is 250 cr."
    # Repairer left the body unchanged (unrepaired).
    repaired = original
    conflicts = (_conflict("revenue", 250.0, 180.0),)
    report = auditor.audit_pair(
        original,
        repaired,
        envelope_values={"revenue": 180.0},
        original_conflicts=conflicts,
    )
    assert report.safe_to_ship is False
    assert any(
        i.kind in ("missing_redaction", "unrepaired_conflict")
        for i in report.issues
    )


# --------------------------------------------------------------------------- #
# 5 — audit_pair passes when conflict is redacted
# --------------------------------------------------------------------------- #


def test_audit_pair_passes_when_conflict_redacted():
    """When the repairer replaced the offending literal with
    ``[value redacted]`` the auditor marks the body safe."""
    auditor = NumericCorrectionAuditor()
    original = "Your revenue is 250 cr."
    repaired = "Your revenue is [value redacted] cr."
    conflicts = (_conflict("revenue", 250.0, None),)
    report = auditor.audit_pair(
        original,
        repaired,
        envelope_values={},
        original_conflicts=conflicts,
    )
    assert report.safe_to_ship is True


# --------------------------------------------------------------------------- #
# 6 — audit_pair passes when conflict is substituted
# --------------------------------------------------------------------------- #


def test_audit_pair_passes_when_conflict_substituted():
    """When the repairer replaced the LLM literal with the
    authoritative envelope value the auditor marks the body safe."""
    auditor = NumericCorrectionAuditor()
    original = "Your revenue is 250 cr."
    repaired = "Your revenue is 180 cr."
    conflicts = (_conflict("revenue", 250.0, 180.0),)
    report = auditor.audit_pair(
        original,
        repaired,
        envelope_values={"revenue": 180.0},
        original_conflicts=conflicts,
    )
    assert report.safe_to_ship is True


# --------------------------------------------------------------------------- #
# 7 — redaction marker alone counts as resolution
# --------------------------------------------------------------------------- #


def test_redaction_marker_alone_resolves_conflict():
    """A redaction marker anywhere in the repaired body counts
    as evidence the repairer addressed the conflict, even when
    the body is otherwise unchanged."""
    auditor = NumericCorrectionAuditor()
    original = "Your revenue is 250 cr."
    # The repairer added the marker (unrepaired body is short).
    repaired = original + " [value redacted]"
    conflicts = (_conflict("revenue", 250.0, None),)
    report = auditor.audit_pair(
        original,
        repaired,
        envelope_values={},
        original_conflicts=conflicts,
    )
    assert report.safe_to_ship is True


# --------------------------------------------------------------------------- #
# 8 — to_dict round-trip on audit report + issue
# --------------------------------------------------------------------------- #


def test_audit_report_to_dict_serialises_issues():
    """:meth:`NumericAuditReport.to_dict` and
    :meth:`NumericAuditIssue.to_dict` serialise safely."""
    issue = NumericAuditIssue(
        kind="residual_conflict",
        metric="revenue",
        llm_value=250.0,
        authoritative_value=180.0,
        tolerance=0.5,
        location="body",
    )
    d = issue.to_dict()
    assert d["kind"] == "residual_conflict"
    assert d["metric"] == "revenue"
    assert d["llm_value"] == 250.0
    assert d["authoritative_value"] == 180.0
    # And the report wraps it.
    report = NumericAuditReport(
        safe_to_ship=False, issues=(issue,), notes="1 issue"
    )
    rd = report.to_dict()
    assert rd["safe_to_ship"] is False
    assert len(rd["issues"]) == 1
    assert rd["notes"] == "1 issue"
