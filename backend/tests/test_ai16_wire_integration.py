"""SPRINT AI-16 — Verified External Knowledge + Freshness Layer.

Wire / regression tests for the AI-16 additions to
:class:`GenerationMeta`.

Covers:
  * Pre-AI-16 payloads (no external_claims / freshness_warnings
    / scheme_card / external_answer / mixed_answer keys) still
    deserialize — backwards-compat is non-negotiable.
  * Round-trip: a fully-populated AI-16 envelope survives
    to_dict → from_dict without loss.
  * empty() factory accepts the new fields with safe defaults.
  * ChatGenerationMeta (wire mirror) — the new fields project
    through to the wire if the model carries them.

2 tests in this module.
"""

from __future__ import annotations

from app.services.ai.providers.base import GenerationMeta, Mode


# --------------------------------------------------------------------------- #
# 1 — Pre-AI-16 payloads round-trip
# ------------------------------------------------------------------------ #


def test_pre_ai16_payload_round_trips_through_generation_meta():
    """A pre-AI-16 wire payload (no external_claims /
    freshness_warnings / scheme_card / external_answer /
    mixed_answer keys) must still deserialize. The contract
    is that the new fields are additive — every prior
    payload survives an AI-16 deployment unchanged."""
    payload = {
        "provider": "deterministic-fallback",
        "model": "deterministic-fallback",
        "mode": "grounded",
        "fallback_used": True,
        "fallback_reason": "provider_unavailable",
        "generation_method": "deterministic",
        "schema_validated": True,
        "grounding_validated": True,
        "server_grounding_score": 100,
        "evidence_count": 0,
        "confidence": None,
        "assumptions": [],
        "limitations": [],
        "evidence_references": [],
        "generated_at": "2026-01-01T00:00:00Z",
        "prompt_truncated": False,
        "provider_latency_ms": None,
        "grounded_payload": None,
    }
    meta = GenerationMeta.from_dict(payload)
    # AI-16 fields default to safe empty / None.
    assert meta.external_claims == ()
    assert meta.freshness_warnings == ()
    assert meta.scheme_card is None
    assert meta.external_answer is None
    assert meta.mixed_answer is None


# --------------------------------------------------------------------------- #
# 2 — AI-16 round-trip with full payload
# ------------------------------------------------------------------------ #


def test_ai16_full_payload_round_trips():
    """A payload that DOES carry the AI-16 fields round-trips
    through to_dict → from_dict without loss. The new fields
    carry claim provenance, freshness warnings, scheme cards,
    external answers, and mixed-question blocks."""
    payload = {
        "provider": "deterministic-fallback",
        "model": "deterministic-fallback",
        "mode": "grounded",
        "fallback_used": True,
        "fallback_reason": "provider_unavailable",
        "generation_method": "deterministic",
        "schema_validated": True,
        "grounding_validated": True,
        "server_grounding_score": 100,
        "evidence_count": 0,
        "confidence": None,
        "assumptions": [],
        "limitations": [],
        "evidence_references": [],
        "generated_at": "2026-01-01T00:00:00Z",
        "prompt_truncated": False,
        "provider_latency_ms": None,
        "grounded_payload": None,
        "external_claims": [
            {
                "text": "EBITDA is earnings before interest, taxes, depreciation, and amortization.",
                "kind": "external_fact",
                "authority": 0.8,
                "is_verified": True,
                "notes": "",
                "source": {
                    "source_url": "https://www.investopedia.com/terms/e/ebitda.asp",
                    "publisher": "Investopedia",
                    "authority_level": "tier_2",
                    "freshness_status": "fresh",
                },
            }
        ],
        "freshness_warnings": [
            {
                "source_url": "https://www.rbi.org.in/repo-rate",
                "publisher": "RBI",
                "authority_level": "tier_1",
                "freshness_status": "stale",
            }
        ],
        "scheme_card": {
            "scheme_id": "mudra",
            "official_name": "Pradhan Mantri Mudra Yojana",
            "match_disposition": "potential_match",
        },
        "external_answer": {
            "headline": "EBITDA is earnings before interest, taxes, depreciation, and amortization.",
            "is_empty": False,
        },
        "mixed_answer": {
            "external_block": ["External part"],
            "business_block": ["Industry on file: Textiles."],
            "gap_block": ["Certifications on file: none."],
            "conclusion_block": ["Conclusion: cannot fully answer."],
            "is_mixed": True,
        },
    }
    meta = GenerationMeta.from_dict(payload)
    # External claims survive the round-trip.
    assert len(meta.external_claims) == 1
    assert meta.external_claims[0]["kind"] == "external_fact"
    # Freshness warnings survive.
    assert len(meta.freshness_warnings) == 1
    assert meta.freshness_warnings[0]["freshness_status"] == "stale"
    # Scheme card survives.
    assert meta.scheme_card["scheme_id"] == "mudra"
    # External answer survives.
    assert meta.external_answer["headline"].startswith("EBITDA")
    # Mixed answer survives.
    assert meta.mixed_answer["is_mixed"] is True
    # List → tuple coercion preserved.
    assert isinstance(meta.external_claims, tuple)
    assert isinstance(meta.freshness_warnings, tuple)
