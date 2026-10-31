"""SPRINT AI-18 — Universal AI Evaluation Harness.

Data-quality profile fixtures.

The brief (PART 5) requires the runner to evaluate the
assistant on profiles that range from complete to adversarial:

  * complete business profile
  * minimal profile
  * missing revenue
  * missing employees
  * missing financial data
  * contradictory profile/analytics
  * stale external source
  * unavailable tool result

Each :class:`DataQualityProfile` is a deterministic
``AssistantContext``-shaped object the runner can plug
into the production pipeline. The harness NEVER mutates
production data — profiles are build-only fixtures.

Profiles use the REAL :class:`AssistantContext` dataclass
so the production layers (AI-1 through AI-17) see a
fully-shaped context. The runner is a fixture harness,
NOT a shortcut around the production path.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Any

from app.services.ai.providers.base import (
    AssistantContext,
    AssistantContextDna,
)


# --------------------------------------------------------------------------- #
# Profile dataclass
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class DataQualityProfile:
    """One evaluation profile + the safety contract.

    ``factory`` is a no-arg callable that returns an
    :class:`AssistantContext` the runner can plug into the
    production provider service.

    ``quality_notes`` describes what is missing / wrong so
    the audit trail knows what the case is testing.
    """

    profile_id: str
    label: str
    factory: Any  # Callable[[], AssistantContext]
    quality_notes: str
    expected_warning: bool = False
    expected_disclosure: bool = False
    expected_confidence_max: float = 100.0

    def build(self) -> AssistantContext:
        return self.factory()


# --------------------------------------------------------------------------- #
# Helper builders
# --------------------------------------------------------------------------- #


def _now_iso(days_ago: int = 0) -> str:
    """Current UTC ISO timestamp; ``-N`` days when ``days_ago`` set."""
    dt = datetime.now(tz=timezone.utc) - timedelta(days=days_ago)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _complete_profile() -> AssistantContext:
    """Healthy Acme — complete revenue, expenses, margin, headcount."""
    return AssistantContext(
        business_id=1,
        legal_name="Acme Textiles",
        trade_name="Acme",
        industry="Textiles",
        sub_industry="Knitted fabrics",
        business_type="Manufacturer",
        location="Tirupur",
        employee_count=42,
        annual_revenue_inr=18_000_000,
        target_revenue_inr=30_000_000,
        monthly_payroll_cost_inr=1_200_000,
        monthly_operating_cash_flow_inr=300_000,
        operating_margin_pct=18.0,
        overall_business_score=68,
        band="Established",
        dna=AssistantContextDna(
            archetype_key="growth_seeker",
            archetype_title="Growth Seeker",
            match_score=82,
        ),
        twin_generated_at=_now_iso(days_ago=1),
        recommendations_generated_at=_now_iso(days_ago=2),
        insights_generated_at=_now_iso(days_ago=3),
        forecasts_generated_at=_now_iso(days_ago=4),
        schemes_generated_at=_now_iso(days_ago=5),
        action_items_generated_at=_now_iso(days_ago=2),
        rules_generated_at=_now_iso(days_ago=1),
        roadmap_generated_at=_now_iso(days_ago=7),
    )


def _minimal_profile() -> AssistantContext:
    """Profile with just the legal-name and industry filled in."""
    return AssistantContext(
        business_id=2,
        legal_name="Bare Necessities",
        industry="Retail",
        overall_business_score=0,
        band="Emerging",
        dna=AssistantContextDna(
            archetype_key="unknown",
            archetype_title="Unknown",
            match_score=0,
        ),
        # Everything else default-zero / empty.
    )


def _missing_revenue_profile() -> AssistantContext:
    """Revenue / margin / target missing but other fields populated."""
    return AssistantContext(
        business_id=3,
        legal_name="Acme Textiles",
        industry="Textiles",
        location="Tirupur",
        business_type="Manufacturer",
        employee_count="42",
        # annual_revenue_inr, target_revenue_inr, monthly_payroll_cost_inr
        # all default to 0 (the AI-7 missing sentinel).
        overall_business_score=68,
        band="Established",
        dna=AssistantContextDna(
            archetype_key="growth_seeker",
            archetype_title="Growth Seeker",
            match_score=82,
        ),
        twin_generated_at=_now_iso(days_ago=1),
        recommendations_generated_at=_now_iso(days_ago=2),
    )


def _missing_employees_profile() -> AssistantContext:
    """Employee count missing."""
    return AssistantContext(
        business_id=4,
        legal_name="Acme Textiles",
        industry="Textiles",
        location="Tirupur",
        business_type="Manufacturer",
        # employee_count missing (defaults to "unknown")
        annual_revenue_inr=18_000_000,
        target_revenue_inr=30_000_000,
        overall_business_score=68,
        band="Established",
        dna=AssistantContextDna(
            archetype_key="growth_seeker",
            archetype_title="Growth Seeker",
            match_score=82,
        ),
        twin_generated_at=_now_iso(days_ago=1),
    )


def _missing_financial_profile() -> AssistantContext:
    """All financial fields missing."""
    return AssistantContext(
        business_id=5,
        legal_name="Acme Textiles",
        industry="Textiles",
        location="Tirupur",
        business_type="Manufacturer",
        employee_count="42",
        # annual_revenue_inr, target_revenue_inr,
        # monthly_payroll_cost_inr, monthly_operating_cash_flow_inr,
        # operating_margin_pct all default to 0.
        overall_business_score=68,
        band="Established",
        dna=AssistantContextDna(
            archetype_key="growth_seeker",
            archetype_title="Growth Seeker",
            match_score=82,
        ),
        twin_generated_at=_now_iso(days_ago=1),
    )


def _contradictory_profile() -> AssistantContext:
    """High score + low margin — the contradiction detector
    should fire on the gap between the two."""
    return AssistantContext(
        business_id=6,
        legal_name="Acme Textiles",
        industry="Textiles",
        location="Tirupur",
        business_type="Manufacturer",
        employee_count="42",
        annual_revenue_inr=18_000_000,
        target_revenue_inr=30_000_000,
        # High score (Leader) with low margin → contradiction.
        operating_margin_pct=5.0,
        overall_business_score=92,
        band="Leader",
        dna=AssistantContextDna(
            archetype_key="leader",
            archetype_title="Leader",
            match_score=92,
        ),
        twin_generated_at=_now_iso(days_ago=1),
    )


def _stale_external_profile() -> AssistantContext:
    """All context stamps are > 90 days old — equivalent to a
    stale external source for freshness testing."""
    return AssistantContext(
        business_id=7,
        legal_name="Acme Textiles",
        industry="Textiles",
        location="Tirupur",
        business_type="Manufacturer",
        employee_count="42",
        annual_revenue_inr=18_000_000,
        target_revenue_inr=30_000_000,
        operating_margin_pct=18.0,
        overall_business_score=68,
        band="Established",
        dna=AssistantContextDna(
            archetype_key="growth_seeker",
            archetype_title="Growth Seeker",
            match_score=82,
        ),
        twin_generated_at=_now_iso(days_ago=120),
        recommendations_generated_at=_now_iso(days_ago=120),
        insights_generated_at=_now_iso(days_ago=120),
        forecasts_generated_at=_now_iso(days_ago=120),
        schemes_generated_at=_now_iso(days_ago=400),
        action_items_generated_at=_now_iso(days_ago=120),
        rules_generated_at=_now_iso(days_ago=120),
        roadmap_generated_at=_now_iso(days_ago=400),
    )


def _unavailable_tool_profile() -> AssistantContext:
    """Profile with no analytics stamps — the dispatcher treats
    missing stamps as "tool unavailable"."""
    return AssistantContext(
        business_id=8,
        legal_name="Acme Textiles",
        industry="Textiles",
        location="Tirupur",
        business_type="Manufacturer",
        employee_count="42",
        annual_revenue_inr=18_000_000,
        target_revenue_inr=30_000_000,
        operating_margin_pct=18.0,
        overall_business_score=68,
        band="Established",
        dna=AssistantContextDna(
            archetype_key="growth_seeker",
            archetype_title="Growth Seeker",
            match_score=82,
        ),
        # Every analytics stamp None / None → dispatcher reads
        # them as "no tool result available".
    )


# --------------------------------------------------------------------------- #
# Profiles
# --------------------------------------------------------------------------- #


DATA_PROFILES: tuple[DataQualityProfile, ...] = (
    DataQualityProfile(
        profile_id="profile_complete_001",
        label="Complete profile (healthy Acme)",
        factory=_complete_profile,
        quality_notes="All financial inputs present; fresh stamps.",
        expected_warning=False,
        expected_confidence_max=100.0,
    ),
    DataQualityProfile(
        profile_id="profile_minimal_001",
        label="Minimal profile (Bare Necessities)",
        factory=_minimal_profile,
        quality_notes="Only legal_name + industry populated.",
        expected_warning=True,
        expected_disclosure=True,
        expected_confidence_max=50.0,
    ),
    DataQualityProfile(
        profile_id="profile_missing_revenue_001",
        label="Missing revenue + margin",
        factory=_missing_revenue_profile,
        quality_notes="Revenue / margin / target all zero.",
        expected_warning=True,
        expected_disclosure=True,
        expected_confidence_max=60.0,
    ),
    DataQualityProfile(
        profile_id="profile_missing_employees_001",
        label="Missing employee count",
        factory=_missing_employees_profile,
        quality_notes="Employee count missing.",
        expected_warning=False,
        expected_confidence_max=85.0,
    ),
    DataQualityProfile(
        profile_id="profile_missing_financial_001",
        label="Missing financial data",
        factory=_missing_financial_profile,
        quality_notes="Revenue, expenses, margin all zero.",
        expected_warning=True,
        expected_disclosure=True,
        expected_confidence_max=55.0,
    ),
    DataQualityProfile(
        profile_id="profile_contradictory_001",
        label="Contradictory profile / analytics",
        factory=_contradictory_profile,
        quality_notes="Score 92 (Leader) with 5% margin.",
        expected_warning=True,
        expected_confidence_max=70.0,
    ),
    DataQualityProfile(
        profile_id="profile_stale_external_001",
        label="Stale external source",
        factory=_stale_external_profile,
        quality_notes="All stamps >90 days old.",
        expected_warning=True,
        expected_confidence_max=75.0,
    ),
    DataQualityProfile(
        profile_id="profile_unavailable_tool_001",
        label="Unavailable tool result",
        factory=_unavailable_tool_profile,
        quality_notes="Every analytics stamp empty (tool unavailable).",
        expected_warning=True,
        expected_disclosure=True,
        expected_confidence_max=50.0,
    ),
)


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #


def all_profiles() -> tuple[DataQualityProfile, ...]:
    """Return every data-quality profile."""
    return DATA_PROFILES


def get_profile(profile_id: str) -> DataQualityProfile | None:
    """Return the profile with id ``profile_id`` (or ``None``)."""
    for p in DATA_PROFILES:
        if p.profile_id == profile_id:
            return p
    return None


__all__ = [
    "DataQualityProfile",
    "all_profiles",
    "get_profile",
]
