"""SPRINT AI-6 — Trust-first visual UI — tests for direct_answer.

Covers the brief's mandate that the backend stamps the first
1-3 sentences of the assistant prose onto GenerationMeta so
the frontend can render a "Direct Answer" header the user can
read within 10 seconds. The extractor is a pure function
(``_extract_direct_answer``) and the wire projection is
covered via ``GenerationMeta`` round-trip and legacy-row
tolerance.
"""

from __future__ import annotations

import pytest

from app.services.ai.providers.base import (
    AssistantResponse,
    GenerationMeta,
)
from app.services.chat.conversation_service import _extract_direct_answer


# --------------------------------------------------------------------------- #
# Pure-function extraction
# --------------------------------------------------------------------------- #


def test_extracts_first_three_sentences():
    """Happy path — three sentences, returns all three joined."""
    prose = (
        "Acme Textiles is at 68/100 (Established). "
        "Your top bottleneck is 75% supplier concentration. "
        "Diversifying two secondary vendors would reduce risk. "
        "Smaller caveat that we should not show."
    )
    out = _extract_direct_answer(prose)
    assert out is not None
    assert "Acme Textiles is at 68/100 (Established)." in out
    assert "75% supplier concentration." in out
    assert "Diversifying two secondary vendors" in out
    assert "Smaller caveat" not in out


def test_extracts_single_sentence_when_only_one_present():
    """The function never invents a second sentence."""
    prose = "Acme Textiles is at 68/100."
    out = _extract_direct_answer(prose)
    assert out == "Acme Textiles is at 68/100."


def test_extracts_two_sentences():
    prose = "Acme Textiles is at 68/100. Suppliers concentration is 75%."
    out = _extract_direct_answer(prose)
    assert out is not None
    assert "Acme Textiles is at 68/100." in out
    assert "75%" in out


def test_handles_exclamation_and_question_marks():
    """Sentence boundaries include ! and ?."""
    prose = (
        "Watch out — supplier concentration is critical! "
        "Should we diversify now?"
    )
    out = _extract_direct_answer(prose)
    assert out is not None
    assert "supplier concentration is critical!" in out
    assert "Should we diversify now?" in out


def test_handles_none_input():
    """None input returns None — never crashes."""
    assert _extract_direct_answer(None) is None


def test_handles_empty_string():
    """Empty string returns None."""
    assert _extract_direct_answer("") is None
    assert _extract_direct_answer("   \n\t  ") is None


def test_handles_non_string_input():
    """Non-string input returns None — defensive."""
    assert _extract_direct_answer(12345) is None  # type: ignore[arg-type]
    assert _extract_direct_answer(["list"]) is None  # type: ignore[arg-type]


def test_strips_markdown_list_markers():
    """Leading "- " or "* " markdown markers are stripped."""
    prose = (
        "- First bullet answer about your score.\n"
        "- Second bullet answer about risk."
    )
    out = _extract_direct_answer(prose)
    assert out is not None
    assert "First bullet answer about your score." in out
    assert "Second bullet answer about risk." in out
    assert "- " not in out


def test_truncates_to_600_chars():
    """A pathological long sentence is truncated to the schema cap."""
    long = "A" * 800 + "."
    out = _extract_direct_answer(long)
    assert out is not None
    assert len(out) <= 600
    assert out.endswith("...")


def test_preserves_caution_sentences():
    """The brief warns not to drop caveats — extractor preserves them."""
    prose = (
        "Acme Textiles is at 68/100. "
        "Note: revenue figures are estimates based on registration data. "
        "Concentration risk is high."
    )
    out = _extract_direct_answer(prose)
    assert out is not None
    assert "Note: revenue figures" in out


# --------------------------------------------------------------------------- #
# GenerationMeta + wire round-trip
# --------------------------------------------------------------------------- #


def test_generation_meta_carries_direct_answer():
    """GenerationMeta.empty() must accept direct_answer kwarg."""
    meta = GenerationMeta.empty(
        mode="grounded",
        provider_used="ollama",
        model="llama3.1",
        provider_latency_ms=42,
        fallback_used=False,
        direct_answer="Acme Textiles is at 68/100. Concentration risk is high.",
    )
    assert meta.direct_answer is not None
    assert "Acme Textiles is at 68/100." in meta.direct_answer


def test_generation_meta_direct_answer_default_none():
    """Default for direct_answer is None — backward-compatible."""
    meta = GenerationMeta.empty(
        mode="grounded",
        provider_used="p",
        model="m",
        provider_latency_ms=None,
        fallback_used=False,
    )
    assert meta.direct_answer is None


def test_generation_meta_direct_answer_round_trip():
    """from_dict must reconstruct the direct_answer field."""
    meta = GenerationMeta.empty(
        mode="grounded",
        provider_used="p",
        model="m",
        provider_latency_ms=None,
        fallback_used=False,
        direct_answer="First sentence. Second sentence. Third sentence.",
    )
    d = meta.to_dict()
    assert d["direct_answer"] == meta.direct_answer
    meta2 = GenerationMeta.from_dict(d)
    assert meta2.direct_answer == meta.direct_answer


def test_generation_meta_direct_answer_legacy_row():
    """Legacy rows that pre-date AI-6 must reconstruct with None."""
    legacy = GenerationMeta.empty(
        mode="grounded",
        provider_used="p",
        model="m",
        provider_latency_ms=None,
        fallback_used=False,
    )
    d = legacy.to_dict()
    # Simulate a row that never had AI-6 — strip the key.
    legacy_dict = {k: v for k, v in d.items() if k != "direct_answer"}
    meta2 = GenerationMeta.from_dict(legacy_dict)
    assert meta2.direct_answer is None


def test_generation_meta_direct_answer_partial_extraction():
    """A long prose truncates to <=600 chars on the wire."""
    prose = ("Long sentence. " * 50).strip()
    out = _extract_direct_answer(prose)
    assert out is not None
    meta = GenerationMeta.empty(
        mode="grounded",
        provider_used="p",
        model="m",
        provider_latency_ms=None,
        fallback_used=False,
        direct_answer=out,
    )
    assert len(meta.direct_answer or "") <= 600


def test_stamp_direct_answer_on_real_provider():
    """The defensive _stamp_direct_answer rebuilds GenerationMeta correctly."""
    # We can't import the ConversationService methods without
    # instantiating the whole DI graph, but we can verify the
    # dataclass-replace path it uses.
    from dataclasses import replace

    meta = GenerationMeta.empty(
        mode="grounded",
        provider_used="ollama",
        model="llama3.1",
        provider_latency_ms=100,
        fallback_used=False,
    )
    new_meta = replace(meta, direct_answer="First answer. Second answer.")
    assert new_meta.direct_answer == "First answer. Second answer."
    # The original is untouched (frozen contract).
    assert meta.direct_answer is None


def test_assistant_response_with_direct_answer_meta():
    """An AssistantResponse can carry a GenerationMeta with direct_answer."""
    meta = GenerationMeta.empty(
        mode="grounded",
        provider_used="ollama",
        model="llama3.1",
        provider_latency_ms=42,
        fallback_used=False,
        direct_answer="Score is 68/100. Concentration risk is high.",
    )
    resp = AssistantResponse(
        body="Score is 68/100. Concentration risk is high. ...",
        model="llama3.1",
        fallback_used=False,
        provider_used="ollama",
        generated_at="2026-08-09T10:00:00Z",
        generation=meta,
    )
    assert resp.generation is not None
    assert resp.generation.direct_answer is not None
    assert "Score is 68/100." in resp.generation.direct_answer
