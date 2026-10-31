"""Parse an LLM's ``claim_aware`` payload into a :class:`ClaimAwareResponse`.

Same fence/prose/JSON tolerance as
:func:`app.services.ai.providers.response_schema.parse_model_output`.
The parser NEVER raises — it returns a :class:`ValidationResult`
whose ``response`` is ``None`` when the LLM didn't fill the new
schema so the caller can fall back to the existing ``GroundedResponse``.

Two entry points
----------------

* :func:`parse_claim_aware_payload` — parses the ``claim_aware``
  dict itself, returning a :class:`ClaimAwareResponse` (or
  ``None``).
* :func:`extract_claim_aware_block` — finds the ``claim_aware``
  key inside a larger LLM payload. Returns ``None`` when the
  key is absent (the common case — most LLMs won't fill the
  new schema).

Audit-only fields
-----------------

The parser strips ``server_confidence``,
``server_confidence_rationale``, and ``numeric_conflicts`` from
the LLM's payload — the LLM cannot author the server's value.
Those fields are populated later by the confidence calculator.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from app.services.ai.providers.claim_schema import (
    ALLOWED_CLAIM_TYPES,
    Claim,
    ClaimAwareResponse,
    ClaimCalculation,
    ClaimRecommendation,
    ClaimScenario,
    ClaimUnknown,
    clamp_confidence,
    clamp_string_list,
    clamp_text,
)


# --------------------------------------------------------------------------- #
# Validation result
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ClaimAwareValidationResult:
    """Outcome of parsing a ``claim_aware`` payload.

    ``response`` is non-None only when the payload was a parseable
    dict whose ``claims`` / ``recommendations`` / ``calculations``
    sections were well-formed enough to fill at least one dataclass.
    ``errors`` lists every parsing / clamping deviation; empty
    tuple means perfect parse.

    ``raw_text`` is the original input (for the audit log).
    """

    response: ClaimAwareResponse | None
    errors: tuple[str, ...] = field(default_factory=tuple)
    raw_text: str = ""

    @property
    def ok(self) -> bool:
        """True iff a :class:`ClaimAwareResponse` was materialised."""
        return self.response is not None


# --------------------------------------------------------------------------- #
# Fence + JSON extraction (mirrors response_schema helpers)
# --------------------------------------------------------------------------- #


_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```\s*$", re.MULTILINE)


def _extract_json(text: str) -> Any:
    """Return the first balanced top-level JSON object in ``text``.

    LLMs commonly wrap JSON in prose + fences. We strip the fence,
    try ``json.loads``, and on failure walk the depth for the first
    balanced ``{...}``.
    """
    cleaned = _FENCE_RE.sub("", text).strip()
    try:
        return json.loads(cleaned)
    except (ValueError, TypeError):
        pass
    start = cleaned.find("{")
    if start < 0:
        return None
    depth = 0
    in_str = False
    escape = False
    for i in range(start, len(cleaned)):
        c = cleaned[i]
        if escape:
            escape = False
            continue
        if c == "\\":
            escape = True
            continue
        if c == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(cleaned[start:i + 1])
                except (ValueError, TypeError):
                    return None
    return None


def extract_claim_aware_block(parsed_response: Any) -> Any:
    """Return the ``claim_aware`` sub-payload from a parsed LLM response.

    The LLM emits a top-level JSON object that may or may not contain
    a ``claim_aware`` key. When the key is absent, the function
    returns ``None`` (not raises) so callers fall back to the
    existing ``GroundedResponse`` flow.
    """
    if not isinstance(parsed_response, dict):
        return None
    block = parsed_response.get("claim_aware")
    if isinstance(block, dict):
        return block
    return None


# --------------------------------------------------------------------------- #
# Public parser
# --------------------------------------------------------------------------- #


# Server-stamped fields the LLM may NOT author. The parser strips
# these from the LLM payload so a model that emits
# ``server_confidence=100`` cannot override the deterministic
# calculator.
_SERVER_FIELDS = frozenset(
    {
        "server_confidence",
        "server_confidence_rationale",
        "numeric_conflicts",
        "server_audit",
    }
)


def parse_claim_aware_payload(raw_text: Any) -> ClaimAwareValidationResult:
    """Parse the LLM's ``claim_aware`` payload.

    Returns a :class:`ClaimAwareValidationResult` whose ``response``
    is ``None`` when:
      * ``raw_text`` is empty / not a string / not a parseable dict.
      * ``raw_text`` parses but does not look like a claim-aware
        object (no ``claims``, ``recommendations``, ``calculations``,
        ``scenarios``, or ``unknowns`` field — at minimum one is
        required for the envelope to be considered authorable).

    The parser clamps text lengths, drops malformed entries, and
    strips server-stamped fields. It never raises.
    """
    raw = raw_text if isinstance(raw_text, str) else ""
    if not raw.strip():
        return ClaimAwareValidationResult(
            response=None, errors=("empty claim_aware payload",), raw_text=raw,
        )
    parsed = _extract_json(raw)
    if not isinstance(parsed, dict):
        return ClaimAwareValidationResult(
            response=None,
            errors=("claim_aware payload is not a JSON object",),
            raw_text=raw,
        )
    errors: list[str] = []

    # ---- claims ---------------------------------------------------- #
    claims_raw = parsed.get("claims") or []
    if not isinstance(claims_raw, list):
        errors.append("claims is not a list")
        claims_raw = []
    claims: list[Claim] = []
    for item in claims_raw[:32]:
        if not isinstance(item, dict):
            continue
        text = clamp_text(item.get("text"), "claim.text", errors)
        if not text:
            continue
        ctype = str(item.get("claim_type") or "UNKNOWN").upper()
        if ctype not in ALLOWED_CLAIM_TYPES:
            ctype = "UNKNOWN"
        refs_raw = item.get("evidence_references") or []
        if not isinstance(refs_raw, list):
            refs_raw = []
        refs = tuple(str(r) for r in refs_raw[:16])
        conf = clamp_confidence(item.get("confidence"), "claim.confidence", errors)
        user_provided = bool(item.get("user_provided"))
        claims.append(Claim(
            text=text,
            claim_type=ctype,
            evidence_references=refs,
            confidence=conf,
            user_provided=user_provided,
        ))

    # ---- recommendations ----------------------------------------- #
    recs_raw = parsed.get("recommendations") or []
    if not isinstance(recs_raw, list):
        errors.append("recommendations is not a list")
        recs_raw = []
    recommendations: list[ClaimRecommendation] = []
    for item in recs_raw[:16]:
        if not isinstance(item, dict):
            continue
        title = clamp_text(item.get("title"), "recommendation.title", errors)
        reason = clamp_text(item.get("reason"), "recommendation.reason", errors)
        if not title and not reason:
            continue
        rid = clamp_text(
            item.get("recommendation_id"), "recommendation.id", errors,
        )
        refs_raw = item.get("evidence_references") or []
        if not isinstance(refs_raw, list):
            refs_raw = []
        refs = tuple(str(r) for r in refs_raw[:16])
        category = clamp_text(item.get("category"), "recommendation.category", errors)
        priority = clamp_text(item.get("priority"), "recommendation.priority", errors)
        sg = item.get("estimated_score_gain")
        try:
            sg_n = int(sg) if sg is not None else None
            if sg_n is not None and (sg_n < 0 or sg_n > 100):
                sg_n = None
                errors.append("recommendation.estimated_score_gain out of range")
        except (TypeError, ValueError):
            sg_n = None
        timeline = clamp_text(
            item.get("estimated_timeline"),
            "recommendation.estimated_timeline",
            errors,
        )
        recommendations.append(ClaimRecommendation(
            title=title,
            reason=reason,
            recommendation_id=rid,
            evidence_references=refs,
            category=category,
            priority=priority,
            estimated_score_gain=sg_n,
            estimated_timeline=timeline,
        ))

    # ---- calculations --------------------------------------------- #
    calcs_raw = parsed.get("calculations") or []
    if not isinstance(calcs_raw, list):
        errors.append("calculations is not a list")
        calcs_raw = []
    calculations: list[ClaimCalculation] = []
    for item in calcs_raw[:16]:
        if not isinstance(item, dict):
            continue
        name = clamp_text(item.get("name"), "calculation.name", errors)
        if not name:
            continue
        try:
            result = float(item.get("result") or 0)
        except (TypeError, ValueError):
            errors.append("calculation.result not a number")
            continue
        unit = clamp_text(item.get("unit"), "calculation.unit", errors)
        source = str(item.get("source") or "").upper()
        expression = clamp_text(
            item.get("expression"), "calculation.expression", errors,
        )
        inputs = item.get("inputs") if isinstance(item.get("inputs"), dict) else {}
        refs_raw = item.get("evidence_references") or []
        if not isinstance(refs_raw, list):
            refs_raw = []
        refs = tuple(str(r) for r in refs_raw[:16])
        calculations.append(ClaimCalculation(
            name=name,
            result=result,
            unit=unit,
            source=source,
            expression=expression,
            inputs=inputs,
            evidence_references=refs,
        ))

    # ---- scenarios ------------------------------------------------- #
    scenarios_raw = parsed.get("scenarios") or []
    if not isinstance(scenarios_raw, list):
        errors.append("scenarios is not a list")
        scenarios_raw = []
    scenarios: list[ClaimScenario] = []
    for item in scenarios_raw[:16]:
        if not isinstance(item, dict):
            continue
        title = clamp_text(item.get("title"), "scenario.title", errors)
        desc = clamp_text(
            item.get("description"), "scenario.description", errors,
        )
        if not title and not desc:
            continue
        assumptions = tuple(
            clamp_text(a, "scenario.assumption", errors)
            for a in (item.get("assumptions") or [])
            if isinstance(a, str)
        )
        rev = clamp_text(
            item.get("revenue_impact"), "scenario.revenue_impact", errors,
        )
        sci = clamp_text(
            item.get("score_impact"), "scenario.score_impact", errors,
        )
        conf = clamp_confidence(
            item.get("confidence"), "scenario.confidence", errors,
        )
        refs_raw = item.get("evidence_references") or []
        if not isinstance(refs_raw, list):
            refs_raw = []
        refs = tuple(str(r) for r in refs_raw[:16])
        scenarios.append(ClaimScenario(
            title=title,
            description=desc,
            assumptions=assumptions,
            revenue_impact=rev,
            score_impact=sci,
            confidence=conf,
            evidence_references=refs,
        ))

    # ---- unknowns -------------------------------------------------- #
    unknowns_raw = parsed.get("unknowns") or []
    if not isinstance(unknowns_raw, list):
        errors.append("unknowns is not a list")
        unknowns_raw = []
    unknowns: list[ClaimUnknown] = []
    for item in unknowns_raw[:16]:
        if not isinstance(item, dict):
            continue
        question = clamp_text(item.get("question"), "unknown.question", errors)
        if not question:
            continue
        impact = str(item.get("impact") or "MEDIUM").upper()
        if impact not in ("HIGH", "MEDIUM", "LOW"):
            impact = "MEDIUM"
        rationale = clamp_text(
            item.get("rationale"), "unknown.rationale", errors,
        )
        clarif = clamp_text(
            item.get("clarification_prompt"),
            "unknown.clarification_prompt",
            errors,
        )
        unknowns.append(ClaimUnknown(
            question=question,
            impact=impact,
            rationale=rationale,
            clarification_prompt=clarif,
        ))

    # ---- top-level scalars ---------------------------------------- #
    answer = clamp_text(parsed.get("answer"), "answer", errors)
    evidence_references = clamp_string_list(
        parsed.get("evidence_references"), "evidence_references", errors,
    )
    assumptions = clamp_string_list(
        parsed.get("assumptions"), "assumptions", errors,
    )
    limitations = clamp_string_list(
        parsed.get("limitations"), "limitations", errors,
    )
    narrative = clamp_text(parsed.get("narrative"), "narrative", errors)

    # The envelope is non-empty only when at least one structured
    # section has data. We don't insist on all five — the LLM may
    # legitimately omit some — but a payload with everything empty
    # isn't worth the wire bytes.
    if not (
        claims or recommendations or calculations or scenarios or unknowns
    ):
        # Still emit an envelope — the LLM might only have filled
        # ``answer`` / ``narrative`` / ``assumptions`` /
        # ``limitations``. Preserve it as long as one of those is
        # non-empty.
        if not (answer or narrative or assumptions or limitations):
            return ClaimAwareValidationResult(
                response=None,
                errors=tuple(errors + ("claim_aware payload is empty",)),
                raw_text=raw,
            )

    response = ClaimAwareResponse(
        answer=answer,
        claims=tuple(claims),
        recommendations=tuple(recommendations),
        calculations=tuple(calculations),
        scenarios=tuple(scenarios),
        unknowns=tuple(unknowns),
        evidence_references=evidence_references,
        assumptions=assumptions,
        limitations=limitations,
        narrative=narrative,
    )
    return ClaimAwareValidationResult(
        response=response,
        errors=tuple(errors),
        raw_text=raw,
    )


__all__ = [
    "ClaimAwareValidationResult",
    "extract_claim_aware_block",
    "parse_claim_aware_payload",
]
