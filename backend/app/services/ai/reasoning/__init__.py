"""Explicit Reasoning Pipeline & Conclusion Sanitizer — Sprint H8.3.

H8.11 extension — the pre-LLM reasoning layer
----------------------------------------------

The H8.11 layer adds two new components to this package:

  * :class:`BusinessReasoningEngine` — orchestrates the
    intent classifier + the H8.3 pipeline + the H8.2
    knowledge graph. Returns a structured
    :class:`ReasoningPlan`.

  * :class:`EvidenceRetriever` — given the plan and an
    existing :class:`EvidenceRegistry`, returns a ranked
    view ordered by intent + KG relevance.

The two new exports are intentionally placed alongside the
H8.3 symbols so callers can mix-and-match the legacy 8-stage
:func:`process` path with the new pre-LLM planning path.
"""
from app.services.ai.reasoning.evidence_retriever import (
    EvidenceRetriever,
    RankedEvidence,
)
from app.services.ai.reasoning.pipeline import (
    Hypothesis,
    ReasoningPipeline,
    ReasoningPlan,
    ReasoningStageResult,
    ReasoningTrace,
)
from app.services.ai.reasoning.reasoning_engine import BusinessReasoningEngine
from app.services.ai.reasoning.sanitizer import ConclusionSanitizer

__all__ = [
    "BusinessReasoningEngine",
    "ConclusionSanitizer",
    "EvidenceRetriever",
    "Hypothesis",
    "RankedEvidence",
    "ReasoningPipeline",
    "ReasoningPlan",
    "ReasoningStageResult",
    "ReasoningTrace",
]