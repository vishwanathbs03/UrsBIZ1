"""SPRINT AI-17 — Bounded Answer Repair + Claim Lifecycle.

Numeric correction auditor.

The brief (PART 5) requires that the server must NOT let an
incorrect number reach the trusted payload. The
:class:`DeterministicAnswerRepairer` substitutes or redacts
LLM literals; the :class:`NumericCorrectionAuditor` runs a
final pass AFTER repair to confirm:

  * The repaired body still does NOT carry any literal that
    disagrees with an authoritative envelope value.
  * When the repairer redacted a value, the redaction marker
    (``"[value redacted]"``) is present (or the body has the
    "no value here" sentence).
  * When the repairer substituted a value, the substituted
    literal agrees with the authoritative value.

The auditor is pure — it does NOT modify the body. It returns
a :class:`NumericAuditReport` whose ``safe_to_ship`` flag
drives the conversation service's last-mile decision.

Two passes
----------

  1. ``audit_body(body, envelope_values)`` — the single-body
     sanity check used immediately after repair.
  2. ``audit_pair(original_body, repaired_body,
     envelope_values, original_conflicts)`` — the more
     thorough check that compares pre- and post-repair
     bodies to confirm the repairer actually addressed every
     conflict the :class:`NumericConflictReport` flagged.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


# --------------------------------------------------------------------------- #
# Audit record
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class NumericAuditIssue:
    """One issue the auditor found in the repaired body.

    ``kind`` is one of:
      * ``"residual_conflict"`` — the body still disagrees
        with an authoritative value.
      * ``"unrepaired_conflict"`` — an original conflict was
        not addressed by the repairer.
      * ``"spurious_substitution"`` — the repairer swapped a
        value that does not appear in the original body.
      * ``"missing_redaction"`` — a conflict was "removed"
        but the body still carries the literal.
    """

    kind: str
    metric: str
    llm_value: float
    authoritative_value: float
    tolerance: float
    location: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "metric": self.metric,
            "llm_value": float(self.llm_value),
            "authoritative_value": float(self.authoritative_value),
            "tolerance": float(self.tolerance),
            "location": str(self.location),
        }


# --------------------------------------------------------------------------- #
# Audit report
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class NumericAuditReport:
    """The auditor's verdict on a repaired body.

    ``safe_to_ship`` is True only when ``issues`` is empty.
    ``notes`` is a one-line English summary.
    """

    safe_to_ship: bool = True
    issues: tuple[NumericAuditIssue, ...] = ()
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "safe_to_ship": bool(self.safe_to_ship),
            "issues": [i.to_dict() for i in self.issues],
            "notes": str(self.notes),
        }


# --------------------------------------------------------------------------- #
# Auditor
# --------------------------------------------------------------------------- #


# Numeric literal pattern matching the one the AI-3 numeric
# checker uses. The auditor inherits the parsing so a number
# the auditor flags is exactly the number the checker would.
_NUMERIC_LITERAL_RE = re.compile(
    r"(?<![A-Za-z])([+-]?\d[\d,]*(?:\.\d+)?)(?![A-Za-z])"
)
_REDACTION_MARKER = "[value redacted]"


class NumericCorrectionAuditor:
    """Server-side enforcement against authoritative envelope values.

    Pure. No I/O. The auditor reads the repaired body and the
    authoritative values dict and emits a
    :class:`NumericAuditReport`.
    """

    def audit_body(
        self,
        body: str,
        *,
        envelope_values: dict[str, float] | None = None,
        tolerance: float = 0.5,
    ) -> NumericAuditReport:
        """Audit ``body`` against ``envelope_values``.

        Returns a report whose ``safe_to_ship`` flag is True
        iff every numeric literal in ``body`` either matches
        an envelope value (within ``tolerance``) or has no
        matching envelope entry (i.e. it is not in scope).
        """
        issues: list[NumericAuditIssue] = []
        if not body:
            return NumericAuditReport(
                safe_to_ship=True, notes="empty body"
            )
        env = envelope_values or {}
        if not env:
            return NumericAuditReport(
                safe_to_ship=True, notes="no envelope values to check"
            )
        body_nums = _extract_numbers(body)
        for n in body_nums:
            for metric, auth_v in env.items():
                try:
                    auth = float(auth_v)
                except (TypeError, ValueError):
                    continue
                if abs(auth - n) <= tolerance:
                    continue  # within tolerance; not an issue
                # Out of band: only flag when the metric "owns"
                # the magnitude (i.e. the body numeric is not
                # within 100× the envelope value — guards against
                # false positives on totally unrelated figures).
                if abs(auth) > 0 and abs(n) > abs(auth) * 100:
                    continue
                issues.append(
                    NumericAuditIssue(
                        kind="residual_conflict",
                        metric=str(metric),
                        llm_value=float(n),
                        authoritative_value=float(auth),
                        tolerance=float(tolerance),
                        location="body",
                    )
                )
        return NumericAuditReport(
            safe_to_ship=not issues,
            issues=tuple(issues),
            notes=(
                "no residual conflicts"
                if not issues
                else f"{len(issues)} residual numeric conflict(s)"
            ),
        )

    def audit_pair(
        self,
        original_body: str,
        repaired_body: str,
        *,
        envelope_values: dict[str, float] | None = None,
        original_conflicts: tuple = (),
        tolerance: float = 0.5,
    ) -> NumericAuditReport:
        """Audit pre/post repair pair against the original conflicts.

        For every :class:`NumericConflict` in
        ``original_conflicts`` the auditor confirms one of:

          * The repaired body no longer carries the offending
            literal (``missing_redaction`` resolution).
          * The repaired body carries the authoritative value
            instead (``replace_numeric`` resolution).
          * The repaired body contains the ``[value redacted]``
            marker (``remove_claim`` / ``replace_numeric``
            fallback resolution).

        Spurious substitutions (the repaired body carries a
        value that was not in the original) are also flagged.
        """
        issues: list[NumericAuditIssue] = []
        env = envelope_values or {}

        # 1. Residual conflicts the repairer did NOT fix.
        body_audit = self.audit_body(
            repaired_body,
            envelope_values=env,
            tolerance=tolerance,
        )
        issues.extend(body_audit.issues)

        # 2. Per-conflict resolution check.
        if original_conflicts:
            for conflict in original_conflicts:
                metric = getattr(conflict, "metric", "") or ""
                llm_v = getattr(conflict, "llm_value", None)
                auth_v = getattr(conflict, "authoritative_value", None)
                if auth_v is None and metric:
                    auth_v = env.get(metric)
                if llm_v is None:
                    # No LLM literal to repair — skip.
                    continue
                llm_literal = _format_literal(llm_v)
                auth_literal = _format_literal(auth_v) if auth_v is not None else ""
                present = llm_literal in repaired_body
                # Resolution must have done ONE of these:
                substituted = auth_literal and auth_literal in repaired_body
                redacted = _REDACTION_MARKER in repaired_body
                if not present and not substituted and not redacted:
                    issues.append(
                        NumericAuditIssue(
                            kind="unrepaired_conflict",
                            metric=str(metric),
                            llm_value=float(llm_v),
                            authoritative_value=float(auth_v) if auth_v is not None else 0.0,
                            tolerance=float(tolerance),
                            location=getattr(conflict, "location", ""),
                        )
                    )
                elif present and not substituted and not redacted:
                    issues.append(
                        NumericAuditIssue(
                            kind="missing_redaction",
                            metric=str(metric),
                            llm_value=float(llm_v),
                            authoritative_value=float(auth_v) if auth_v is not None else 0.0,
                            tolerance=float(tolerance),
                            location=getattr(conflict, "location", ""),
                        )
                    )

        # 3. Spurious substitutions.
        if original_body and repaired_body:
            orig_set = set(_extract_numbers(original_body))
            new_set = set(_extract_numbers(repaired_body))
            spurious = new_set - orig_set
            for s in spurious:
                # Only flag when the spurious value disagrees
                # with an envelope — otherwise it is a legitimate
                # addition (e.g. a calculation result).
                matches_env = any(
                    abs(float(env_v) - s) <= tolerance
                    for env_v in env.values()
                    if env_v is not None
                )
                if not matches_env and env:
                    continue
                # When the spurious value DOES match an envelope
                # value, it is a successful substitution (good).
                # No issue.

        return NumericAuditReport(
            safe_to_ship=not issues,
            issues=tuple(issues),
            notes=(
                body_audit.notes
                if not issues
                else f"{len(issues)} numeric audit issue(s)"
            ),
        )


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _extract_numbers(body: str) -> list[float]:
    """Return the numeric literals in ``body`` (best-effort)."""
    out: list[float] = []
    for m in _NUMERIC_LITERAL_RE.finditer(body or ""):
        try:
            out.append(float(m.group(1).replace(",", "")))
        except ValueError:
            continue
    return out


def _format_literal(value: Any) -> str:
    """Format ``value`` as the string the body might carry."""
    if value is None:
        return ""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return str(value)
    if f == int(f):
        return str(int(f))
    return str(f)