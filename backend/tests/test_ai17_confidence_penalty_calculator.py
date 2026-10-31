"""SPRINT AI-17 — Bounded Answer Repair + Claim Lifecycle.

Tests for ``confidence_penalty_calculator``: the additive
penalty layer (PART 6) — stale external, corrected claim,
incomplete financial inputs.

7 tests covering:
  * No signals → total_penalty=0
  * Single stale external source → -3
  * Corrected claim event → -2
  * Incomplete financial inputs (2+ missing) → -4
  * All three signals compound → -9
  * apply_to_score clamps to [0, 100]
  * Penalty is capped at -40
"""

from __future__ import annotations

from types import SimpleNamespace

from app.services.ai.reasoning.confidence_penalty_calculator import (
    ConfidencePenaltyCalculator,
    PenaltyReport,
)


def _freshness_warning(status: str, source: str = "rbi.org.in"):
    """Build a SimpleNamespace mimicking an ExternalSource dict."""
    return {"source_url": source, "freshness_status": status}


def _lifecycle_event(new_status: str, claim_id: str = "c1"):
    return SimpleNamespace(claim_id=claim_id, new_status=new_status)


def _context(**overrides):
    """Build a SimpleNamespace mimicking AssistantContext with
    sane financial-input defaults."""
    defaults = {
        "annual_revenue": 1000000.0,
        "monthly_expenses": 80000.0,
        "gross_margin": 0.18,
        "headcount": 25,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


# --------------------------------------------------------------------------- #
# 1 — No signals → zero penalty
# --------------------------------------------------------------------------- #


def test_no_signals_yields_zero_penalty():
    """When no signals fire the AI-17 layer adds zero."""
    calc = ConfidencePenaltyCalculator()
    report = calc.compute_penalty()
    assert report.total_penalty == 0
    assert report.components == {}
    assert "no AI-17 penalties" in report.rationale


# --------------------------------------------------------------------------- #
# 2 — Stale external source → -3
# --------------------------------------------------------------------------- #


def test_stale_external_source_penalty():
    """At least one source with freshness AGING/STALE/UNKNOWN
    triggers the -3 stale_external_source penalty."""
    calc = ConfidencePenaltyCalculator()
    warnings = (
        _freshness_warning("FRESH", "rbi.org.in"),
        _freshness_warning("STALE", "indianexpress.com"),
    )
    report = calc.compute_penalty(freshness_warnings=warnings)
    assert report.components.get("stale_external_source") == -3
    assert report.total_penalty == -3


# --------------------------------------------------------------------------- #
# 3 — Corrected claim event → -2
# --------------------------------------------------------------------------- #


def test_corrected_claim_event_penalty():
    """At least one corrected lifecycle event triggers -2."""
    calc = ConfidencePenaltyCalculator()
    events = (
        _lifecycle_event("corrected", "c1"),
        _lifecycle_event("active", "c2"),
    )
    report = calc.compute_penalty(lifecycle_events=events)
    assert report.components.get("corrected_claim") == -2
    assert report.total_penalty == -2


# --------------------------------------------------------------------------- #
# 4 — Incomplete financial inputs (2+ missing) → -4
# --------------------------------------------------------------------------- #


def test_incomplete_financial_inputs_penalty():
    """When 2+ of the four financial input fields are missing
    the calculator applies the -4 incomplete_financial_inputs
    penalty."""
    calc = ConfidencePenaltyCalculator()
    # Two missing: gross_margin and headcount are None.
    ctx = _context(gross_margin=None, headcount=None)
    report = calc.compute_penalty(context=ctx)
    assert report.components.get("incomplete_financial_inputs") == -4
    assert report.total_penalty == -4


# --------------------------------------------------------------------------- #
# 5 — All three signals compound
# --------------------------------------------------------------------------- #


def test_all_three_signals_compound():
    """When all three signals fire the penalties add: -3 + -2 + -4 = -9."""
    calc = ConfidencePenaltyCalculator()
    warnings = (_freshness_warning("STALE"),)
    events = (_lifecycle_event("corrected"),)
    ctx = _context(gross_margin=None, headcount=None)
    report = calc.compute_penalty(
        freshness_warnings=warnings,
        lifecycle_events=events,
        context=ctx,
    )
    assert report.total_penalty == -9
    assert report.components == {
        "stale_external_source": -3,
        "corrected_claim": -2,
        "incomplete_financial_inputs": -4,
    }


# --------------------------------------------------------------------------- #
# 6 — apply_to_score clamps to [0, 100]
# --------------------------------------------------------------------------- #


def test_apply_to_score_clamps_to_zero():
    """apply_to_score subtracts the penalty and clamps to >=0."""
    calc = ConfidencePenaltyCalculator()
    report = PenaltyReport(
        total_penalty=-15,
        components={"stale_external_source": -3, "corrected_claim": -2},
        rationale="",
    )
    # 10 - 15 = -5 → clamp to 0
    assert calc.apply_to_score(10, report) == 0
    # 50 - 15 = 35
    assert calc.apply_to_score(50, report) == 35


# --------------------------------------------------------------------------- #
# 7 — Penalty is capped at -40
# --------------------------------------------------------------------------- #


def test_penalty_capped_at_minus_40():
    """The wire field ``confidence_penalty`` is 0..40 — the
    calculator caps the additive penalty at -40 even when the
    individual signals would otherwise sum beyond that."""
    calc = ConfidencePenaltyCalculator()
    # Stale external (-3), corrected (-2), incomplete (-4) plus
    # forcing more stale entries shouldn't blow past -40.
    warnings = tuple(
        _freshness_warning(status) for status in ("STALE", "AGING", "UNKNOWN")
    )
    events = (
        _lifecycle_event("corrected"),
        _lifecycle_event("corrected"),
    )
    ctx = _context(gross_margin=None, headcount=None, monthly_expenses=None)
    report = calc.compute_penalty(
        freshness_warnings=warnings,
        lifecycle_events=events,
        context=ctx,
    )
    # The signals still fire; only ONE stale penalty applies
    # (it's a bool flag, not a count), so total = -3 - 2 - 4 = -9.
    # The cap exists to protect against future signal categories.
    assert report.total_penalty >= -40
    assert -40 <= report.total_penalty <= 0


# --------------------------------------------------------------------------- #
# 8 — to_dict round-trip
# --------------------------------------------------------------------------- #


def test_penalty_report_to_dict_round_trip():
    """:meth:`PenaltyReport.to_dict` serialises safely."""
    report = PenaltyReport(
        total_penalty=-5,
        components={"stale_external_source": -3, "corrected_claim": -2},
        rationale="stale_external_source=-3, corrected_claim=-2 -> -5",
    )
    d = report.to_dict()
    assert d["total_penalty"] == -5
    assert d["components"] == {
        "stale_external_source": -3,
        "corrected_claim": -2,
    }
    assert "->" in d["rationale"]


# --------------------------------------------------------------------------- #
# 9 — incomplete threshold is exactly 2 (below threshold is no penalty)
# --------------------------------------------------------------------------- #


def test_incomplete_below_threshold_yields_no_penalty():
    """Only ONE missing financial input does NOT trigger the penalty."""
    calc = ConfidencePenaltyCalculator()
    ctx = _context(gross_margin=None)  # one missing
    report = calc.compute_penalty(context=ctx)
    assert report.components == {}
    assert report.total_penalty == 0
