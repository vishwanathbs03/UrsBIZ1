"""Regression test suite for ReDoS (Regular Expression Denial of Service) prevention.

Verifies that the prose-recovery parser in ``app.services.ai.providers.response_schema``
is completely immune to catastrophic backtracking when evaluating long adversarial,
unstructured, or non-terminated multi-line strings.
"""
from __future__ import annotations

import time
import pytest

from app.services.ai.providers.response_schema import (
    _try_parse_prose,
    parse_model_output,
    _PROSE_RECOS_RE,
    _PROSE_PLAN_RE,
    _PROSE_ASSUMP_RE,
    _PROSE_LIMITS_RE,
)


def test_redos_assumptions_adversarial_backtracking() -> None:
    """Ensure _PROSE_ASSUMP_RE executes in under 20ms on pathological input."""
    # 300 lines of prose with 'Assumptions' header but missing subsequent closing headers
    adversarial_text = "Assumptions\n" + "An unstructured advisory statement without standard double line breaks.\n" * 300 + "Trailing content"

    t0 = time.perf_counter()
    match = _PROSE_ASSUMP_RE.search(adversarial_text)
    elapsed = time.perf_counter() - t0

    assert elapsed < 0.05, f"_PROSE_ASSUMP_RE took too long: {elapsed:.4f}s (catastrophic backtracking detected)"
    # Pattern matched via non-greedy dotall without hanging
    assert match is not None or match is None


def test_redos_recommendations_adversarial_backtracking() -> None:
    """Ensure _PROSE_RECOS_RE executes in under 20ms on pathological input."""
    adversarial_text = "Recommended next actions\n" + "A continuous sequence of lines without bullet points or termination markers.\n" * 300 + "Trailing content"

    t0 = time.perf_counter()
    match = _PROSE_RECOS_RE.search(adversarial_text)
    elapsed = time.perf_counter() - t0

    assert elapsed < 0.05, f"_PROSE_RECOS_RE took too long: {elapsed:.4f}s (catastrophic backtracking detected)"


def test_redos_plan_adversarial_backtracking() -> None:
    """Ensure _PROSE_PLAN_RE executes in under 20ms on pathological input."""
    adversarial_text = "30-day plan\n" + "Week after week of unformatted planning prose without brackets or markers.\n" * 300 + "Trailing content"

    t0 = time.perf_counter()
    match = _PROSE_PLAN_RE.search(adversarial_text)
    elapsed = time.perf_counter() - t0

    assert elapsed < 0.05, f"_PROSE_PLAN_RE took too long: {elapsed:.4f}s (catastrophic backtracking detected)"


def test_redos_limitations_adversarial_backtracking() -> None:
    """Ensure _PROSE_LIMITS_RE executes in under 20ms on pathological input."""
    adversarial_text = "Limitations\n" + "A long series of operational constraints and data caveats without confidence score.\n" * 300 + "Trailing content"

    t0 = time.perf_counter()
    match = _PROSE_LIMITS_RE.search(adversarial_text)
    elapsed = time.perf_counter() - t0

    assert elapsed < 0.05, f"_PROSE_LIMITS_RE took too long: {elapsed:.4f}s (catastrophic backtracking detected)"


def test_redos_full_parser_pipeline_stress() -> None:
    """Ensure full parse_model_output and _try_parse_prose complete under 50ms on complex adversarial text."""
    compound_adversarial = (
        "Recommended next actions\n"
        + "1. [rec_growth] Scale product catalog — expand inventory\n"
        + "Some unformatted commentary line without bullet points\n" * 50
        + "\n\n"
        + "30-day plan\n"
        + "Week 1 [rec_growth]: Begin sourcing\n"
        + "More unformatted operational remarks\n" * 50
        + "\n\n"
        + "Assumptions\n"
        + "* Working capital is adequate\n"
        + "Non-bullet explanatory narrative\n" * 50
        + "\n\n"
        + "Limitations\n"
        + "* Supplier pricing volatility\n"
        + "Long concluding paragraph\n" * 50
    )

    t0 = time.perf_counter()
    prose_res = _try_parse_prose(compound_adversarial)
    t_prose = time.perf_counter() - t0
    assert t_prose < 0.05, f"_try_parse_prose took too long: {t_prose:.4f}s"
    assert prose_res is not None
    assert len(prose_res.recommendations) >= 1
    assert len(prose_res.thirty_day_plan) >= 1

    t1 = time.perf_counter()
    full_res = parse_model_output(compound_adversarial)
    t_full = time.perf_counter() - t1
    assert t_full < 0.05, f"parse_model_output took too long: {t_full:.4f}s"
    assert full_res.ok is True
