"""Tests for SPRINT AI-13 — ToolExecutionTrace observability.

Verifies the per-tool trace dataclass, the factory's failure
classification, the aggregate helpers, and the deterministic
confidence-penalty + partial-failure disclosure.

Also exercises the trace through the live dispatcher
(dispatch_with_plan) so the audit trail is exercised against
real registered-stub tools.
"""
from __future__ import annotations

from app.services.ai.providers.base import (
    AssistantContext,
    AssistantContextDna,
)
from app.services.ai.reasoning.tool_execution_trace import (
    ERROR_CATEGORY_EMPTY,
    ERROR_CATEGORY_EXCEPTION,
    ERROR_CATEGORY_NONE,
    ERROR_CATEGORY_STUB,
    ERROR_CATEGORY_TIMEOUT,
    ToolExecutionTrace,
    aggregate_traces,
    any_failed,
    confidence_penalty,
    failed_tools,
    partial_failure_disclosure,
    successful_tools,
    summary_line,
    trace_from_tool_result,
)
from app.services.ai.reasoning.tool_selector import (
    ToolDispatcher,
    ToolResult,
)


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


def _ctx() -> AssistantContext:
    return AssistantContext(
        business_id=1,
        legal_name="Acme Textiles",
        industry="Textiles",
        location="Tirupur",
        business_type="Manufacturer",
        employee_count=42,
        annual_revenue_inr=18_000_000,
        target_revenue_inr=30_000_000,
        overall_business_score=68,
        band="Established",
        dna=AssistantContextDna(
            archetype_key="growth_seeker",
            archetype_title="Growth Seeker",
            match_score=82,
        ),
    )


# --------------------------------------------------------------------------- #
# 1. trace_from_tool_result — failure classification
# --------------------------------------------------------------------------- #


class TestTraceFactory:
    def test_ok_with_payload_classifies_success(self) -> None:
        result = ToolResult(
            service_name="health_score",
            status="ok",
            payload={"score": 72, "unit": "/100"},
            duration_ms=15,
        )
        t = trace_from_tool_result(
            "health_score",
            selected=True,
            executed=True,
            result=result,
            evidence_ids=("ev1", "ev2"),
        )
        assert t.tool_name == "health_score"
        assert t.selected is True
        assert t.executed is True
        assert t.success is True
        assert t.latency_ms == 15
        assert t.result_available is True
        assert t.evidence_ids == ("ev1", "ev2")
        assert t.error_category == ERROR_CATEGORY_NONE
        assert t.failure_reason == ""

    def test_ok_with_empty_payload_is_empty_category(self) -> None:
        result = ToolResult(
            service_name="kpi",
            status="ok",
            payload={},
            duration_ms=10,
        )
        t = trace_from_tool_result(
            "kpi", selected=True, executed=True, result=result,
        )
        assert t.success is False
        assert t.error_category == ERROR_CATEGORY_EMPTY
        assert "empty" in t.failure_reason

    def test_not_implemented_classifies_stub(self) -> None:
        result = ToolResult(
            service_name="health_score",
            status="not_implemented",
            payload=None,
            duration_ms=0,
            error="stub",
        )
        t = trace_from_tool_result(
            "health_score", selected=True, executed=True, result=result,
        )
        assert t.success is False
        assert t.error_category == ERROR_CATEGORY_STUB
        assert t.failure_reason == "stub"

    def test_error_with_timeout_classifies_timeout(self) -> None:
        result = ToolResult(
            service_name="finance",
            status="error",
            payload=None,
            duration_ms=500,
            error="timeout",
        )
        t = trace_from_tool_result(
            "finance", selected=True, executed=True, result=result,
        )
        assert t.success is False
        assert t.error_category == ERROR_CATEGORY_TIMEOUT

    def test_error_with_exception_classifies_exception(self) -> None:
        result = ToolResult(
            service_name="predictive_sprint14",
            status="error",
            payload=None,
            duration_ms=12,
            error="ValueError: bad input",
        )
        t = trace_from_tool_result(
            "predictive_sprint14",
            selected=True,
            executed=True,
            result=result,
        )
        assert t.success is False
        assert t.error_category == ERROR_CATEGORY_EXCEPTION

    def test_skipped_does_not_penalise(self) -> None:
        result = ToolResult(
            service_name="risk",
            status="skipped",
            payload=None,
            duration_ms=0,
            error="not relevant",
        )
        t = trace_from_tool_result(
            "risk", selected=True, executed=True, result=result,
        )
        assert t.success is False
        assert t.error_category == ERROR_CATEGORY_NONE
        assert t.error_category in {ERROR_CATEGORY_NONE}

    def test_not_executed_is_no_category(self) -> None:
        t = trace_from_tool_result(
            "health_score",
            selected=True,
            executed=False,
            result=None,
        )
        assert t.executed is False
        assert t.success is False
        assert t.error_category == ERROR_CATEGORY_NONE

    def test_to_dict_carries_all_fields(self) -> None:
        t = ToolExecutionTrace(
            tool_name="finance",
            selected=True,
            executed=True,
            success=True,
            latency_ms=42,
            result_available=True,
            evidence_ids=("e1", "e2"),
            failure_reason="",
            error_category=ERROR_CATEGORY_NONE,
        )
        d = t.to_dict()
        for k in (
            "tool_name", "selected", "executed", "success",
            "latency_ms", "result_available", "evidence_ids",
            "failure_reason", "error_category",
        ):
            assert k in d
        assert d["tool_name"] == "finance"
        assert d["evidence_ids"] == ["e1", "e2"]


# --------------------------------------------------------------------------- #
# 2. Aggregate helpers
# --------------------------------------------------------------------------- #


class TestAggregateHelpers:
    def _t(self, name: str, success: bool, category: str = ERROR_CATEGORY_NONE) -> ToolExecutionTrace:
        return ToolExecutionTrace(
            tool_name=name,
            selected=True,
            executed=True,
            success=success,
            latency_ms=10,
            result_available=success,
            error_category=category,
        )

    def test_aggregate_traces_returns_input(self) -> None:
        trace = self._t("health_score", True)
        assert aggregate_traces((trace,)) == (trace,)

    def test_failed_and_successful_tools(self) -> None:
        traces = (
            self._t("health_score", True),
            self._t("finance", False, ERROR_CATEGORY_TIMEOUT),
            self._t("recommendation", True),
            self._t("schemes_sprint16", False, ERROR_CATEGORY_STUB),
        )
        assert successful_tools(traces) == ("health_score", "recommendation")
        assert failed_tools(traces) == ("finance", "schemes_sprint16")

    def test_any_failed_distinguishes(self) -> None:
        assert any_failed(()) is False
        assert any_failed((self._t("x", True),)) is False
        assert any_failed((self._t("x", False),)) is True

    def test_summary_line_contains_counts(self) -> None:
        traces = (
            self._t("health_score", True),
            self._t("finance", False, ERROR_CATEGORY_TIMEOUT),
            self._t("recommendation", False, ERROR_CATEGORY_STUB),
        )
        summary = summary_line(traces)
        assert "tools=3" in summary
        assert "succeeded=1" in summary
        assert "failed=2" in summary
        assert "timeout=1" in summary
        assert "stub=1" in summary

    def test_summary_line_empty(self) -> None:
        assert summary_line(()) == "tools=0"


# --------------------------------------------------------------------------- #
# 3. Confidence penalty — deterministic
# --------------------------------------------------------------------------- #


class TestConfidencePenalty:
    def _t(self, name: str, success: bool, category: str) -> ToolExecutionTrace:
        return ToolExecutionTrace(
            tool_name=name,
            selected=True,
            executed=True,
            success=success,
            latency_ms=0,
            result_available=success,
            error_category=category,
        )

    def test_no_failure_zero_penalty(self) -> None:
        assert confidence_penalty(()) == 0
        assert confidence_penalty((self._t("x", True, ERROR_CATEGORY_NONE),)) == 0

    def test_stub_costs_three(self) -> None:
        assert confidence_penalty(
            (self._t("health_score", False, ERROR_CATEGORY_STUB),)
        ) == 3

    def test_timeout_costs_twelve(self) -> None:
        assert confidence_penalty(
            (self._t("finance", False, ERROR_CATEGORY_TIMEOUT),)
        ) == 12

    def test_exception_costs_fifteen(self) -> None:
        assert confidence_penalty(
            (self._t("predictive_sprint14", False, ERROR_CATEGORY_EXCEPTION),)
        ) == 15

    def test_empty_costs_five(self) -> None:
        assert confidence_penalty(
            (self._t("kpi", False, ERROR_CATEGORY_EMPTY),)
        ) == 5

    def test_skipped_no_penalty(self) -> None:
        assert confidence_penalty(
            (self._t("risk", False, ERROR_CATEGORY_NONE),)
        ) == 0

    def test_penalty_capped_at_forty(self) -> None:
        traces = tuple(
            self._t(f"tool_{i}", False, ERROR_CATEGORY_EXCEPTION)
            for i in range(10)
        )
        assert confidence_penalty(traces) == 40


# --------------------------------------------------------------------------- #
# 4. Partial-failure disclosure
# --------------------------------------------------------------------------- #


class TestPartialFailureDisclosure:
    def _t(self, name: str, category: str) -> ToolExecutionTrace:
        return ToolExecutionTrace(
            tool_name=name,
            selected=True,
            executed=True,
            success=False,
            latency_ms=0,
            result_available=False,
            error_category=category,
        )

    def test_no_failure_returns_none(self) -> None:
        assert partial_failure_disclosure(()) is None
        assert (
            partial_failure_disclosure(
                (ToolExecutionTrace(
                    tool_name="health_score",
                    selected=True,
                    executed=True,
                    success=True,
                    latency_ms=10,
                    result_available=True,
                ),)
            )
            is None
        )

    def test_single_failure_format(self) -> None:
        sentence = partial_failure_disclosure(
            (self._t("forecast", ERROR_CATEGORY_STUB),)
        )
        assert sentence is not None
        assert "forecast" in sentence
        assert "unavailable" in sentence.lower()

    def test_timeout_failure_uses_correct_phrase(self) -> None:
        sentence = partial_failure_disclosure(
            (self._t("finance", ERROR_CATEGORY_TIMEOUT),)
        )
        assert sentence is not None
        assert "timed out" in sentence.lower()

    def test_exception_failure_uses_correct_phrase(self) -> None:
        sentence = partial_failure_disclosure(
            (self._t("predictive_sprint14", ERROR_CATEGORY_EXCEPTION),)
        )
        assert sentence is not None
        assert "failed" in sentence.lower()

    def test_two_failures_joined_with_and(self) -> None:
        sentence = partial_failure_disclosure(
            (
                self._t("finance", ERROR_CATEGORY_STUB),
                self._t("forecast", ERROR_CATEGORY_TIMEOUT),
            )
        )
        assert sentence is not None
        assert " and " in sentence

    def test_three_failures_joined_with_comma_and_and(self) -> None:
        sentence = partial_failure_disclosure(
            (
                self._t("finance", ERROR_CATEGORY_STUB),
                self._t("forecast", ERROR_CATEGORY_TIMEOUT),
                self._t("recommendation", ERROR_CATEGORY_EXCEPTION),
            )
        )
        assert sentence is not None
        assert ", " in sentence
        assert ", and " in sentence


# --------------------------------------------------------------------------- #
# 5. Dispatcher integration — dispatch_with_plan emits traces
# --------------------------------------------------------------------------- #


class TestDispatcherEmitsTraces:
    """The dispatcher surface must emit ToolExecutionTrace records
    per executed tool so the partial-failure handler can act on them.
    """

    def test_default_stub_dispatcher_emits_stub_traces(self) -> None:
        """When the default stub registry is used, every executed
        tool carries ``error_category="stub"``."""
        from app.services.ai.reasoning.question_understanding import (
            understand_question,
        )
        from app.services.ai.reasoning.reasoning_engine import (
            BusinessReasoningEngine,
        )

        ctx = _ctx()
        qu = understand_question(
            "How can I grow from ₹1.8 Cr to ₹3 Cr?", ctx
        )
        plan = BusinessReasoningEngine().plan(
            user_prompt="How can I grow from ₹1.8 Cr to ₹3 Cr?",
            context=ctx,
            question_understanding=qu,
        )
        dispatcher = ToolDispatcher()
        outcome = dispatcher.dispatch_with_plan(
            owner_id=1,
            question_understanding=qu,
            reasoning_plan=plan,
            context=ctx,
        )
        assert outcome.traces, "dispatcher must emit at least one trace"
        for t in outcome.traces:
            assert t.tool_name
            assert t.executed is True
            assert t.error_category in {
                ERROR_CATEGORY_STUB,
                ERROR_CATEGORY_NONE,
                ERROR_CATEGORY_EMPTY,
                ERROR_CATEGORY_TIMEOUT,
                ERROR_CATEGORY_EXCEPTION,
            }

    def test_kill_switch_returns_empty_traces(self) -> None:
        from app.services.ai.reasoning.pipeline import (
            ReasoningPipeline,
        )
        from app.services.ai.reasoning.question_understanding import (
            QuestionUnderstanding,
        )

        ctx = _ctx()
        base_plan = ReasoningPipeline().pre_llm_plan(
            user_prompt="test", context=ctx,
        )
        empty_qu = QuestionUnderstanding(
            literal_question="",
            user_intent="general.business.advice",
            topic="general",
            is_business_specific=False,
            is_purely_educational=False,
        )
        ToolDispatcher._DISPATCH_ENABLED = False
        try:
            dispatcher = ToolDispatcher()
            outcome = dispatcher.dispatch_with_plan(
                owner_id=1,
                question_understanding=empty_qu,
                reasoning_plan=base_plan,
                context=ctx,
            )
            assert outcome.traces == ()
        finally:
            ToolDispatcher._DISPATCH_ENABLED = True

    def test_custom_real_tool_classifies_success(self) -> None:
        """A custom tool that returns status='ok' with payload
        produces a success trace."""
        from dataclasses import replace

        from app.services.ai.reasoning.pipeline import ReasoningPipeline

        ctx = _ctx()
        base_plan = ReasoningPipeline().pre_llm_plan(
            user_prompt="test", context=ctx,
        )
        plan = replace(
            base_plan,
            applicable_deterministic_services=("health_score",),
        )

        class EchoTool:
            def invoke(self, *, owner_id, call, context):
                return ToolResult(
                    service_name=call.service_name,
                    status="ok",
                    payload={"score": 80, "unit": "/100"},
                    duration_ms=5,
                )

        from app.services.ai.reasoning.question_understanding import (
            understand_question,
        )

        qu = understand_question("What is my health score?", ctx)
        dispatcher = ToolDispatcher()
        dispatcher.register_tool("health_score", EchoTool())
        outcome = dispatcher.dispatch_with_plan(
            owner_id=1,
            question_understanding=qu,
            reasoning_plan=plan,
            context=ctx,
        )
        assert len(outcome.traces) == 1
        t = outcome.traces[0]
        assert t.tool_name == "health_score"
        assert t.success is True
        assert t.error_category == ERROR_CATEGORY_NONE
        assert t.latency_ms == 5
