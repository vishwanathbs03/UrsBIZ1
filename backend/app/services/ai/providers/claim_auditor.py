"""Server-side Claim Auditor — SPRINT AI-4.

The auditor sits between the parsed ``ClaimAwareResponse`` and
the wire projection. It inspects every material claim,
classifies it across the 9 attribute axes the brief mandates,
applies hard-rejection when the answer is fundamentally
unsupportable, soft-corrects when only one claim is faulty, and
persists a compact claim trace on ``GenerationMeta.claim_audit``.

The trace is what the frontend's "Why am I seeing this?"
disclosure panel renders — only validated claims surface, with
their evidence IDs + confidence score. Chain-of-thought is never
persisted; the auditor's internal flags stay inside the audit
report.

Reused from earlier sprints
---------------------------

* :data:`claim_schema.ALLOWED_CLAIM_TYPES`
* :data:`claim_validator._FORBIDDEN_SUBSTRINGS`
* :class:`evidence_registry.EvidenceRegistry` (``has_id``, ``by_kind``)
* :class:`numeric_checker.NumericConflictReport`

Architectural notes
-------------------

The auditor is **additive** on top of AI-3. ``ClaimValidator`` and
``NumericConsistencyChecker`` keep running; this layer consumes
their reports and produces the compact per-claim trace. The
hard-rejection path does NOT raise — it stamps the envelope so
the chat endpoint still returns a valid response (the frontend
renders an "Answer withheld — reason" stub from the rejection
flag).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, replace as _replace
from typing import Any, Iterable

from app.services.ai.providers.claim_schema import (
    ALLOWED_CLAIM_TYPES,
    ClaimAwareResponse,
    ClaimCalculation,
    ClaimRecommendation,
    ClaimScenario,
    ClaimUnknown,
    Claim,
)
from app.services.ai.providers.claim_validator import _FORBIDDEN_SUBSTRINGS
from app.services.ai.providers.evidence_registry import EvidenceKind


# --------------------------------------------------------------------------- #
# Hard-rejection reason labels — exposed so tests and the frontend can
# branch on stable strings without depending on regex output.
# --------------------------------------------------------------------------- #

REJECTION_FABRICATED_NUMBER = "fabricated_business_number"
REJECTION_FABRICATED_EVIDENCE_ID = "fabricated_evidence_id"
REJECTION_CONTRADICTS_AUTHORITY = "contradicts_authoritative_business_data"
REJECTION_FABRICATED_SCHEME_BENEFIT = "fabricated_scheme_benefit"
REJECTION_LEGAL_ELIGIBILITY_GUARANTEE = "legal_eligibility_presented_as_guaranteed"
REJECTION_SCENARIO_AS_FORECAST = "scenario_presented_as_forecast"
REJECTION_RECOMMENDATION_AS_GUARANTEE = "recommendation_as_guaranteed_outcome"
REJECTION_UNSUPPORTED_CONFIDENCE = "unsupported_confidence"
REJECTION_FABRICATED_TOP_LEVEL_REF = "fabricated_evidence_references"

# Soft-eligible rejections — when ONE claim fails with one of these AND
# no other record fails with a hard-only rejection, the auditor attempts
# a soft-correction (clamp / rewrite) instead of rejecting the whole
# response. Every other rejection reason is hard-only and the
# response-level verdict is rejected=True.
_SOFT_ELIGIBLE_REJECTIONS: frozenset[str] = frozenset({
    REJECTION_UNSUPPORTED_CONFIDENCE,
    REJECTION_CONTRADICTS_AUTHORITY,
})


# --------------------------------------------------------------------------- #
# Regexes
# --------------------------------------------------------------------------- #

# Hypothetical markers — case-insensitive, word-boundary anchored.
_HYPOTHETICAL_MARKER_RE = re.compile(
    r"\b(could|may|might|potentially|if|would|should)\b",
    re.IGNORECASE,
)

# Currency tokens — same family the AI-3 numeric checker uses.
_CURRENCY_RE = re.compile(
    r"\b(\d[\d,.]*)\s*(cr(?:ore)?|lakh|mn|million|thousand|k)\b",
    re.IGNORECASE,
)

# Scheme benefit pattern — "scheme" near a numeric benefit.
_SCHEME_BENEFIT_RE = re.compile(
    r"\bscheme\b.{0,40}\b(\d[\d,.]*\s*(?:cr(?:ore)?|lakh|mn|million|thousand|k)?)\b",
    re.IGNORECASE | re.DOTALL,
)

# Forbidden substring matcher — lower-cased once.
_FORBIDDEN_LOWER: tuple[str, ...] = tuple(s.lower() for s in _FORBIDDEN_SUBSTRINGS)


# --------------------------------------------------------------------------- #
# Per-claim trace record
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ClaimAuditRecord:
    """Compact per-claim trace.

    The 9 attribute axes the brief mandates are: ``claim_type``,
    ``evidence_ids`` (which feeds ``evidence_exists`` /
    ``evidence_supports``), ``numeric_match``, ``is_inference``,
    ``has_assumptions``, ``is_hypothetical``, ``requires_verification``,
    ``validated``, plus the ``confidence`` score the trace surfaces.
    The trace never persists full prose — only ``text_preview``
    (first 120 chars).
    """

    claim_id: str
    claim_type: str
    text_preview: str
    evidence_ids: tuple[str, ...]
    evidence_exists: bool
    evidence_supports: bool
    numeric_match: bool
    is_inference: bool
    has_assumptions: bool
    is_hypothetical: bool
    requires_verification: bool
    validated: bool
    confidence: int
    rejection_reason: str
    soft_corrected: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "claim_type": self.claim_type,
            "text_preview": self.text_preview,
            "evidence_ids": list(self.evidence_ids),
            "evidence_exists": self.evidence_exists,
            "evidence_supports": self.evidence_supports,
            "numeric_match": self.numeric_match,
            "is_inference": self.is_inference,
            "has_assumptions": self.has_assumptions,
            "is_hypothetical": self.is_hypothetical,
            "requires_verification": self.requires_verification,
            "validated": self.validated,
            "confidence": int(self.confidence),
            "rejection_reason": self.rejection_reason,
            "soft_corrected": self.soft_corrected,
        }


@dataclass(frozen=True)
class ClaimAuditReport:
    """The auditor's verdict on a ``ClaimAwareResponse``.

    ``rejected`` is True iff at least one hard-rejection condition
    fired. ``rejection_reason`` is the stable label of the FIRST
    condition that fired (deterministic order: the rules are
    evaluated in a fixed sequence so two consecutive runs against
    the same input produce the same verdict). ``soft_corrections``
    counts how many claims the auditor rewrote without rejecting
    the whole answer.
    """

    rejected: bool
    rejection_reason: str
    soft_corrections: int
    records: tuple[ClaimAuditRecord, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rejected": bool(self.rejected),
            "rejection_reason": str(self.rejection_reason),
            "soft_corrections": int(self.soft_corrections),
            "records": [r.to_dict() for r in self.records],
        }


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


# Per-claim-type acceptance mask. A claim's cited evidence is
# considered "supporting" when EVERY cited ID's ``kind`` is in
# the allowed set. UNKNOWN claims accept no evidence (they are
# gaps, not claims).
_KIND_ACCEPTANCE: dict[str, frozenset[str]] = {
    "FACT": frozenset({
        EvidenceKind.SCORE.value,
        EvidenceKind.RECOMMENDATION.value,
        EvidenceKind.RULE.value,
        EvidenceKind.INSIGHT.value,
        EvidenceKind.SCHEME.value,
        EvidenceKind.FORECAST.value,
        EvidenceKind.ACTION.value,
        EvidenceKind.DNA.value,
    }),
    "INFERENCE": frozenset({
        EvidenceKind.SCORE.value,
        EvidenceKind.RULE.value,
        EvidenceKind.INSIGHT.value,
        EvidenceKind.ACTION.value,
        EvidenceKind.DNA.value,
    }),
    "RECOMMENDATION": frozenset({EvidenceKind.RECOMMENDATION.value}),
    "SCENARIO": frozenset({
        EvidenceKind.FORECAST.value,
        EvidenceKind.RECOMMENDATION.value,
    }),
    "CALCULATION": frozenset({
        EvidenceKind.SCORE.value,
        EvidenceKind.FORECAST.value,
        EvidenceKind.INSIGHT.value,
    }),
    "EXTERNAL_FACT": frozenset({
        EvidenceKind.SCHEME.value,
        EvidenceKind.INSIGHT.value,
    }),
    "UNKNOWN": frozenset(),  # UNKNOWN is a gap — no evidence accepted.
}


def _preview(text: str, *, cap: int = 120) -> str:
    """First ``cap`` chars of ``text``. Never raises."""
    if not text:
        return ""
    text = str(text)
    if len(text) > cap:
        return text[: cap - 1].rstrip() + "…"
    return text


def _has_forbidden(text: str) -> bool:
    """Return True iff ``text`` contains any AI-3 forbidden substring."""
    if not text:
        return False
    lower = str(text).lower()
    return any(f in lower for f in _FORBIDDEN_LOWER)


def _is_hypothetical(text: str, *, claim_type: str) -> bool:
    """A SCENARIO is always hypothetical; otherwise we look for markers."""
    if claim_type == "SCENARIO":
        return True
    if not text:
        return False
    return bool(_HYPOTHETICAL_MARKER_RE.search(str(text)))


def _evidence_supports(registry: Any, claim_type: str, ref_ids: Iterable[str]) -> bool:
    """True iff every cited ID resolves AND every entry's kind matches the type."""
    allowed = _KIND_ACCEPTANCE.get(claim_type, frozenset())
    if not allowed:
        # UNKNOWN — accepts nothing. If ref_ids is empty we still
        # consider this supported (no evidence was claimed).
        return len(list(ref_ids)) == 0
    for ref in ref_ids:
        entry = registry.by_id(ref) if registry else None
        if entry is None:
            return False
        kind_value = getattr(getattr(entry, "kind", None), "value", None) or str(entry.kind)
        if str(kind_value).lower() not in allowed:
            return False
    return True


def _has_currency(text: str) -> bool:
    return bool(text and _CURRENCY_RE.search(str(text)))


def _has_scheme_benefit_fabrication(text: str, registry: Any) -> bool:
    """True iff ``text`` claims a numeric benefit from a scheme.

    Heuristic: ``text`` contains the word "scheme" within 40 chars
    of a numeric literal AND the numeric literal is NOT present in
    any ``scheme_*`` registry entry's value. The auditor falls
    back to True when no scheme entry is available — schemes that
    don't exist in the registry are presumed fabricated.
    """
    if not text:
        return False
    m = _SCHEME_BENEFIT_RE.search(str(text))
    if not m:
        return False
    benefit_literal = m.group(1)
    # Check whether any scheme_* entry in the registry mentions
    # this literal in its value. If we have no registry, we
    # conservatively call it fabricated.
    if registry is not None:
        for entry in registry.by_kind(EvidenceKind.SCHEME):
            value = getattr(entry, "value", "") or ""
            if benefit_literal in value:
                return False
    return True


# --------------------------------------------------------------------------- #
# Auditor
# --------------------------------------------------------------------------- #


class ClaimAuditor:
    """Inspect a ``ClaimAwareResponse`` and produce a trace.

    Constructor takes the same inputs every AI-3 / AI-4 stage
    already consumes: the ``EvidenceRegistry`` and the
    ``NumericConflictReport``. ``audit(response)`` returns the
    ``ClaimAuditReport``.

    The auditor is read-only on the response object except for
    soft-corrections, which mutate the underlying dataclass via
    ``object.__setattr__`` (the dataclass is frozen). The mutation
    is scoped to the auditor's return — the caller's reference to
    ``response`` sees the rewritten text on the next read.
    """

    # Hard-rejection threshold — claims with confidence > 90 but
    # zero cited evidence are flagged "unsupported_confidence".
    UNSUPPORTED_CONFIDENCE_THRESHOLD = 90

    def __init__(
        self,
        registry: Any,
        numeric_report: Any = None,
    ) -> None:
        self._registry = registry
        self._numeric_report = numeric_report

    # ---- public API ------------------------------------------------- #

    def audit(self, response: ClaimAwareResponse) -> ClaimAuditReport:
        """Run the audit and return the trace.

        The verdict is deterministic for any given input — the
        hard-rejection rules are evaluated in a fixed order and
        only the first match is reported.
        """
        if response is None:
            return ClaimAuditReport(
                rejected=False,
                rejection_reason="",
                soft_corrections=0,
                records=(),
            )

        records: list[ClaimAuditRecord] = []
        soft_corrections = 0

        # 1. Per-claim classifier ------------------------------------ #
        # The classification loop stamps each record with its own
        # rejection_reason but does NOT set the response-level verdict
        # yet. The verdict is decided in step 6 (below) once we know
        # whether the failures are soft-eligible.
        for cidx, claim in enumerate(response.claims):
            claim_id = f"claim_{cidx:03d}"
            record, _ = self._classify_claim(claim, claim_id)
            records.append(record)

        # 2. Per-recommendation classifier --------------------------- #
        for ridx, rec in enumerate(response.recommendations):
            claim_id = f"recommendation_{ridx:03d}"
            record, _ = self._classify_recommendation(rec, claim_id)
            records.append(record)

        # 3. Per-calculation classifier ------------------------------ #
        for cidx, calc in enumerate(response.calculations):
            claim_id = f"calculation_{cidx:03d}"
            record, _ = self._classify_calculation(calc, claim_id)
            records.append(record)

        # 4. Per-scenario classifier --------------------------------- #
        for sidx, scen in enumerate(response.scenarios):
            claim_id = f"scenario_{sidx:03d}"
            record, _ = self._classify_scenario(scen, claim_id)
            records.append(record)

        # 5. Top-level fabricated references ------------------------- #
        top_level_fabricated = False
        for ref in response.evidence_references:
            if self._registry and not self._registry.has_id(ref):
                top_level_fabricated = True
                break

        # 6. Decision: soft-correct or hard-reject ------------------ #
        # We classify every failure into two buckets:
        #   - hard_only_failures: must hard-reject (fabricated IDs,
        #     scheme-benefit fabrication, legal guarantee, scenario
        #     as forecast, recommendation as guarantee, top-level
        #     fabricated ref).
        #   - soft_eligible_failures: numeric mismatch on a single
        #     FACT or CALCULATION, unsupported confidence.
        # If any hard-only failure is present -> hard-reject.
        # Else if exactly one soft-eligible failure -> soft-correct.
        # Else if multiple soft-eligible failures -> leave as-is
        # (rejected=False, per-record reasons surface in the trace
        # so the disclosure panel can show them).
        rejection_reason = ""
        failing_records = [r for r in records if not r.validated]
        hard_only_failing = [
            r for r in failing_records
            if r.rejection_reason
            and r.rejection_reason not in _SOFT_ELIGIBLE_REJECTIONS
        ]
        soft_eligible_failing = [
            r for r in failing_records
            if r.rejection_reason in _SOFT_ELIGIBLE_REJECTIONS
        ]

        if hard_only_failing:
            rejection_reason = hard_only_failing[0].rejection_reason
            soft_corrections = 0
        elif top_level_fabricated:
            rejection_reason = REJECTION_FABRICATED_TOP_LEVEL_REF
            soft_corrections = 0
        elif len(soft_eligible_failing) == 1 and len(failing_records) == 1:
            # Single soft-eligible failure -> try to soft-correct.
            soft_corrections = self._soft_correct(response, records)
            if soft_corrections == 0:
                # Soft correction refused (e.g. no usable authority).
                rejection_reason = soft_eligible_failing[0].rejection_reason
        # else: multiple failures -> leave rejected=False; the trace
        # surfaces the per-record rejection reasons for the disclosure
        # panel. We deliberately do NOT hard-reject on multiple soft
        # failures — those are per-record data quality issues the
        # disclosure panel can present without refusing the whole answer.

        return ClaimAuditReport(
            rejected=bool(rejection_reason),
            rejection_reason=str(rejection_reason),
            soft_corrections=int(soft_corrections),
            records=tuple(records),
        )

    # ---- per-shape classifiers -------------------------------------- #

    def _classify_claim(
        self, claim: Claim, claim_id: str,
    ) -> tuple[ClaimAuditRecord, str]:
        """Classify one ``Claim``. Return ``(record, rejection_reason)``.

        ``rejection_reason`` is empty when the claim is not the
        cause of a hard-rejection; otherwise it is the stable label
        of the rule that fired.
        """
        text = str(claim.text or "")
        ctype = str(claim.claim_type or "UNKNOWN").upper()
        if ctype not in ALLOWED_CLAIM_TYPES:
            ctype = "UNKNOWN"

        ref_ids = tuple(claim.evidence_references or ())
        evidence_exists = all(self._registry.has_id(r) for r in ref_ids) if self._registry and ref_ids else (not ref_ids)
        evidence_supports = _evidence_supports(
            self._registry, ctype, ref_ids
        )

        # Numeric match — look up the AI-3 numeric checker report.
        numeric_match = self._numeric_match_for_claim(text)

        # Hypothetical / assumptions / verification axes.
        is_inference = ctype == "INFERENCE"
        has_assumptions = bool(claim.audit_log) or False  # placeholder; overwritten below
        is_hypothetical = _is_hypothetical(text, claim_type=ctype)
        requires_verification = (
            ctype == "EXTERNAL_FACT" and bool(getattr(claim, "requires_verification", False))
        )

        # Confidence — mirror the claim's self-reported value; the
        # auditor flags unsupported confidence when the model said
        # > 90 but cited no evidence.
        confidence = int(claim.confidence) if claim.confidence is not None else 0
        unsupported_conf = (
            confidence > self.UNSUPPORTED_CONFIDENCE_THRESHOLD
            and not ref_ids
        )

        # Build the rejection reason for THIS claim (empty when the
        # claim itself isn't the cause of hard-rejection).
        rejection = ""

        if not evidence_exists and ref_ids:
            rejection = REJECTION_FABRICATED_EVIDENCE_ID
        elif not evidence_supports and ref_ids:
            rejection = REJECTION_FABRICATED_EVIDENCE_ID
        elif _has_scheme_benefit_fabrication(text, self._registry):
            rejection = REJECTION_FABRICATED_SCHEME_BENEFIT
        elif _has_forbidden(text):
            rejection = REJECTION_LEGAL_ELIGIBILITY_GUARANTEE
        elif not numeric_match and ctype in ("FACT", "CALCULATION"):
            rejection = REJECTION_CONTRADICTS_AUTHORITY
        elif unsupported_conf:
            rejection = REJECTION_UNSUPPORTED_CONFIDENCE

        # Validate the claim.
        validated = (
            evidence_exists
            and evidence_supports
            and numeric_match
            and not rejection
        )

        return ClaimAuditRecord(
            claim_id=claim_id,
            claim_type=ctype,
            text_preview=_preview(text),
            evidence_ids=ref_ids,
            evidence_exists=bool(evidence_exists),
            evidence_supports=bool(evidence_supports),
            numeric_match=bool(numeric_match),
            is_inference=is_inference,
            has_assumptions=has_assumptions,
            is_hypothetical=is_hypothetical,
            requires_verification=requires_verification,
            validated=bool(validated),
            confidence=int(confidence),
            rejection_reason=rejection,
        ), rejection

    def _classify_recommendation(
        self, rec: ClaimRecommendation, claim_id: str,
    ) -> tuple[ClaimAuditRecord, str]:
        """Classify a recommendation. The rec acts like a FACT for axis purposes."""
        text = str(rec.reason or rec.title or "")
        ref_ids = tuple(rec.evidence_references or ())
        evidence_exists = all(self._registry.has_id(r) for r in ref_ids) if self._registry and ref_ids else (not ref_ids)
        evidence_supports = _evidence_supports(
            self._registry, "RECOMMENDATION", ref_ids
        )
        numeric_match = self._numeric_match_for_text(text, location_hint="recommendation")
        is_inference = False
        has_assumptions = bool(text)
        is_hypothetical = _is_hypothetical(text, claim_type="RECOMMENDATION")
        requires_verification = False
        confidence = 0

        rejection = ""
        if not evidence_exists and ref_ids:
            rejection = REJECTION_FABRICATED_EVIDENCE_ID
        elif not evidence_supports and ref_ids:
            rejection = REJECTION_FABRICATED_EVIDENCE_ID
        elif _has_currency(text) and _has_forbidden(text):
            rejection = REJECTION_RECOMMENDATION_AS_GUARANTEE
        elif _has_forbidden(text):
            rejection = REJECTION_LEGAL_ELIGIBILITY_GUARANTEE

        validated = (
            evidence_exists
            and evidence_supports
            and numeric_match
            and not rejection
        )

        return ClaimAuditRecord(
            claim_id=claim_id,
            claim_type="RECOMMENDATION",
            text_preview=_preview(text),
            evidence_ids=ref_ids,
            evidence_exists=bool(evidence_exists),
            evidence_supports=bool(evidence_supports),
            numeric_match=bool(numeric_match),
            is_inference=is_inference,
            has_assumptions=has_assumptions,
            is_hypothetical=is_hypothetical,
            requires_verification=requires_verification,
            validated=bool(validated),
            confidence=int(confidence),
            rejection_reason=rejection,
        ), rejection

    def _classify_calculation(
        self, calc: ClaimCalculation, claim_id: str,
    ) -> tuple[ClaimAuditRecord, str]:
        """Classify a calculation."""
        text = str(calc.expression or "")
        ref_ids = tuple(calc.evidence_references or ())
        evidence_exists = all(self._registry.has_id(r) for r in ref_ids) if self._registry and ref_ids else (not ref_ids)
        evidence_supports = _evidence_supports(
            self._registry, "CALCULATION", ref_ids
        )
        numeric_match = self._numeric_match_for_text(text, location_hint="calculation")
        is_inference = False
        has_assumptions = bool(text)
        is_hypothetical = _is_hypothetical(text, claim_type="CALCULATION")
        requires_verification = False
        confidence = 0

        rejection = ""
        if not evidence_exists and ref_ids:
            rejection = REJECTION_FABRICATED_EVIDENCE_ID
        elif not evidence_supports and ref_ids:
            rejection = REJECTION_FABRICATED_EVIDENCE_ID

        validated = (
            evidence_exists
            and evidence_supports
            and numeric_match
            and not rejection
        )

        return ClaimAuditRecord(
            claim_id=claim_id,
            claim_type="CALCULATION",
            text_preview=_preview(text),
            evidence_ids=ref_ids,
            evidence_exists=bool(evidence_exists),
            evidence_supports=bool(evidence_supports),
            numeric_match=bool(numeric_match),
            is_inference=is_inference,
            has_assumptions=has_assumptions,
            is_hypothetical=is_hypothetical,
            requires_verification=requires_verification,
            validated=bool(validated),
            confidence=int(confidence),
            rejection_reason=rejection,
        ), rejection

    def _classify_scenario(
        self, scen: ClaimScenario, claim_id: str,
    ) -> tuple[ClaimAuditRecord, str]:
        """Classify a scenario."""
        text = str(scen.description or scen.title or "")
        ref_ids = tuple(scen.evidence_references or ())
        evidence_exists = all(self._registry.has_id(r) for r in ref_ids) if self._registry and ref_ids else (not ref_ids)
        evidence_supports = _evidence_supports(
            self._registry, "SCENARIO", ref_ids
        )
        # SCENARIO numerics are exempt from cross-check (the AI-3
        # numeric checker also exempts scenarios). We treat the
        # scenario's numeric_match as True unless the AI-3 report
        # explicitly flagged it (which the AI-3 checker does NOT
        # do — scenarios are exempt).
        numeric_match = True
        is_inference = False
        has_assumptions = bool(scen.assumptions)
        is_hypothetical = True  # SCENARIO is always hypothetical
        requires_verification = False
        confidence = int(scen.confidence) if scen.confidence is not None else 0

        rejection = ""
        # Scenario-as-forecast is the most semantically critical check —
        # a SCENARIO without assumptions or hypothetical markers is being
        # presented as a guaranteed forecast. We check it BEFORE the
        # evidence-kind rules so the rejection reason surfaces the
        # structural failure rather than the kind mismatch.
        if not has_assumptions and not _HYPOTHETICAL_MARKER_RE.search(text or ""):
            rejection = REJECTION_SCENARIO_AS_FORECAST
        elif not evidence_exists and ref_ids:
            rejection = REJECTION_FABRICATED_EVIDENCE_ID
        elif not evidence_supports and ref_ids:
            rejection = REJECTION_FABRICATED_EVIDENCE_ID

        validated = (
            evidence_exists
            and evidence_supports
            and numeric_match
            and not rejection
        )

        return ClaimAuditRecord(
            claim_id=claim_id,
            claim_type="SCENARIO",
            text_preview=_preview(text),
            evidence_ids=ref_ids,
            evidence_exists=bool(evidence_exists),
            evidence_supports=bool(evidence_supports),
            numeric_match=bool(numeric_match),
            is_inference=is_inference,
            has_assumptions=has_assumptions,
            is_hypothetical=is_hypothetical,
            requires_verification=requires_verification,
            validated=bool(validated),
            confidence=int(confidence),
            rejection_reason=rejection,
        ), rejection

    # ---- numeric cross-check ---------------------------------------- #

    def _numeric_match_for_claim(self, text: str) -> bool:
        """Return True unless the numeric checker flagged a conflict on this claim."""
        return self._numeric_match_for_text(text, location_hint="claim")

    def _numeric_match_for_text(
        self, text: str, *, location_hint: str
    ) -> bool:
        """Walk the numeric checker's report; True when no conflict touches the text."""
        if self._numeric_report is None:
            return True
        conflicts = getattr(self._numeric_report, "conflicts", ()) or ()
        if not conflicts:
            return True
        # The numeric checker's location field carries the path
        # ("claim[<idx>].text", etc.). Without an index we
        # conservatively treat the text as matched when ANY
        # conflict exists for the same shape.
        hint = str(location_hint or "").lower()
        for conflict in conflicts:
            loc = str(getattr(conflict, "location", "") or "").lower()
            if hint in loc:
                return False
        return True

    # ---- soft-correction --------------------------------------------- #

    def _soft_correct(
        self,
        response: ClaimAwareResponse,
        records: list[ClaimAuditRecord],
    ) -> int:
        """Rewrite / clamp unsupported claims when ONLY ONE failed.

        Returns the number of soft-corrections applied. The caller
        has already verified ``rejection_reason == ""`` so we know
        a hard-rejection didn't fire — only individual records
        carry ``validated=False`` here.
        """
        failing = [r for r in records if not r.validated]
        if not failing:
            return 0
        if len(failing) > 1:
            # Multi-claim failure: leave as-is (no soft correction).
            return 0

        # Single failing claim — attempt to rewrite it.
        failing_record = failing[0]
        corrected = False

        # 1. Confidence unsupported — clamp the model's
        #    self-reported confidence on the original Claim object.
        if failing_record.rejection_reason == REJECTION_UNSUPPORTED_CONFIDENCE:
            self._clamp_claim_confidence(response, failing_record.claim_id, value=60)
            corrected = True

        # 2. evidence_supports=False (wrong kind) — annotate the
        #    claim's audit_log with a qualifier.
        elif failing_record.rejection_reason == REJECTION_FABRICATED_EVIDENCE_ID:
            # Don't try to "rewrite" — fabricated IDs are hard
            # rejections. Leave as-is.
            return 0

        # 3. Numeric mismatch on a FACT — rewrite the text via
        #    the AI-3 numeric checker's authoritative values.
        elif failing_record.rejection_reason == REJECTION_CONTRADICTS_AUTHORITY:
            rewritten = self._rewrite_claim_with_authority(
                response, failing_record
            )
            corrected = rewritten

        if corrected:
            failing_record_2 = failing_record
            object.__setattr__(failing_record_2, "soft_corrected", True)
            object.__setattr__(failing_record_2, "validated", True)
            object.__setattr__(
                failing_record_2, "rejection_reason", ""
            )
            return 1
        return 0

    def _clamp_claim_confidence(
        self,
        response: ClaimAwareResponse,
        claim_id: str,
        *,
        value: int,
    ) -> None:
        """Clamp the model's per-claim confidence on the source dataclass."""
        prefix, _, idx_str = claim_id.partition("_")
        if not idx_str.isdigit():
            return
        idx = int(idx_str)
        if prefix == "claim" and 0 <= idx < len(response.claims):
            claim = response.claims[idx]
            new_claim = _replace(claim, confidence=value)
            try:
                object.__setattr__(
                    response, "claims",
                    tuple(
                        new_claim if i == idx else c
                        for i, c in enumerate(response.claims)
                    ),
                )
            except Exception:
                pass

    def _rewrite_claim_with_authority(
        self,
        response: ClaimAwareResponse,
        record: ClaimAuditRecord,
    ) -> bool:
        """Rewrite one claim's text using the AI-3 numeric checker's authoritative value."""
        prefix, _, idx_str = record.claim_id.partition("_")
        if prefix != "claim" or not idx_str.isdigit():
            return False
        idx = int(idx_str)
        if not (0 <= idx < len(response.claims)):
            return False
        claim = response.claims[idx]
        # The numeric checker's report is the source of authority.
        if self._numeric_report is None:
            return False
        conflicts = list(getattr(self._numeric_report, "conflicts", ()) or ())
        # Find the conflict for this claim.
        relevant = [
            c for c in conflicts
            if str(getattr(c, "location", "")).startswith(f"claim[{idx}]")
        ]
        if not relevant:
            return False
        conflict = relevant[0]
        original = str(getattr(conflict, "original", "") or "")
        replacement = str(getattr(conflict, "replacement", "") or "")
        if not original or not replacement or replacement.startswith("(unchanged"):
            return False
        new_text = (claim.text or "").replace(original, replacement, 1)
        if new_text == claim.text:
            return False
        new_claim = _replace(claim, text=new_text)
        try:
            object.__setattr__(
                response, "claims",
                tuple(
                    new_claim if i == idx else c
                    for i, c in enumerate(response.claims)
                ),
            )
        except Exception:
            return False
        return True


__all__ = [
    "ClaimAuditor",
    "ClaimAuditRecord",
    "ClaimAuditReport",
    "REJECTION_FABRICATED_NUMBER",
    "REJECTION_FABRICATED_EVIDENCE_ID",
    "REJECTION_CONTRADICTS_AUTHORITY",
    "REJECTION_FABRICATED_SCHEME_BENEFIT",
    "REJECTION_LEGAL_ELIGIBILITY_GUARANTEE",
    "REJECTION_SCENARIO_AS_FORECAST",
    "REJECTION_RECOMMENDATION_AS_GUARANTEE",
    "REJECTION_UNSUPPORTED_CONFIDENCE",
    "REJECTION_FABRICATED_TOP_LEVEL_REF",
]