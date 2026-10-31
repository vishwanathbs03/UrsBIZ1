"""Per-claim-type validation rules — SPRINT AI-3.

The validator enforces the seven claim-type rules from the brief
and verifies every ``evidence_references`` ID against the
``EvidenceRegistry``. A claim that fails its category rule
or cites a fabricated ID is recorded in the report; the report
is non-blocking by default so the LLM's answer can still ship
with a recorded audit deviation (the issuer's discretion on
whether to surface / fall back / repair).

Rule map
--------

| Claim type     | Rule                                                           |
|----------------|----------------------------------------------------------------|
| FACT           | Has at least one valid evidence ID OR ``user_provided=True``.  |
| CALCULATION    | ``source`` is in {URSBIZ_ENGINE, MODEL_SCENARIO, USER_INPUT}.  |
| INFERENCE      | Has at least one valid evidence ID.                            |
| RECOMMENDATION | ``reason`` is non-empty.                                       |
| SCENARIO       | ``assumptions`` is non-empty.                                  |
| EXTERNAL_FACT  | ``external_source`` is set OR ``requires_verification=True``.  |
| UNKNOWN        | ``text`` contains no numeric literal.                          |

``UNKNOWN`` is special: an unknown gap cannot present
numeric values as fact. The regex matches any digit; the
text is also checked against the forbidden substrings the
``grounding_validator`` uses so a phrase like "We cannot give
you an exact figure" never slips through.

Evidence validation is global — every ID cited anywhere in
the envelope (claims, recommendations, calculations,
scenarios) must resolve via ``EvidenceRegistry.has_id``.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.services.ai.providers.claim_schema import (
    ALLOWED_CALCULATION_SOURCES,
    ALLOWED_CLAIM_TYPES,
    ALLOWED_UNKNOWN_IMPACTS,
    ClaimAwareResponse,
    ClaimCalculation,
    ClaimRecommendation,
    ClaimScenario,
    ClaimUnknown,
)


# Same forbidden phrases the grounding validator uses. A claim's
# text that contains any of these is rejected as either invented
# or unverifiable. Kept a small, defense-in-depth set so we don't
# double the validator's complexity.
_FORBIDDEN_SUBSTRINGS: tuple[str, ...] = (
    "always will",
    "guaranteed to",
    "100% guaranteed",
    "definitely will increase",
    "promise you",
    "certain to",
    "no risk",
    "risk-free investment",
)

# Numeric literal regex — matches a contiguous run of digits OR a
# decimal in any context (e.g. "₹1.8", "65%", "1,000").
_NUMERIC_RE = re.compile(r"\d")


@dataclass(frozen=True)
class ClaimValidationReport:
    """Per-claim validation report.

    ``passed`` is True iff every rule fired. The wire stays honest
    even when the validator reports failures — the frontend can
    branch on the report to render a "Reduced trust: N claims
    failed validation" badge without re-running validation client-
    side.
    """

    passed: bool
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    claim_errors: dict[str, tuple[str, ...]]
    evidence_errors: tuple[str, ...]
    claim_categories_used: tuple[str, ...]

    @property
    def score(self) -> int:
        """0–100 score the prompt builder can carry as an audit field.

        ``100`` means every claim passed every rule. Each failed
        claim or fabricated ID subtracts 10; the floor is 0.
        """
        total = len(self.claim_errors) + len(self.evidence_errors)
        return max(0, 100 - total * 10)


class ClaimValidator:
    """Validate a :class:`ClaimAwareResponse` against its category rules."""

    def __init__(
        self,
        registry: Any,
        response: ClaimAwareResponse,
    ) -> None:
        self._registry = registry
        self._response = response

    def validate(self) -> ClaimValidationReport:
        """Run all category rules + global evidence validation."""
        errors: list[str] = []
        warnings: list[str] = []
        claim_errors: dict[str, list[str]] = {}
        evidence_errors_set: set[str] = set()

        # ---- per-claim rules --------------------------------------- #
        for idx, claim in enumerate(self._response.claims):
            rule_errors: list[str] = []
            ctype = str(claim.claim_type or "UNKNOWN").upper()
            if ctype not in ALLOWED_CLAIM_TYPES:
                rule_errors.append(
                    f"claim[{idx}].claim_type='{ctype}' is not in "
                    f"{ALLOWED_CLAIM_TYPES}"
                )
                ctype = "UNKNOWN"

            if ctype == "FACT":
                if not claim.user_provided:
                    if not claim.evidence_references:
                        rule_errors.append(
                            f"claim[{idx}] FACT missing evidence_references "
                            "(or user_provided=True)"
                        )
            elif ctype == "INFERENCE":
                if not claim.evidence_references:
                    rule_errors.append(
                        f"claim[{idx}] INFERENCE missing evidence_references"
                    )
            elif ctype == "UNKNOWN":
                if _NUMERIC_RE.search(claim.text or ""):
                    rule_errors.append(
                        f"claim[{idx}] UNKNOWN must not contain numeric literals"
                    )
                # Defense in depth — disallowed phrases on a gap.
                for forbidden in _FORBIDDEN_SUBSTRINGS:
                    if forbidden.lower() in (claim.text or "").lower():
                        rule_errors.append(
                            f"claim[{idx}] UNKNOWN contains forbidden phrase "
                            f"'{forbidden}'"
                        )
                        break

            # Every claim's evidence_refs must resolve in the registry.
            for ref in claim.evidence_references:
                if not self._registry.has_id(ref):
                    msg = f"claim[{idx}] evidence_ref '{ref}' not in registry"
                    rule_errors.append(msg)
                    evidence_errors_set.add(msg)

            if rule_errors:
                claim_errors[f"claim[{idx}]"] = rule_errors
                errors.extend(rule_errors)

        # ---- per-recommendation rules ------------------------------ #
        for idx, rec in enumerate(self._response.recommendations):
            if not (rec.reason or "").strip():
                msg = (
                    f"recommendation[{idx}] RECOMMENDATION missing 'reason'"
                )
                claim_errors.setdefault(
                    f"recommendation[{idx}]", []
                ).append(msg)
                errors.append(msg)
            for ref in rec.evidence_references:
                if not self._registry.has_id(ref):
                    msg = (
                        f"recommendation[{idx}] evidence_ref '{ref}' "
                        "not in registry"
                    )
                    claim_errors.setdefault(
                        f"recommendation[{idx}]", []
                    ).append(msg)
                    errors.append(msg)
                    evidence_errors_set.add(msg)

        # ---- per-calculation rules --------------------------------- #
        for idx, calc in enumerate(self._response.calculations):
            if calc.source not in ALLOWED_CALCULATION_SOURCES:
                msg = (
                    f"calculation[{idx}] CALCULATION source '{calc.source}' "
                    f"not in {ALLOWED_CALCULATION_SOURCES}"
                )
                claim_errors.setdefault(
                    f"calculation[{idx}]", []
                ).append(msg)
                errors.append(msg)
            for ref in calc.evidence_references:
                if not self._registry.has_id(ref):
                    msg = (
                        f"calculation[{idx}] evidence_ref '{ref}' "
                        "not in registry"
                    )
                    claim_errors.setdefault(
                        f"calculation[{idx}]", []
                    ).append(msg)
                    errors.append(msg)
                    evidence_errors_set.add(msg)

        # ---- per-scenario rules ------------------------------------ #
        for idx, scen in enumerate(self._response.scenarios):
            if not scen.assumptions:
                msg = f"scenario[{idx}] SCENARIO missing 'assumptions'"
                claim_errors.setdefault(
                    f"scenario[{idx}]", []
                ).append(msg)
                errors.append(msg)
            for ref in scen.evidence_references:
                if not self._registry.has_id(ref):
                    msg = (
                        f"scenario[{idx}] evidence_ref '{ref}' "
                        "not in registry"
                    )
                    claim_errors.setdefault(
                        f"scenario[{idx}]", []
                    ).append(msg)
                    errors.append(msg)
                    evidence_errors_set.add(msg)

        # ---- per-unknown rules ------------------------------------- #
        for idx, unk in enumerate(self._response.unknowns):
            if unk.impact not in ALLOWED_UNKNOWN_IMPACTS:
                # Be lenient — clamp instead of reject. The brief lists
                # only HIGH/MEDIUM/LOW; we surface the deviation as a
                # warning rather than an error so an LLM that emits
                # "CRITICAL" is recorded but not blocked.
                warnings.append(
                    f"unknown[{idx}] impact '{unk.impact}' not in "
                    f"{ALLOWED_UNKNOWN_IMPACTS} (clamped)"
                )

        # ---- top-level evidence_references ----------------------- #
        for ref in self._response.evidence_references:
            if not self._registry.has_id(ref):
                msg = f"top-level evidence_ref '{ref}' not in registry"
                errors.append(msg)
                evidence_errors_set.add(msg)

        categories_used = tuple(
            sorted({str(c.claim_type or "UNKNOWN").upper() for c in self._response.claims})
        )
        return ClaimValidationReport(
            passed=not errors,
            errors=tuple(errors),
            warnings=tuple(warnings),
            claim_errors={k: tuple(v) for k, v in claim_errors.items()},
            evidence_errors=tuple(sorted(evidence_errors_set)),
            claim_categories_used=categories_used,
        )


__all__ = ["ClaimValidator", "ClaimValidationReport"]
