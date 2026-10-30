"""SPRINT AI-12 wire schema test.

Two tests:

  * new fields on ``ChatGenerationMeta`` accept AI-12 values,
  * legacy payload round-trips without the AI-12 fields.
"""
from __future__ import annotations

from pydantic import ValidationError

import pytest

from app.schemas.chat import ChatGenerationMeta, ChatMessageOut


class TestSprintAI12WireSchema:

    def test_chat_generation_meta_accepts_ai12_fields(self) -> None:
        gm = ChatGenerationMeta(
            provider="x", model="y", fallback_used=False,
            generation_method="deterministic", generated_at="2026-01-01T00:00:00Z",
            tool_plan={"required": [], "optional": [], "parallelizable": [], "sequential": [], "rationale": "test"},
            evidence_requirements={"required": ["profile"], "optional": [], "rationale": "x"},
            contradiction_report={"severity": "low", "items": [], "rationale": "r"},
            answer_quality={"total": 7.0, "needs_retry": False, "weakest_axis": ""},
            structured_tool_envelopes=[{"tool_name": "x", "metric": None}],
            answer_mode="business_analysis",
        )
        assert gm.tool_plan is not None
        assert gm.evidence_requirements["required"] == ["profile"]
        assert gm.contradiction_report["severity"] == "low"
        assert gm.answer_quality["total"] == 7.0
        assert gm.structured_tool_envelopes
        assert gm.answer_mode == "business_analysis"

    def test_legacy_chat_generation_meta_round_trips(self) -> None:
        """A legacy ChatGenerationMeta (no AI-12 fields) must
        construct cleanly and serialise with all AI-12 fields
        as None / []."""
        gm = ChatGenerationMeta(
            provider="x", model="y", fallback_used=False,
            generation_method="deterministic", generated_at="2026-01-01T00:00:00Z",
        )
        assert gm.tool_plan is None
        assert gm.evidence_requirements is None
        assert gm.contradiction_report is None
        assert gm.answer_quality is None
        assert gm.structured_tool_envelopes == []
        assert gm.answer_mode == "general_knowledge"

    def test_chat_message_out_accepts_ai12_mirrors(self) -> None:
        mo = ChatMessageOut(
            id=1, role="assistant", content="hi",
            created_at="2026-01-01T00:00:00Z",
            tool_plan={"required": []},
            evidence_requirements={"required": []},
            contradiction_report={"severity": "low"},
            answer_quality={"total": 7.0},
            structured_tool_envelopes=[],
            answer_mode="business_analysis",
        )
        assert mo.answer_mode == "business_analysis"
        assert mo.answer_quality["total"] == 7.0

    def test_legacy_message_out_round_trips(self) -> None:
        mo = ChatMessageOut(
            id=1, role="user", content="hi",
            created_at="2026-01-01T00:00:00Z",
        )
        # AI-12 mirrors default to None / [] / "general_knowledge"
        assert mo.tool_plan is None
        assert mo.answer_mode == "general_knowledge"
        assert mo.structured_tool_envelopes == []

    def test_extra_forbid_blocks_unknown_field(self) -> None:
        with pytest.raises(ValidationError):
            ChatGenerationMeta(
                provider="x", model="y", fallback_used=False,
                generation_method="deterministic", generated_at="2026-01-01T00:00:00Z",
                unknown_ai12_field_xyz=True,  # type: ignore[call-arg]
            )
