"""Test suite for SPRINT AI-1 — Stage 4: ReasoningPlan upgrade."""

import pytest

from app.services.ai.providers.base import (
    AssistantContext,
    AssistantContextDna,
)
from app.services.ai.reasoning.pipeline import ReasoningPipeline, ReasoningPlan
from app.services.ai.reasoning.question_understanding import understand_question
from app.services.ai.reasoning.reasoning_engine import BusinessReasoningEngine


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture
def acme_context():
    """A minimal Acme Textiles context."""
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


# --------------------------------------------------------------------------- #
# 1. New fields have defaults — backward-compat preservation
# --------------------------------------------------------------------------- #


def test_1_reasoning_plan_default_fields_have_safe_defaults(acme_context):
    """A 6-arg ReasoningPlan construction still works — new fields default safely."""
    plan = ReasoningPipeline().pre_llm_plan(
        user_prompt="How can I grow?", context=acme_context
    )
    # New AI-1 fields
    assert plan.question_interpretation == ""
    assert plan.applicable_deterministic_services == ()
    assert plan.calculations_required == ()
    assert plan.unknowns == ()
    assert plan.possible_answer_structure == "expanded"


# --------------------------------------------------------------------------- #
# 2. pre_llm_plan with question_understanding populates new fields
# --------------------------------------------------------------------------- #


def test_2_pre_llm_plan_with_understanding_populates_new_fields(acme_context):
    """When a QuestionUnderstanding is supplied, the new fields are populated."""
    understanding = understand_question(
        "How can I grow from ₹1.8 Cr to ₹3 Cr?", acme_context
    )
    plan = ReasoningPipeline().pre_llm_plan(
        user_prompt="How can I grow from ₹1.8 Cr to ₹3 Cr?",
        context=acme_context,
        question_understanding=understanding,
    )
    # The user_intent dotted path is threaded into the plan
    assert "strategic" in plan.question_interpretation or "finance" in plan.question_interpretation
    # The services tuple must contain at least one service
    assert len(plan.applicable_deterministic_services) >= 1
    # Strategy + complex prompt → expanded shell (default)
    assert plan.possible_answer_structure in {"expanded", "scenario", "missing_info"}


# --------------------------------------------------------------------------- #
# 3. Scenario complexity flips the answer structure to "scenario"
# --------------------------------------------------------------------------- #


def test_3_scenario_complexity_flips_answer_structure(acme_context):
    """A scenario prompt flips possible_answer_structure to 'scenario'."""
    understanding = understand_question(
        "What happens if my supplier increases prices by 10%?", acme_context
    )
    plan = ReasoningPipeline().pre_llm_plan(
        user_prompt="What happens if my supplier increases prices by 10%?",
        context=acme_context,
        question_understanding=understanding,
    )
    assert plan.possible_answer_structure == "scenario"


# --------------------------------------------------------------------------- #
# 4. Missing-info shell fires when unknowns is non-empty
# --------------------------------------------------------------------------- #


def test_4_missing_info_shell_fires_when_unknowns_present():
    """When the context is missing required fields, unknowns non-empty → missing_info shell."""
    # A context with NO industry + NO revenue — every prompt
    # should see unknowns populated.
    ctx = AssistantContext(
        business_id=1,
        legal_name="",
        overall_business_score=0,
        band="Unknown",
        dna=AssistantContextDna("unknown", "Unknown", 0),
    )
    understanding = understand_question("Help me grow", ctx)
    assert len(understanding.unknowns) >= 1
    plan = ReasoningPipeline().pre_llm_plan(
        user_prompt="Help me grow",
        context=ctx,
        question_understanding=understanding,
    )
    assert plan.possible_answer_structure == "missing_info"


# --------------------------------------------------------------------------- #
# 5. BusinessReasoningEngine.plan accepts optional question_understanding
# --------------------------------------------------------------------------- #


def test_5_engine_plan_accepts_optional_question_understanding(acme_context):
    """Calling plan() without a question_understanding still works (legacy 2-kwarg form)."""
    engine = BusinessReasoningEngine()
    plan = engine.plan(user_prompt="Help me grow", context=acme_context)
    # The plan is valid even though no question_understanding was passed.
    assert plan.intent in {"general", "reach_revenue_target", "biggest_weakness"}
    # AI-1 fields default to safe values
    assert plan.possible_answer_structure in {"expanded", "scenario", "missing_info", "executive"}


def test_6_engine_plan_accepts_shared_question_understanding(acme_context):
    """Calling plan() with an explicit question_understanding populates the new fields."""
    engine = BusinessReasoningEngine()
    understanding = understand_question(
        "Should I expand exports to Europe?", acme_context
    )
    plan = engine.plan(
        user_prompt="Should I expand exports to Europe?",
        context=acme_context,
        question_understanding=understanding,
    )
    # The engine's intent overrides the pipeline's "general"
    assert plan.intent == "export_expansion"
    # The understanding's user_intent is threaded into the plan
    assert "export" in plan.question_interpretation.lower()