"""Test suite for SPRINT AI-1 — Stage 2: BusinessContextManifest upgrade."""

import pytest

from app.services.ai.providers.base import (
    AssistantContext,
    AssistantContextDna,
    BusinessContextManifest,
)
from app.services.ai.providers.context_builder import select_relevant_context


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture
def acme_context():
    """A realistic Acme Textiles context with every category populated."""
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
        recommendations=(),
        rules=(),
        insights=(),
        schemes=(),
        forecasts=(),
        action_items=(),
        analytics_metrics=(),
        report_summaries=(),
        certifications=("ISO 9001",),
        export_history=("EU 2022",),
        products=("Cotton yarn",),
        services=(),
        goals=("Reach ₹3 Cr turnover",),
        challenges=(),
        supplier_dependencies=(),
        customer_dependencies=(),
    )


# --------------------------------------------------------------------------- #
# 1. New fields have defaults — backward compat preserved
# --------------------------------------------------------------------------- #


def test_1_business_context_manifest_default_construction_preserves_compat():
    """An empty BusinessContextManifest still constructs with all-new-fields defaults."""
    m = BusinessContextManifest()
    # Original H7.8C fields
    assert m.business_context_used == ()
    assert m.records_used == 0
    assert m.prompt_truncated is False
    # New AI-1 fields
    assert m.categories_available == ()
    assert m.categories_used == ()
    assert m.records_available == 0
    assert m.evidence_ids_used == ()
    assert m.context_priority == ()
    assert m.context_selection_reason == ""


# --------------------------------------------------------------------------- #
# 2. to_dict round-trips the new fields
# --------------------------------------------------------------------------- #


def test_2_business_context_manifest_to_dict_includes_new_fields():
    """to_dict() round-trips every new field for the JSON audit trail."""
    m = BusinessContextManifest(
        business_context_used=("business_profile", "recommendations"),
        records_used=5,
        categories_available=("business_profile", "recommendations"),
        categories_used=("business_profile", "recommendations"),
        records_available=5,
        evidence_ids_used=("rec_001", "rule_002"),
        context_priority=("business_profile", "recommendations"),
        context_selection_reason="intent=general; categories=2",
    )
    d = m.to_dict()
    assert d["business_context_used"] == ["business_profile", "recommendations"]
    assert d["records_used"] == 5
    assert d["categories_available"] == ["business_profile", "recommendations"]
    assert d["records_used"] == 5
    assert d["categories_available"] == ["business_profile", "recommendations"]
    assert d["categories_used"] == ["business_profile", "recommendations"]
    assert d["records_available"] == 5
    assert d["evidence_ids_used"] == ["rec_001", "rule_002"]
    assert d["context_priority"] == ["business_profile", "recommendations"]
    assert d["context_selection_reason"] == "intent=general; categories=2"


# --------------------------------------------------------------------------- #
# 3. select_relevant_context populates categories_available
# --------------------------------------------------------------------------- #


def test_3_select_relevant_context_categories_available(acme_context):
    """The manifest's categories_available field mirrors the full category list."""
    out = select_relevant_context(acme_context, "How can I grow my business?")
    m = out.context_manifest
    assert m is not None
    # categories_available should be at least as long as business_context_used
    assert len(m.categories_available) >= len(m.business_context_used)
    assert "business_profile" in m.categories_available
    assert "products" in m.categories_available


# --------------------------------------------------------------------------- #
# 4. context_priority is reordered by intent — flagship revenue target
# --------------------------------------------------------------------------- #


def test_4_select_relevant_context_priority_ordered_by_intent(acme_context):
    """The context_priority field reorders categories for the detected intent."""
    out = select_relevant_context(
        acme_context, "How can I grow from ₹1.8 Cr to ₹3 Cr?"
    )
    m = out.context_manifest
    assert m is not None
    # Revenue-target intent puts business_profile first
    assert m.context_priority[0] == "business_profile"
    # The priority ordering must contain every available category
    assert set(m.context_priority) == set(m.categories_available)


# --------------------------------------------------------------------------- #
# 5. context_selection_reason includes intent + count
# --------------------------------------------------------------------------- #


def test_5_select_relevant_context_selection_reason_format(acme_context):
    """context_selection_reason follows the stable 'intent=<x>; categories=<n>' format."""
    out = select_relevant_context(
        acme_context, "What is my biggest weakness?"
    )
    m = out.context_manifest
    assert m is not None
    assert m.context_selection_reason.startswith("intent=")
    assert "categories=" in m.context_selection_reason


# --------------------------------------------------------------------------- #
# 6. evidence_ids_used tolerates empty / missing KG
# --------------------------------------------------------------------------- #


def test_6_select_relevant_context_evidence_ids_safe_with_no_kg():
    """The KG is always built from the context, but the field is always a tuple.

    The context builder always constructs a KG via
    ``BusinessKnowledgeGraph.from_context``. Even a minimal
    Acme profile has at least ``biz_profile_revenue`` and
    ``biz_dna`` evidence IDs. The invariant we test is that
    the field is a tuple — never raises, never returns
    None or a list.
    """
    ctx = AssistantContext(
        business_id=1,
        overall_business_score=68,
        band="Established",
        dna=AssistantContextDna("growth_operator", "Growth Operator", 85),
        legal_name="Acme Textiles",
        industry="Textiles",
        annual_revenue_inr=18000000,
    )
    out = select_relevant_context(ctx, "")
    assert out.context_manifest is not None
    # Always a tuple — never None, never a list.
    assert isinstance(out.context_manifest.evidence_ids_used, tuple)
    # The minimal Acme profile generates at least one
    # profile-level evidence ID.
    assert len(out.context_manifest.evidence_ids_used) >= 1
