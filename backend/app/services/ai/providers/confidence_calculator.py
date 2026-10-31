"""Deterministic server-confidence calculator — SPRINT AI-3.

The confidence score surfaced on the wire is ALWAYS the result
of this formula. The LLM's self-reported confidence is recorded
in the audit JSON (``GenerationMeta.grounded_payload``) for
transparency but never overrides the server.

Formula
-------

::

    base                              30  — baseline floor
    + evidence_coverage * 20         max 20
    + source_authority * 15          max 15
    + freshness * 5                   max  5
    - assumption_count * 2            max -10
    + calculation_availability * 10   max 10
    - missing_data_penalty * 5        max  -5
    - contradiction_penalty * 10     max -10

  Total = base + evidence_coverage_score
                  + source_authority_score
                  + freshness_score
                  - assumption_penalty
                  + calculation_availability_score
                  - missing_data_penalty
                  - contradiction_penalty

The total is clamped to ``[0, 100]``. The 3 strongest
contributions (positive or negative) are listed in the rationale
string so the audit log answers "why did this score what it did"
in one line.

Per-component weights and inputs
-------------------------------

| Component                  | Weight | Inputs                                                       |
|----------------------------|--------|--------------------------------------------------------------|
| ``base``                   | 30     | constant                                                     |
| ``evidence_coverage``      | max 20 | ``cited_refs / registry_count`` × 20                         |
| ``source_authority``       | max 15 | registry kind mix: score/forecast 1.0; recommendation/rule 0.8; insight/action 0.5; scheme 0.3 |
| ``freshness``              | max 5  | newest sidecar in <24h: 5; <7d: 3; <30d: 1; older: 0        |
| ``assumption_count``       | -2 each | caps at -10                                                 |
| ``calculation_availability``| max 10 | ``tool_results OK / total dispatched`` × 10                  |
| ``missing_data_penalty``   | -2 per HIGH-impact unknown, capped at -5                     |
| ``contradiction_penalty``  | -3 per numeric conflict, capped at -10                       |
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


# --------------------------------------------------------------------------- #
# Report
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ConfidenceReport:
    """The calculator's output.

    ``score`` is the integer 0..100 the wire carries. ``components``
    is the per-component contribution (positive or negative) so an
    auditor can see which move dominated. ``rationale`` is the
    one-line English summary joining the three strongest contributors.
    """

    score: int
    components: dict[str, float]
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": int(self.score),
            "components": {
                k: float(v) for k, v in self.components.items()
            },
            "rationale": self.rationale,
        }


# --------------------------------------------------------------------------- #
# Calculator
# --------------------------------------------------------------------------- #


# Per-kind authority weight (used in source_authority).
_KIND_WEIGHTS: dict[str, float] = {
    "score": 1.0,
    "forecast": 1.0,
    "recommendation": 0.8,
    "rule": 0.8,
    "insight": 0.5,
    "action": 0.5,
    "scheme": 0.3,
    "dna": 0.4,
}


class ConfidenceCalculator:
    """Deterministic confidence calculator."""

    BASE: int = 30
    EVIDENCE_COVERAGE_CAP: int = 20
    SOURCE_AUTHORITY_CAP: int = 15
    FRESHNESS_CAP: int = 5
    ASSUMPTION_PENALTY_CAP: int = -10
    CALC_AVAILABILITY_CAP: int = 10
    MISSING_DATA_PENALTY_CAP: int = -5
    CONTRADICTION_PENALTY_CAP: int = -10

    def compute(
        self,
        *,
        context: Any = None,
        tool_results: tuple = (),
        registry: Any = None,
        claim_response: Any = None,
        claim_report: Any = None,
        numeric_report: Any = None,
    ) -> ConfidenceReport:
        """Compute the score from the documented formula.

        ``context`` is the :class:`AssistantContext`. ``registry``
        is an :class:`EvidenceRegistry`. ``claim_response`` is the
        parsed :class:`ClaimAwareResponse` (None when the LLM
        didn't fill the new schema). ``claim_report`` is the
        :class:`ClaimValidationReport`. ``numeric_report`` is the
        :class:`NumericConflictReport`. ``tool_results`` is the
        tuple the AI-2 dispatcher returned.
        """
        components: dict[str, float] = {}

        # 1. base ----------------------------------------------------- #
        components["base"] = float(self.BASE)

        # 2. evidence_coverage --------------------------------------- #
        components["evidence_coverage"] = self._evidence_coverage(
            claim_response, registry
        )

        # 3. source_authority ---------------------------------------- #
        components["source_authority"] = self._source_authority(registry)

        # 4. freshness ----------------------------------------------- #
        components["freshness"] = self._freshness(context)

        # 5. assumption_count (penalty) ------------------------------ #
        components["assumption_penalty"] = self._assumption_penalty(
            claim_response
        )

        # 6. calculation_availability -------------------------------- #
        components["calculation_availability"] = self._calculation_availability(
            tool_results
        )

        # 7. missing_data_penalty ------------------------------------ #
        components["missing_data_penalty"] = self._missing_data_penalty(
            claim_response
        )

        # 8. contradiction_penalty ----------------------------------- #
        components["contradiction_penalty"] = self._contradiction_penalty(
            numeric_report, claim_report
        )

        total = sum(components.values())
        score = max(0, min(100, int(round(total))))
        rationale = self._rationale(components, score)
        return ConfidenceReport(
            score=score, components=components, rationale=rationale,
        )

    # ---- per-component helpers ------------------------------------ #

    def _evidence_coverage(self, claim_response: Any, registry: Any) -> float:
        if registry is None:
            return 0.0
        total = int(getattr(registry, "count", 0) or 0)
        if not total:
            return 0.0
        cited: set[str] = set()
        if claim_response is not None:
            for claim in getattr(claim_response, "claims", ()) or ():
                for ref in getattr(claim, "evidence_references", ()) or ():
                    cited.add(str(ref))
            for rec in getattr(claim_response, "recommendations", ()) or ():
                for ref in getattr(rec, "evidence_references", ()) or ():
                    cited.add(str(ref))
            for calc in getattr(claim_response, "calculations", ()) or ():
                for ref in getattr(calc, "evidence_references", ()) or ():
                    cited.add(str(ref))
            for scen in getattr(claim_response, "scenarios", ()) or ():
                for ref in getattr(scen, "evidence_references", ()) or ():
                    cited.add(str(ref))
        cited = {c for c in cited if registry.has_id(c)}
        if not cited:
            return 0.0
        ratio = min(1.0, len(cited) / max(1, total))
        return min(
            float(self.EVIDENCE_COVERAGE_CAP),
            ratio * self.EVIDENCE_COVERAGE_CAP,
        )

    def _source_authority(self, registry: Any) -> float:
        if registry is None:
            return 0.0
        total = 0
        weighted_sum = 0.0
        for entry in registry.all() or ():
            kind = getattr(getattr(entry, "kind", None), "value", None) or str(entry.kind)
            weight = _KIND_WEIGHTS.get(str(kind).lower(), 0.5)
            total += 1
            weighted_sum += weight
        if not total:
            return 0.0
        avg_weight = weighted_sum / total
        return min(
            float(self.SOURCE_AUTHORITY_CAP),
            avg_weight * self.SOURCE_AUTHORITY_CAP,
        )

    def _freshness(self, context: Any) -> float:
        if context is None:
            return 0.0
        timestamps: list[str] = []
        for attr in (
            "twin_generated_at",
            "recommendations_generated_at",
            "roadmap_generated_at",
            "rules_generated_at",
            "insights_generated_at",
            "schemes_generated_at",
            "forecasts_generated_at",
            "action_items_generated_at",
        ):
            value = getattr(context, attr, None)
            if isinstance(value, str) and value:
                timestamps.append(value)
        if not timestamps:
            return 0.0
        # Use the most recent timestamp's bucket.
        newest = max(timestamps)
        try:
            ts = datetime.fromisoformat(newest.replace("Z", "+00:00"))
        except ValueError:
            return 0.0
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        age = datetime.now(tz=timezone.utc) - ts
        seconds = age.total_seconds()
        if seconds < 24 * 3600:
            return float(self.FRESHNESS_CAP)
        if seconds < 7 * 24 * 3600:
            return 3.0
        if seconds < 30 * 24 * 3600:
            return 1.0
        return 0.0

    def _assumption_penalty(self, claim_response: Any) -> float:
        if claim_response is None:
            return 0.0
        # Count every assumption list entry (global + scenario-local).
        count = 0
        for a in getattr(claim_response, "assumptions", ()) or ():
            if a:
                count += 1
        return max(
            float(self.ASSUMPTION_PENALTY_CAP),
            -2.0 * count,
        )

    def _calculation_availability(self, tool_results: tuple) -> float:
        if not tool_results:
            return 0.0
        total = len(tool_results)
        ok = 0
        for r in tool_results or ():
            status = getattr(r, "status", None)
            if status == "ok":
                ok += 1
        ratio = ok / max(1, total)
        return min(
            float(self.CALC_AVAILABILITY_CAP),
            ratio * self.CALC_AVAILABILITY_CAP,
        )

    def _missing_data_penalty(self, claim_response: Any) -> float:
        if claim_response is None:
            return 0.0
        count = 0
        for unk in getattr(claim_response, "unknowns", ()) or ():
            impact = str(getattr(unk, "impact", "") or "").upper()
            if impact == "HIGH":
                count += 1
        return max(
            float(self.MISSING_DATA_PENALTY_CAP),
            -2.0 * count,
        )

    def _contradiction_penalty(
        self, numeric_report: Any, claim_report: Any
    ) -> float:
        # Sum: numeric conflicts * 3 + claim validation errors * 1, capped.
        nconf = 0
        if numeric_report is not None:
            nconf = len(getattr(numeric_report, "conflicts", ()) or ())
        cer = 0
        if claim_report is not None:
            cer = len(getattr(claim_report, "errors", ()) or ())
        penalty = -3.0 * nconf - 1.0 * cer
        return max(float(self.CONTRADICTION_PENALTY_CAP), penalty)

    # ---- rationale ------------------------------------------------ #

    def _rationale(
        self, components: dict[str, float], score: int
    ) -> str:
        """One-line English summary of the 3 strongest contributors."""
        ranked = sorted(
            components.items(),
            key=lambda kv: abs(kv[1]),
            reverse=True,
        )[:3]
        if not ranked:
            return f"score={score}/100"
        bits: list[str] = []
        for k, v in ranked:
            bits.append(f"{k}={v:+.1f}")
        return ", ".join(bits) + f" -> {score}/100"


__all__ = ["ConfidenceCalculator", "ConfidenceReport"]
