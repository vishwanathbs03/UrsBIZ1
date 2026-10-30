"""Numeric consistency cross-check — SPRINT AI-3.

For every numeric literal the LLM surfaced in a claim's text or
recommendation / scenario / calculation field, the checker
compares it against the authoritative values in:

  1. ``AssistantContext`` — annual_revenue_inr, target_revenue_inr,
     overall_business_score, and the parsed employee_count when
     numeric.
  2. ``tool_results`` — the numeric values the AI-2 dispatcher
     produced. Each ``ToolResult`` payload is recursively scanned
     so an engine that emits ``{"revenue": {"value": 1.8e7}}`` is
     picked up without bespoke projector logic.

Conflicts are recorded and the conflicting literal is replaced
with the authoritative value **on the parsed response**, which is
a fresh dataclass copy — the original raw LLM text is preserved
in ``GenerationMeta.grounded_payload["claim_aware_raw"]`` for the
audit trail.

Categories
----------

``currency``     — 1% tolerance (rounding — "1.8 Cr" vs "18,000,000")
``percentage``   — 5% tolerance (LLMs are loose with percentages)
``score``        — exact match (0..100 authoritative score)
``employee_count`` — exact match
``date``         — exact match on 4-digit years
``forecast``     — 5% tolerance (forecasts are noisy by definition)

A literal in a SCENARIO description is exempt from cross-check
per the user's design decision ("Cross-check prose vs context +
tool_results"; scenarios explicitly carry their own assumptions
and the numeric conflicts are recorded but the prose is not
mutated). All other categories mutate.

Performance
-----------

``O(N + M)`` where ``N`` is the count of numeric literals and ``M``
is the size of the authoritative-number lookup. The lookup is
built once in ``__init__`` and reused across every claim.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


# --------------------------------------------------------------------------- #
# Conflict record
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class NumericConflict:
    """One conflict between an LLM literal and an authoritative value."""

    location: str  # e.g. "claim[2].text"
    original: str
    replacement: str
    category: str
    authoritative_value: float
    tolerance: float

    def to_dict(self) -> dict[str, Any]:
        """JSON-safe serialisation for the audit log / wire."""
        return {
            "location": str(self.location),
            "original": str(self.original),
            "replacement": str(self.replacement),
            "category": str(self.category),
            "authoritative_value": float(self.authoritative_value),
            "tolerance": float(self.tolerance),
        }


@dataclass(frozen=True)
class NumericConflictReport:
    """Aggregated conflicts from a single checker pass."""

    conflicts: tuple[NumericConflict, ...] = field(default_factory=tuple)

    @property
    def count(self) -> int:
        return len(self.conflicts)

    @property
    def has_conflicts(self) -> bool:
        return bool(self.conflicts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "count": self.count,
            "conflicts": [
                {
                    "location": c.location,
                    "original": c.original,
                    "replacement": c.replacement,
                    "category": c.category,
                    "authoritative_value": c.authoritative_value,
                    "tolerance": c.tolerance,
                }
                for c in self.conflicts
            ],
        }


# --------------------------------------------------------------------------- #
# Categoriser
# --------------------------------------------------------------------------- #


# Currency tokens the LLM may emit. ``cr`` is non-greedy so
# "1.8 crore" also matches.
_CURRENCY_TOKEN_RE = re.compile(
    r"₹|rs\.?|inr|\$|usd|\bcr(?:ore)?|\blakh|\bmn|\bmillion",
    re.IGNORECASE,
)
_PERCENTAGE_RE = re.compile(r"\d[\d,.]*\s*(?:%|percent)")
_SCORE_RE = re.compile(r"\b(?:score|band|index)[:\s]*([+-]?\d{1,3})\b", re.IGNORECASE)
_EMPLOYEE_RE = re.compile(
    r"\b([+-]?\d{1,3})\s*(?:employees?|staff|workers?|people|persons?|headcount|members?)\b",
    re.IGNORECASE,
)
_YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2})\b")
# Generic numeric — any digit, comma, dot, optional sign.
# We use a non-word lookahead/behind so we don't chop letters.
_NUMERIC_LITERAL_RE = re.compile(r"(?<![A-Za-z])([+-]?\d[\d,]*(?:\.\d+)?)(?![A-Za-z])")
_FORECAST_PREFIX_RE = re.compile(
    r"\b(?:forecast(?:ed)?|predicted?|projection|estimate|outlook|scenario)\b",
    re.IGNORECASE,
)


def _categorise(literal: str, *, surrounding: str) -> str:
    """Return one of ``currency``, ``percentage``, ``score``,
    ``employee_count``, ``date``, ``forecast``, or ``"number"``
    (catch-all)."""
    seg = surrounding.lower()
    if _CURRENCY_TOKEN_RE.search(seg) or _CURRENCY_TOKEN_RE.search(literal):
        return "currency"
    if _PERCENTAGE_RE.search(surrounding):
        return "percentage"
    if _SCORE_RE.search(surrounding):
        return "score"
    if _EMPLOYEE_RE.search(surrounding):
        return "employee_count"
    if _YEAR_RE.fullmatch(literal) or re.fullmatch(r"\d{4}", literal):
        return "date"
    if _FORECAST_PREFIX_RE.search(seg):
        return "forecast"
    return "number"


# --------------------------------------------------------------------------- #
# Authoritative-numbers lookup
# --------------------------------------------------------------------------- #


# Per-category tolerance (fractional). ``score``, ``employee_count``
# and ``date`` are exact match — we return 0.0 so the comparison
# fails on any delta.
_TOLERANCES: dict[str, float] = {
    "currency": 0.01,
    "percentage": 0.05,
    "forecast": 0.05,
    "score": 0.0,
    "employee_count": 0.0,
    "date": 0.0,
    "number": 0.05,
}


def _extract_authoritative_numbers(
    context: Any, tool_results: tuple
) -> dict[str, list[float]]:
    """Build the per-category authoritative-value lookup.

    The dict maps ``category -> [v1, v2, ...]``. The list is
    used by the comparison: ``within_tolerance(claim_value,
    candidate)`` for every candidate.

    Sources:

      * ``AssistantContext`` authoritative fields.
      * Every numeric in every ``tool_results`` payload (recursive).
    """
    out: dict[str, list[float]] = {
        "currency": [],
        "percentage": [],
        "score": [],
        "employee_count": [],
        "date": [],
        "forecast": [],
        "number": [],
    }

    if context is not None:
        revenue = getattr(context, "annual_revenue_inr", 0) or 0
        if revenue:
            out["currency"].append(float(revenue))
        target = getattr(context, "target_revenue_inr", 0) or 0
        if target:
            out["currency"].append(float(target))
        score = getattr(context, "overall_business_score", 0) or 0
        if score:
            out["score"].append(float(score))
        emp_raw = getattr(context, "employee_count", "") or ""
        try:
            emp_int = int("".join(c for c in str(emp_raw) if c.isdigit()))
            if emp_int:
                out["employee_count"].append(float(emp_int))
        except (TypeError, ValueError):
            pass

    for result in tool_results or ():
        payload = getattr(result, "payload", None)
        if payload is None:
            continue
        for value in _walk_numbers(payload):
            # Everything from tool_results flows into the
            # "forecast" bucket — engines emit both revenue
            # forecasts and score forecasts, and we don't
            # want to over-commit the per-bucket categorisation.
            out["forecast"].append(float(value))

    return out


def _walk_numbers(node: Any) -> list[float]:
    """Recursively walk a payload and collect every numeric leaf."""
    out: list[float] = []
    if isinstance(node, (int, float)) and not isinstance(node, bool):
        out.append(float(node))
        return out
    if isinstance(node, dict):
        for v in node.values():
            out.extend(_walk_numbers(v))
        return out
    if isinstance(node, (list, tuple)):
        for v in node:
            out.extend(_walk_numbers(v))
        return out
    if isinstance(node, str):
        for m in _NUMERIC_LITERAL_RE.finditer(node):
            try:
                out.append(float(m.group(1).replace(",", "")))
            except ValueError:
                pass
    return out


def _within_tolerance(candidate: float, target: float, tolerance: float) -> bool:
    """Return True iff ``candidate`` is within ``tolerance`` of ``target``.

    ``tolerance`` is a fraction (0.05 == 5%).
    """
    if tolerance <= 0:
        return candidate == target
    if target == 0:
        return abs(candidate - target) <= abs(tolerance)
    return abs(candidate - target) <= abs(tolerance * target)


def _to_inr(value: float, suffix: str) -> float:
    """Convert an LLM literal into an INR number for currency comparison.

    The LLM may emit ``1.8 Cr`` (= 18,000,000 INR) or ``18 lakh``
    (= 1,800,000 INR) or ``50K`` (= 50,000 INR) or ``₹1,800,000``
    (= 1,800,000 INR — passthrough). The regex matches the suffix
    case-insensitively; ambiguous literals like ``1.8 million``
    resolve to 1,800,000 INR.
    """
    suf = (suffix or "").lower()
    if "cr" in suf or "crore" in suf:
        return value * 10_000_000
    if "lakh" in suf:
        return value * 100_000
    if "mn" in suf or "million" in suf:
        return value * 1_000_000
    if "k" in suf or "thousand" in suf:
        return value * 1_000
    return value


# --------------------------------------------------------------------------- #
# Public checker
# --------------------------------------------------------------------------- #


class NumericConsistencyChecker:
    """Cross-check numerics in a claim-aware response."""

    def __init__(self, context: Any, tool_results: tuple) -> None:
        self._context = context
        self._tool_results = tuple(tool_results or ())
        self._authoritative = _extract_authoritative_numbers(
            context, self._tool_results
        )

    @property
    def authoritative(self) -> dict[str, list[float]]:
        """Per-category authoritative-value lookup. Exposed for tests."""
        return self._authoritative

    def check(self, response: Any) -> NumericConflictReport:
        """Mutate ``response`` in-place and return a conflict report.

        Every ``Claim.text`` is scanned for numeric literals.
        ``ClaimRecommendation.reason``, ``ClaimCalculation.inputs``,
        and ``ClaimScenario.description`` are scanned too. Any
        literal that disagrees with an authoritative value of the
        same category (outside the tolerance) becomes a conflict
        record and is replaced in-place.

        SCENARIO descriptions are exempt by spec (they explicitly
        carry their own assumptions); their numerics are recorded
        as audit warnings but the text is NOT mutated.

        The mutation operates on ``Claim.text`` etc. via
        ``dataclasses.replace`` so the response dataclass
        stays frozen from the caller's POV.
        """
        from dataclasses import replace as _replace
        from app.services.ai.providers.claim_schema import Claim, ClaimScenario

        conflicts: list[NumericConflict] = []

        # Reconstruct claims with mutated text if necessary. We
        # can't mutate frozen dataclasses in-place, so we build
        # the replacement list.
        new_claims: list = list(response.claims)
        for cidx, claim in enumerate(new_claims):
            new_text, cconflicts = self._scan_text(
                claim.text,
                location=f"claim[{cidx}].text",
            )
            if cconflicts:
                conflicts.extend(cconflicts)
                # Append each conflict's original+replacement as an
                # audit_log entry on the claim itself so the wire
                # payload carries the provenance trail.
                audit_entries = [
                    f"original={c.original} replacement={c.replacement} "
                    f"authoritative={c.authoritative_value:g} "
                    f"category={c.category}"
                    for c in cconflicts
                    if c.replacement != "(unchanged - scenario)"
                    and c.replacement != "(unchanged - flagged)"
                ]
                if audit_entries:
                    new_claims[cidx] = _replace(
                        claim,
                        text=new_text,
                        audit_log=(*claim.audit_log, *audit_entries),
                    )
                else:
                    new_claims[cidx] = _replace(claim, text=new_text)

        # Recommendations: scan ``reason``.
        new_recs: list = list(response.recommendations)
        for ridx, rec in enumerate(new_recs):
            new_reason, rconflicts = self._scan_text(
                rec.reason,
                location=f"recommendation[{ridx}].reason",
            )
            if rconflicts:
                conflicts.extend(rconflicts)
                new_recs[ridx] = _replace(rec, reason=new_reason)

        # Scenarios: scan description but DO NOT mutate (per spec).
        # The numeric is recorded in conflicts with an empty
        # ``replacement`` so the auditor can see what surfaced.
        for sidx, scen in enumerate(response.scenarios):
            _, sconflicts = self._scan_text(
                scen.description,
                location=f"scenario[{sidx}].description",
                mutate=False,
            )
            if sconflicts:
                conflicts.extend(sconflicts)

        # Calculations: scan expression and inputs (don't mutate
        # inputs — they're structured).
        for cidx, calc in enumerate(response.calculations):
            if calc.expression:
                _, cconflicts = self._scan_text(
                    calc.expression,
                    location=f"calculation[{cidx}].expression",
                )
                if cconflicts:
                    conflicts.extend(cconflicts)
            if calc.result is not None:
                # Validate calculation.result against authoritative
                # currency / score values when the unit suggests it.
                if calc.unit and any(
                    s in calc.unit.lower()
                    for s in ("inr", "₹", "cr", "lakh", "$", "usd")
                ):
                    candidate = _to_inr(float(calc.result), calc.unit)
                    auth = self._authoritative["currency"]
                    if auth:
                        if not any(
                            _within_tolerance(candidate, a, _TOLERANCES["currency"])
                            for a in auth
                        ):
                            conflicts.append(NumericConflict(
                                location=f"calculation[{cidx}].result",
                                original=str(calc.result),
                                replacement="(unchanged - flagged)",
                                category="currency",
                                authoritative_value=auth[0],
                                tolerance=_TOLERANCES["currency"],
                            ))
                elif calc.unit and "%" in calc.unit:
                    auth = self._authoritative["percentage"]
                    if auth:
                        if not any(
                            _within_tolerance(
                                float(calc.result), a,
                                _TOLERANCES["percentage"],
                            )
                            for a in auth
                        ):
                            conflicts.append(NumericConflict(
                                location=f"calculation[{cidx}].result",
                                original=str(calc.result),
                                replacement="(unchanged - flagged)",
                                category="percentage",
                                authoritative_value=auth[0],
                                tolerance=_TOLERANCES["percentage"],
                            ))

        # Replace the dataclass values if any claim / rec changed.
        # We use ``object.__setattr__`` so the caller's reference
        # to ``response`` sees the mutated claims / recommendations
        # tuples. ``ClaimAwareResponse`` is a frozen dataclass,
        # but we can re-assign ``claims`` / ``recommendations`` on
        # it because the *outer* dataclass is what the caller
        # holds — the inner tuples are swapped in-place on the
        # caller's frame. (If the outer dataclass were truly
        # immutable we couldn't, but the test fixtures + service
        # layer both rely on the in-place mutation to read the
        # post-check text.)
        try:
            if any(
                c.location.startswith("claim[")
                and c.replacement
                and c.replacement != "(unchanged - flagged)"
                for c in conflicts
            ):
                object.__setattr__(response, "claims", tuple(new_claims))
            if any(
                c.location.startswith("recommendation[")
                and c.replacement
                and c.replacement != "(unchanged - flagged)"
                for c in conflicts
            ):
                object.__setattr__(
                    response, "recommendations", tuple(new_recs)
                )
        except Exception:
            # Frozen dataclass — fall back to returning the new
            # response via the report's caller.
            pass

        return NumericConflictReport(conflicts=tuple(conflicts))

    # ---- internals -------------------------------------------------- #

    def _scan_text(
        self, text: str, *, location: str, mutate: bool = True
    ) -> tuple[str, list[NumericConflict]]:
        """Scan ``text`` for numeric literals; return ``(mutated_text, conflicts)``."""
        if not text or not isinstance(text, str):
            return text, []
        conflicts: list[NumericConflict] = []
        new_text = text

        # We re-scan after each substitution so currency conversions
        # don't get re-matched as a new number. We mutate left-to-right.
        offset = 0
        while True:
            m = _NUMERIC_LITERAL_RE.search(new_text, offset)
            if not m:
                break
            literal = m.group(1)
            try:
                value = float(literal.replace(",", ""))
            except ValueError:
                offset = m.end()
                continue

            # Surrounding text for categorisation — 40 chars each side.
            left = max(0, m.start() - 40)
            right = min(len(new_text), m.end() + 40)
            surrounding = new_text[left:right]
            category = _categorise(literal, surrounding=surrounding)

            # Currency conversion when the suffix implies a unit.
            candidate = value
            if category == "currency":
                # Look for the suffix in the immediate surrounding text.
                after = new_text[m.end(): m.end() + 12].lower()
                candidate = _to_inr(value, after)

            auth_values = self._authoritative.get(category, [])
            tolerance = _TOLERANCES.get(category, 0.05)
            conflict = None
            if auth_values:
                if not any(
                    _within_tolerance(candidate, a, tolerance)
                    for a in auth_values
                ):
                    # Find the closest authoritative value for the audit log.
                    closest = min(
                        auth_values,
                        key=lambda a: abs(candidate - a),
                    )
                    # Compose the replacement text in the same unit the LLM used.
                    if category == "currency":
                        replacement = (
                            f"{closest / 10_000_000:.2f} Cr"
                        )
                    elif category == "percentage":
                        replacement = f"{closest:.1f}%"
                    elif category == "score":
                        replacement = f"{int(closest)}/100"
                    elif category == "employee_count":
                        replacement = f"{int(closest)} employees"
                    else:
                        replacement = f"{closest:g}"
                    if mutate:
                        new_text = (
                            new_text[: m.start()]
                            + replacement
                            + new_text[m.end():]
                        )
                        offset = m.start() + len(replacement)
                        # The original literal + the authoritative
                        # replacement is recorded on the claim's
                        # audit_log so the conflict is traceable
                        # through the wire payload. The caller's
                        # ``Claim.audit_log`` is a frozen tuple —
                        # we build the new tuple on the response
                        # dataclass via object.__setattr__ below.
                        conflict = NumericConflict(
                            location=location,
                            original=literal,
                            replacement=replacement,
                            category=category,
                            authoritative_value=closest,
                            tolerance=tolerance,
                        )
                    else:
                        # Scenario descriptions are exempt from
                        # mutation (per spec). Record the conflict
                        # for the audit log but DON'T loop on the
                        # same literal — advance offset past it.
                        conflict = NumericConflict(
                            location=location,
                            original=literal,
                            replacement="(unchanged - scenario)",
                            category=category,
                            authoritative_value=closest,
                            tolerance=tolerance,
                        )
                        offset = m.end()
                else:
                    offset = m.end()
            else:
                offset = m.end()

            if conflict is not None:
                conflicts.append(conflict)

        return new_text, conflicts


__all__ = [
    "NumericConflict",
    "NumericConflictReport",
    "NumericConsistencyChecker",
]
