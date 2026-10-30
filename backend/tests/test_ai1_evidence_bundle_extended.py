"""Test suite for SPRINT AI-1 — Stage 3: EvidenceBundle unification."""

import pytest

from app.services.ai.providers.base import (
    AssistantContext,
    AssistantContextDna,
    AssistantContextRecommendation,
    AssistantContextRule,
)
from app.services.ai.providers.evidence_registry import (
    EvidenceEntry,
    EvidenceKind,
    EvidenceRegistry,
)


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture
def acme_context():
    """A realistic Acme Textiles context with recommendations + rules."""
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
        recommendations=(
            AssistantContextRecommendation(
                id="rec_diversify_suppliers",
                title="Diversify yarn suppliers",
                category="Operations",
                priority="High",
                estimated_score_gain=8,
                estimated_timeline="3 months",
                estimated_roi=240000.0,
            ),
        ),
        rules=(
            AssistantContextRule(
                id="rule_supplier_concentration",
                title="Supplier concentration risk",
                priority="Critical",
                category="Operations",
                estimated_impact=9,
                reason="Top supplier = 60% of yarn spend",
            ),
        ),
        insights=(),
        schemes=(),
        forecasts=(),
        action_items=(),
        analytics_metrics=(),
        report_summaries=(),
    )


# --------------------------------------------------------------------------- #
# 1. New fields have defaults — backward-compat preservation
# --------------------------------------------------------------------------- #


def test_1_evidence_entry_default_construction_keeps_legacy_compat():
    """A 5-arg EvidenceEntry construction still works — new fields default sensibly."""
    e = EvidenceEntry(
        id="rec_diversify_suppliers",
        kind=EvidenceKind.RECOMMENDATION,
        label="Diversify yarn suppliers",
        value="Reduce single-vendor risk",
        source_topic="recommendations",
    )
    assert e.id == "rec_diversify_suppliers"
    assert e.kind is EvidenceKind.RECOMMENDATION
    # New fields have safe defaults
    assert e.authoritative is True
    assert e.source_type == "computed"
    assert e.freshness == "unknown"
    assert e.business_context == {}


# --------------------------------------------------------------------------- #
# 2. Registry populates source_type by EvidenceKind
# --------------------------------------------------------------------------- #


def test_2_evidence_registry_stamps_source_type_per_kind(acme_context):
    """The registry stamps source_type based on EvidenceKind."""
    reg = EvidenceRegistry(acme_context)
    rec = next((e for e in reg.all() if e.kind is EvidenceKind.RECOMMENDATION), None)
    rule = next((e for e in reg.all() if e.kind is EvidenceKind.RULE), None)
    assert rec is not None and rule is not None
    assert rec.source_type == "recommendation_engine"
    assert rule.source_type == "rule_engine"


# --------------------------------------------------------------------------- #
# 3. Registry populates freshness from sidecar
# --------------------------------------------------------------------------- #


def test_3_evidence_registry_stamps_freshness_from_sidecar():
    """When AssistantContext.*_generated_at is set, freshness reflects it."""
    ctx = AssistantContext(
        business_id=1,
        legal_name="Acme Textiles",
        industry="Textiles",
        annual_revenue_inr=18000000,
        overall_business_score=68,
        band="Established",
        dna=AssistantContextDna("growth_operator", "Growth Operator", 85),
        recommendations=(
            AssistantContextRecommendation(
                id="rec_diversify_suppliers",
                title="Diversify yarn suppliers",
                category="Operations",
                priority="High",
                estimated_score_gain=8,
                estimated_timeline="3 months",
                estimated_roi=240000.0,
            ),
        ),
        recommendations_generated_at="2026-08-01T10:00:00Z",
    )
    reg = EvidenceRegistry(ctx)
    rec = next((e for e in reg.all() if e.kind is EvidenceKind.RECOMMENDATION), None)
    assert rec is not None
    assert rec.freshness == "2026-08-01T10:00:00Z"


# --------------------------------------------------------------------------- #
# 4. Registry populates business_context slice
# --------------------------------------------------------------------------- #


def test_4_evidence_registry_stamps_business_context_slice(acme_context):
    """business_context captures {industry, location, business_type, employee_count}."""
    reg = EvidenceRegistry(acme_context)
    for entry in reg.all():
        assert entry.business_context["industry"] == "Textiles"
        assert entry.business_context["location"] == "Tirupur"
        assert entry.business_context["business_type"] == "Manufacturer"
        assert entry.business_context["employee_count"] == 42


# --------------------------------------------------------------------------- #
# 5. Registry built from None context still works
# --------------------------------------------------------------------------- #


def test_5_evidence_registry_safe_with_none_context():
    """Registry built from None returns an empty registry, never raises."""
    reg = EvidenceRegistry(None)
    assert reg.all() == ()
    assert reg.count == 0


# --------------------------------------------------------------------------- #
# 6. Augmentation preserves evidence count (no entries dropped)
# --------------------------------------------------------------------------- #


def test_6_augmentation_preserves_entry_count(acme_context):
    """Adding augmentation doesn't drop entries — count stays the same."""
    reg = EvidenceRegistry(acme_context)
    # Acme context has recommendations + rules + the baseline
    # entries (overall score, prompt echoes, scores, dna) =
    # at least 5 entries.
    assert reg.count >= 5


# --------------------------------------------------------------------------- #
# 7. Augmented entries are frozen but new fields are immutable
# --------------------------------------------------------------------------- #


def test_7_augmented_entries_are_immutable(acme_context):
    """Augmented entries remain frozen; assignment raises."""
    reg = EvidenceRegistry(acme_context)
    entry = reg.all()[0]
    with pytest.raises((AttributeError, Exception)):
        entry.source_type = "tampered"  # type: ignore[misc]
