"""Test suite for SPRINT AI-1 — Stage 8: AdaptiveAnswer composition."""

import pytest

from app.services.ai.reasoning.answer_composer import (
    AdaptiveAnswer,
    AnswerShell,
    compose_adaptive_answer,
)


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


class _FakeUnderstanding:
    """Stand-in for :class:`QuestionUnderstanding`."""

    def __init__(
        self,
        *,
        complexity: str = "moderate",
        unknowns: tuple[str, ...] = (),
    ) -> None:
        self.complexity = complexity
        self.unknowns = unknowns


class _FakePlan:
    """Stand-in for :class:`ReasoningPlan`."""

    def __init__(self, possible_answer_structure: str = "") -> None:
        self.possible_answer_structure = possible_answer_structure


class _FakeKeyFinding:
    def __init__(self, statement: str) -> None:
        self.statement = statement


class _FakeRecommendation:
    def __init__(self, title: str) -> None:
        self.title = title


class _FakeParsed:
    """Stand-in for a parsed response (GroundedResponse shape)."""

    def __init__(
        self,
        *,
        executive_summary: str = "",
        key_findings: tuple = (),
        recommendations: tuple = (),
    ) -> None:
        self.executive_summary = executive_summary
        self.key_findings = key_findings
        self.recommendations = recommendations


# --------------------------------------------------------------------------- #
# 1. AdaptiveAnswer is a frozen dataclass with the expected defaults
# --------------------------------------------------------------------------- #


def test_1_adaptive_answer_defaults():
    """An empty AdaptiveAnswer has expanded mode + empty tuples."""
    aa = AdaptiveAnswer()
    assert aa.mode_used == "expanded"
    assert aa.sections == ()
    assert aa.executive_summary == ""
    assert aa.key_findings == ()
    assert aa.recommendations == ()
    assert aa.assumptions == ()
    assert aa.limitations == ()

    # Frozen
    with pytest.raises((AttributeError, Exception)):
        aa.mode_used = "executive"  # type: ignore[misc]


# --------------------------------------------------------------------------- #
# 2. Composer picks the executive shell for simple complexity
# --------------------------------------------------------------------------- #


def test_2_executive_shell_for_simple():
    """complexity='simple' → executive (3-section) shell."""
    parsed = _FakeParsed(executive_summary="Quick answer.")
    understanding = _FakeUnderstanding(complexity="simple")
    plan = _FakePlan()
    aa = compose_adaptive_answer(
        parsed=parsed,
        question_understanding=understanding,
        reasoning_plan=plan,
    )
    assert aa.mode_used == "executive"
    assert len(aa.sections) == 3
    assert aa.executive_summary == "Quick answer."


# --------------------------------------------------------------------------- #
# 3. Composer picks the scenario shell for scenario complexity
# --------------------------------------------------------------------------- #


def test_3_scenario_shell_for_scenario_complexity():
    """complexity='scenario' → scenario (4-section) shell."""
    parsed = _FakeParsed(executive_summary="Best case outcome.")
    understanding = _FakeUnderstanding(complexity="scenario")
    plan = _FakePlan()
    aa = compose_adaptive_answer(
        parsed=parsed,
        question_understanding=understanding,
        reasoning_plan=plan,
    )
    assert aa.mode_used == "scenario"
    assert len(aa.sections) == 4
    assert "SCENARIO ASSUMPTIONS" in aa.sections[0]
    assert any("estimates" in a for a in aa.assumptions)


# --------------------------------------------------------------------------- #
# 4. Composer picks missing_info shell when unknowns present
# --------------------------------------------------------------------------- #


def test_4_missing_info_shell_when_unknowns_present():
    """When unknowns is non-empty, missing_info wins over complexity."""
    parsed = _FakeParsed()
    understanding = _FakeUnderstanding(
        complexity="moderate", unknowns=("customer_mix", "unit_economics")
    )
    plan = _FakePlan()
    aa = compose_adaptive_answer(
        parsed=parsed,
        question_understanding=understanding,
        reasoning_plan=plan,
    )
    assert aa.mode_used == "missing_info"
    assert any("customer_mix" in lim for lim in aa.limitations)
    assert any("unit_economics" in lim for lim in aa.limitations)


# --------------------------------------------------------------------------- #
# 5. Plan's possible_answer_structure overrides understanding
# --------------------------------------------------------------------------- #


def test_5_plan_possible_answer_structure_overrides():
    """The plan's possible_answer_structure wins over complexity/unknowns."""
    parsed = _FakeParsed()
    understanding = _FakeUnderstanding(
        complexity="simple", unknowns=("some_unknown",)
    )
    plan = _FakePlan(possible_answer_structure="scenario")
    aa = compose_adaptive_answer(
        parsed=parsed,
        question_understanding=understanding,
        reasoning_plan=plan,
    )
    assert aa.mode_used == "scenario"


# --------------------------------------------------------------------------- #
# 6. Composer extracts key findings + recommendations from parsed
# --------------------------------------------------------------------------- #


def test_6_extracts_findings_and_recommendations():
    """Top-5 findings + top-3 recs surface from a parsed response."""
    parsed = _FakeParsed(
        executive_summary="Revenue at ₹1.8 Cr.",
        key_findings=(
            _FakeKeyFinding("Top risk is supplier concentration."),
            _FakeKeyFinding("Cash cycle is 68 days."),
            _FakeKeyFinding("Margin compressed 4pp QoQ."),
        ),
        recommendations=(
            _FakeRecommendation("Diversify supplier base"),
            _FakeRecommendation("Renegotiate top-3 contracts"),
            _FakeRecommendation("Open export desk"),
        ),
    )
    understanding = _FakeUnderstanding(complexity="moderate")
    plan = _FakePlan()
    aa = compose_adaptive_answer(
        parsed=parsed,
        question_understanding=understanding,
        reasoning_plan=plan,
    )
    assert aa.mode_used == "expanded"
    assert len(aa.sections) == 10
    assert "supplier concentration" in aa.key_findings[0]
    assert "Diversify" in aa.recommendations[0]
    assert len(aa.key_findings) == 3
    assert len(aa.recommendations) == 3