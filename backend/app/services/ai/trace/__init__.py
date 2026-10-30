"""SPRINT AI-10 — Explain My Answer.

Public API for the decision-trace module. Re-exports the
builder + dataclasses so callers can ``from app.services.ai.trace
import build_trace, DecisionTrace`` without knowing the
internal module split.

The module is intentionally thin — all real work lives in
:mod:`app.services.ai.trace.builder` and
:mod:`app.services.ai.trace.decision_trace`.
"""
from __future__ import annotations

from app.services.ai.trace.builder import (
    build_trace,
    confidence_label_for,
)
from app.services.ai.trace.decision_trace import (
    DecisionTrace,
    TraceAlternative,
    TraceAssumption,
    TraceCalculationItem,
    TraceDecisionFactor,
    TraceEvidenceItem,
    TraceUncertainty,
)


__all__ = [
    "build_trace",
    "confidence_label_for",
    "DecisionTrace",
    "TraceAlternative",
    "TraceAssumption",
    "TraceCalculationItem",
    "TraceDecisionFactor",
    "TraceEvidenceItem",
    "TraceUncertainty",
]
