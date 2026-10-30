"""SPRINT AI-13 — Dispatch Outcome Adapter.

The single function below turns a :class:`DispatchOutcome`
into the three AI-13 wire fields:

  * ``tool_execution_traces`` — tuple of
    :class:`ToolExecutionTrace.to_dict()` mirrors.
  * ``partial_failure_disclosure`` — the one-line sentence
    the partial-failure handler built (None when every tool
    succeeded).
  * ``confidence_penalty`` — the integer 0..40 penalty the
    partial-failure handler computed. 0 when every tool
    succeeded.

The adapter is a pure function over the outcome. It does
NOT mutate the outcome. It is exception-free — an exception
raises a structured crash but the dispatcher never reaches
it because the trace factory is already exception-free.

A second helper ``apply_partial_failure_to_confidence``
reduces the AI-3 server confidence by the penalty amount,
clamped to [0, 100].
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PartialFailureStamp:
    """The three AI-13 wire fields the adapter produces.

    The stamp is a pure value object — the consumer (the
    service stampler) unpacks it into ``GenerationMeta`` via
    ``dataclasses.replace``.
    """

    tool_execution_traces: tuple[dict, ...]
    partial_failure_disclosure: str | None
    confidence_penalty: int


def mint_partial_failure_stamp(
    dispatch_outcome: Any | None,
) -> PartialFailureStamp:
    """Derive the three AI-13 wire fields from a DispatchOutcome.

    Returns an empty stamp when the outcome is None or its
    trace tuple is empty. Never raises.
    """
    if dispatch_outcome is None:
        return PartialFailureStamp((), None, 0)

    # Lazy imports keep the module load-graph small.
    from app.services.ai.reasoning.tool_execution_trace import (
        partial_failure_disclosure as _disclosure,
        confidence_penalty as _penalty,
    )

    traces = tuple(getattr(dispatch_outcome, "traces", ()) or ())
    if not traces:
        return PartialFailureStamp((), None, 0)

    return PartialFailureStamp(
        tool_execution_traces=tuple(
            t.to_dict() if hasattr(t, "to_dict") else dict(t)
            for t in traces
        ),
        partial_failure_disclosure=_disclosure(traces),
        confidence_penalty=int(_penalty(traces)),
    )


def apply_partial_failure_to_confidence(
    *,
    server_confidence: int | None,
    confidence_penalty: int,
) -> int | None:
    """Reduce the server confidence by the penalty amount.

    Returns ``None`` when the original confidence is ``None``
    (the AI-3 layer never produced a score). The result is
    clamped to [0, 100]. The penalty is itself clamped to
    [0, 100] (the trace module caps it at 40 today; the
    ceiling here is a belt-and-braces guard).
    """
    if server_confidence is None:
        return None
    p = max(0, min(100, int(confidence_penalty or 0)))
    return max(0, min(100, int(server_confidence) - p))
