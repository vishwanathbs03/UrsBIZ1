"""ToolExecutionTrace — SPRINT AI-13 Production Orchestration.

SPRINT AI-13 mandate: every production tool invocation must be
observable through a deterministic trace record. The trace is
the audit / diagnostics / testing surface — never user-facing
by default.

Each trace record carries:

  * ``tool_name`` — the service the dispatcher invoked (e.g.
    ``"health_score"``, ``"finance"``, ``"predictive_sprint14"``).
  * ``selected`` — True iff the selector put this tool in the
    :class:`ToolPlan` (either required or optional). False for
    "never ran" entries that the test/audit surface wants to
    record as known-skipped.
  * ``executed`` — True iff the dispatcher actually invoked
    ``tool.invoke(...)``. False for kill-switch / disabled /
    short-circuited plans.
  * ``success`` — True iff the :class:`ToolResult.status` is
    ``"ok"``. ``"not_implemented"`` and ``"error"`` are both
    not-success.
  * ``latency_ms`` — wall-clock duration the dispatcher
    observed (0 for stubs, populated for real services).
  * ``result_available`` — True iff the result payload is
    non-empty / non-None. ``"not_implemented"`` stubs return
    ``payload=None`` so this is False for them.
  * ``evidence_ids`` — the evidence IDs the envelope
    derived (or ``()`` when none).
  * ``failure_reason`` — short string describing the failure
    mode (``"stub"``, ``"timeout"``, ``"error"``,
    ``"disabled"``). Empty string on success.
  * ``error_category`` — one of ``"none"``, ``"stub"``,
    ``"timeout"``, ``"exception"``, ``"empty_payload"``.
    Drives the deterministic confidence-down + disclosure
    block consumed by the partial-failure handler.

The trace is built by the dispatcher itself; the conversation
service stamps it onto ``GenerationMeta`` (new field
``tool_execution_traces``) so the wire mirror surfaces it for
the frontend trust UX.

The trace does NOT expose internal implementation details
(stack traces, file paths, API keys). It is intentionally
short, structured, and free-form-text-free.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


# --------------------------------------------------------------------------- #
# Failure category vocabulary
# --------------------------------------------------------------------------- #


# Failures are bucketed into 5 categories so the partial-failure
# handler can write a deterministic disclosure block + reduce
# confidence by a fixed amount per category.
ERROR_CATEGORY_NONE = "none"
ERROR_CATEGORY_STUB = "stub"
ERROR_CATEGORY_TIMEOUT = "timeout"
ERROR_CATEGORY_EXCEPTION = "exception"
ERROR_CATEGORY_EMPTY = "empty_payload"

_ERROR_CATEGORIES = frozenset(
    {
        ERROR_CATEGORY_NONE,
        ERROR_CATEGORY_STUB,
        ERROR_CATEGORY_TIMEOUT,
        ERROR_CATEGORY_EXCEPTION,
        ERROR_CATEGORY_EMPTY,
    }
)


# --------------------------------------------------------------------------- #
# ToolExecutionTrace dataclass
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ToolExecutionTrace:
    """A single per-tool execution trace record.

    Frozen dataclass so the trace can be safely shared across
    threads and serialised into the audit trail without
    defensive cloning. ``to_dict()`` is the wire projection.

    Sprint AI-20 — four additive fields drive the
    tool-minimality metric. All default-safe so every
    pre-AI-20 call site round-trips unchanged:

      * ``required_or_optional`` — one of ``"required"``,
        ``"optional"``, ``"unknown"``. Mirrors the
        :class:`ToolPlan` slot the call came from.
      * ``evidence_produced`` — True iff the tool's
        envelope carried a usable payload (i.e. the
        dispatcher recorded
        ``result_available=True``).
      * ``used_in_final_answer`` — True iff at least one
        envelope value/key/finding token appears in the
        assistant's final body. Computed by the
        ``_answer_uses_envelope`` helper.
      * ``failure_status`` — short string for grep
        convenience (``"none"``, ``"stub"``,
        ``"timeout"``, ``"exception"``,
        ``"empty_payload"``). Mirrors
        :attr:`error_category`.
    """

    tool_name: str
    selected: bool
    executed: bool
    success: bool
    latency_ms: int
    result_available: bool
    evidence_ids: tuple[str, ...] = field(default_factory=tuple)
    failure_reason: str = ""
    error_category: str = ERROR_CATEGORY_NONE
    # Sprint AI-20 — additive tool-minimality fields.
    required_or_optional: str = "unknown"
    evidence_produced: bool = False
    used_in_final_answer: bool = False
    failure_status: str = ""

    def to_dict(self) -> dict[str, Any]:
        """JSON-serialisable mirror for the wire."""
        return {
            "tool_name": self.tool_name,
            "selected": self.selected,
            "executed": self.executed,
            "success": self.success,
            "latency_ms": self.latency_ms,
            "result_available": self.result_available,
            "evidence_ids": list(self.evidence_ids),
            "failure_reason": self.failure_reason,
            "error_category": self.error_category,
            # Sprint AI-20 — additive tool-minimality fields.
            "required_or_optional": self.required_or_optional,
            "evidence_produced": self.evidence_produced,
            "used_in_final_answer": self.used_in_final_answer,
            "failure_status": self.failure_status,
        }


# --------------------------------------------------------------------------- #
# Factory — derive a trace from a ToolResult
# --------------------------------------------------------------------------- #


def trace_from_tool_result(
    tool_name: str,
    *,
    selected: bool,
    executed: bool,
    result: Any | None,
    latency_ms: int = 0,
    evidence_ids: tuple[str, ...] = (),
    required_or_optional: str = "unknown",
    final_answer_body: str = "",
    envelope: Any | None = None,
) -> ToolExecutionTrace:
    """Derive a :class:`ToolExecutionTrace` from a tool result.

    The factory classifies the failure category deterministically
    by inspecting ``result.status`` + ``result.payload`` + the
    latency. The mapping is:

    * ``status == "ok"`` + ``payload`` non-empty → success,
      ``error_category="none"``.
    * ``status == "ok"`` + empty payload → success=False,
      ``error_category="empty_payload"`` (the tool ran but
      returned nothing meaningful).
    * ``status == "not_implemented"`` → success=False,
      ``error_category="stub"``.
    * ``status == "skipped"`` → success=False,
      ``error_category="none"`` (the tool deliberately chose
      to skip — not a failure).
    * ``status == "error"`` → success=False,
      ``error_category="timeout"`` when ``error == "timeout"``,
      else ``"exception"``.
    * ``executed=False`` → success=False,
      ``error_category="none"`` when the kill-switch was
      off, else ``"stub"``.

    Sprint AI-20 — three additive keyword arguments enrich the
    trace with the tool-minimality fields:

      * ``required_or_optional`` — mirrors the ToolPlan
        slot the call came from.
      * ``final_answer_body`` — the assistant's final
        response body; the factory calls the pure
        :func:`_answer_uses_envelope` helper to set
        ``used_in_final_answer``.
      * ``envelope`` — the StructuredToolEnvelope (or
        any dict-like with ``metric`` / ``value`` /
        ``formula`` keys). Used to compute both
        ``evidence_produced`` and ``used_in_final_answer``
        when ``final_answer_body`` is provided.

    The factory is a pure function: same inputs ⇒ same trace.
    Never raises.
    """
    # Defensive: when ``result`` is None we treat it as a
    # non-executed entry. This is the kill-switch / disabled
    # path.
    if not executed or result is None:
        return ToolExecutionTrace(
            tool_name=tool_name,
            selected=selected,
            executed=False,
            success=False,
            latency_ms=0,
            result_available=False,
            evidence_ids=tuple(evidence_ids),
            failure_reason="not_executed",
            error_category=ERROR_CATEGORY_NONE,
            required_or_optional=required_or_optional,
            evidence_produced=False,
            used_in_final_answer=False,
            failure_status="none",
        )

    status = getattr(result, "status", "error") or "error"
    payload = getattr(result, "payload", None)
    error = getattr(result, "error", "") or ""
    duration = getattr(result, "duration_ms", latency_ms) or latency_ms

    if status == "ok":
        # Success path — accept the payload unless it's empty.
        result_available = _payload_has_value(payload)
        success = result_available
        if result_available:
            error_category = ERROR_CATEGORY_NONE
            failure_reason = ""
        else:
            error_category = ERROR_CATEGORY_EMPTY
            failure_reason = "ok but empty payload"
    elif status == "not_implemented":
        success = False
        result_available = False
        error_category = ERROR_CATEGORY_STUB
        failure_reason = error or "stub"
    elif status == "skipped":
        success = False
        result_available = False
        error_category = ERROR_CATEGORY_NONE
        failure_reason = error or "skipped"
    elif status == "error":
        success = False
        result_available = False
        if error == "timeout":
            error_category = ERROR_CATEGORY_TIMEOUT
        else:
            error_category = ERROR_CATEGORY_EXCEPTION
        failure_reason = error or "error"
    else:
        success = False
        result_available = False
        error_category = ERROR_CATEGORY_EXCEPTION
        failure_reason = f"unknown status: {status}"

    # Sprint AI-20 — derive evidence_produced and
    # used_in_final_answer from the envelope (when present).
    # evidence_produced mirrors result_available for the
    # ok + non-empty case; otherwise False.
    evidence_produced = bool(result_available)
    used_in_answer = False
    if envelope is not None and final_answer_body:
        used_in_answer = _answer_uses_envelope(
            final_answer_body, envelope
        )

    return ToolExecutionTrace(
        tool_name=tool_name,
        selected=selected,
        executed=True,
        success=success,
        latency_ms=int(duration or 0),
        result_available=result_available,
        evidence_ids=tuple(evidence_ids),
        failure_reason=failure_reason,
        error_category=error_category,
        required_or_optional=required_or_optional,
        evidence_produced=evidence_produced,
        used_in_final_answer=used_in_answer,
        failure_status=error_category,
    )


def _answer_uses_envelope(body: str, envelope: Any) -> bool:
    """Pure helper — True iff the envelope's evidence
    appears in the assistant's final body.

    Sprint AI-20 — the tool-minimality metric flags a tool
    as "unnecessary" when its envelope is never cited in
    the final answer. The check uses deterministic
    substring matching on the envelope's
    ``metric`` / ``value`` / ``formula`` text — same
    algorithm as the AI-19 ``contains_semantic_value``
    helper, scoped to a single envelope.

    The helper is intentionally narrow: it does NOT
    attempt paraphrasing. A future sprint can swap in an
    LLM judge for richer recall (out of scope for AI-20).
    """
    if not body or envelope is None:
        return False
    body_lower = body.lower()
    candidates: list[str] = []
    if hasattr(envelope, "metric"):
        candidates.append(str(getattr(envelope, "metric", "") or ""))
        candidates.append(str(getattr(envelope, "value", "") or ""))
        candidates.append(str(getattr(envelope, "formula", "") or ""))
    elif isinstance(envelope, Mapping):
        for key in ("metric", "value", "formula"):
            v = envelope.get(key)
            if v:
                candidates.append(str(v))
    for cand in candidates:
        cand = cand.strip().lower()
        if not cand:
            continue
        # Require at least 4 chars of overlap to avoid
        # trivial matches on stopwords / units.
        if len(cand) < 4:
            continue
        if cand in body_lower:
            return True
        # Token-overlap fallback: if any token ≥ 4 chars
        # appears in the body, count it as used.
        for token in cand.split():
            if len(token) >= 4 and token in body_lower:
                return True
    return False


def _payload_has_value(payload: Any) -> bool:
    """Return True if a payload is non-empty / non-None.

    Used to distinguish "ok with empty payload" from
    "ok with real data". For dicts the test is non-empty
    keys; for lists the test is non-empty len; for scalars
    the test is truthy.
    """
    if payload is None:
        return False
    if isinstance(payload, Mapping):
        return bool(payload)
    if isinstance(payload, (list, tuple, set)):
        return bool(payload)
    if isinstance(payload, (str, bytes)):
        return bool(payload)
    # Numbers / bools / other scalars — treat as available.
    return True


# --------------------------------------------------------------------------- #
# Aggregate helpers
# --------------------------------------------------------------------------- #


def aggregate_traces(
    traces: tuple[ToolExecutionTrace, ...],
) -> tuple[ToolExecutionTrace, ...]:
    """Return the trace tuple unchanged. Convenience for callers."""
    return traces


def failed_tools(
    traces: tuple[ToolExecutionTrace, ...],
) -> tuple[str, ...]:
    """Return the names of tools that did NOT succeed.

    "Did not succeed" means:
      * status != "ok" (failure modes: stub, timeout, exception,
        skipped), OR
      * payload was empty (status == "ok" but useless).
    """
    return tuple(
        t.tool_name
        for t in traces
        if not t.success
    )


def successful_tools(
    traces: tuple[ToolExecutionTrace, ...],
) -> tuple[str, ...]:
    """Return the names of tools that succeeded (status == "ok" with payload)."""
    return tuple(t.tool_name for t in traces if t.success)


def any_failed(traces: tuple[ToolExecutionTrace, ...]) -> bool:
    """True iff at least one trace is non-success."""
    return any(not t.success for t in traces)


def summary_line(traces: tuple[ToolExecutionTrace, ...]) -> str:
    """One-line summary of the trace — for the audit log.

    Format: ``"tools=N succeeded=M failed=K (categories: stub=S, timeout=T, exception=E, empty=P)"``.

    Used by the conversation service to stamp a short
    human-readable summary onto the GenerationMeta
    (not user-facing by default).
    """
    if not traces:
        return "tools=0"
    n = len(traces)
    succeeded = sum(1 for t in traces if t.success)
    failed = n - succeeded
    stub = sum(1 for t in traces if t.error_category == ERROR_CATEGORY_STUB)
    timeout = sum(
        1 for t in traces if t.error_category == ERROR_CATEGORY_TIMEOUT
    )
    exception = sum(
        1 for t in traces if t.error_category == ERROR_CATEGORY_EXCEPTION
    )
    empty = sum(
        1 for t in traces if t.error_category == ERROR_CATEGORY_EMPTY
    )
    return (
        f"tools={n} succeeded={succeeded} failed={failed} "
        f"(categories: stub={stub}, timeout={timeout}, "
        f"exception={exception}, empty={empty})"
    )


# --------------------------------------------------------------------------- #
# Partial-failure disclosure and confidence reduction
# --------------------------------------------------------------------------- #


# Deterministic confidence penalty per failed-tool category.
# Stubs cost the least (they're a known gap); exceptions cost
# the most (real data was attempted and failed). The total
# penalty is the SUM of per-category penalties across all
# failed tools, capped at ``_MAX_PENALTY_TOTAL``.
_PENALTY_PER_STUB = 3
_PENALTY_PER_TIMEOUT = 12
_PENALTY_PER_EXCEPTION = 15
_PENALTY_PER_EMPTY = 5
_MAX_PENALTY_TOTAL = 40


def confidence_penalty(
    traces: tuple[ToolExecutionTrace, ...],
) -> int:
    """Return the integer confidence penalty for the trace tuple.

    Deterministic — same trace ⇒ same penalty. Used by the
    ``partial_failure_disclosure`` module to reduce the
    server-confidence number when at least one tool failed.
    Returns ``0`` when every tool succeeded.
    """
    if not traces or not any_failed(traces):
        return 0
    total = 0
    for t in traces:
        if t.success:
            continue
        if t.error_category == ERROR_CATEGORY_STUB:
            total += _PENALTY_PER_STUB
        elif t.error_category == ERROR_CATEGORY_TIMEOUT:
            total += _PENALTY_PER_TIMEOUT
        elif t.error_category == ERROR_CATEGORY_EXCEPTION:
            total += _PENALTY_PER_EXCEPTION
        elif t.error_category == ERROR_CATEGORY_EMPTY:
            total += _PENALTY_PER_EMPTY
        # ERROR_CATEGORY_NONE on skipped tools → no penalty.
    return min(total, _MAX_PENALTY_TOTAL)


def partial_failure_disclosure(
    traces: tuple[ToolExecutionTrace, ...],
) -> str | None:
    """Build a deterministic partial-failure disclosure sentence.

    Returns ``None`` when every tool succeeded (no disclosure
    needed). Otherwise returns a one-line sentence describing
    the failed tools, e.g. ``"Forecast data was unavailable, so
    the forecast portion could not be verified."`` (multi-tool
    failures are joined with "and").

    Used by the partial-failure handler to inject a sentence
    into the LLM context so the answer discloses the gap.
    """
    failed = tuple(t for t in traces if not t.success)
    if not failed:
        return None

    # Stable, deterministic order = original tuple order.
    parts: list[str] = []
    for t in failed:
        parts.append(_disclosure_phrase(t))
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return f"{parts[0]} and {parts[1]}"
    return ", ".join(parts[:-1]) + f", and {parts[-1]}"


def _disclosure_phrase(t: ToolExecutionTrace) -> str:
    """One-line phrase for a single failed tool."""
    if t.error_category == ERROR_CATEGORY_STUB:
        return (
            f"{t.tool_name} data was unavailable, so the "
            f"{t.tool_name} portion could not be verified"
        )
    if t.error_category == ERROR_CATEGORY_TIMEOUT:
        return (
            f"{t.tool_name} timed out, so the {t.tool_name} "
            f"portion could not be verified"
        )
    if t.error_category == ERROR_CATEGORY_EXCEPTION:
        return (
            f"{t.tool_name} failed with an error, so the "
            f"{t.tool_name} portion could not be verified"
        )
    if t.error_category == ERROR_CATEGORY_EMPTY:
        return (
            f"{t.tool_name} returned no data, so the "
            f"{t.tool_name} portion could not be verified"
        )
    # skipped
    return (
        f"{t.tool_name} was skipped, so the {t.tool_name} "
        f"portion could not be verified"
    )
