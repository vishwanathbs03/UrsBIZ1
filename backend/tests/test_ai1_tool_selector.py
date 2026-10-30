"""Test suite for SPRINT AI-1 — Stage 5: ToolSelector + ToolDispatcher."""

import time

import pytest

from app.services.ai.providers.base import (
    AssistantContext,
    AssistantContextDna,
)
from app.services.ai.reasoning.pipeline import ReasoningPlan
from app.services.ai.reasoning.question_understanding import (
    QuestionUnderstanding,
    understand_question,
)
from app.services.ai.reasoning.tool_selector import (
    StubToolInterface,
    ToolCall,
    ToolDispatcher,
    ToolInterface,
    ToolResult,
    ToolSelector,
)


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture
def acme_context():
    return AssistantContext(
        business_id=1,
        legal_name="Acme Textiles",
        industry="Textiles",
        location="Tirupur",
        business_type="Manufacturer",
        employee_count=42,
        annual_revenue_inr=18000000,
        target_revenue_inr=30000000,
        overall_business_score=68,
        band="Established",
        dna=AssistantContextDna("growth_operator", "Growth Operator", 85),
    )


@pytest.fixture
def acme_understanding(acme_context):
    return understand_question(
        "How can I grow from ₹1.8 Cr to ₹3 Cr?", acme_context
    )


@pytest.fixture
def acme_plan(acme_context, acme_understanding):
    from app.services.ai.reasoning.reasoning_engine import BusinessReasoningEngine

    return BusinessReasoningEngine().plan(
        user_prompt="How can I grow from ₹1.8 Cr to ₹3 Cr?",
        context=acme_context,
        question_understanding=acme_understanding,
    )


# --------------------------------------------------------------------------- #
# 1. ToolCall / ToolResult are frozen
# --------------------------------------------------------------------------- #


def test_1_tool_call_and_result_are_frozen():
    """Both dataclasses are frozen — assignment raises."""
    call = ToolCall(service_name="health_score")
    assert call.service_name == "health_score"
    assert call.inputs == {}
    result = ToolResult(service_name="health_score", status="ok")
    assert result.status == "ok"
    with pytest.raises((AttributeError, Exception)):
        call.service_name = "tampered"  # type: ignore[misc]


# --------------------------------------------------------------------------- #
# 2. StubToolInterface returns not_implemented
# --------------------------------------------------------------------------- #


def test_2_stub_tool_returns_not_implemented():
    """The default stub tool returns status='not_implemented'."""
    stub = StubToolInterface()
    out = stub.invoke(
        owner_id=1,
        call=ToolCall(service_name="health_score"),
        context=None,
    )
    assert out.status == "not_implemented"
    assert out.service_name == "health_score"
    assert out.error == "stub"


# --------------------------------------------------------------------------- #
# 3. ToolSelector picks from plan.applicable_deterministic_services
# --------------------------------------------------------------------------- #


def test_3_selector_picks_from_plan_services(acme_plan, acme_understanding, acme_context):
    """The selector reads from ReasoningPlan.applicable_deterministic_services.

    SPRINT AI-12 — the selector returns a :class:`ToolPlan`
    instead of a flat tuple. The legacy tuple is exposed via
    ``plan.all_tools()`` so existing tests stay valid.
    """
    selector = ToolSelector()
    plan = selector.select(
        question_understanding=acme_understanding,
        reasoning_plan=acme_plan,
        context=acme_context,
    )
    calls = plan.all_tools()
    assert len(calls) >= 1
    assert all(isinstance(c, ToolCall) for c in calls)
    # The selector never exceeds the cap
    assert len(calls) <= 5


# --------------------------------------------------------------------------- #
# 4. ToolSelector caps at MAX_TOOL_CALLS_PER_REQUEST
# --------------------------------------------------------------------------- #


def test_4_selector_caps_at_max_tool_calls(acme_understanding, acme_context):
    """When the plan has more than 5 services, the selector caps at 5."""
    # Build a fake plan with 8 services
    from app.services.ai.reasoning.pipeline import (
        ReasoningPipeline,
        ReasoningTrace,
    )

    plan = ReasoningPipeline().pre_llm_plan(
        user_prompt="test",
        context=acme_context,
    )
    # Replace via dataclasses.replace
    from dataclasses import replace

    plan = replace(
        plan,
        applicable_deterministic_services=(
            "health_score", "recommendation", "schemes_sprint16", "finance",
            "knowledge_retrieval", "risk", "insights", "business_dna",
        ),
    )
    selector = ToolSelector()
    tool_plan = selector.select(
        question_understanding=acme_understanding,
        reasoning_plan=plan,
        context=acme_context,
    )
    calls = tool_plan.all_tools()
    assert len(calls) == 5


# --------------------------------------------------------------------------- #
# 5. Dispatcher never raises — empty plan → empty results
# --------------------------------------------------------------------------- #


def test_5_dispatcher_empty_plan_returns_empty_results(
    acme_context, acme_understanding
):
    """A plan with no services returns an empty tuple — never raises."""
    from dataclasses import replace

    from app.services.ai.reasoning.pipeline import ReasoningPipeline
    from app.services.ai.reasoning.question_understanding import (
        QuestionUnderstanding,
    )

    # An "empty plan" with no services.
    base_plan = ReasoningPipeline().pre_llm_plan(
        user_prompt="test",
        context=acme_context,
    )
    empty_plan = replace(base_plan, applicable_deterministic_services=())

    # And an understanding with no services either, so the
    # selector's fallback path also returns empty.
    empty_understanding = QuestionUnderstanding(
        literal_question="",
        user_intent="general.business.advice",
        topic="general",
        is_business_specific=False,
        is_purely_educational=False,
        needs_deterministic_services=(),
    )

    dispatcher = ToolDispatcher()
    out = dispatcher.dispatch(
        owner_id=1,
        question_understanding=empty_understanding,
        reasoning_plan=empty_plan,
        context=acme_context,
    )
    assert out == ()


# --------------------------------------------------------------------------- #
# 6. Dispatcher with default registry returns not_implemented for each call
# --------------------------------------------------------------------------- #


def test_6_dispatcher_default_registry_returns_stubs(
    acme_context, acme_plan, acme_understanding
):
    """The default dispatcher registry returns not_implemented for every call."""
    dispatcher = ToolDispatcher()
    out = dispatcher.dispatch(
        owner_id=1,
        question_understanding=acme_understanding,
        reasoning_plan=acme_plan,
        context=acme_context,
    )
    assert len(out) >= 1
    for r in out:
        assert r.status == "not_implemented"
        assert r.error == "stub"


# --------------------------------------------------------------------------- #
# 7. Dispatcher respects DISPATCH_ENABLED kill switch
# --------------------------------------------------------------------------- #


def test_7_dispatcher_kill_switch_returns_empty(
    acme_context, acme_plan, acme_understanding
):
    """When the kill switch is off, the dispatcher returns an empty tuple."""
    ToolDispatcher._DISPATCH_ENABLED = False
    try:
        dispatcher = ToolDispatcher()
        out = dispatcher.dispatch(
            owner_id=1,
            question_understanding=acme_understanding,
            reasoning_plan=acme_plan,
            context=acme_context,
        )
        assert out == ()
    finally:
        ToolDispatcher._DISPATCH_ENABLED = True


# --------------------------------------------------------------------------- #
# 8. Custom tool registered and dispatched
# --------------------------------------------------------------------------- #


def test_8_dispatcher_invokes_custom_tool(
    acme_context, acme_understanding
):
    """A custom tool can be registered and the dispatcher invokes it."""
    from dataclasses import replace

    from app.services.ai.reasoning.pipeline import ReasoningPipeline

    base_plan = ReasoningPipeline().pre_llm_plan(
        user_prompt="test",
        context=acme_context,
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
                payload={"echo": call.inputs},
                duration_ms=1,
            )

    dispatcher = ToolDispatcher()
    dispatcher.register_tool("health_score", EchoTool())
    out = dispatcher.dispatch(
        owner_id=1,
        question_understanding=acme_understanding,
        reasoning_plan=plan,
        context=acme_context,
    )
    assert len(out) == 1
    assert out[0].status == "ok"
    assert out[0].payload["echo"]["industry"] == "Textiles"