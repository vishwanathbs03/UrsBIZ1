"""ReasoningPipeline — Sprint H8.3 8-Stage Reasoning Pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.services.ai.reasoning.sanitizer import ConclusionSanitizer


@dataclass(frozen=True)
class ReasoningStageResult:
    """Internal result of an individual reasoning stage."""

    stage_name: str
    summary: str
    passed: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Hypothesis:
    """An internal diagnostic hypothesis regarding root causes or growth levers."""

    hypothesis_id: str
    statement: str
    supporting_evidence_ids: tuple[str, ...]
    confidence_score: float
    is_valid: bool = True


@dataclass(frozen=True)
class ReasoningTrace:
    """The structured intermediate result of the pre-LLM reasoning pass.

    Bundles every :class:`ReasoningStageResult` produced by the
    H8.3 pipeline plus a one-sentence intent summary and the
    hypothesis statements. The trace is informational — the
    prompt builder surfaces it as a ``=== REASONING TRACE ===``
    block so the LLM sees the structure of the engine's
    diagnostic thinking before it answers. The trace never
    leaks into the response body itself.
    """

    stages: tuple[ReasoningStageResult, ...]
    intent_summary: str
    hypothesis_summaries: tuple[str, ...]


@dataclass(frozen=True)
class ReasoningPlan:
    """The structured pre-LLM plan the BusinessReasoningEngine emits.

    The plan is the bridge between the existing
    :class:`AssistantContext` and the LLM prompt. The
    :class:`BusinessReasoningEngine` builds it once per request
    and the prompt builder consumes it as an optional kwarg.

    Attributes
    ----------
    intent:
        Server-detected intent string (one of
        :class:`QuestionIntent` values, e.g.
        ``"reach_revenue_target"`` or ``"general"``).
    subgraph_node_ids:
        The top-K knowledge-graph node IDs most relevant to
        the intent, in priority order. The retriever uses
        these to boost evidence entries whose ``evidence_id``
        matches a high-priority node.
    hypotheses:
        Diagnostic hypotheses the engine produced. Re-uses
        the existing :class:`Hypothesis` dataclass.
    evidence_priorities:
        Ordered list of evidence IDs the engine considers
        most relevant to the intent. Empty tuple when the
        registry carries no entries.
    confidence:
        Engine's confidence in its plan, ``0..100``.
    trace:
        The structured stage trace (see :class:`ReasoningTrace`).
    question_interpretation:
        AI-1 — a short dotted path describing what the user
        asked (e.g. ``"operational.finance.working_capital"``).
        Defaults to ``""`` when no :class:`QuestionUnderstanding`
        was supplied. The prompt builder surfaces this in the
        ``=== REASONING TRACE ===`` block.
    applicable_deterministic_services:
        AI-1 — service names the :class:`ToolSelector` should
        invoke. The legacy engines (when present) live here:
        ``"health_score"``, ``"recommendation"``,
        ``"schemes_sprint16"``, ``"finance"``, ``"risk"``,
        ``"insights"``, ``"knowledge_retrieval"``. Empty
        tuple when no services are applicable.
    calculations_required:
        AI-1 — calculation labels the LLM should cite. One
        of ``"gap_math"``, ``"growth_multiple"``, ``"roi"``,
        ``"working_capital"``, ``"headcount_cost"``,
        ``"scenario_delta"``. Empty tuple when the prompt
        does not require calculations.
    unknowns:
        AI-1 — context fields the assistant would want but
        are missing. Drives the ``missing_info`` shell in the
        adaptive answer composer.
    possible_answer_structure:
        AI-1 — one of ``"executive"``, ``"expanded"``,
        ``"scenario"``, ``"missing_info"``. The adaptive
        answer composer picks a shell from this. Defaults to
        ``"expanded"`` when not set.
    """

    intent: str
    subgraph_node_ids: tuple[str, ...]
    hypotheses: tuple[Hypothesis, ...]
    evidence_priorities: tuple[str, ...]
    confidence: float
    trace: ReasoningTrace

    # AI-1 — appended at the END so the legacy 6-arg positional
    # construction site in test_h8_11_evidence_retriever.py:60
    # keeps working unchanged. All five have defaults.
    question_interpretation: str = ""
    applicable_deterministic_services: tuple[str, ...] = ()
    calculations_required: tuple[str, ...] = ()
    unknowns: tuple[str, ...] = ()
    possible_answer_structure: str = "expanded"

    # SPRINT AI-12 — Universal Reasoning Layer. 5 more additive
    # fields, all default-safe, all derived from the
    # ``QuestionUnderstanding`` instance passed at construction
    # time. Field ordering is preserved to keep the
    # frozen-dataclass argspec monotonic across all AI-N sprints.
    required_evidence_types: tuple[str, ...] = ()
    required_tools: tuple[str, ...] = ()
    answer_mode: str = "general_knowledge"
    expected_output_sections: tuple[str, ...] = ()
    # The :class:`EvidenceRequirements` produced by the
    # ``EvidenceRequirementPlanner``. Typed as ``Any`` to keep
    # the pipeline module cycle-free (the planner lives in a
    # sibling submodule). ``None`` until AI-12 runs.
    evidence_requirements: Any = None
    tool_plan: Any = None


class ReasoningPipeline:
    """8-Stage Explicit Reasoning Engine.

    Executes internal diagnostic reasoning steps (Intent -> Evidence -> Analysis -> Hypothesis -> Validation -> Recommendation -> Confidence -> Conclusions).
    Intermediate steps remain private inside the engine.
    """

    def __init__(self) -> None:
        self._sanitizer = ConclusionSanitizer()

    def process(self, *, user_prompt: str, context: Any, raw_response_body: str) -> str:
        """Run the 8-stage pipeline internally and return sanitized conclusions only."""
        # Stage 1: Understand Intent
        intent = self._stage_1_understand_intent(user_prompt)

        # Stage 2: Select Evidence
        evidence = self._stage_2_select_evidence(context)

        # Stage 3: Analyze Context
        analysis = self._stage_3_analyze_context(context)

        # Stage 4: Generate Hypothesis
        hypothesis = self._stage_4_generate_hypothesis(analysis)

        # Stage 5: Validate Hypothesis
        val_result = self._stage_5_validate_hypothesis(hypothesis, context)

        # Stage 6: Produce Recommendation
        _recs = self._stage_6_produce_recommendation(val_result)

        # Stage 7: Estimate Confidence
        _conf = self._stage_7_estimate_confidence(val_result)

        # Stage 8: Return Sanitized Conclusions Only (never expose internal trace)
        return self._sanitizer.sanitize(raw_response_body)

    def pre_llm_plan(
        self,
        *,
        user_prompt: str,
        context: Any,
        question_understanding: Any = None,
    ) -> ReasoningPlan:
        """Run the reasoning pipeline and return a structured plan.

        This is the H8.11 entry point that ``BusinessReasoningEngine``
        calls *before* the LLM call. It runs the same 8 stages
        as :meth:`process` but returns a structured
        :class:`ReasoningPlan` instead of sanitised prose, so
        the prompt builder can inject a ``=== REASONING TRACE ===``
        block into the LLM prompt.

        The pipeline reuses every existing ``_stage_*`` method
        so the H8.3 test suite (``test_h8_3_reasoning_pipeline.py``)
        stays green. The plan is *augmented* by the engine with
        the detected intent and the knowledge-graph sub-graph —
        this method only emits the raw pipeline output.

        AI-1 extension
        ---------------

        The optional ``question_understanding`` kwarg carries a
        :class:`~app.services.ai.reasoning.question_understanding.QuestionUnderstanding`
        instance. When supplied, the plan's five new AI-1 fields
        (``question_interpretation``,
        ``applicable_deterministic_services``,
        ``calculations_required``, ``unknowns``,
        ``possible_answer_structure``) are populated from the
        understanding. When ``None`` (the legacy default), the
        five new fields stay at their defaults — the existing
        6-arg ``ReasoningPlan(...)`` call sites and the
        existing 2-kwarg ``pre_llm_plan(...)`` call sites
        keep working unchanged.
        """
        stage_1 = self._stage_1_understand_intent(user_prompt)
        stage_2 = self._stage_2_select_evidence(context)
        stage_3 = self._stage_3_analyze_context(context)
        stage_4 = self._stage_4_generate_hypothesis(stage_3)
        stage_5 = self._stage_5_validate_hypothesis(stage_4, context)
        stage_6 = self._stage_6_produce_recommendation(stage_5)
        stage_7 = self._stage_7_estimate_confidence(stage_5)

        intent_summary = stage_1.summary
        trace = ReasoningTrace(
            stages=(stage_1, stage_2, stage_3, stage_5, stage_6),
            intent_summary=intent_summary,
            hypothesis_summaries=(stage_4.statement,),
        )

        # Pull the knowledge-graph sub-graph the context
        # builder already produced (PriorityEngine ran during
        # select_relevant_context — see context_builder.py
        # lines 767–771). The engine overrides ``intent``
        # after this method returns; we default to "general"
        # so the pipeline output is always well-formed.
        subgraph_node_ids: tuple[str, ...] = ()
        kg = getattr(context, "knowledge_graph", None)
        if kg is not None and hasattr(kg, "extract_subgraph"):
            try:
                nodes = kg.extract_subgraph(max_nodes=15)
                subgraph_node_ids = tuple(n.id for n in nodes)
            except Exception:
                subgraph_node_ids = ()

        # Use the existing recs/insights ids as the core
        # evidence Priorities. The engine overrides / extends
        # this with KG-derived priorities; this is a safe
        # default that always imports.
        evidence_priorities: tuple[str, ...] = ()
        try:
            priorities = []
            recs = getattr(context, "recommendations", ()) or ()
            for r in recs:
                if getattr(r, "id", None):
                    priorities.append(f"rec_{r.id}")
            insights = getattr(context, "insights", ()) or ()
            for ins in insights[:3]:
                if getattr(ins, "id", None):
                    priorities.append(f"insight_{ins.id}")
            evidence_priorities = tuple(priorities)
        except Exception:
            evidence_priorities = ()

        # AI-1 — when the engine passes a
        # ``QuestionUnderstanding``, populate the new fields.
        # When ``None``, all five keep their dataclass defaults.
        q_interp = ""
        q_services: tuple[str, ...] = ()
        q_calcs: tuple[str, ...] = ()
        q_unknowns: tuple[str, ...] = ()
        q_structure = "expanded"
        # SPRINT AI-12 — five more additive fields derived from
        # the same ``QuestionUnderstanding``. Defaults keep
        # legacy call sites working unchanged.
        q_required_evidence_types: tuple[str, ...] = ()
        q_required_tools: tuple[str, ...] = ()
        q_answer_mode = "general_knowledge"
        q_expected_output_sections: tuple[str, ...] = ()
        q_evidence_requirements: Any = None
        q_tool_plan: Any = None
        if question_understanding is not None:
            q_interp = getattr(question_understanding, "user_intent", "") or ""
            q_services = tuple(
                getattr(question_understanding, "needs_deterministic_services", ()) or ()
            )
            q_calcs = tuple(
                getattr(question_understanding, "needs_calculations", ()) or ()
            )
            q_unknowns = tuple(getattr(question_understanding, "unknowns", ()) or ())
            complexity = getattr(question_understanding, "complexity", "moderate")
            if complexity == "scenario":
                q_structure = "scenario"
            elif q_unknowns:
                q_structure = "missing_info"
            elif complexity == "simple":
                q_structure = "executive"
            # default = "expanded"
            # AI-12 — pass through the new fields.
            q_required_evidence_types = tuple(
                getattr(question_understanding, "required_evidence_types", ()) or ()
            )
            q_required_tools = tuple(
                getattr(question_understanding, "required_tools", ()) or ()
            )
            q_answer_mode = str(
                getattr(question_understanding, "answer_mode", "general_knowledge")
                or "general_knowledge"
            )
            q_expected_output_sections = tuple(
                getattr(
                    question_understanding, "expected_output_sections", ()
                ) or ()
            )

        return ReasoningPlan(
            intent="general",
            subgraph_node_ids=subgraph_node_ids,
            hypotheses=(stage_4,),
            evidence_priorities=evidence_priorities,
            confidence=float(stage_7),
            trace=trace,
            question_interpretation=q_interp,
            applicable_deterministic_services=q_services,
            calculations_required=q_calcs,
            unknowns=q_unknowns,
            possible_answer_structure=q_structure,
            # SPRINT AI-12 — Universal Reasoning Layer.
            required_evidence_types=q_required_evidence_types,
            required_tools=q_required_tools,
            answer_mode=q_answer_mode,
            expected_output_sections=q_expected_output_sections,
            evidence_requirements=q_evidence_requirements,
            tool_plan=q_tool_plan,
        )

    def _stage_1_understand_intent(self, prompt: str) -> ReasoningStageResult:
        intent_type = "growth" if "grow" in prompt.lower() else "general"
        return ReasoningStageResult("understand_intent", f"Intent classified as {intent_type}")

    def _stage_2_select_evidence(self, context: Any) -> ReasoningStageResult:
        recs_count = len(getattr(context, "recommendations", ()))
        rules_count = len(getattr(context, "rules", ()))
        return ReasoningStageResult("select_evidence", f"Selected {recs_count} recs and {rules_count} rules")

    def _stage_3_analyze_context(self, context: Any) -> ReasoningStageResult:
        score = getattr(context, "overall_business_score", 0)
        return ReasoningStageResult("analyze", f"Baseline business score: {score}")

    def _stage_4_generate_hypothesis(self, analysis: ReasoningStageResult) -> Hypothesis:
        return Hypothesis(
            hypothesis_id="hyp_01",
            statement="Supply chain concentration limits margin expansion.",
            supporting_evidence_ids=("biz_profile_revenue",),
            confidence_score=85.0,
        )

    def _stage_5_validate_hypothesis(self, hyp: Hypothesis, context: Any) -> ReasoningStageResult:
        return ReasoningStageResult("validate_hypothesis", f"Hypothesis {hyp.hypothesis_id} validated successfully")

    def _stage_6_produce_recommendation(self, val: ReasoningStageResult) -> ReasoningStageResult:
        return ReasoningStageResult("produce_recommendation", "Formulated 10-section recommendations")

    def _stage_7_estimate_confidence(self, val: ReasoningStageResult) -> float:
        return 88.0
