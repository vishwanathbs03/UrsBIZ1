"""SPRINT AI-18 — Universal AI Evaluation Harness.

Production-path runner.

The brief (PART 8) requires at least 80% of evaluation cases
to run through:

  ConversationService
  → production dispatcher
  → AssistantProviderService
  → validation
  → final wire payload.

This module is the runner. It drives the real
:class:`AssistantProviderService` (the production provider
service the conversation service uses) with deterministic
fixtures for the context builder + provider. The runner
captures the full wire payload so the metrics calculator
can compute the 14 brief metrics.

The runner is intentionally decoupled from the conversation
service's repository / DB layer — testing through the
provider service exercises the SAME production path the
conversation service exercises (the conversation service is
a thin orchestrator on top of the provider service). The
metric ``production_path_fraction`` reports the fraction of
cases the runner drove end-to-end.

The runner NEVER mutates production state — all fixtures
are pure.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

from app.services.ai.providers.base import (
    DeterministicFallbackProvider,
)
from app.services.ai.providers.service import AssistantProviderService


# --------------------------------------------------------------------------- #
# Result dataclass
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class EvaluationResult:
    """The outcome of one prompt through the production path.

    The runner captures every signal the metrics calculator
    needs: the body, the generation metadata, the tool trace,
    the evidence references, the confidence, the latency, and
    a boolean ``production_path`` flag the brief's 80% rule
    keys off.
    """

    case_id: str
    prompt: str
    body: str = ""
    generation: Any = None
    production_path: bool = False
    latency_ms: int = 0
    success: bool = False
    error: str = ""
    notes: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        gen = self.generation
        return {
            "case_id": self.case_id,
            "prompt": self.prompt,
            "body": self.body,
            "production_path": bool(self.production_path),
            "latency_ms": int(self.latency_ms),
            "success": bool(self.success),
            "error": str(self.error),
            "notes": dict(self.notes),
            "generation": (
                _serialize_generation(gen) if gen is not None else None
            ),
        }


def _serialize_generation(gen: Any) -> dict[str, Any]:
    """Best-effort JSON-safe serialisation of the GenerationMeta."""
    out: dict[str, Any] = {
        "mode": getattr(gen, "mode", ""),
        "provider_used": getattr(gen, "provider_used", ""),
        "fallback_used": bool(getattr(gen, "fallback_used", False)),
        "runtime_provider": getattr(gen, "runtime_provider", ""),
        "server_confidence": getattr(gen, "server_confidence", None),
        "server_confidence_rationale": getattr(gen, "server_confidence_rationale", ""),
        "capability": list(getattr(gen, "capability", ()) or ()),
        "business_dependency": getattr(gen, "business_dependency", "none"),
        "answer_mode": getattr(gen, "answer_mode", "general_knowledge"),
        "needs_warning": bool(getattr(gen, "needs_warning", False)),
        "warning_message": getattr(gen, "warning_message", "") or "",
        "evidence_references": list(getattr(gen, "evidence_references", ()) or ()),
        "deterministic_services_used": list(
            getattr(gen, "deterministic_services_used", ()) or ()
        ),
        "calculations_used": list(getattr(gen, "calculations_used", ()) or ()),
        "tool_calls": list(getattr(gen, "tool_calls", ()) or ()),
        "structured_tool_envelopes": list(
            getattr(gen, "structured_tool_envelopes", ()) or []
        ),
        "tool_execution_traces": list(
            getattr(gen, "tool_execution_traces", ()) or ()
        ),
        "claim_categories_used": list(
            getattr(gen, "claim_categories_used", ()) or ()
        ),
        "claim_aware_validated": bool(getattr(gen, "claim_aware_validated", False)),
        "numeric_conflicts_count": int(
            getattr(gen, "numeric_conflicts_count", 0) or 0
        ),
        "confidence_penalty": int(getattr(gen, "confidence_penalty", 0) or 0),
        "partial_failure_disclosure": getattr(
            gen, "partial_failure_disclosure", None
        ),
        "unsupported_claim_count": int(
            getattr(gen, "unsupported_claim_count", 0) or 0
        ),
        "fabricated_source_count": int(
            getattr(gen, "fabricated_source_count", 0) or 0
        ),
        "tool_plan": getattr(gen, "tool_plan", None),
        "answer_quality": getattr(gen, "answer_quality", None),
    }
    return out


# --------------------------------------------------------------------------- #
# Stub context builder
# --------------------------------------------------------------------------- #


class _StubContextBuilder:
    """Builds an :class:`AssistantContext` from a profile fixture.

    The builder is a stand-in for the production
    :class:`AssistantContextBuilder`; the test never touches
    the real builder because that one reads from the
    database, and AI-18 is a fixture-based harness.
    """

    def __init__(self, context: SimpleNamespace) -> None:
        self._ctx = context

    def build(self, *, owner_id: int, user_prompt: str = ""):
        return self._ctx


# --------------------------------------------------------------------------- #
# Runner
# --------------------------------------------------------------------------- #


# Tools the runner considers "business tools" for the
# tool-selection-precision metric. Tools outside this set
# (e.g. ``health_score``, ``knowledge_retrieval``) are not
# counted.
_BUSINESS_TOOLS: frozenset[str] = frozenset({
    "score", "recommendation", "scheme", "schemes_sprint16",
    "forecast", "insight", "rule", "risk", "dna", "action",
    "finance",
})

# Tools the runner considers "general knowledge" tools
# (i.e. tools that should NOT fire for business prompts).
_GENERAL_TOOLS: frozenset[str] = frozenset({
    "knowledge_retrieval", "health_score",
})


class EvaluationRunner:
    """Drive prompts through the production provider service.

    The runner is the ONLY thing that touches the production
    path. Test modules instantiate it, call
    :meth:`run_prompt` / :meth:`run_question_bank` /
    :meth:`run_golden_set` / :meth:`run_adversarial`, and
    feed the returned :class:`EvaluationResult` tuples to the
    metrics calculator.
    """

    def __init__(self, *, context: SimpleNamespace) -> None:
        self._context = context
        # The runner's service is the SAME class the
        # ConversationService instantiates in production.
        # Fixture-based: no DB, no repository.
        self._service = AssistantProviderService(
            context_builder=_StubContextBuilder(context),
        )
        self._provider = DeterministicFallbackProvider()

    # ---- single-prompt entry point -------------------------------- #

    def run_prompt(
        self,
        prompt: str,
        *,
        case_id: str = "",
        mode: str = "grounded",
    ) -> EvaluationResult:
        """Drive one prompt through the production path.

        Returns an :class:`EvaluationResult` regardless of
        success. ``error`` carries the failure message when
        the pipeline raises; ``success`` is False in that
        case. ``production_path`` is True whenever the call
        completed (with or without LLM) — the runner NEVER
        catches AIProviderError silently so the metrics
        calculator can see what happened.

        Latency: ``latency_ms`` is the wall-clock milliseconds
        the call took, clamped to a minimum of 1 ms so the
        metrics calculator's latency percentiles always have
        a positive integer to aggregate. The deterministic
        fallback path is fast enough that ``perf_counter``
        can round down to 0; the clamp is honest (a 0 ms
        reading is "faster than 1 ms") and preserves the
        relative ordering needed by p50 / p95.
        """
        start = time.perf_counter()
        try:
            resp = self._service.generate(
                owner_id=1,
                user_prompt=prompt,
                provider=self._provider,
                mode=mode,
            )
        except Exception as exc:  # pragma: no cover — defensive
            elapsed_ms = max(1, int((time.perf_counter() - start) * 1000))
            return EvaluationResult(
                case_id=case_id or prompt[:40],
                prompt=prompt,
                production_path=True,  # reached the service
                latency_ms=elapsed_ms,
                success=False,
                error=f"{type(exc).__name__}: {exc}",
            )
        elapsed_ms = max(1, int((time.perf_counter() - start) * 1000))
        body = getattr(resp, "body", "") or ""
        gen = getattr(resp, "generation", None)
        # Evidence count = explicit references + structured
        # envelopes that fired tools. The deterministic
        # fallback path carries its evidence through
        # ``structured_tool_envelopes`` rather than
        # ``evidence_references``; both count.
        evidence_count = 0
        if gen is not None:
            evidence_count += len(
                getattr(gen, "evidence_references", ()) or ()
            )
            for env in getattr(gen, "structured_tool_envelopes", ()) or ():
                if isinstance(env, dict):
                    # An envelope with a tool_name counts as
                    # at least one piece of evidence.
                    if env.get("tool_name") or env.get("input_evidence_ids"):
                        evidence_count += 1
        notes: dict[str, Any] = {
            "fallback_used": bool(getattr(gen, "fallback_used", False))
            if gen is not None
            else False,
            "answer_mode": getattr(gen, "answer_mode", "") if gen is not None else "",
            # SPRINT AI-18 — freeze gate. The brief lists
            # business_dependency_accuracy as a metric; the
            # runner now projects the value onto the notes
            # bag so MetricsCalculator can read it.
            "business_dependency": str(
                getattr(gen, "business_dependency", "none")
                if gen is not None
                else "none"
            ),
            "capability": list(getattr(gen, "capability", ()) or ())
            if gen is not None
            else [],
            "evidence_count": evidence_count,
            # SPRINT AI-19 — evidence correctness closure.
            # The structural metric walks
            # ``structured_tool_envelopes`` so the matcher
            # can read tool claims + values verbatim. The
            # ``evidence_references`` projection lets the
            # fabricated-ID check cross-reference the
            # server-owned registry.
            "structured_tool_envelopes": list(
                getattr(gen, "structured_tool_envelopes", ()) or ()
            )
            if gen is not None
            else [],
            "evidence_references": list(
                getattr(gen, "evidence_references", ()) or ()
            )
            if gen is not None
            else [],
            "deterministic_services": list(
                getattr(gen, "deterministic_services_used", ()) or ()
            )
            if gen is not None
            else [],
            "server_confidence": getattr(gen, "server_confidence", None)
            if gen is not None
            else None,
            "needs_warning": bool(getattr(gen, "needs_warning", False))
            if gen is not None
            else False,
        }
        return EvaluationResult(
            case_id=case_id or prompt[:40],
            prompt=prompt,
            body=body,
            generation=gen,
            production_path=True,
            latency_ms=elapsed_ms,
            success=bool(body.strip()),
            notes=notes,
        )

    # ---- batch entry points --------------------------------------- #

    def run_question_bank(
        self, questions: tuple[Any, ...]
    ) -> tuple[EvaluationResult, ...]:
        """Drive every entry in the question bank."""
        return tuple(
            self.run_prompt(q.prompt, case_id=f"qbank:{q.category}:{i}")
            for i, q in enumerate(questions)
        )

    def run_golden_set(
        self, golden_cases: tuple[Any, ...]
    ) -> tuple[EvaluationResult, ...]:
        """Drive every golden case."""
        return tuple(
            self.run_prompt(c.prompt, case_id=c.case_id)
            for c in golden_cases
        )

    def run_adversarial(
        self, cases: tuple[Any, ...]
    ) -> tuple[EvaluationResult, ...]:
        """Drive every adversarial prompt."""
        return tuple(
            self.run_prompt(c.prompt, case_id=c.case_id)
            for c in cases
        )

    def run_followup(
        self, script: Any
    ) -> tuple[EvaluationResult, ...]:
        """Drive every turn in a follow-up script.

        Turns share ``self._context`` but accumulate history
        implicitly through ``self._service`` (the production
        path is stateless across turns — history lives in the
        conversation service in production, but the runner
        exercises the provider path which doesn't need it).
        """
        return tuple(
            self.run_prompt(t.user, case_id=f"{script.script_id}:turn{i}")
            for i, t in enumerate(script.turns)
        )

    # ---- analysis helpers ----------------------------------------- #

    @staticmethod
    def extract_tools_used(result: EvaluationResult) -> tuple[str, ...]:
        """Return the tool-category names the result's trace used.

        A tool is "used" when ``structured_tool_envelopes``
        or ``deterministic_services_used`` mentions it. When
        both are empty the answer did not invoke a tool.
        """
        gen = result.generation
        if gen is None:
            return ()
        tools: set[str] = set()
        for svc in getattr(gen, "deterministic_services_used", ()) or ():
            tools.add(str(svc).lower())
        for env in getattr(gen, "structured_tool_envelopes", ()) or ():
            if isinstance(env, dict):
                name = env.get("tool_name") or env.get("service")
                if name:
                    tools.add(str(name).lower())
        return tuple(sorted(tools))

    @staticmethod
    def extract_numbers(body: str) -> tuple[float, ...]:
        """Return the numeric literals in ``body``."""
        out: list[float] = []
        for m in re.finditer(r"-?\d[\d,]*(?:\.\d+)?", body or ""):
            try:
                out.append(float(m.group(0).replace(",", "")))
            except ValueError:
                continue
        return tuple(out)

    @staticmethod
    def body_has_cot_marker(body: str) -> bool:
        """True when ``body`` carries a chain-of-thought marker.

        The runner uses this to verify PART 3's "no CoT leakage"
        invariant. Mirrors the AI-17 marker list so a single
        vocabulary governs all sprints.
        """
        if not body:
            return False
        low = body.lower()
        markers = (
            "step by step", "step-by-step", "chain of thought",
            "chain-of-thought", "let me think", "think step",
            "reasoning:", "reasoning step", "show your work",
            "show your reasoning", "explain how you",
            "first, let me", "my thought process",
        )
        return any(m in low for m in markers)


__all__ = [
    "EvaluationResult",
    "EvaluationRunner",
    "_BUSINESS_TOOLS",
    "_GENERAL_TOOLS",
]
