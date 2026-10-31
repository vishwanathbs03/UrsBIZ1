"""BusinessReasoningEngine — Sprint H8.11.

Orchestrates the H8.11 pre-LLM reasoning layer. The engine
sits between :class:`AssistantContextBuilder` and
:class:`AssistantPromptBuilder` in
``AssistantProviderService.generate`` and emits a
:class:`ReasoningPlan` the prompt builder consumes.

What it does
------------

  1. **Intent Understanding** — calls the existing
     :func:`classify_intent` from
     ``app.services.ai.providers.intent_router`` to detect
     one of the six :class:`QuestionIntent` values
     (reach_revenue_target / biggest_weakness / etc.).
  2. **Sub-graph extraction** — reads
     ``context.knowledge_graph`` (the H8.2
     :class:`BusinessKnowledgeGraph` the context builder
     already populated with
     :func:`select_relevant_context`). If the graph is
     missing, the engine rebuilds it inline by running
     :class:`RelationshipEngine` and :class:`PriorityEngine`
     — same three lines ``context_builder.py:763-771`` uses.
  3. **Pipeline run** — invokes
     :meth:`ReasoningPipeline.pre_llm_plan` to get the
     structured plan, then **overrides** the plan's
     ``intent`` field with the detected intent and
     **extends** its evidence priorities with high-priority
     KG node ids.

The engine never invents data — every hypothesis, priority,
and KG node id comes from upstream sources the existing
pipelines already produced. The :class:`ReasoningPlan` it
returns is purely structural glue that the prompt builder
surfaces to the LLM.
"""
from __future__ import annotations

from typing import Any

from app.services.ai.knowledge.knowledge_graph import BusinessKnowledgeGraph
from app.services.ai.knowledge.priority_engine import PriorityEngine
from app.services.ai.knowledge.relationship_engine import RelationshipEngine
from app.services.ai.reasoning.pipeline import (
    ReasoningPipeline,
    ReasoningPlan,
)
# ``classify_intent`` is imported lazily inside :meth:`plan` to
# avoid a circular import through
# ``app.services.ai.providers.__init__`` (which eagerly loads
# :class:`AssistantProviderService`, which in turn loads this
# module). The runtime cost is negligible — the classifier is
# a pure-Python keyword scan.


# Default sub-graph size. The engine trims the full KG to
# the top-N nodes so the prompt's reasoning trace stays
# bounded. Matches the plan agent's recommendation in the
# H8.11 design.
_DEFAULT_SUBGRAPH_MAX_NODES = 15


class BusinessReasoningEngine:
    """Produce a :class:`ReasoningPlan` from a user prompt + context.

    The engine is the first H8.11 layer called inside
    ``AssistantProviderService.generate``. It is a *thin
    orchestrator*: it never recomputes a score, never re-runs
    the recommendations engine, never overrides the
    deterministic fallback body. It only chains the
    existing pieces — IntentRouter, H8.3 ReasoningPipeline,
    BusinessKnowledgeGraph / RelationshipEngine /
    PriorityEngine — into a single pre-LLM step.

    Construction
    ------------

    ``pipeline`` is injectable so tests can pass a stub or
    a pre-loaded fixture. The default is a fresh
    :class:`ReasoningPipeline`.

    ``subgraph_max_nodes`` is the cap the engine imposes on
    the KG sub-graph it returns in the plan. The default of
    15 matches the cap the prompt builder uses elsewhere.
    """

    def __init__(
        self,
        *,
        pipeline: ReasoningPipeline | None = None,
        subgraph_max_nodes: int = _DEFAULT_SUBGRAPH_MAX_NODES,
    ) -> None:
        self._pipeline = pipeline or ReasoningPipeline()
        self._subgraph_max_nodes = max(1, int(subgraph_max_nodes))

    # ---- public API -------------------------------------------------- #

    def plan(
        self,
        *,
        user_prompt: str,
        context: Any,
        question_understanding: Any = None,
    ) -> ReasoningPlan:
        """Build a :class:`ReasoningPlan` for ``user_prompt`` against ``context``.

        The plan always carries:

          * ``intent`` — the detected :class:`QuestionIntent`
            string (e.g. ``"reach_revenue_target"``).
          * ``subgraph_node_ids`` — top-K KG nodes by priority.
          * ``hypotheses`` — output of
            :meth:`ReasoningPipeline.pre_llm_plan`.
          * ``evidence_priorities`` — ``rec_*`` /
            ``insight_*`` ids from the pipeline, extended
            with any KG node id that points to an existing
            evidence entry.
          * ``confidence`` — the pipeline's confidence score.
          * ``trace`` — the structured stage trace.

        AI-1 extension
        ---------------

        The optional ``question_understanding`` kwarg lets the
        caller pass a pre-built
        :class:`~app.services.ai.reasoning.question_understanding.QuestionUnderstanding`
        (so a single instance flows through the whole service
        call). When ``None`` (the legacy default), the engine
        builds the understanding itself via
        :func:`understand_question` and threads it into the
        pipeline. The legacy 2-kwarg ``plan(user_prompt=...,
        context=...)`` call sites keep working unchanged.
        """
        # 1. Intent — deterministic keyword scan. Lazy-import
        #    to avoid the circular import through
        #    ``app.services.ai.providers.__init__``.
        from app.services.ai.providers.intent_router import classify_intent

        intent_enum = classify_intent(user_prompt or "")
        intent_value = intent_enum.value

        # 2. Sub-graph — use existing KG when present, else
        #    rebuild (mirrors context_builder.py:767-771).
        #    A ``None`` context short-circuits to an empty
        #    tuple rather than trying to read a missing KG.
        if context is None:
            subgraph_node_ids: tuple[str, ...] = ()
        else:
            subgraph_node_ids = self._extract_subgraph_ids(context)

        # AI-1 — build the question understanding if the caller
        # didn't pass one. This keeps the legacy 2-kwarg
        # ``plan(...)`` call sites working unchanged while
        # letting the service pass a single shared instance
        # through all stages (the tool selector, the prompt
        # builder, the answer composer all need the same
        # understanding).
        if question_understanding is None:
            from app.services.ai.reasoning.question_understanding import (
                understand_question,
            )
            question_understanding = understand_question(user_prompt or "", context)

        # 3. Pipeline run — returns a plan with intent
        #    defaulting to "general". We override it.
        plan = self._pipeline.pre_llm_plan(
            user_prompt=user_prompt or "",
            context=context,
            question_understanding=question_understanding,
        )

        # 4. Augment the plan with the detected intent and
        #    KG-derived evidence priorities. We use
        #    ``dataclasses.replace`` to keep the dataclass
        #    frozen.
        from dataclasses import replace

        augmented_priorities = self._augment_priorities(
            base=plan.evidence_priorities,
            context=context,
            subgraph_ids=subgraph_node_ids,
        )

        return replace(
            plan,
            intent=intent_value,
            subgraph_node_ids=subgraph_node_ids,
            evidence_priorities=augmented_priorities,
        )

    # ---- internal helpers ------------------------------------------- #

    def _extract_subgraph_ids(self, context: Any) -> tuple[str, ...]:
        """Return the top-K KG node ids relevant to the context.

        If ``context.knowledge_graph`` is set, the engine
        trusts it (the context builder already ran the
        PriorityEngine). If absent, the engine rebuilds the
        KG from the context — this happens in tests that
        build a context without going through the context
        builder.
        """
        kg = getattr(context, "knowledge_graph", None)
        if kg is None:
            try:
                kg = BusinessKnowledgeGraph.from_context(context)
            except Exception:
                return ()
            try:
                RelationshipEngine().infer_and_link_relationships(kg)
            except Exception:
                pass
            try:
                PriorityEngine().score_nodes(kg)
            except Exception:
                pass

        if kg is None or not hasattr(kg, "extract_subgraph"):
            return ()
        try:
            nodes = kg.extract_subgraph(max_nodes=self._subgraph_max_nodes)
            return tuple(n.id for n in nodes)
        except Exception:
            return ()

    @staticmethod
    def _augment_priorities(
        *,
        base: tuple[str, ...],
        context: Any,
        subgraph_ids: tuple[str, ...],
    ) -> tuple[str, ...]:
        """Extend ``base`` with KG-derived evidence ids.

        Many KG nodes carry an ``evidence_id`` that maps
        onto an :class:`EvidenceRegistry` entry. The engine
        appends those ids to the plan's evidence priorities
        so the retriever can boost them. De-duplicated and
        order-preserved.
        """
        if not subgraph_ids:
            return base
        kg = getattr(context, "knowledge_graph", None)
        if kg is None or not hasattr(kg, "get_node"):
            return base
        seen = set(base)
        out = list(base)
        for nid in subgraph_ids:
            try:
                node = kg.get_node(nid)
            except Exception:
                continue
            if node is None:
                continue
            evid = getattr(node, "evidence_id", None)
            if evid and evid not in seen:
                seen.add(evid)
                out.append(evid)
        return tuple(out)