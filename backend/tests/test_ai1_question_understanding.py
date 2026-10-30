"""Test suite for SPRINT AI-1 — Stage 1: QuestionUnderstanding."""

import pytest
from app.services.ai.providers.intent_router import QuestionIntent
from app.services.ai.reasoning.question_understanding import (
    QuestionUnderstanding,
    is_purely_educational,
    understand_question,
)


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture
def acme_context():
    """A realistic Acme Textiles context for the rank-and-share tests."""
    from app.services.ai.providers.base import AssistantContext, AssistantContextDna

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
# 1. understand_question — flagship intent still works
# --------------------------------------------------------------------------- #


def test_1_understand_question_flagship_revenue_target_returns_tuple(acme_context):
    """A flagship revenue-target prompt carries the existing QuestionIntent."""
    u = understand_question(
        "How can I grow from ₹1.8 Cr to ₹3 Cr?", acme_context
    )
    assert isinstance(u, QuestionUnderstanding)
    assert QuestionIntent.REACH_REVENUE_TARGET in u.relevant_existing_intents
    assert u.is_business_specific is True
    assert u.is_purely_educational is False
    assert u.topic in {"strategy", "finance"}


# --------------------------------------------------------------------------- #
# 2. Marketing question — non-flagship, still structured
# --------------------------------------------------------------------------- #


def test_2_understand_question_marketing_returns_topic_and_services(acme_context):
    """A marketing question gets a real topic + services tuple, not 'general'."""
    u = understand_question(
        "How should I market my B2B business?", acme_context
    )
    assert u.topic == "marketing"
    assert u.is_business_specific is True
    assert u.is_purely_educational is False
    assert u.complexity in {"simple", "moderate", "strategic", "scenario"}
    # Marketing prompts should request insights service
    assert "insights" in u.needs_deterministic_services
    # MUST NOT be empty — the system never says "I don't recognize this intent"
    assert u.relevant_existing_intents != ()


# --------------------------------------------------------------------------- #
# 3. Educational question — detected, classified, language-safe
# --------------------------------------------------------------------------- #


def test_3_understand_question_educational_what_is_working_capital(acme_context):
    """A pure educational question is flagged is_purely_educational=True."""
    u = understand_question("What is working capital?", acme_context)
    assert u.is_purely_educational is True
    assert u.is_business_specific is False
    # Topic is "education" or "finance" — both are acceptable
    # because "working capital" is a finance keyword AND the
    # prompt opens with an educational opener. The deterministic
    # invariant is that the prompt is educational + not
    # business-specific.
    assert u.topic in {"education", "finance"}
    assert u.complexity == "simple"


# --------------------------------------------------------------------------- #
# 4. Educational question vs. business-specific — distinction preserved
# --------------------------------------------------------------------------- #


def test_4_understand_question_what_is_my_working_capital_is_business_specific(
    acme_context,
):
    """A possessively phrased question is business-specific, not educational."""
    u = understand_question(
        "What is my working capital gap?", acme_context
    )
    assert u.is_purely_educational is False
    assert u.is_business_specific is True
    # The needle must point to finance, not education
    assert u.topic in {"finance", "strategy"}


# --------------------------------------------------------------------------- #
# 5. is_purely_educational — direct unit tests
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "prompt",
    [
        "What is working capital?",
        "Explain what a marketing funnel is.",
        "Define GST.",
        "What does ROI mean?",
        "What is photosynthesis?",
        "Explain the difference between marketing and advertising.",
    ],
)
def test_5_is_purely_educational_returns_true(prompt):
    """Pure educational/definition prompts are all flagged."""
    assert is_purely_educational(prompt) is True


@pytest.mark.parametrize(
    "prompt",
    [
        "What is my working capital gap?",
        "Help me grow my business.",
        "Should I hire five employees?",
        "What is the best marketing funnel for my business?",
        "Which government scheme should I apply for?",
        "",
        "   ",
    ],
)
def test_6_is_purely_educational_returns_false(prompt):
    """Business-specific and empty prompts are NOT educational."""
    assert is_purely_educational(prompt) is False


# --------------------------------------------------------------------------- #
# 7. Scenario question — scenario topic + complexity
# --------------------------------------------------------------------------- #


def test_7_understand_question_scenario_question(acme_context):
    """A 'what if' scenario question gets topic=scenario + complexity=scenario."""
    u = understand_question(
        "What happens if my supplier increases yarn prices by 10%?", acme_context
    )
    assert u.topic == "scenario"
    assert u.complexity == "scenario"
    assert "scenario_delta" in u.needs_calculations
    assert u.is_business_specific is True


# --------------------------------------------------------------------------- #
# 8. None / empty prompt — graceful fallback, no exception
# --------------------------------------------------------------------------- #


def test_8_understand_question_empty_prompt_returns_default():
    """An empty prompt returns a well-formed QuestionUnderstanding without raising."""
    u = understand_question("", None)
    assert isinstance(u, QuestionUnderstanding)
    assert u.literal_question == ""
    assert u.topic == "general"
    assert u.complexity == "moderate"
    assert u.is_business_specific is False
    # MUST include at least one existing intent (the GENERAL fallback)
    assert u.relevant_existing_intents == (QuestionIntent.GENERAL,)
