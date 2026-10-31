"""15-category test — SPRINT AI-12 universal question sweep.

Drives 15 hand-written prompts through the universal
understanding layer + answer_composer + minimal_slice. Asserts:

  * every prompt produces a non-empty capability tuple,
  * every prompt produces an answer_mode from the 8-literal
    vocabulary,
  * the answer composer picks a recognised shell for every
    prompt.
"""
from __future__ import annotations

from app.services.ai.reasoning.answer_composer import (
    _SECTIONS_BY_SHELL,
    compose_adaptive_answer,
)
from app.services.ai.reasoning.question_understanding import (
    QuestionUnderstanding,
    understand_question,
)


CATEGORIES = [
    ("What is my business health score?",
     ("CALCULATION",)),
    ("How can I reach my revenue target?",
     ("FINANCIAL", "RECOMMENDATION")),
    ("What MSME schemes can I apply for?",
     ("GOVERNMENT_SCHEME",)),
    ("What is EBITDA?",
     ("GENERAL_KNOWLEDGE",)),
    ("What if cotton prices increase by 12%?",
     ("SCENARIO",)),
    ("Predict my revenue for next quarter",
     ("FORECAST",)),
    ("Compare my business with industry average",
     ("COMPARISON",)),
    ("Calculate my working capital gap",
     ("CALCULATION",)),
    ("Recommend ways to grow my business",
     ("RECOMMENDATION",)),
    ("What are the export procedures?",
     ("EXPORT",)),
    ("Build a 12-month roadmap for me",
     ("ROADMAP",)),
    ("What should I do next month?",
     ("ROADMAP",)),
    ("Tell me about the Udyam registration process",
     ("GOVERNMENT_SCHEME",)),
    ("What is my biggest risk right now?",
     ("RISK",)),
    ("Should I hire two more staff?",
     ("OPERATIONAL",)),
]

ANSWER_MODES = {
    "general_knowledge", "business_analysis", "calculation", "scenario",
    "comparison", "scheme", "external", "mixed",
}


class TestSprintAI12Categories:

    def test_each_category_classified(self) -> None:
        for prompt, expected_caps in CATEGORIES:
            qu = understand_question(prompt)
            assert qu.capability, f"empty capability for: {prompt!r}"
            assert qu.answer_mode in ANSWER_MODES, (
                f"unexpected answer_mode for: {prompt!r} → {qu.answer_mode}"
            )
            # Every expected capability token must appear in
            # the capability tuple (loose match — multi-capability
            # prompts can also surface other tokens).
            for cap in expected_caps:
                assert cap in qu.capability, (
                    f"missing {cap} in capability for: {prompt!r} "
                    f"→ {qu.capability}"
                )

    def test_each_category_picks_a_registered_shell(self) -> None:
        for prompt, _ in CATEGORIES:
            qu = understand_question(prompt)
            class _Q:
                answer_mode = qu.answer_mode
                unknowns = qu.unknowns
                complexity = qu.complexity
            class _P:
                possible_answer_structure = ""
            aa = compose_adaptive_answer(
                parsed=None, question_understanding=_Q(), reasoning_plan=_P(),
            )
            assert aa.mode_used in _SECTIONS_BY_SHELL, (
                f"unregistered shell for: {prompt!r} → {aa.mode_used}"
            )
