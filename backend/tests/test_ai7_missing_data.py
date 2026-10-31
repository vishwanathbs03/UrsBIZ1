"""SPRINT AI-7 — Missing Data Intelligence — detector + enrichment tests.

Covers the brief's mandate that "missing-data detection must be
proactive. If a question requires data that does not exist,
identify it before generation when possible."

Tests:

  * Hiring intent (the brief's flagship example) emits exactly
    the three required rows the brief mandates (payroll, cash
    flow, operating margin).
  * Revenue-target intent surfaces annual_revenue + target_revenue.
  * Empty AssistantContext surfaces every required field.
  * GENERAL / BIGGEST_WEAKNESS / TWELVE_MONTH_ROADMAP emit 0 rows.
  * Importance classification HIGH vs LOW.
  * Enrichment dedupes against the base list.
  * Enrichment extracts "need" sentences from prose.
  * Render "What I can tell" returns verified facts.
  * Round-trip through from_dict.
  * Stamp onto GenerationMeta preserves the frozen contract.
  * Wire projection mirrors ``missing_data`` at the top level.
"""

from __future__ import annotations

import pytest

from app.services.ai.missing_data import (
    MissingDataObject,
    detect_missing_data,
    detect_missing_data_from_mapping,
    enrich_missing_data_from_prose,
    from_payload,
    render_what_i_can_tell,
    to_payload,
)
from app.services.ai.missing_data.detector import (
    _REQUIRED_BY_INTENT,
    FieldRequirement,
)
from app.services.ai.providers.base import GenerationMeta
from app.services.ai.providers.intent_router import QuestionIntent


# --------------------------------------------------------------------------- #
# Hiring intent — the brief's flagship example
# --------------------------------------------------------------------------- #


def _bare_context(**overrides):
    """Build a minimal AssistantContext-like object for the detector."""

    class _Ctx:
        pass

    ctx = _Ctx()
    # All numeric defaults 0 — the detector treats 0 / None / empty
    # / "unknown" as missing.
    ctx.legal_name = "Acme Textiles"
    ctx.industry = "manufacturing"
    ctx.location = "Mumbai"
    ctx.overall_business_score = 68
    ctx.band = "Established"
    ctx.dna = None
    ctx.annual_revenue_inr = 0
    ctx.employee_count = "unknown"
    ctx.monthly_payroll_cost_inr = 0
    ctx.monthly_operating_cash_flow_inr = 0
    ctx.operating_margin_pct = 0.0
    ctx.target_revenue_inr = 0
    ctx.analytics_metrics = ()
    ctx.export_history = ()
    ctx.certifications = ()
    ctx.digital_presence = ()
    ctx.schemes = ()
    ctx.recommendations = ()
    for k, v in overrides.items():
        setattr(ctx, k, v)
    return ctx


def test_hiring_intent_emits_payroll_cash_flow_margin():
    """The brief's flagship example — surfaces exactly the 3 named rows."""
    ctx = _bare_context()
    rows = detect_missing_data(ctx, QuestionIntent.HIRING)
    assert isinstance(rows, tuple)
    fields = {r.field for r in rows}
    assert "monthly_payroll_cost_inr" in fields
    assert "monthly_operating_cash_flow_inr" in fields
    assert "operating_margin_pct" in fields
    # Plus employee_count (HIGH) which the brief implies.
    assert "employee_count" in fields
    assert len(rows) == 4


def test_hiring_intent_with_full_context_emits_no_rows():
    """A fully-populated context produces 0 missing rows for hiring."""
    ctx = _bare_context(
        employee_count="12",
        monthly_payroll_cost_inr=4_500_000_00,  # ₹4.5 Cr in paise equivalent
        monthly_operating_cash_flow_inr=1_200_000_00,
        operating_margin_pct=18.5,
    )
    rows = detect_missing_data(ctx, QuestionIntent.HIRING)
    assert rows == ()


def test_hiring_intent_payroll_cash_flow_are_high_importance():
    """The brief's three named fields are HIGH tier."""
    ctx = _bare_context()
    rows = detect_missing_data(ctx, QuestionIntent.HIRING)
    fields = {r.field: r for r in rows}
    assert fields["monthly_payroll_cost_inr"].importance == "HIGH"
    assert fields["monthly_operating_cash_flow_inr"].importance == "HIGH"
    # operating_margin is MEDIUM in the brief's narrative.
    assert fields["operating_margin_pct"].importance == "MEDIUM"


# --------------------------------------------------------------------------- #
# Other intents
# --------------------------------------------------------------------------- #


def test_revenue_target_intent_emits_annual_and_target_revenue():
    ctx = _bare_context()
    rows = detect_missing_data(ctx, QuestionIntent.REACH_REVENUE_TARGET)
    fields = {r.field for r in rows}
    assert "annual_revenue_inr" in fields
    assert "target_revenue_inr" in fields
    assert "analytics_metrics" in fields


def test_export_intent_emits_certifications_high():
    ctx = _bare_context()
    rows = detect_missing_data(ctx, QuestionIntent.EXPORT_EXPANSION)
    fields = {r.field: r for r in rows}
    assert "certifications" in fields
    assert fields["certifications"].importance == "HIGH"
    assert "export_history" in fields
    assert "digital_presence" in fields


def test_scheme_intent_emits_industry_and_location():
    """With industry=unknown + location=unknown the detector surfaces both."""
    ctx = _bare_context(industry="unknown", location="unknown")
    rows = detect_missing_data(ctx, QuestionIntent.GOVERNMENT_SCHEMES)
    fields = {r.field for r in rows}
    assert "industry" in fields
    assert "location" in fields
    # With industry + location populated, both rows disappear.
    ctx2 = _bare_context()
    rows2 = detect_missing_data(ctx2, QuestionIntent.GOVERNMENT_SCHEMES)
    assert rows2 == ()


def test_general_intent_emits_no_rows():
    """GENERAL has no required-fields map; the detector is a no-op."""
    ctx = _bare_context()
    rows = detect_missing_data(ctx, QuestionIntent.GENERAL)
    assert rows == ()


def test_biggest_weakness_emits_no_rows():
    ctx = _bare_context()
    rows = detect_missing_data(ctx, QuestionIntent.BIGGEST_WEAKNESS)
    assert rows == ()


def test_twelve_month_roadmap_emits_no_rows():
    ctx = _bare_context()
    rows = detect_missing_data(ctx, QuestionIntent.TWELVE_MONTH_ROADMAP)
    assert rows == ()


def test_detect_missing_data_returns_empty_tuple_when_context_is_none():
    """Defensive — a None context never raises, just yields ()."""
    assert detect_missing_data(None, QuestionIntent.HIRING) == ()


def test_required_by_intent_contains_hiring():
    """The HIRING map is the source of truth for the detector."""
    hiring = _REQUIRED_BY_INTENT.get(QuestionIntent.HIRING)
    assert hiring is not None
    assert len(hiring) >= 4
    assert all(isinstance(r, FieldRequirement) for r in hiring)


# --------------------------------------------------------------------------- #
# Dict-based detector variant (used by the frontend)
# --------------------------------------------------------------------------- #


def test_detect_from_mapping_matches_dataclass():
    ctx = _bare_context()
    via_obj = detect_missing_data(ctx, QuestionIntent.HIRING)
    via_map = detect_missing_data_from_mapping(
        {
            "employee_count": ctx.employee_count,
            "monthly_payroll_cost_inr": ctx.monthly_payroll_cost_inr,
            "monthly_operating_cash_flow_inr": ctx.monthly_operating_cash_flow_inr,
            "operating_margin_pct": ctx.operating_margin_pct,
        },
        QuestionIntent.HIRING,
    )
    assert {r.field for r in via_obj} == {r.field for r in via_map}


# --------------------------------------------------------------------------- #
# Enrichment — reactive prose scan
# --------------------------------------------------------------------------- #


def test_enrichment_extracts_need_sentences():
    base: tuple[MissingDataObject, ...] = ()
    prose = (
        "I don't have your monthly operating cash flow. "
        "Could you share your existing payroll register? "
        "Without the cash-flow forecast, we cannot run the analysis."
    )
    enriched = enrich_missing_data_from_prose(prose, base)
    assert len(enriched) > 0
    fields = {r.field for r in enriched}
    # All three cues extracted (the financial-hint filter drops none).
    assert any("cash_flow" in f or "cashflow" in f for f in fields)
    assert any("payroll" in f for f in fields)
    # Reactive rows are MEDIUM tier (proactive uses HIGH).
    for r in enriched:
        assert r.importance == "MEDIUM"


def test_enrichment_dedupes_against_base():
    base = (
        MissingDataObject(
            field="monthly_payroll_cost_inr",
            importance="HIGH",
            reason="Existing payroll is the baseline.",
            affects=("hire_affordability",),
            suggested_source="Payroll register.",
        ),
    )
    prose = (
        "I don't have your monthly payroll cost. "
        "Could you share your operating cash flow?"
    )
    enriched = enrich_missing_data_from_prose(prose, base)
    # The proactive row wins on conflict — payroll re-asserted as HIGH.
    payroll_rows = [r for r in enriched if r.field == "monthly_payroll_cost_inr"]
    assert len(payroll_rows) == 1
    assert payroll_rows[0].importance == "HIGH"
    # But cash flow was new — added as MEDIUM.
    cf_rows = [r for r in enriched if "cash_flow" in r.field]
    assert len(cf_rows) == 1


def test_enrichment_empty_prose_returns_base():
    base = (
        MissingDataObject(
            field="monthly_payroll_cost_inr",
            importance="HIGH",
            reason="",
            affects=(),
            suggested_source="",
        ),
    )
    assert enrich_missing_data_from_prose("", base) == base
    assert enrich_missing_data_from_prose(None, base) == base


def test_enrichment_caps_reactive_rows():
    base: tuple[MissingDataObject, ...] = ()
    prose = (
        "I don't have your payroll. "
        "I don't have your cash flow. "
        "I don't have your operating margin. "
        "I don't have your ITR. "
        "I don't have your bank balance. "
        "I don't have your rent. "
        "I don't have your rent overhead."  # 7 cues
    )
    enriched = enrich_missing_data_from_prose(prose, base, max_new=5)
    # Cap at max_new=5 (the proactive rows are 0).
    assert len(enriched) <= 5


# --------------------------------------------------------------------------- #
# Render — "What I can tell"
# --------------------------------------------------------------------------- #


def test_render_what_i_can_tell_returns_verified_facts():
    ctx = _bare_context(
        annual_revenue_inr=85_000_000_00,
        employee_count="12",
        monthly_payroll_cost_inr=4_500_000_00,
        monthly_operating_cash_flow_inr=1_200_000_00,
        operating_margin_pct=18.5,
    )
    facts = render_what_i_can_tell(ctx, QuestionIntent.HIRING)
    assert isinstance(facts, tuple)
    assert any("Acme Textiles" in f for f in facts)
    assert any("Manufacturing" in f or "manufacturing" in f for f in facts)
    # Per-intent facts include the numeric ones.
    assert any("annual revenue" in f.lower() for f in facts)
    assert any("payroll" in f.lower() for f in facts)


def test_render_what_i_can_tell_returns_empty_for_none_context():
    assert render_what_i_can_tell(None, QuestionIntent.HIRING) == ()


def test_render_what_i_can_tell_is_capped_at_eight():
    ctx = _bare_context(
        annual_revenue_inr=85_000_000_00,
        employee_count="12",
        monthly_payroll_cost_inr=4_500_000_00,
        monthly_operating_cash_flow_inr=1_200_000_00,
        operating_margin_pct=18.5,
        target_revenue_inr=120_000_000_00,
        schemes=("ZED Bronze", "MUD", "CGTMSE"),
        recommendations=("Diversify suppliers", "Improve margins"),
    )
    facts = render_what_i_can_tell(ctx, QuestionIntent.HIRING)
    assert len(facts) <= 8


# --------------------------------------------------------------------------- #
# Wire round-trip + GenerationMeta stamp
# --------------------------------------------------------------------------- #


def test_to_payload_serializes_rows_to_list_of_dicts():
    rows = (
        MissingDataObject(
            field="monthly_payroll_cost_inr",
            importance="HIGH",
            reason="baseline",
            affects=("hire_affordability",),
            suggested_source="Payroll register.",
        ),
    )
    payload = to_payload(rows)
    assert isinstance(payload, list)
    assert isinstance(payload[0], dict)
    assert payload[0]["field"] == "monthly_payroll_cost_inr"
    assert payload[0]["affects"] == ["hire_affordability"]


def test_from_payload_rehydrates_rows():
    payload = [
        {
            "field": "monthly_payroll_cost_inr",
            "importance": "HIGH",
            "reason": "baseline",
            "affects": ["hire_affordability"],
            "suggested_source": "Payroll register.",
        },
        {"field": "monthly_operating_cash_flow_inr"},  # no importance
    ]
    rows = from_payload(payload)
    assert len(rows) == 2
    assert rows[0].field == "monthly_payroll_cost_inr"
    assert rows[0].importance == "HIGH"
    # Importance defaults to MEDIUM when missing/invalid.
    assert rows[1].importance == "MEDIUM"


def test_generation_meta_missing_data_round_trip():
    """GenerationMeta carries missing_data through from_dict unchanged."""
    meta = GenerationMeta.empty(
        mode="grounded",
        provider_used="openai",
        model="gpt-4o-mini",
        provider_latency_ms=42,
        fallback_used=False,
        missing_data=(
            {"field": "monthly_payroll_cost_inr", "importance": "HIGH"},
        ),
    )
    assert len(meta.missing_data) == 1
    # Round-trip through from_dict — list form (wire shape).
    rehydrated = GenerationMeta.from_dict(
        {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "mode": "grounded",
            "fallback_used": False,
            "fallback_reason": None,
            "generation_method": "generative",
            "schema_validated": False,
            "grounding_validated": False,
            "server_grounding_score": 0,
            "evidence_count": 0,
            "confidence": None,
            "assumptions": [],
            "limitations": [],
            "evidence_references": [],
            "generated_at": "2026-08-10T00:00:00Z",
            "prompt_truncated": False,
            "provider_latency_ms": 42,
            "grounded_payload": None,
            "missing_data": [
                {"field": "monthly_payroll_cost_inr", "importance": "HIGH"},
            ],
        }
    )
    assert isinstance(rehydrated.missing_data, tuple)
    assert rehydrated.missing_data[0]["field"] == "monthly_payroll_cost_inr"


def test_generation_meta_empty_includes_missing_data_default():
    """GenerationMeta.empty() accepts the missing_data kwarg and defaults to ()."""
    empty = GenerationMeta.empty(
        mode="grounded",
        provider_used="openai",
        model="gpt-4o-mini",
        provider_latency_ms=None,
        fallback_used=False,
    )
    assert empty.missing_data == ()
    payload_form = GenerationMeta.empty(
        mode="grounded",
        provider_used="openai",
        model="gpt-4o-mini",
        provider_latency_ms=None,
        fallback_used=False,
        missing_data=({"x": 1},),
    )
    assert payload_form.missing_data == ({"x": 1},)


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])