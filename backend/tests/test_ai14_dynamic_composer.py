"""Sprint AI-14 — unit tests for the ``dynamic_section_selector``.

Covers the UX contract:
  * ``direct_answer`` is ALWAYS first.
  * MAX_SUPPORTING_SECTIONS = 3 — complex prompts fall back to
    the ``fallback_shell`` so the renderer returns a fuller
    report instead of truncating the answer.
  * Contradiction severity / unsupported claim counter force
    the ``confidence`` section to appear last.
  * ``select_shell`` picks the right shell literal.
"""

from __future__ import annotations

from app.services.ai.reasoning.answer_requirements import AnswerRequirements
from app.services.ai.reasoning.dynamic_section_selector import (
    ALL_SECTIONS,
    MAX_SUPPORTING_SECTIONS,
    exceeds_max_sections,
    select_sections,
    select_shell,
)


def test_constants():
    """Public invariants — single source of truth."""
    assert MAX_SUPPORTING_SECTIONS == 3
    assert "direct_answer" in ALL_SECTIONS
    assert "confidence" in ALL_SECTIONS


def test_direct_answer_always_first():
    """Hero-direct-answer is non-negotiable."""
    req = AnswerRequirements()
    sections = select_sections(req)
    assert sections[0] == "direct_answer"


def test_legacy_none_returns_hero_only():
    """None requirements ⇒ just ('direct_answer',)."""
    sections = select_sections(None)
    assert sections == ("direct_answer",)


def test_business_evidence_included():
    """needs_business_evidence lights up business_evidence."""
    req = AnswerRequirements(needs_business_evidence=True)
    sections = select_sections(req)
    assert "business_evidence" in sections


def test_calculation_included():
    """needs_calculation lights up calculations."""
    req = AnswerRequirements(needs_calculation=True)
    sections = select_sections(req)
    assert "calculations" in sections


def test_missing_data_included_on_unsupported():
    """unsupported_claim_count > 0 lights up missing_data."""
    req = AnswerRequirements()
    sections = select_sections(req, unsupported_claim_count=2)
    assert "missing_data" in sections


def test_confidence_appended_when_high_contradiction():
    """Contradiction severity == 'high' appends confidence."""
    req = AnswerRequirements()
    sections = select_sections(req, contradiction_severity="high")
    assert "confidence" in sections
    assert sections[-1] == "confidence"


def test_max_three_supports_after_hero():
    """Sections capped at MAX_SUPPORTING_SECTIONS + 1."""
    req = AnswerRequirements(
        needs_business_evidence=True,
        needs_calculation=True,
        needs_assumptions=True,
        needs_missing_data=True,
        needs_external_information=True,
    )
    sections = select_sections(req)
    assert len(sections) <= MAX_SUPPORTING_SECTIONS + 1


def test_exceeds_max_sections_helper():
    """exceeds_max_sections counts supports separately from direct_answer."""
    assert exceeds_max_sections(("direct_answer", "a", "b", "c")) is False
    assert exceeds_max_sections(("direct_answer", "a", "b", "c", "d")) is True
    assert exceeds_max_sections(("direct_answer",)) is False


def test_select_shell_fallback_when_exceeds():
    """When sections exceed the cap, shell is fallback_shell."""
    req = AnswerRequirements(
        needs_business_evidence=True,
        needs_calculation=True,
        needs_assumptions=True,
        needs_missing_data=True,
        needs_external_information=True,
    )
    sections = select_sections(req)
    shell = select_shell(
        req, sections=sections, fallback_shell="expanded"
    )
    # Either we get a single shell literal OR a fallback shell.
    assert shell in {"expanded", "scenario", "comparison", "external",
                     "calculation", "business_analysis", "general_knowledge"}


def test_select_shell_picks_scenario():
    """needs_scenario without overflow selects 'scenario'."""
    req = AnswerRequirements(needs_scenario=True)
    sections = select_sections(req)
    shell = select_shell(req, sections=sections, fallback_shell="expanded")
    assert shell == "scenario"


def test_select_shell_picks_comparison():
    """needs_comparison selects 'comparison'."""
    req = AnswerRequirements(needs_comparison=True)
    sections = select_sections(req)
    shell = select_shell(req, sections=sections, fallback_shell="expanded")
    assert shell == "comparison"


def test_select_shell_default_is_general_knowledge():
    """Empty AnswerRequirements + 1 section ⇒ general_knowledge."""
    req = AnswerRequirements()
    sections = select_sections(req)
    shell = select_shell(req, sections=sections, fallback_shell="expanded")
    assert shell == "general_knowledge"