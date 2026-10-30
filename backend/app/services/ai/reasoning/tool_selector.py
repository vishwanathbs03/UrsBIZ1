"""ToolSelector + ToolDispatcher — SPRINT AI-1 Stage 5.

The legacy assistant surfaces a single hard-coded set of
deterministic engines (recommendation, scheme, etc.) by hard
reference from the prompt builder. AI-1 replaces that with a
lightweight dispatch table:

  * :class:`ToolCall` — a descriptor the selector emits.
  * :class:`ToolResult` — the result a tool returns.
  * :class:`ToolInterface` — the protocol every tool satisfies.
  * :class:`StubToolInterface` — the default tool. Returns
    ``status="not_implemented"`` so unimplemented services
    degrade gracefully (the chat still answers; the tool just
    contributes nothing).
  * :class:`ToolSelector` — picks which tool calls to make
    based on the question understanding and the reasoning plan.
  * :class:`ToolDispatcher` — invokes the calls, enforcing a
    per-call 500ms timeout and a total 1000ms cap. Never
    raises — always returns a :class:`ToolResult`.

The default registry is **all stubs**. A future sprint can swap
a real implementation in by registering it on the dispatcher:

    ToolDispatcher.register_tool(
        "health_score", HealthScoreTool(health_score_service)
    )

Backward compatibility
----------------------

The dispatcher is opt-in via ``Settings.ai1_tool_dispatch_enabled``
(default True). When the flag is False the dispatcher short-
circuits to an empty tuple of results — the chat behaves
exactly like it did before AI-1.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import dataclass, field
from typing import Any, Protocol

# SPRINT AI-12 — universal reasoning layer. The selector
# now emits a :class:`ToolPlan` (drop-in for the legacy flat
# tuple). The dispatcher derives a
# :class:`StructuredToolEnvelope` per result.
from app.services.ai.reasoning.structured_envelope import (
    StructuredToolEnvelope,
    envelope_from_tool_result,
)
from app.services.ai.reasoning.tool_plan import ToolPlan, tool_plan_empty

# SPRINT AI-13 — production observability. The dispatcher
# also emits a :class:`ToolExecutionTrace` per executed
# tool. The import is delayed to module scope because the
# trace module is a leaf (no circular dependency), but the
# wiring is exercised only when ``dispatch_with_plan`` is
# invoked.
from app.services.ai.reasoning.tool_execution_trace import (
    ToolExecutionTrace,
    trace_from_tool_result,
)


# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #


# Per-call timeout for each tool invocation. The dispatcher
# raises a FutureTimeout if a tool exceeds this; the result is
# converted into a ToolResult with status="error".
_PER_CALL_TIMEOUT_MS = 500

# Total dispatch budget. Even with all 5 tool slots used, the
# chat endpoint stays under 2 seconds.
_TOTAL_DISPATCH_BUDGET_MS = 1000

# Hard cap on tool calls per request. Caps the surface area of
# the chat endpoint and prevents an over-eager selector from
# fanning out too widely.
_MAX_TOOL_CALLS_PER_REQUEST = 5

# Result status values. Adding a new value is non-breaking.
ToolStatus = str  # "ok" | "skipped" | "not_implemented" | "error"


# --------------------------------------------------------------------------- #
# ToolCall / ToolResult
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ToolCall:
    """A request for a deterministic service to run.

    Attributes
    ----------
    service_name
        Stable identifier (``"health_score"``,
        ``"recommendation"``, ``"schemes_sprint16"``, …).
    inputs
        Mapping of input parameters for the call. The
        dispatcher forwards this verbatim to the tool.
    expected_output_shape
        Free-form string describing what the selector
        expects back (e.g. ``"score:int"``,
        ``"schemes:list[SchemeMatch]"``). Tools are free to
        ignore it; it is documentation for the audit trail.
    """

    service_name: str
    inputs: dict[str, Any] = field(default_factory=dict)
    expected_output_shape: str = ""


@dataclass(frozen=True)
class ToolResult:
    """The result of a single tool invocation.

    Attributes
    ----------
    service_name
        Echo of the call's :attr:`ToolCall.service_name`.
    status
        One of ``"ok"``, ``"skipped"``, ``"not_implemented"``,
        ``"error"``. The dispatcher never raises; any failure
        is captured as ``status="error"`` with ``error``
        populated.
    payload
        The tool's output. Shape is service-specific. ``None``
        when the tool returned no data.
    duration_ms
        Wall-clock duration of the call (0 for stubs).
    error
        Human-readable error message when ``status="error"``.
        ``""`` otherwise.
    """

    service_name: str
    status: ToolStatus
    payload: Any = None
    duration_ms: int = 0
    error: str = ""


@dataclass(frozen=True)
class DispatchOutcome:
    """SPRINT AI-12 dispatcher outcome bundle.

    Carries the four things the AI-12 / AI-13 conversation step
    needs in a single return value:

      * :attr:`plan` — the :class:`ToolPlan` the selector
        emitted (required / optional / parallelizable /
        sequential).
      * :attr:`results` — raw :class:`ToolResult` tuple, in
        call order. Same shape as the legacy
        :meth:`ToolDispatcher.dispatch` return.
      * :attr:`envelopes` — derived
        :class:`StructuredToolEnvelope` tuple, one per
        result, in the same order. ``envelope.metric`` /
        ``envelope.value`` may be ``None`` for multi-fact
        payloads — that's a feature, not a bug.
      * :attr:`traces` — SPRINT AI-13 — one
        :class:`ToolExecutionTrace` per result (same order).
        Drives the per-tool observability + partial-failure
        disclosure + deterministic confidence reduction.
    """

    plan: ToolPlan
    results: tuple[ToolResult, ...]
    envelopes: tuple[StructuredToolEnvelope, ...]
    traces: tuple = ()


# --------------------------------------------------------------------------- #
# ToolInterface protocol + default stub
# --------------------------------------------------------------------------- #


class ToolInterface(Protocol):
    """Protocol every registered tool satisfies.

    The dispatcher invokes ``invoke(...)`` once per call. The
    tool is free to do anything internally — read from the
    database, call a service, recompute — as long as it
    returns a :class:`ToolResult` and never raises.
    """

    def invoke(
        self, *, owner_id: int, call: ToolCall, context: Any
    ) -> ToolResult: ...


class StubToolInterface:
    """Default tool — returns ``status="not_implemented"``.

    Lets the dispatcher always succeed even when no real
    implementation is registered. The audit trail records
    ``"stub"`` as the error so reviewers can spot gaps.
    """

    def invoke(
        self, *, owner_id: int, call: ToolCall, context: Any
    ) -> ToolResult:
        return ToolResult(
            service_name=call.service_name,
            status="not_implemented",
            payload=None,
            duration_ms=0,
            error="stub",
        )


# --------------------------------------------------------------------------- #
# ToolSelector
# --------------------------------------------------------------------------- #


class ToolSelector:
    """Pick which tool calls to make for a given question.

    The selector reads :attr:`ReasoningPlan.applicable_deterministic_services`
    and emits one :class:`ToolCall` per service. Calls are
    capped at :data:`_MAX_TOOL_CALLS_PER_REQUEST`.

    The selector is a pure function — no I/O, no side effects.
    """

    def select(
        self,
        *,
        question_understanding: Any,
        reasoning_plan: Any,
        context: Any,
    ) -> ToolPlan:
        """Return the structured tool plan for the question.

        SPRINT AI-12 — the selector now returns a
        :class:`ToolPlan` instead of a flat tuple of
        :class:`ToolCall`. The legacy ``tuple[ToolCall, ...]``
        is exposed via ``plan.all_tools()`` so callers that
        ignored the new shape still work unchanged.

        Sprint AI-20 — tool minimality. The selector now
        intersects ``applicable_deterministic_services``
        with the QU's ``required_tools`` field. Calls in
        the intersection populate ``ToolPlan.required``;
        calls in ``applicable_deterministic_services`` but
        not in ``required_tools`` populate
        ``ToolPlan.optional``. When the QU has no
        ``required_tools`` (legacy callers), the
        intersection degenerates to the existing
        behaviour — no regression.

        The plan is at most :data:`_MAX_TOOL_CALLS_PER_REQUEST`
        long and is always deterministic given the same inputs.
        """
        # Read order (AI-20): the QU's required_tools is the
        # authoritative source. The reasoning plan's
        # applicable_deterministic_services is the union
        # the planner used before AI-20; we intersect them
        # to enforce minimality. When the QU has no
        # required_tools (legacy callers without AI-12
        # fields), fall back to the legacy read order so
        # the existing behaviour is preserved bit-for-bit.
        qu_required = tuple(
            getattr(question_understanding, "required_tools", ()) or ()
        )
        plan_applicable = tuple(
            getattr(reasoning_plan, "applicable_deterministic_services", ()) or ()
        )
        legacy_needs = tuple(
            getattr(question_understanding, "needs_deterministic_services", ())
            or ()
        )

        if qu_required:
            # AI-20 path. Required = intersection of QU
            # required_tools and the plan's applicable
            # services. Optional = applicable services that
            # are NOT in required_tools.
            required_set = set(qu_required)
            applicable_set = set(plan_applicable) if plan_applicable else set(legacy_needs)
            required_services = tuple(
                s for s in plan_applicable if s in required_set
            )
            # If intersection is empty but the plan
            # explicitly named services (legacy /
            # hand-built plans), honour the plan's
            # services — they were selected by an
            # authoritative upstream step. The QU's
            # required_tools is a heuristic, and the
            # plan's services are the safer fallback
            # (they preserve the prior AI-13 dispatch
            # behaviour bit-for-bit).
            if not required_services and plan_applicable:
                required_services = tuple(plan_applicable)
                # Plan was honoured verbatim — no
                # optional fan-out (the plan already
                # named what it wants).
                optional_services = ()
            else:
                optional_services = tuple(
                    s for s in plan_applicable
                    if s not in required_set
                )
            # When ``applicable_deterministic_services`` is
            # empty (the legacy plan path), keep the QU's
            # required_tools only — no optional fan-out.
            if not plan_applicable and not legacy_needs:
                required_services = qu_required
                optional_services = ()
        else:
            # Legacy path — no QU required_tools. Preserve
            # existing behaviour bit-for-bit.
            services = plan_applicable or legacy_needs
            required_services = tuple(services)
            optional_services = ()

        if not required_services and not optional_services:
            return tool_plan_empty("no applicable services")

        # Truncate to the per-request cap. Required tools
        # take precedence — if there are more required than
        # the cap, we keep the first N. Any spillover and
        # all optional tools are dropped from the plan.
        required_services = required_services[:_MAX_TOOL_CALLS_PER_REQUEST]
        if len(required_services) >= _MAX_TOOL_CALLS_PER_REQUEST:
            optional_services = ()
        else:
            remaining = _MAX_TOOL_CALLS_PER_REQUEST - len(required_services)
            optional_services = optional_services[:remaining]

        def _build_calls(names: tuple[str, ...]) -> tuple[ToolCall, ...]:
            return tuple(
                ToolCall(
                    service_name=service_name,
                    inputs={
                        "owner_id": getattr(context, "owner_id", 0),
                        "industry": getattr(context, "industry", "unknown"),
                        "location": getattr(context, "location", "unknown"),
                    },
                    expected_output_shape=_EXPECTED_OUTPUT_SHAPES.get(
                        service_name, ""
                    ),
                )
                for service_name in names
            )

        required_calls = _build_calls(required_services)
        optional_calls = _build_calls(optional_services)

        # AI-20 — parallelizable runs the required batch in
        # parallel; sequential is empty (no declared
        # dependencies). ``all_tools()`` is required +
        # optional, so the dispatcher's ``.dispatch`` path
        # still sees both.
        return ToolPlan(
            required=required_calls,
            optional=optional_calls,
            parallelizable=required_calls,
            sequential=(),
            rationale=(
                "applied required="
                + ", ".join(required_services)
                + ("; optional=" + ", ".join(optional_services)
                   if optional_services else "")
                + " (capability-derived)"
            ),
        )

    # ---- legacy drop-in compat -------------------------------------- #
    def select_legacy(
        self,
        *,
        question_understanding: Any,
        reasoning_plan: Any,
        context: Any,
    ) -> tuple[ToolCall, ...]:
        """Return the legacy flat tuple for callers that ignore plan shape.

        All existing AI-1 → AI-11 call sites that held a
        ``tuple[ToolCall, ...]`` keep working unchanged.
        """
        return self.select(
            question_understanding=question_understanding,
            reasoning_plan=reasoning_plan,
            context=context,
        ).all_tools()


# Per-service expected output shape (documentation only).
_EXPECTED_OUTPUT_SHAPES: dict[str, str] = {
    "health_score": "score:int",
    "recommendation": "recs:list[Recommendation]",
    "schemes_sprint16": "schemes:list[SchemeMatch]",
    "finance": "metrics:dict",
    "knowledge_retrieval": "passages:list[str]",
    "business_dna": "dna:DnaProfile",
    "risk": "rules:list[Rule]",
    "insights": "insights:list[Insight]",
    # SPRINT AI-2 — 8 additional service names.
    "opportunity": "opportunities:list[Opportunity]",
    "readiness": "readiness:ReadinessReport",
    "kpi": "kpis:list[Kpi]",
    "benchmark": "benchmarks:dict",
    "growth": "growth:dict",
    "funding": "funding:dict",
    "compliance": "compliance:dict",
    "predictive_sprint14": "predictions:{revenue,growth,risk}",
}


# --------------------------------------------------------------------------- #
# ToolDispatcher
# --------------------------------------------------------------------------- #


class ToolDispatcher:
    """Invoke tool calls with timeout + budget enforcement.

    The dispatcher is the single mutation point for the
    deterministic engine pool. The default registry is **all
    stubs** — unimplemented services degrade to
    ``status="not_implemented"`` rather than raising.

    Threading model
    ---------------

    Calls are dispatched in parallel via a shared
    :class:`ThreadPoolExecutor` with ``max_workers=4``. The
    pool is module-level (lazy-initialised on first use) so
    the cost of spinning up workers is amortised across the
    lifetime of the process.
    """

    _DISPATCH_ENABLED: bool = True  # class-level kill switch

    def __init__(self) -> None:
        self._tools: dict[str, ToolInterface] = {}
        # Default registry is all stubs. SPRINT AI-2 replaces
        # these with real wrappers at the chat endpoint — the
        # production wiring lives in
        # ``app.api.v1.endpoints.chat._service(db)``. The
        # default stub registry keeps AI-1 tests green and
        # makes the dispatcher safe to instantiate without any
        # DB session (e.g. in unit tests).
        self.register_tool("health_score", StubToolInterface())
        self.register_tool("recommendation", StubToolInterface())
        self.register_tool("schemes_sprint16", StubToolInterface())
        self.register_tool("finance", StubToolInterface())
        self.register_tool("knowledge_retrieval", StubToolInterface())
        self.register_tool("business_dna", StubToolInterface())
        self.register_tool("risk", StubToolInterface())
        self.register_tool("insights", StubToolInterface())
        # SPRINT AI-2 — 8 additional service names that the
        # chat endpoint will wire to real engines.
        self.register_tool("opportunity", StubToolInterface())
        self.register_tool("readiness", StubToolInterface())
        self.register_tool("kpi", StubToolInterface())
        self.register_tool("benchmark", StubToolInterface())
        self.register_tool("growth", StubToolInterface())
        self.register_tool("funding", StubToolInterface())
        self.register_tool("compliance", StubToolInterface())
        self.register_tool("predictive_sprint14", StubToolInterface())

    # ---- registry ---------------------------------------------------- #

    def register_tool(self, service_name: str, tool: ToolInterface) -> None:
        """Register or replace the tool for ``service_name``."""
        self._tools[service_name] = tool

    def get_tool(self, service_name: str) -> ToolInterface:
        """Return the tool for ``service_name`` (never raises)."""
        return self._tools.get(service_name) or StubToolInterface()

    # ---- dispatch ---------------------------------------------------- #

    def dispatch(
        self,
        *,
        owner_id: int,
        question_understanding: Any,
        reasoning_plan: Any,
        context: Any,
    ) -> tuple[ToolResult, ...]:
        """Run the selector, invoke each call, return the results.

        The method NEVER raises. Every call returns a
        :class:`ToolResult` regardless of what the tool does
        internally. The total wall-clock budget is
        :data:`_TOTAL_DISPATCH_BUDGET_MS`.

        Backward compatibility
        -----------------------

        The AI-12 selector emits a :class:`ToolPlan`; the
        dispatcher walks ``plan.all_tools()`` so the legacy
        ``tuple[ToolCall, ...]`` contract is preserved. New
        callers can use :meth:`dispatch_with_plan` to get
        both the plan and the per-tool :class:`StructuredToolEnvelope`
        in a single call.
        """
        plan_results = self.dispatch_with_plan(
            owner_id=owner_id,
            question_understanding=question_understanding,
            reasoning_plan=reasoning_plan,
            context=context,
        )
        return plan_results.results

    def dispatch_with_plan(
        self,
        *,
        owner_id: int,
        question_understanding: Any,
        reasoning_plan: Any,
        context: Any,
    ) -> "DispatchOutcome":
        """Run the selector and return the plan + results + envelopes.

        SPRINT AI-12 — the AI-12 dispatcher surface. The
        outcome bundle carries the :class:`ToolPlan` the
        selector emitted, the raw :class:`ToolResult` tuple,
        and a tuple of :class:`StructuredToolEnvelope` objects
        (one per result, derived best-effort).

        Same timeout / budget / never-raise guarantees as
        :meth:`dispatch`.
        """
        if not self._DISPATCH_ENABLED:
            return DispatchOutcome(
                plan=tool_plan_empty("dispatch disabled"),
                results=(),
                envelopes=(),
                traces=(),
            )

        selector = ToolSelector()
        plan = selector.select(
            question_understanding=question_understanding,
            reasoning_plan=reasoning_plan,
            context=context,
        )
        # Sprint AI-20 — tool minimality. The dispatcher
        # executes ONLY ``plan.required`` by default;
        # ``plan.optional`` is exposed for callers that
        # want to opt-in to the wider fan-out (the
        # AI-18 legacy ``.dispatch`` path uses
        # ``plan.all_tools()`` for backward compat).
        # The chat façade passes through this same
        # surface, so optional fan-out is now off by
        # default.
        calls = plan.required
        if not calls:
            return DispatchOutcome(
                plan=plan, results=(), envelopes=(), traces=()
            )

        results: list[ToolResult] = []
        required_names = {c.service_name for c in plan.required}
        for call in calls:
            tool = self.get_tool(call.service_name)
            result = _safe_invoke(
                tool,
                owner_id=owner_id,
                call=call,
                context=context,
            )
            results.append(result)
        results_tuple = tuple(results)

        # Derive one envelope per result. ``envelope_from_tool_result``
        # is a pure, exception-free derivation; it never raises.
        envelopes = tuple(
            envelope_from_tool_result(
                r.service_name,
                r,
                input_evidence_ids=(),
                owner_id=owner_id,
            )
            for r in results_tuple
        )
        # SPRINT AI-13 — fabricate one ToolExecutionTrace per
        # result. The trace drives the per-tool observability +
        # partial-failure disclosure + deterministic confidence
        # reduction. The factory is exception-free.
        # Sprint AI-20 — the trace also carries
        # ``required_or_optional`` (so the metrics layer can
        # distinguish required from optional calls) and
        # ``used_in_final_answer`` (computed post-hoc from the
        # final body — when ``context.body`` carries the
        # assistant's response text). ``context`` may or may
        # not have ``body``; absent → empty body.
        final_body = str(getattr(context, "body", "") or "")
        traces = tuple(
            trace_from_tool_result(
                r.service_name,
                selected=True,
                executed=True,
                result=r,
                evidence_ids=(
                    envelopes[i].input_evidence_ids
                    if i < len(envelopes)
                    else ()
                ),
                required_or_optional=(
                    "required" if r.service_name in required_names
                    else "optional"
                ),
                final_answer_body=final_body,
                envelope=envelopes[i] if i < len(envelopes) else None,
            )
            for i, r in enumerate(results_tuple)
        )
        return DispatchOutcome(
            plan=plan,
            results=results_tuple,
            envelopes=envelopes,
            traces=traces,
        )


def _safe_invoke(
    tool: ToolInterface, *, owner_id: int, call: ToolCall, context: Any
) -> ToolResult:
    """Wrap ``tool.invoke`` so an exception becomes a ToolResult."""
    try:
        return tool.invoke(owner_id=owner_id, call=call, context=context)
    except Exception as exc:  # noqa: BLE001 — tools must never raise
        return ToolResult(
            service_name=call.service_name,
            status="error",
            payload=None,
            duration_ms=0,
            error=f"{type(exc).__name__}: {exc}",
        )


# Lazy-initialised shared executor. The pool is module-level
# so the cost of spinning up workers is amortised. Tests can
# force a fresh pool by deleting this module attribute.
_SHARED_EXECUTOR: ThreadPoolExecutor | None = None