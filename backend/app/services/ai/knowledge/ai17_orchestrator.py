"""SPRINT AI-17 — Bounded Answer Repair + Claim Lifecycle.

Top-level orchestrator helper.

The AI-17 pipeline runs AFTER the AI-15 / AI-16 stamping and
BEFORE the message lands on the wire. The pipeline is:

  1. ``classify(...)`` — read the envelope failure signals.
  2. ``repair_deterministic(...)`` — attempt every safe
     deterministic repair; accumulate audit trails.
  3. ``should_retry(...)`` — gate the (single, bounded) retry.
  4. On retry, the caller invokes the provider a second time,
     then re-runs the validators.
  5. ``adjust_confidence(...)`` — apply the brief's penalty
     table.

This module is intentionally small — it composes the AI-17
sub-modules into ONE pure, idempotent helper that the
provider service can call inside its fenced try/except.

The helper NEVER calls the LLM. The retry call is the caller's
responsibility: the orchestrator returns
``retry_recommended=True`` and the caller is the only place
that may invoke ``_call_with_hard_timeout``.
"""

from __future__ import annotations

from typing import Any

from app.services.ai.knowledge.ai17_bounded_retry import (
    build_retry_prompt,
    retry_prompt_audit_text,
    should_retry,
)
from app.services.ai.knowledge.ai17_confidence_adjust import (
    adjust_from_envelopes,
    adjust_confidence,
)
from app.services.ai.knowledge.ai17_deterministic_repair import (
    repair_deterministic,
)
from app.services.ai.knowledge.ai17_numeric_correction_audit import (
    NumericCorrectionAuditLog,
)
from app.services.ai.knowledge.ai17_quality_failure_classifier import (
    classify,
)
from app.services.ai.reasoning.claim_lifecycle import (
    ClaimLifecycleStore,
)

# Hard-cap schema version — every place that stamps the
# version uses this constant so a single grep surfaces all
# wires.
BOUNDED_REPAIR_VERSION: str = "ai17-v1"


def run_ai17_pipeline(
    *,
    payload: Any,
    starting_confidence: int,
    materially_useful: bool,
    budget_remaining_ms: int,
    hard_call_timeout_ms: int,
    retry_already_attempted: bool,
    authoritative_fields: dict[str, Any] | None = None,
    original_prompt: str = "",
    repair_context: str = "",
    upper_bound: int = 100,
) -> dict[str, Any]:
    """Run the full AI-17 pipeline against ``payload``.

    Returns a dict with:

      * ``failure_classification`` — one of 9 classes.
      * ``repaired_payload`` — the post-repair payload (the
        input unchanged when no repair applied).
      * ``applied_repairs`` — tuple of repair names.
      * ``audit_log`` — the :class:`NumericCorrectionAuditLog`.
      * ``lifecycle_store`` — the :class:`ClaimLifecycleStore`.
      * ``retry_recommended`` — boolean; ``True`` iff the
        bounded-retry gate said yes.
      * ``retry_prompt`` — the composed retry message.
      * ``adjusted_confidence`` — post-penalty confidence.
      * ``bounded_repair_version`` — schema version.

    The function is **pure** — no I/O, no LLM call, no clock.
    The orchestrator decides whether to actually fire the
    retry by inspecting ``retry_recommended``.
    """
    failure_class = classify(payload)
    audit_log = NumericCorrectionAuditLog()
    lifecycle_store = ClaimLifecycleStore()

    repair_result = repair_deterministic(
        classification=failure_class,
        payload=payload,
        context=None,
        authoritative_fields=authoritative_fields,
        numeric_audit_log=audit_log,
        lifecycle_store=lifecycle_store,
    )

    retry_decision = should_retry(
        failure_class=failure_class,
        budget_remaining_ms=budget_remaining_ms,
        hard_call_timeout_ms=hard_call_timeout_ms,
        materially_useful=materially_useful,
        retry_already_attempted=retry_already_attempted,
    )

    composed_retry = build_retry_prompt(
        original_prompt=original_prompt,
        failure_class=failure_class,
        repair_applied=repair_result["applied_repairs"],
        extra_context=repair_context,
    )
    prompt_ok, _ = retry_prompt_audit_text(composed_retry)

    adjusted = adjust_from_envelopes(
        starting_confidence=starting_confidence,
        failure_class=failure_class,
        repair_applied=repair_result["applied_repairs"],
        generation_meta=payload,
    )
    # Clamp to upper bound.
    adjusted = max(0, min(upper_bound, int(adjusted or 0)))

    return {
        "failure_classification": failure_class,
        "repaired_payload": repair_result["repaired_payload"],
        "applied_repairs": repair_result["applied_repairs"],
        "audit_log": audit_log,
        "lifecycle_store": lifecycle_store,
        "retry_recommended": bool(retry_decision and prompt_ok),
        "retry_prompt": composed_retry if prompt_ok else "",
        "adjusted_confidence": adjusted,
        "bounded_repair_version": BOUNDED_REPAIR_VERSION,
    }


def stamp_ai17_onto(
    meta: Any,
    *,
    pipeline_result: dict[str, Any],
) -> Any:
    """Stamp the AI-17 fields onto a GenerationMeta (or duck-type).

    Pure helper; no I/O. The caller decides whether to use
    ``dataclasses.replace`` or ``object.__setattr__``.
    """
    # The helper accepts a duck-typed meta so the orchestrator
    # can stamp the same fields on both ``GenerationMeta``
    # dataclass instances and on raw dicts.

    def _set(name: str, value: Any) -> None:
        if isinstance(meta, dict):
            meta[name] = value
        else:
            try:
                object.__setattr__(meta, name, value)
            except Exception:
                # Frozen dataclass: caller must use replace().
                pass

    audit_log: NumericCorrectionAuditLog = pipeline_result["audit_log"]
    lifecycle_store: ClaimLifecycleStore = pipeline_result["lifecycle_store"]

    _set("failure_classification", pipeline_result["failure_classification"])
    _set("repair_applied", tuple(pipeline_result["applied_repairs"] or ()))
    _set(
        "numeric_corrections",
        tuple(r.to_dict() for r in audit_log.rows),
    )
    _set("claim_lifecycle", lifecycle_store.to_dict())
    _set(
        "retry_attempted",
        bool(pipeline_result["retry_recommended"]),
    )
    _set("retry_succeeded", None)
    _set("bounded_repair_version", pipeline_result["bounded_repair_version"])
    return meta


__all__ = [
    "BOUNDED_REPAIR_VERSION",
    "run_ai17_pipeline",
    "stamp_ai17_onto",
]
