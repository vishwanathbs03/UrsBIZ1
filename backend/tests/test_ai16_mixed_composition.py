"""SPRINT AI-16 — Mixed Question Answer Composition + Scheme Card.

End-to-end tests for the orchestrator pair
(:mod:`app.services.ai.knowledge.ai16_mixed_composer` and
:mod:`app.services.ai.knowledge.ai16_scheme_composer`) plus the
wire envelope they stamp onto (``GenerationMeta`` /
``ChatMessageOut``).

The brief mandates six canonical scenarios — every one of them
is asserted below:

  1. ``Explain EBITDA and tell me whether my business is healthy``
     → ``general_explanation`` + ``business_interpretation`` +
     ``next_action``.
  2. ``Calculate my working capital gap and recommend what to do``
     → ``calculation`` + ``recommendation`` + ``next_action``.
  3. ``Which government schemes fit my business and what should I
     apply for first`` → ``schemes`` + ``business_interpretation``
     + ``recommendation`` + ``next_action``.
  4. ``Forecast revenue and tell me which scheme could support the
     expansion`` → ``calculation`` (forecast) + ``schemes`` +
     ``next_action``.
  5. ``Compare supplier diversification with inventory buffering
     and tell me which is better for reaching ₹3 Cr`` →
     ``calculation`` + ``recommendation`` + ``business_interpretation``.
  6. ``My business needs a loan but my eligibility is unclear``
     → ``uncertainty`` populated when unknowns are present.

Plus the supporting invariants:

  * non-mixed prompt (``What is EBITDA?``) → ``is_mixed=False``.
  * no duplicate evidence IDs across sections.
  * scheme-card full-profile path → conservative disposition.
  * scheme-card sparse-profile path → ``GAP_UNKNOWN``.
  * scheme-card unknown-scheme path → ``None`` (no fabrication).
  * wire envelope carries ``scheme_card`` for scheme prompts.
  * wire envelope carries ``mixed_answer`` for mixed prompts.
  * disposition phrase always one of the brief's 4 canonical
    strings.
"""

from __future__ import annotations

import pytest

from app.services.ai.knowledge.ai16_mixed_composer import (
    SECTION_KEYS,
    MixedSection,
    MixedSectionsResult,
    compose_mixed_sections,
)
from app.services.ai.knowledge.ai16_scheme_composer import (
    DISPOSITION_PHRASE_APPEARS_ELIGIBLE,
    DISPOSITION_PHRASE_INSUFFICIENT_INFORMATION,
    DISPOSITION_PHRASE_LIKELY_MATCH,
    DISPOSITION_PHRASE_REQUIRES_VERIFICATION,
    compose_scheme_card,
    disposition_phrase,
    select_scheme_id,
)


# --------------------------------------------------------------------------- #
# Stubs — minimal objects the composers read via ``getattr``.
# --------------------------------------------------------------------------- #


class _StubQU:
    """Minimal QuestionUnderstanding stub."""

    def __init__(self, **kw):
        self.literal_question = kw.get("literal_question", "")
        self.capability = kw.get("capability", ())
        self.answer_mode = kw.get("answer_mode", "general_knowledge")
        self.business_dependency = kw.get(
            "business_dependency", "none"
        )
        self.requires_calculation = kw.get(
            "requires_calculation", False
        )
        self.requires_scenario_analysis = kw.get(
            "requires_scenario_analysis", False
        )
        self.requires_forecast = kw.get("requires_forecast", False)
        self.requires_external_information = kw.get(
            "requires_external_information", False
        )
        self.unknowns = kw.get("unknowns", ())


class _StubEnv:
    """Minimal envelope stub (one row of the AI-15 tool output)."""

    def __init__(self, **kw):
        self.tool_name = kw.get("tool_name", "finance")
        self.metric = kw.get("metric", "amount")
        self.value = kw.get("value", None)
        self.unit = kw.get("unit", "INR")
        self.formula = kw.get("formula", "")
        self.input_evidence_ids = kw.get("input_evidence_ids", ())
        self.calculation_id = kw.get("calculation_id", "")
        self.assumptions = kw.get("assumptions", ())
        self.limitations = kw.get("limitations", ())
        self.confidence = kw.get("confidence", 1.0)


class _FullContext:
    """Stub profile with every field the scheme builder checks."""

    def __init__(self):
        self.industry = "Food Processing"
        self.annual_revenue_inr = 12_000_000.0
        self.employee_count = 14
        self.udyam_number = "UDYAM-TN-12-0001234"
        self.is_registered_msme = True


class _SparseContext:
    """Stub profile with no useful data — most fields missing."""

    def __init__(self):
        self.industry = ""
        self.annual_revenue_inr = None
        self.employee_count = None


# --------------------------------------------------------------------------- #
# 1 — general+business mixed ("Explain EBITDA …")
# --------------------------------------------------------------------------- #


def test_compose_mixed_general_and_business():
    """``Explain EBITDA and tell me whether my business is healthy``
    must emit ``general_explanation`` + ``business_interpretation``
    + ``next_action``. ``schemes`` is absent (no scheme cue)."""
    qu = _StubQU(
        literal_question="Explain EBITDA and tell me whether my business is healthy",
        capability=("EXTERNAL_INFORMATION", "BUSINESS_FACT"),
        answer_mode="mixed",
        business_dependency="required",
        requires_external_information=True,
    )
    kr_env = _StubEnv(
        tool_name="knowledge_retrieval",
        value=(
            "EBITDA (Earnings Before Interest, Taxes, Depreciation, "
            "and Amortization) measures operating profitability."
        ),
        input_evidence_ids=("e_kr",),
    )
    env = _StubEnv(
        metric="kpi",
        value=2_400_000.0,
        input_evidence_ids=("e1",),
        calculation_id="c1",
    )
    result = compose_mixed_sections(
        question_understanding=qu,
        envelopes=(kr_env, env),
        context=_FullContext(),
    )
    assert isinstance(result, MixedSectionsResult)
    assert result.is_mixed is True
    keys = {s.key for s in result.sections}
    assert "general_explanation" in keys
    assert "business_interpretation" in keys
    assert "next_action" in keys
    assert "schemes" not in keys


# --------------------------------------------------------------------------- #
# 2 — calculation + recommendation mixed
# --------------------------------------------------------------------------- #


def test_compose_mixed_calculation_and_recommendation():
    """``Calculate my working capital gap and recommend what to do``
    must emit ``calculation`` + ``recommendation`` +
    ``next_action``."""
    qu = _StubQU(
        literal_question=(
            "Calculate my working capital gap and recommend what to do"
        ),
        capability=("CALCULATION", "RECOMMENDATION"),
        answer_mode="mixed",
        business_dependency="required",
        requires_calculation=True,
    )
    env = _StubEnv(
        metric="working_capital_gap",
        value={"gap_inr": 1_500_000.0, "drivers": ["receivables"]},
        input_evidence_ids=("e1", "e2"),
        calculation_id="c1",
    )
    parsed = {
        "recommendations": [
            {"id": "r1", "title": "Tighten receivables"},
            {"id": "r2", "title": "Negotiate supplier credit"},
        ]
    }
    result = compose_mixed_sections(
        question_understanding=qu,
        envelopes=(env,),
        parsed=parsed,
        context=_FullContext(),
    )
    assert result.is_mixed is True
    keys = {s.key for s in result.sections}
    assert "calculation" in keys
    assert "recommendation" in keys
    assert "next_action" in keys


# --------------------------------------------------------------------------- #
# 3 — scheme + business + recommendation mixed
# --------------------------------------------------------------------------- #


def test_compose_mixed_scheme_and_business_analysis():
    """``Which government schemes fit my business and what should I
    apply for first`` must emit ``schemes`` +
    ``business_interpretation`` + ``recommendation`` +
    ``next_action``."""
    qu = _StubQU(
        literal_question=(
            "Which government schemes fit my business and what should "
            "I apply for first"
        ),
        capability=(
            "GOVERNMENT_SCHEME",
            "BUSINESS_FACT",
            "RECOMMENDATION",
        ),
        answer_mode="mixed",
        business_dependency="required",
    )
    scheme_card_payload = compose_scheme_card(
        question_understanding=qu,
        context=_FullContext(),
    )
    env = _StubEnv(metric="kpi", value=12_000_000.0)
    parsed = {
        "recommendations": [
            {"id": "r1", "title": "Apply for MUDRA loan"},
        ]
    }
    result = compose_mixed_sections(
        question_understanding=qu,
        envelopes=(env,),
        parsed=parsed,
        context=_FullContext(),
        scheme_card=(
            scheme_card_payload.card if scheme_card_payload else None
        ),
    )
    assert result.is_mixed is True
    keys = {s.key for s in result.sections}
    assert "schemes" in keys
    assert "business_interpretation" in keys
    assert "recommendation" in keys
    assert "next_action" in keys


# --------------------------------------------------------------------------- #
# 4 — forecast + scheme mixed
# --------------------------------------------------------------------------- #


def test_compose_mixed_forecast_and_scheme():
    """``Forecast revenue and tell me which scheme could support the
    expansion`` must emit ``calculation`` (forecast) + ``schemes``
    + ``next_action``."""
    qu = _StubQU(
        literal_question=(
            "Forecast revenue and tell me which scheme could support "
            "the expansion"
        ),
        capability=("FORECAST", "GOVERNMENT_SCHEME"),
        answer_mode="mixed",
        business_dependency="required",
        requires_forecast=True,
        requires_calculation=True,
    )
    scheme_card_payload = compose_scheme_card(
        question_understanding=qu,
        context=_FullContext(),
    )
    env = _StubEnv(
        metric="forecast",
        value={
            "series": [
                {"x": "Q1", "y": 10_000_000.0},
                {"x": "Q2", "y": 12_000_000.0},
                {"x": "Q3", "y": 14_500_000.0},
            ]
        },
        input_evidence_ids=("e1",),
        calculation_id="c1",
    )
    result = compose_mixed_sections(
        question_understanding=qu,
        envelopes=(env,),
        context=_FullContext(),
        scheme_card=(
            scheme_card_payload.card if scheme_card_payload else None
        ),
    )
    assert result.is_mixed is True
    keys = {s.key for s in result.sections}
    assert "calculation" in keys
    assert "schemes" in keys
    assert "next_action" in keys


# --------------------------------------------------------------------------- #
# 5 — comparison + recommendation mixed
# --------------------------------------------------------------------------- #


def test_compose_mixed_comparison_and_recommendation():
    """``Compare supplier diversification with inventory buffering
    and tell me which is better for reaching ₹3 Cr`` must emit
    ``calculation`` + ``recommendation`` +
    ``business_interpretation``."""
    qu = _StubQU(
        literal_question=(
            "Compare supplier diversification with inventory "
            "buffering and tell me which is better for reaching ₹3 Cr"
        ),
        capability=("COMPARISON", "RECOMMENDATION"),
        answer_mode="mixed",
        business_dependency="required",
        requires_calculation=True,
        requires_scenario_analysis=True,
    )
    env = _StubEnv(
        metric="compare",
        value={
            "left": {"label": "Diversification", "score": 0.72},
            "right": {"label": "Inventory buffering", "score": 0.61},
        },
        input_evidence_ids=("e1", "e2"),
        calculation_id="c1",
    )
    parsed = {
        "recommendations": [
            {"id": "r1", "title": "Diversify suppliers"},
        ]
    }
    result = compose_mixed_sections(
        question_understanding=qu,
        envelopes=(env,),
        parsed=parsed,
        context=_FullContext(),
    )
    assert result.is_mixed is True
    keys = {s.key for s in result.sections}
    assert "calculation" in keys
    assert "recommendation" in keys
    assert "business_interpretation" in keys


# --------------------------------------------------------------------------- #
# 6 — missing-data section populated when unknowns are present
# --------------------------------------------------------------------------- #


def test_compose_mixed_with_missing_data_section():
    """A mixed prompt whose QU carries unknowns must emit the
    ``uncertainty`` section."""
    qu = _StubQU(
        literal_question=(
            "My business needs a loan but my eligibility is unclear"
        ),
        capability=("GOVERNMENT_SCHEME", "BUSINESS_FACT"),
        answer_mode="mixed",
        business_dependency="required",
        unknowns=("employee_count", "udyam_number"),
    )
    result = compose_mixed_sections(
        question_understanding=qu,
        envelopes=(),
        context=_SparseContext(),
    )
    assert result.is_mixed is True
    keys = {s.key for s in result.sections}
    assert "uncertainty" in keys
    unc = next(s for s in result.sections if s.key == "uncertainty")
    # Section body must surface the unknowns as prose — never as a
    # fabricated "you are eligible" claim.
    body = "\n".join(unc.body_lines).lower()
    assert "unknown" in body or "missing" in body or "require" in body


# --------------------------------------------------------------------------- #
# 7 — non-mixed prompt returns is_mixed=False
# --------------------------------------------------------------------------- #


def test_non_mixed_prompt_returns_no_sections():
    """``What is EBITDA?`` (pure-external, no business cue) must
    return ``is_mixed=False`` and emit zero sections — the
    existing 10-section composer handles it."""
    qu = _StubQU(
        literal_question="What is EBITDA?",
        capability=("EXTERNAL_INFORMATION",),
        answer_mode="general_knowledge",
    )
    result = compose_mixed_sections(question_understanding=qu)
    assert result.is_mixed is False
    assert result.sections == ()


# --------------------------------------------------------------------------- #
# 8 — no duplicate evidence IDs across sections
# --------------------------------------------------------------------------- #


def test_no_duplicate_evidence_ids_across_sections():
    """Every evidence ID in the result must appear in at most one
    section. The renderer relies on this to attribute each claim
    to a single section."""
    qu = _StubQU(
        literal_question=(
            "Forecast revenue and tell me which scheme could support "
            "the expansion"
        ),
        capability=("FORECAST", "GOVERNMENT_SCHEME"),
        answer_mode="mixed",
        business_dependency="required",
        requires_forecast=True,
    )
    scheme_card_payload = compose_scheme_card(
        question_understanding=qu,
        context=_FullContext(),
    )
    env = _StubEnv(
        metric="forecast",
        value={"series": [{"x": "Q1", "y": 1.0}, {"x": "Q2", "y": 1.2}]},
        input_evidence_ids=("e1", "e2", "e3"),
        calculation_id="c1",
    )
    result = compose_mixed_sections(
        question_understanding=qu,
        envelopes=(env,),
        context=_FullContext(),
        scheme_card=(
            scheme_card_payload.card if scheme_card_payload else None
        ),
    )
    seen: set[str] = set()
    for section in result.sections:
        for eid in section.evidence_ids:
            assert eid not in seen, (
                f"duplicate evidence_id {eid} in section {section.key}"
            )
            seen.add(eid)


# --------------------------------------------------------------------------- #
# 9 — to_dict() round-trip preserves section shape
# --------------------------------------------------------------------------- #


def test_mixed_sections_to_dict_round_trip():
    """``MixedSectionsResult.to_dict()`` must yield a JSON-safe
    payload the wire projector can serialise."""
    qu = _StubQU(
        literal_question="What is my business readiness and what schemes apply?",
        capability=("BUSINESS_FACT", "GOVERNMENT_SCHEME"),
        answer_mode="mixed",
        business_dependency="required",
    )
    scheme_card_payload = compose_scheme_card(
        question_understanding=qu,
        context=_FullContext(),
    )
    env = _StubEnv(metric="kpi", value=12_000_000.0)
    result = compose_mixed_sections(
        question_understanding=qu,
        envelopes=(env,),
        context=_FullContext(),
        scheme_card=(
            scheme_card_payload.card if scheme_card_payload else None
        ),
    )
    payload = result.to_dict()
    assert isinstance(payload, dict)
    assert payload["is_mixed"] is True
    assert isinstance(payload["sections"], list)
    assert all(isinstance(s, dict) for s in payload["sections"])
    for section in payload["sections"]:
        assert set(section.keys()) >= {
            "key",
            "title",
            "body_lines",
            "source_kind",
            "evidence_ids",
            "confidence",
        }
        assert isinstance(section["body_lines"], list)
        assert isinstance(section["evidence_ids"], list)
        assert section["key"] in SECTION_KEYS


# --------------------------------------------------------------------------- #
# 10 — SECTION_KEYS ordering matches the brief
# --------------------------------------------------------------------------- #


def test_section_keys_match_brief_order():
    """The brief lists 7 sections in a specific order; the
    composer's ``SECTION_KEYS`` tuple MUST mirror that order so
    the renderer iterates in brief-canonical sequence."""
    assert SECTION_KEYS == (
        "general_explanation",
        "business_interpretation",
        "calculation",
        "recommendation",
        "schemes",
        "uncertainty",
        "next_action",
    )


# --------------------------------------------------------------------------- #
# 11 — scheme_card full profile ⇒ conservative disposition
# --------------------------------------------------------------------------- #


def test_scheme_card_full_profile_potential_match():
    """Full-profile scheme prompt must produce a
    ``SchemeCardPayload`` whose disposition is one of the brief's
    conservative values — never ``DEFINITELY_ELIGIBLE``."""
    qu = _StubQU(
        literal_question="Tell me about MUDRA loan for my business",
        capability=("GOVERNMENT_SCHEME", "BUSINESS_FACT"),
        answer_mode="mixed",
    )
    payload = compose_scheme_card(
        question_understanding=qu,
        context=_FullContext(),
    )
    assert payload is not None
    card = payload.card
    # Disposition is one of the 3-value enum members — never a
    # fabricated "DEFINITELY_ELIGIBLE".
    assert card.match_disposition.value in {
        "potential_match",
        "gap_unknown",
        "conflict",
    }
    # The renderer phrase is one of the 4 brief-mandated phrases.
    assert payload.phrase in {
        DISPOSITION_PHRASE_LIKELY_MATCH,
        DISPOSITION_PHRASE_APPEARS_ELIGIBLE,
        DISPOSITION_PHRASE_REQUIRES_VERIFICATION,
        DISPOSITION_PHRASE_INSUFFICIENT_INFORMATION,
    }
    # The mandatory final-authority disclaimer is present.
    assert "Final eligibility" in card.final_authority_disclaimer


# --------------------------------------------------------------------------- #
# 12 — scheme_card sparse profile ⇒ GAP_UNKNOWN
# --------------------------------------------------------------------------- #


def test_scheme_card_sparse_profile_gap_unknown():
    """Sparse profile ⇒ disposition is ``gap_unknown`` and the
    renderer phrase says verification / insufficient info."""
    from app.services.ai.knowledge.scheme_answer_card import (
        MatchDisposition,
    )

    qu = _StubQU(
        literal_question="Tell me about MUDRA loan for my business",
        capability=("GOVERNMENT_SCHEME",),
        answer_mode="general_knowledge",
    )
    payload = compose_scheme_card(
        question_understanding=qu,
        context=_SparseContext(),
    )
    assert payload is not None
    card = payload.card
    assert card.match_disposition == MatchDisposition.GAP_UNKNOWN
    assert payload.phrase in {
        DISPOSITION_PHRASE_REQUIRES_VERIFICATION,
        DISPOSITION_PHRASE_INSUFFICIENT_INFORMATION,
    }


# --------------------------------------------------------------------------- #
# 13 — scheme_card unknown scheme ⇒ None (no fabrication)
# --------------------------------------------------------------------------- #


def test_scheme_card_unknown_scheme_returns_none():
    """Prompt with no scheme cue returns ``None`` — the
    orchestrator must NEVER fabricate a card."""
    qu = _StubQU(
        literal_question="What is EBITDA?",
        capability=("EXTERNAL_INFORMATION",),
        answer_mode="general_knowledge",
    )
    payload = compose_scheme_card(
        question_understanding=qu,
        context=_FullContext(),
    )
    assert payload is None


# --------------------------------------------------------------------------- #
# 14 — disposition phrase always one of the 4 canonical phrases
# --------------------------------------------------------------------------- #


def test_disposition_phrase_4_tier_mapping():
    """Every (disposition, score) combo must return one of the
    brief's 4 canonical phrases — never a custom string."""
    allowed = {
        DISPOSITION_PHRASE_LIKELY_MATCH,
        DISPOSITION_PHRASE_APPEARS_ELIGIBLE,
        DISPOSITION_PHRASE_REQUIRES_VERIFICATION,
        DISPOSITION_PHRASE_INSUFFICIENT_INFORMATION,
    }
    cases = [
        ("potential_match", 95),
        ("potential_match", 80),
        ("potential_match", 79),
        ("potential_match", 50),
        ("potential_match", 49),
        ("potential_match", None),
        ("gap_unknown", None),
        ("conflict", None),
    ]
    for disp, score in cases:
        phrase = disposition_phrase(disp, score)
        assert phrase in allowed, (
            f"disposition={disp!r} score={score!r} yielded {phrase!r}"
        )


# --------------------------------------------------------------------------- #
# 15 — select_scheme_id covers all 5 schemes + Udyam fallback
# --------------------------------------------------------------------------- #


def test_select_scheme_id_keyword_scan():
    """Each scheme keyword must resolve to its scheme ID; generic
    scheme prompts fall back to Udyam; non-scheme prompts return
    ``None``."""
    cases = [
        ("Apply for MUDRA loan for working capital", "mudra"),
        ("Tell me about PMEGP project cost", "pmegp"),
        ("CGTMSE credit guarantee for my business", "cgtmse"),
        ("TReDS invoice discounting", "treds"),
        ("Udyam registration process", "udyam"),
        ("Which government schemes fit my business", "udyam"),
        ("What is EBITDA", None),
    ]
    for text, expected in cases:
        assert select_scheme_id(text) == expected, (
            f"text={text!r} expected={expected!r}"
        )


# --------------------------------------------------------------------------- #
# 16 — wire envelope carries scheme_card for scheme prompts
# --------------------------------------------------------------------------- #


def test_wire_envelope_carries_scheme_card_for_scheme_prompts():
    """Driving the orchestrator path for a scheme prompt must
    surface a ``scheme_card`` dict on the GenerationMeta envelope
    AND on the ChatMessageOut mirror."""
    from app.services.ai.providers.base import GenerationMeta
    from app.schemas.chat import ChatMessageOut

    qu = _StubQU(
        literal_question="Tell me about MUDRA loan for my business",
        capability=("GOVERNMENT_SCHEME", "BUSINESS_FACT"),
        answer_mode="mixed",
    )
    # Drive the composer the same way the orchestrator does.
    scheme_card_payload = compose_scheme_card(
        question_understanding=qu,
        context=_FullContext(),
    )
    scheme_card_dict = (
        scheme_card_payload.card.to_dict()
        if scheme_card_payload is not None
        else None
    )
    # Stamp onto a fresh GenerationMeta and verify the field
    # round-trips through the ChatMessageOut wire mirror.
    meta = GenerationMeta.empty(
        mode="grounded",
        provider_used="deterministic",
        model="rule-engine",
        provider_latency_ms=10,
        fallback_used=True,
        scheme_card=scheme_card_dict,
    )
    assert meta.scheme_card is not None
    assert meta.scheme_card["scheme_id"] == "mudra"
    # ChatMessageOut mirrors the field. The projector copies
    # ``generation.scheme_card`` to the top level; we do the
    # same here so the wire model carries it both ways.
    gen_dict = meta.to_dict()
    out = ChatMessageOut.model_validate(
        {
            "id": 1,
            "role": "assistant",
            "content": "stub",
            "created_at": "2026-08-13T00:00:00Z",
            "generation": gen_dict,
            "scheme_card": gen_dict.get("scheme_card"),
        }
    )
    assert out.scheme_card is not None
    assert out.scheme_card["scheme_id"] == "mudra"
    assert "Final eligibility" in out.scheme_card["final_authority_disclaimer"]
    # The same value also lives on ``out.generation.scheme_card``.
    assert out.generation is not None
    assert out.generation.scheme_card is not None
    assert out.generation.scheme_card["scheme_id"] == "mudra"


# --------------------------------------------------------------------------- #
# 17 — wire envelope carries mixed_answer for mixed prompts
# --------------------------------------------------------------------------- #


def test_wire_envelope_carries_mixed_answer_for_mixed_prompts():
    """Driving the orchestrator path for a mixed prompt must
    surface a ``mixed_answer`` dict on the GenerationMeta
    envelope AND on the ChatMessageOut mirror."""
    from app.services.ai.providers.base import GenerationMeta
    from app.schemas.chat import ChatMessageOut

    qu = _StubQU(
        literal_question=(
            "Explain EBITDA and tell me whether my business is healthy"
        ),
        capability=("EXTERNAL_INFORMATION", "BUSINESS_FACT"),
        answer_mode="mixed",
        business_dependency="required",
        requires_external_information=True,
    )
    kr_env = _StubEnv(
        tool_name="knowledge_retrieval",
        value=(
            "EBITDA (Earnings Before Interest, Taxes, Depreciation, "
            "and Amortization) measures operating profitability."
        ),
        input_evidence_ids=("e_kr",),
    )
    env = _StubEnv(
        metric="kpi",
        value=2_400_000.0,
        input_evidence_ids=("e1",),
        calculation_id="c1",
    )
    result = compose_mixed_sections(
        question_understanding=qu,
        envelopes=(kr_env, env),
        context=_FullContext(),
    )
    mixed_dict = (
        result.to_dict() if result.is_mixed else None
    )
    meta = GenerationMeta.empty(
        mode="grounded",
        provider_used="deterministic",
        model="rule-engine",
        provider_latency_ms=10,
        fallback_used=True,
        mixed_answer=mixed_dict,
    )
    assert meta.mixed_answer is not None
    assert meta.mixed_answer["is_mixed"] is True
    assert isinstance(meta.mixed_answer["sections"], list)
    # ChatMessageOut mirrors the field. The projector copies
    # ``generation.mixed_answer`` to the top level; we do the
    # same here so the wire model carries it both ways.
    gen_dict = meta.to_dict()
    out = ChatMessageOut.model_validate(
        {
            "id": 2,
            "role": "assistant",
            "content": "stub",
            "created_at": "2026-08-13T00:00:00Z",
            "generation": gen_dict,
            "mixed_answer": gen_dict.get("mixed_answer"),
        }
    )
    assert out.mixed_answer is not None
    assert out.mixed_answer["is_mixed"] is True
    assert isinstance(out.mixed_answer["sections"], list)
    # The renderer-gating field: ``is_mixed`` propagates.
    assert len(out.mixed_answer["sections"]) >= 1
    # The same value also lives on ``out.generation.mixed_answer``.
    assert out.generation is not None
    assert out.generation.mixed_answer is not None
    assert out.generation.mixed_answer["is_mixed"] is True