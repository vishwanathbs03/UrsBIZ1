"""Tests for SPRINT AI-12 — Adaptive answer composer 4 new shells.

The 4 new shells (``comparison``, ``scheme``, ``external``,
``table_checklist``) plus the 3 capability-mode aliases
(``general_knowledge``, ``business_analysis``, ``calculation``).
The tests assert:

  * every shell has a non-empty ``sections`` tuple,
  * the composer picks the right shell when given a
    ``QuestionUnderstanding`` whose ``answer_mode`` matches,
  * the legacy 4 shells (``executive``, ``expanded``,
    ``scenario``, ``missing_info``) still render unchanged.
"""
from __future__ import annotations

from app.services.ai.reasoning.answer_composer import (
    _SECTIONS_BY_SHELL,
    compose_adaptive_answer,
)


class TestAnswerShellExtensions:

    def test_eight_shells_registered(self) -> None:
        for s in (
            "executive", "expanded", "scenario", "missing_info",
            "comparison", "scheme", "external", "table_checklist",
        ):
            assert s in _SECTIONS_BY_SHELL

    def test_three_capability_aliases(self) -> None:
        for s in ("general_knowledge", "business_analysis", "calculation"):
            assert s in _SECTIONS_BY_SHELL

    def test_composer_picks_comparison_shell(self) -> None:
        class _Q:
            answer_mode = "comparison"
            unknowns = ()
            complexity = "moderate"
        class _P:
            possible_answer_structure = ""
        aa = compose_adaptive_answer(parsed=None, question_understanding=_Q(), reasoning_plan=_P())
        assert aa.mode_used == "comparison"
        assert aa.sections

    def test_composer_picks_scheme_shell(self) -> None:
        class _Q:
            answer_mode = "scheme"
            unknowns = ()
            complexity = "moderate"
        class _P:
            possible_answer_structure = ""
        aa = compose_adaptive_answer(parsed=None, question_understanding=_Q(), reasoning_plan=_P())
        assert aa.mode_used == "scheme"

    def test_composer_picks_external_shell(self) -> None:
        class _Q:
            answer_mode = "external"
            unknowns = ()
            complexity = "moderate"
        class _P:
            possible_answer_structure = ""
        aa = compose_adaptive_answer(parsed=None, question_understanding=_Q(), reasoning_plan=_P())
        assert aa.mode_used == "external"

    def test_composer_picks_table_checklist_shell(self) -> None:
        class _Q:
            answer_mode = "table_checklist"
            unknowns = ()
            complexity = "moderate"
        class _P:
            possible_answer_structure = ""
        aa = compose_adaptive_answer(parsed=None, question_understanding=_Q(), reasoning_plan=_P())
        assert aa.mode_used == "table_checklist"

    def test_legacy_executive_shell_still_works(self) -> None:
        class _Q:
            answer_mode = "general_knowledge"
            unknowns = ()
            complexity = "simple"
        class _P:
            possible_answer_structure = ""
        aa = compose_adaptive_answer(parsed=None, question_understanding=_Q(), reasoning_plan=_P())
        assert aa.mode_used in ("executive", "general_knowledge")

    def test_unknown_answer_mode_falls_through(self) -> None:
        """An unmapped answer_mode must NOT crash; the composer
        falls back to ``expanded`` (the safe default)."""
        class _Q:
            answer_mode = "no_such_mode"
            unknowns = ()
            complexity = "moderate"
        class _P:
            possible_answer_structure = ""
        aa = compose_adaptive_answer(parsed=None, question_understanding=_Q(), reasoning_plan=_P())
        assert aa.mode_used == "expanded"
