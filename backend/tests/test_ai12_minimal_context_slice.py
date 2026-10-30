"""Tests for SPRINT AI-12 — select_minimal_slice.

Two tests:

  * the slice contains only the attributes the question
    demanded (via ``required_evidence_types``),
  * the full ``AssistantContext`` is preserved untouched (the
    slice builds a new context, never mutating the input).
"""
from __future__ import annotations

from app.services.ai.providers.context_builder import (
    AssistantContext,
    AssistantContextDna,
)
from app.services.ai.reasoning.minimal_slice import (
    MinimalSlice,
    select_minimal_slice,
)


def _ctx():
    dna = AssistantContextDna(
        archetype_key="general", archetype_title="General", match_score=0.5,
    )
    return AssistantContext(
        dna=dna, business_id=1,
        legal_name="A", trade_name="A",
        industry="i", sub_industry="si", business_type="pvt",
        location="L", employee_count="5",
        annual_revenue_inr=1000, target_revenue_inr=2000,
        products=("a",), services=("b",),
        overall_business_score=72, band="B",
        schemes=("s1",), forecasts=("f1",),
        recommendations=("r1",), action_items=("act",),
    )


class TestSelectMinimalSlice:

    def test_government_scheme_slice_drops_unused_attrs(self) -> None:
        ctx = _ctx()
        class _Q:
            required_evidence_types = ("scheme", "profile", "funding")
        slice_obj = select_minimal_slice(ctx, _Q())
        # schemes are kept (evidence=scheme)
        assert slice_obj.context.schemes == ("s1",)
        # revenue kept (evidence=funding)
        assert slice_obj.context.annual_revenue_inr == 1000
        # forecasts dropped (no forecast evidence)
        assert slice_obj.context.forecasts == ()
        # recommendations dropped
        assert slice_obj.context.recommendations == ()
        # Original context untouched
        assert ctx.schemes == ("s1",)
        assert ctx.forecasts == ("f1",)

    def test_business_analysis_slice_keeps_scoring(self) -> None:
        ctx = _ctx()
        class _Q:
            required_evidence_types = ("analytics", "kpi_history")
        slice_obj = select_minimal_slice(ctx, _Q())
        # scores kept
        assert slice_obj.context.overall_business_score == 72
        # schemes dropped (no scheme evidence)
        assert slice_obj.context.schemes == ()

    def test_empty_evidence_types_minimal_slice(self) -> None:
        """When the QU carries no required types, the slice is
        driven by the baseline only (kept attrs are the small
        baseline set + nothing extra)."""
        ctx = _ctx()
        class _Q:
            required_evidence_types = ()
        slice_obj = select_minimal_slice(ctx, _Q())
        assert slice_obj.kept_attributes  # non-empty (baseline)
        # Original context is preserved (every field still there)
        assert ctx.schemes == ("s1",)

    def test_slice_rationale_is_string(self) -> None:
        ctx = _ctx()
        class _Q:
            required_evidence_types = ("scheme",)
        slice_obj = select_minimal_slice(ctx, _Q())
        assert isinstance(slice_obj.rationale, str)
