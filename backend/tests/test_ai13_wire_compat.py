"""SPRINT AI-13 — Wire compatibility tests.

Tests every wire scenario:

  * legacy messages WITHOUT AI-13 fields (must round-trip)
  * new messages WITH all AI-13 fields
  * null / empty / malformed optional fields
  * persistence / reload via GenerationMeta.from_dict
  * frontend deserialization via ChatGenerationMeta + ChatMessageOut

These tests guard the cutover against a regression where the
new fields accidentally break a legacy row.
"""
from __future__ import annotations

from dataclasses import asdict

from app.services.ai.providers.base import GenerationMeta
from app.schemas.chat import ChatGenerationMeta, ChatMessageOut


# --------------------------------------------------------------------------- #
# 1. GenerationMeta round-trip
# --------------------------------------------------------------------------- #


class TestGenerationMetaCompat:
    def test_legacy_construction_with_only_known_fields(self) -> None:
        """A pre-AI-13 row that carries only the legacy
        fields must construct + serialise + deserialise."""
        meta = GenerationMeta(
            provider="deterministic-fallback",
            model="deterministic-fallback",
            mode="grounded",
            fallback_used=True,
            fallback_reason=None,
            generation_method="deterministic",
            schema_validated=True,
            grounding_validated=True,
            server_grounding_score=100,
            evidence_count=0,
            confidence=None,
            assumptions=(),
            limitations=(),
            evidence_references=(),
            generated_at="2026-08-11T00:00:00+00:00",
            prompt_truncated=False,
            provider_latency_ms=12,
            grounded_payload=None,
            business_evidence_validated=False,
            context_manifest=None,
            deterministic_services_used=(),
            calculations_used=(),
            question_understanding=None,
            tool_calls=(),
            claim_categories_used=(),
            claim_aware_validated=False,
            numeric_conflicts_count=0,
            server_confidence=None,
            server_confidence_rationale="",
            claim_audit=None,
            claim_audit_rejected=False,
            claim_audit_soft_corrections=0,
            scenario_analysis=None,
            direct_answer=None,
            missing_data=(),
            llm_tool_results=(),
            explanation=None,
            capability=(),
            business_dependency="none",
            # AI-13 NOT passed — defaults fire.
        )
        assert meta.tool_execution_traces == ()
        assert meta.partial_failure_disclosure is None
        assert meta.confidence_penalty == 0

        # Round-trip via from_dict.
        d = asdict(meta)
        restored = GenerationMeta.from_dict(d)
        assert restored.tool_execution_traces == ()
        assert restored.partial_failure_disclosure is None
        assert restored.confidence_penalty == 0

    def test_new_construction_with_all_ai13_fields(self) -> None:
        """A post-AI-13 row with every field populated
        round-trips."""
        traces = (
            {
                "tool_name": "health_score",
                "selected": True,
                "executed": True,
                "success": True,
                "latency_ms": 12,
                "result_available": True,
                "evidence_ids": ["ev1", "ev2"],
                "failure_reason": "",
                "error_category": "none",
            },
            {
                "tool_name": "predictive_sprint14",
                "selected": True,
                "executed": True,
                "success": False,
                "latency_ms": 500,
                "result_available": False,
                "evidence_ids": [],
                "failure_reason": "timeout",
                "error_category": "timeout",
            },
        )
        meta = GenerationMeta(
            provider="openai",
            model="gpt-4",
            mode="grounded",
            fallback_used=False,
            fallback_reason=None,
            generation_method="generative",
            schema_validated=True,
            grounding_validated=True,
            server_grounding_score=85,
            evidence_count=4,
            confidence=82,
            assumptions=("a",),
            limitations=("l",),
            evidence_references=("ev1",),
            generated_at="2026-08-11T00:00:00+00:00",
            prompt_truncated=False,
            provider_latency_ms=300,
            grounded_payload=None,
            business_evidence_validated=True,
            context_manifest=None,
            deterministic_services_used=("health_score",),
            calculations_used=(),
            question_understanding=None,
            tool_calls=({"service_name": "health_score", "inputs": {}},),
            claim_categories_used=(),
            capability=("BUSINESS_ANALYSIS",),
            business_dependency="required",
            tool_execution_traces=traces,
            partial_failure_disclosure=(
                "predictive_sprint14 timed out, so the predictive_sprint14 "
                "portion could not be verified"
            ),
            confidence_penalty=12,
        )
        # Round-trip.
        d = asdict(meta)
        assert tuple(d["tool_execution_traces"]) == traces
        restored = GenerationMeta.from_dict(d)
        assert restored.tool_execution_traces == traces
        assert (
            restored.partial_failure_disclosure
            == "predictive_sprint14 timed out, so the predictive_sprint14 "
            "portion could not be verified"
        )
        assert restored.confidence_penalty == 12
        assert restored.capability == ("BUSINESS_ANALYSIS",)

    def test_legacy_dict_with_missing_ai13_fields(self) -> None:
        """A dict from a pre-AI-13 row (no AI-13 keys) still
        constructs via from_dict because the dataclass has
        safe defaults."""
        d = {
            "provider": "deterministic-fallback",
            "model": "deterministic-fallback",
            "mode": "grounded",
            "fallback_used": True,
            "fallback_reason": None,
            "generation_method": "deterministic",
            "schema_validated": True,
            "grounding_validated": True,
            "server_grounding_score": 100,
            "evidence_count": 0,
            "confidence": None,
            "assumptions": [],
            "limitations": [],
            "evidence_references": [],
            "generated_at": "2026-08-11T00:00:00+00:00",
            "prompt_truncated": False,
            "provider_latency_ms": 12,
            "grounded_payload": None,
            "business_evidence_validated": False,
            "context_manifest": None,
            "deterministic_services_used": [],
            "calculations_used": [],
            "question_understanding": None,
            "tool_calls": [],
            "claim_categories_used": [],
            "capability": [],
            "business_dependency": "none",
            # NOTE: no AI-13 keys.
        }
        meta = GenerationMeta.from_dict(d)
        assert meta.tool_execution_traces == ()
        assert meta.partial_failure_disclosure is None
        assert meta.confidence_penalty == 0

    def test_malformed_ai13_fields_fall_back_to_safe_defaults(self) -> None:
        """Malformed (non-dict) tool_execution_traces entries
        don't crash the constructor — the trace list passes
        through verbatim. (The projector is responsible for
        rejecting malformed trace entries; the dataclass is
        permissive.)"""
        d = {
            "provider": "deterministic-fallback",
            "model": "deterministic-fallback",
            "mode": "grounded",
            "fallback_used": True,
            "fallback_reason": None,
            "generation_method": "deterministic",
            "schema_validated": True,
            "grounding_validated": True,
            "server_grounding_score": 100,
            "evidence_count": 0,
            "confidence": None,
            "assumptions": [],
            "limitations": [],
            "evidence_references": [],
            "generated_at": "2026-08-11T00:00:00+00:00",
            "prompt_truncated": False,
            "provider_latency_ms": 12,
            "grounded_payload": None,
            "business_evidence_validated": False,
            "context_manifest": None,
            "deterministic_services_used": [],
            "calculations_used": [],
            "question_understanding": None,
            "tool_calls": [],
            "claim_categories_used": [],
            "capability": [],
            "business_dependency": "none",
            "tool_execution_traces": [{"malformed": True}],
            "partial_failure_disclosure": "",
            "confidence_penalty": 0,
        }
        meta = GenerationMeta.from_dict(d)
        assert meta.tool_execution_traces == ({"malformed": True},)


# --------------------------------------------------------------------------- #
# 2. ChatGenerationMeta + ChatMessageOut — frontend deserialization
# --------------------------------------------------------------------------- #


class TestPydanticCompat:
    def test_chat_generation_meta_accepts_legacy_only(self) -> None:
        """A pre-AI-13 ChatGenerationMeta payload
        deserialises with the AI-13 fields as safe defaults."""
        legacy = {
            "provider": "deterministic-fallback",
            "model": "deterministic-fallback",
            "mode": "grounded",
            "fallback_used": True,
            "fallback_reason": None,
            "generation_method": "deterministic",
            "schema_validated": True,
            "grounding_validated": True,
            "server_grounding_score": 100,
            "evidence_count": 0,
            "confidence": None,
            "assumptions": [],
            "limitations": [],
            "evidence_references": [],
            "generated_at": "2026-08-11T00:00:00+00:00",
            "prompt_truncated": False,
            "provider_latency_ms": 12,
            "grounded_payload": None,
            "business_evidence_validated": False,
            "context_manifest": None,
            "deterministic_services_used": [],
            "calculations_used": [],
            "question_understanding": None,
            "tool_calls": [],
            "claim_categories_used": [],
            "capability": [],
            "business_dependency": "none",
            "claim_aware_validated": False,
            "numeric_conflicts_count": 0,
            "server_confidence": None,
            "server_confidence_rationale": "",
            "claim_audit": None,
            "claim_audit_rejected": False,
            "claim_audit_soft_corrections": 0,
            "scenario_analysis": None,
            "direct_answer": None,
            "missing_data": [],
            "llm_tool_results": [],
            "explanation": None,
            # AI-12 + AI-13 fields missing — defaults fire.
        }
        meta = ChatGenerationMeta(**legacy)
        assert meta.tool_execution_traces == []
        assert meta.partial_failure_disclosure is None
        assert meta.confidence_penalty == 0

    def test_chat_generation_meta_accepts_ai13_fields(self) -> None:
        """A post-AI-13 ChatGenerationMeta payload with every
        AI-13 field populated deserialises."""
        legacy = {
            "provider": "openai",
            "model": "gpt-4",
            "mode": "grounded",
            "fallback_used": False,
            "fallback_reason": None,
            "generation_method": "generative",
            "schema_validated": True,
            "grounding_validated": True,
            "server_grounding_score": 85,
            "evidence_count": 4,
            "confidence": 80,
            "assumptions": [],
            "limitations": [],
            "evidence_references": [],
            "generated_at": "2026-08-11T00:00:00+00:00",
            "prompt_truncated": False,
            "provider_latency_ms": 300,
            "grounded_payload": None,
            "business_evidence_validated": True,
            "context_manifest": None,
            "deterministic_services_used": [],
            "calculations_used": [],
            "question_understanding": None,
            "tool_calls": [],
            "claim_categories_used": [],
            "capability": ["BUSINESS_ANALYSIS"],
            "business_dependency": "required",
            "claim_aware_validated": False,
            "numeric_conflicts_count": 0,
            "server_confidence": 80,
            "server_confidence_rationale": "",
            "claim_audit": None,
            "claim_audit_rejected": False,
            "claim_audit_soft_corrections": 0,
            "scenario_analysis": None,
            "direct_answer": None,
            "missing_data": [],
            "llm_tool_results": [],
            "explanation": None,
            "tool_execution_traces": [
                {
                    "tool_name": "health_score",
                    "selected": True,
                    "executed": True,
                    "success": True,
                    "latency_ms": 10,
                    "result_available": True,
                    "evidence_ids": [],
                    "failure_reason": "",
                    "error_category": "none",
                },
            ],
            "partial_failure_disclosure": None,
            "confidence_penalty": 0,
        }
        meta = ChatGenerationMeta(**legacy)
        assert len(meta.tool_execution_traces) == 1
        assert meta.tool_execution_traces[0]["tool_name"] == "health_score"

    def test_chat_message_out_accepts_legacy_only(self) -> None:
        """A pre-AI-13 ChatMessageOut payload deserialises
        with AI-13 defaults."""
        msg = ChatMessageOut(
            id=1,
            role="assistant",
            content="Hello.",
            created_at="2026-08-11T00:00:00+00:00",
            generation=None,
            # AI-12 + AI-13 fields missing — defaults fire.
        )
        assert msg.tool_execution_traces == []
        assert msg.partial_failure_disclosure is None
        assert msg.confidence_penalty == 0

    def test_chat_message_out_accepts_ai13_mirrors(self) -> None:
        """A post-AI-13 ChatMessageOut payload with the three
        top-level AI-13 mirrors deserialises."""
        msg = ChatMessageOut(
            id=1,
            role="assistant",
            content="Hello.",
            created_at="2026-08-11T00:00:00+00:00",
            generation=None,
            tool_execution_traces=[
                {"tool_name": "health_score", "success": True},
            ],
            partial_failure_disclosure=None,
            confidence_penalty=0,
        )
        assert len(msg.tool_execution_traces) == 1
        assert msg.confidence_penalty == 0
