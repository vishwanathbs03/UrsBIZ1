"""ConversationService — Sprint 7 Part 3.

The service composes the chat persistence layer with the
Sprint 7 Part 2 AI provider layer:

    ChatSessionRepository     <— storage
            ^
            |
    ConversationService       <— this file
            |
            v
    AssistantProviderService   <— Sprint 7 Part 2
    AssistantContextBuilder    <— Sprint 7 Part 2

The service owns three pieces of *session-level* state:

  * **Rolling context** — the last N turns fed back into the
    assistant provider as the ``history`` field of the
    request. N is small (default 8) so the prompt stays
    bounded.
  * **Conversation summary** — a short deterministic string
    rebuilt every time a new message is appended. Capped at
    500 chars so the sidebar can render it without joining
    ``chat_messages``. The summary is *derived from the
    existing assistant context* (Twin + Recommendations +
    Roadmap + Rules + Insights) — no new business logic.
  * **Title** — auto-derived from the first user message
    ("First 80 chars of 'How can I improve my business?'")
    when the caller does not pass an explicit one.

What this service is NOT
------------------------

  * It does NOT re-implement intent classification. The
    ``kind`` field on the message is whatever the caller
    classifies — the assistant provider does not require a
    kind to answer.
  * It does NOT store vector embeddings. RAG and semantic
    search are out of scope.
  * It does NOT modify the Business Digital Twin. The
    session is a user-level artefact.
  * It does NOT modify the assistant provider's
    response shape. The provider already returns a
    deterministic body + sources + model + fallback_used;
    the service persists them verbatim.

Determinism contract
--------------------

When the configured provider is the deterministic fallback
(default), two appends of the same user message to the same
session produce the same assistant body (sans the
``generated_at`` / ``updated_at`` timestamps). When Ollama
is configured and reachable, the assistant body is whatever
the model returns — non-deterministic by construction.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Sequence

from app.repositories.chat_session_repository import (
    ChatSessionNotFound,
    ChatSessionRepository,
)
from app.services.ai.providers.base import (
    AssistantContext,
    AssistantTurn,
    GenerationMeta,
    ProviderUnavailableError,
    ProviderTimeoutError,
)
from app.services.ai.providers.context_builder import AssistantContextBuilder
from app.services.ai.providers.factory import ProviderFactory
from app.services.ai.providers.intent_router import (
    QuestionIntent,
    classify_intent,
)
from app.services.ai.providers.ollama import OllamaProvider
from app.services.ai.providers.service import AssistantProviderService
from app.services.ai.simulation.analysis import ScenarioAnalyzer
from app.services.knowledge_retrieval.service import KnowledgeRetrievalService

# SPRINT AI-7 — missing-data intelligence. The detector runs
# BEFORE the provider call (step 3.7) and the enrichment pass
# runs AFTER (step 5.8). The wire mirror in ``_message_payload``
# carries the resulting tuple to the frontend ``MissingInfoCard``.
from app.services.ai.missing_data import (
    MissingDataObject,
    detect_missing_data,
    enrich_missing_data_from_prose,
    to_payload as missing_data_to_payload,
)


# SPRINT AI-12 — Universal Reasoning Layer. Three new
# deterministic gates the orchestrator runs between the
# question understanding and the LLM call (step 3.9) and
# between the tool dispatch and the LLM call (step 4.5)
# and after the LLM call (step 5.5b). All three are
# pure-function over ``context`` + ``question_understanding``
# + the dispatcher outcome — no LLM access, no I/O.
from app.services.ai.reasoning.answer_quality_validator import (
    AnswerQualityValidator,
)
from app.services.ai.reasoning.contradiction_detector import (
    CrossSourceContradictionDetector,
)
from app.services.ai.reasoning.evidence_requirements import (
    plan as plan_evidence_requirements,
)
from app.services.ai.reasoning.minimal_slice import select_minimal_slice
from app.services.ai.reasoning.question_understanding import understand_question
from app.services.ai.reasoning.tool_selector import (
    ToolDispatcher,
    ToolPlan,
)


# Default number of recent turns replayed into the
# provider's history. Keep small so the prompt stays
# bounded; raise in a later milestone if needed.
_ROLLING_CONTEXT_TURNS = 8


# Summary cap. Matches the column width on chat_sessions.
_SUMMARY_CAP = 480

# Title cap. Matches the column width on chat_sessions.
_TITLE_CAP = 80


@dataclass(frozen=True)
class AppendResult:
    """The result of an append-message call.

    The service returns this envelope so the endpoint can
    render both messages + a refreshed session detail in a
    single Pydantic response.
    """

    user_message: dict
    assistant_message: dict
    session: dict


class ConversationService:
    """The façade the chat endpoint depends on."""

    def __init__(
        self,
        repo: ChatSessionRepository,
        *,
        assistant_service: AssistantProviderService | None = None,
        rolling_context_turns: int = _ROLLING_CONTEXT_TURNS,
        knowledge_retriever: KnowledgeRetrievalService | None = None,
        scenario_analyzer: ScenarioAnalyzer | None = None,
    ) -> None:
        self._repo = repo
        self._assistant = assistant_service or self._default_assistant_service()
        self._rolling_context_turns = max(0, int(rolling_context_turns))
        # Optional Sprint 7 Part 4 retrieval layer. When None
        # the chat service is identical to Part 3 — no
        # retrieval, no citations.
        self._knowledge = knowledge_retriever
        # Sprint AI-5 — Business Scenario Copilot. The analyzer
        # is pure (no I/O, no LLM call). When None, a default
        # instance is used so callers don't have to wire one.
        self._scenario_analyzer = scenario_analyzer or ScenarioAnalyzer()

    # ---- CRUD -------------------------------------------------------- #

    def list_sessions(self, *, owner_id: int) -> list[dict]:
        sessions = self._repo.list_sessions(owner_id=owner_id)
        return [_session_summary(s) for s in sessions]

    def get_session(self, *, owner_id: int, session_id: int) -> dict:
        session = self._repo.get_session(owner_id=owner_id, session_id=session_id)
        if session is None:
            raise ChatSessionNotFound(
                f"Session {session_id} not found for owner {owner_id}"
            )
        return _session_detail(session)

    def create_session(
        self, *, owner_id: int, title: str = ""
    ) -> dict:
        session = self._repo.create_session(owner_id=owner_id, title=title)
        return _session_detail(session)

    def delete_session(self, *, owner_id: int, session_id: int) -> bool:
        deleted = self._repo.delete_session(
            owner_id=owner_id, session_id=session_id
        )
        if not deleted:
            raise ChatSessionNotFound(
                f"Session {session_id} not found for owner {owner_id}"
            )
        return True

    def append_message(
        self,
        *,
        owner_id: int,
        session_id: int,
        content: str,
        mode: str = "grounded",
        language: str = "en",
    ) -> AppendResult:
        """Append a user message + the assistant's reply.

        1. Load the session (404 if not found).
        2. Insert the user message.
        3. Compose the rolling context from the last N turns.
        4. Build the AssistantContext via the existing
           Part 2 context builder.
        5. Call the AssistantProviderService.
        6. Insert the assistant message.
        7. Refresh the session title / summary / last_model /
           fallback_used / message_count.

        ``mode`` (H7.8C) selects the hybrid assistant mode.
        ``"grounded"`` is the default — evidence-bounded.
        ``"open"`` is the permissive general-purpose mode.
        The mode is forwarded to the provider so the prompt
        builder, grounding validator, and response schema all
        line up.
        """
        session = self._repo.get_session(owner_id=owner_id, session_id=session_id)
        if session is None:
            raise ChatSessionNotFound(
                f"Session {session_id} not found for owner {owner_id}"
            )

        # 1. Insert the user message.
        user_msg = self._repo.add_message(
            session=session,
            role="user",
            content=content,
            kind="",
        )

        # 2. Compose rolling history. Use every existing
        #    message *before* the user message we just added.
        history = self._build_history(session, exclude_message_id=user_msg.id)

        # 3. Build the assistant context via Part 2.
        context = self._assistant.build_context(owner_id=owner_id)

        # 3.5. Sprint AI-5 — Business Scenario Copilot.
        scenario_envelope = self._maybe_build_scenario_analysis(
            context=context, prompt=content
        )

        # 3.7. Sprint AI-7 — Missing Data Intelligence.
        try:
            detected_intent = classify_intent(content)
        except Exception:  # pragma: no cover — defensive
            detected_intent = QuestionIntent.GENERAL
        try:
            proactive_rows = detect_missing_data(context, detected_intent)
        except Exception:  # pragma: no cover — defensive
            proactive_rows = ()

        # 3.9. SPRINT AI-12 — Evidence Requirement Planner.
        try:
            qu = understand_question(content, context)
            evidence_requirements = plan_evidence_requirements(qu)
        except Exception:  # pragma: no cover — defensive
            evidence_requirements = None

        # 4. Sprint 7 Part 4 — retrieve, rank, build citations.
        knowledge_ctx = None
        if self._knowledge is not None:
            owner_context = self._build_owner_context(context)
            knowledge_ctx = self._knowledge.retrieve(
                query=content,
                owner_context=owner_context,
            )

        # 5. Call the provider.
        assistant_resp = self._assistant.generate(
            owner_id=owner_id,
            user_prompt=content,
            history=history,
            knowledge=knowledge_ctx,
            mode=mode,
            context=context,
            language=language,
        )

        # SPRINT AI-12 — stamp the step-3.9 evidence
        # requirements onto the GenerationMeta now that it
        # exists. ``evidence_requirements`` may be ``None``
        # when the planner raised (the helper no-ops).
        self._stamp_evidence_requirements(
            assistant_resp=assistant_resp,
            evidence_requirements=evidence_requirements,
        )

        # 5.5. Sprint AI-5 — stamp the scenario envelope onto
        #      the provider's GenerationMeta (or create one when
        #      the legacy mock-provider path returned None).
        #      The envelope is always a dict so the wire projection
        #      can carry it verbatim. When the prompt was not a
        #      scenario question, ``scenario_envelope`` is None and
        #      we leave the GenerationMeta untouched.
        if scenario_envelope is not None:
            self._stamp_scenario_analysis(
                assistant_resp=assistant_resp, envelope=scenario_envelope
            )

        # 5.7. Sprint AI-6 — Trust-first visual UI. Stamp the
        #      "Direct Answer" 1-3 sentence extraction onto the
        #      GenerationMeta so the frontend can render the
        #      10-second-read header. The extraction is a pure
        #      function over ``assistant_resp.body``; it never
        #      raises. When the body is empty / non-string /
        #      sentence-less, the function returns None and the
        #      wire mirror is also None (the frontend projector
        #      falls back to ``consultant.body`` / ``content``).
        direct_answer = _extract_direct_answer(
            getattr(assistant_resp, "body", None)
        )
        if direct_answer is not None:
            self._stamp_direct_answer(
                assistant_resp=assistant_resp, direct_answer=direct_answer
            )

        # 5.8. Sprint AI-7 — Missing Data Intelligence. Enrich
        #      the proactive rows with anything the LLM prose
        #      surfaced (reactive harvest), then stamp the
        #      combined tuple onto the GenerationMeta. The
        #      enrichment is a pure regex-based scan; it never
        #      raises and dedupes against the proactive list.
        #      The deterministic fallback keeps only the
        #      proactive list (the LLM wasn't called).
        if proactive_rows:
            try:
                prose = getattr(assistant_resp, "body", None) or ""
                enriched_rows = enrich_missing_data_from_prose(
                    prose, proactive_rows
                )
            except Exception:  # pragma: no cover — defensive
                enriched_rows = proactive_rows
            self._stamp_missing_data(
                assistant_resp=assistant_resp,
                missing_data=enriched_rows,
            )

        # SPRINT AI-8 — step 5.10 — stamp the validated
        # tool-loop results (if any) onto ``GenerationMeta``.
        # The router already sanitised each entry through
        # ``strip_leaked_secrets`` (no leaked secrets survive),
        # so the stamper is just a verbatim copy. Empty tuple
        # when no tool calls were requested (the legacy / non-
        # router-wired paths, plus any future flow that
        # disables AI-8).
        try:
            existing_results = tuple(
                getattr(
                    getattr(assistant_resp, "generation", None),
                    "llm_tool_results",
                    (),
                )
                or ()
            )
            self._stamp_llm_tool_results(
                assistant_resp=assistant_resp,
                llm_tool_results=existing_results,
            )
        except Exception:  # pragma: no cover — defensive
            pass

        # SPRINT AI-10 — step 5.11 — Explain My Answer. Build
        #      a DecisionTrace for every recommendation in the
        #      turn and stamp the dict on ``GenerationMeta.explanation``.
        #      The builder is a pure function over the
        #      ``Recommendation`` payload + ``EvidenceRegistry``;
        #      no LLM is involved. When the builder raises or the
        #      upstream ``Recommendation`` list is empty, the trace
        #      is silently dropped (the panel hides itself). Never
        #      raises — a failure here would crash the chat
        #      endpoint for an audit-only field.
        try:
            # The EvidenceRegistry isn't passed through to the
            # chat service today — the service layer doesn't
            # expose it. The trace builder degrades gracefully
            # when ``registry`` is None (the Evidence section
            # becomes empty; Calculations, Decision factors,
            # Assumptions, Uncertainty still populate from the
            # rec payload). A future sprint that threads the
            # registry through can pass it here without changing
            # the trace dataclass shape.
            self._stamp_explanation(
                assistant_resp=assistant_resp,
                context_snapshot=context,
            )
        except Exception:  # pragma: no cover — defensive
            pass

        # SPRINT AI-12 — step 5.12 — AnswerQualityValidator.
        # Score the LLM response on 8 quality axes. When the
        # total score falls below 5.5, ``needs_retry`` is True;
        # the conversation service does NOT loop because the
        # 15s hard timeout caps the total request budget. The
        # validator result is stamped on ``GenerationMeta``
        # for the audit trail so the frontend trust disclosure
        # can render the per-axis breakdown. Never raises.
        try:
            self._stamp_answer_quality(
                assistant_resp=assistant_resp,
                body=getattr(assistant_resp, "body", None) or "",
            )
        except Exception:  # pragma: no cover — defensive
            pass

        # 6. Persist the assistant reply. Sources are the
        #    union of the provider's own sources and the
        #    knowledge retrieval's citations. The chat
        #    schema is the same either way.
        provider_sources = _sources_to_payload(
            getattr(assistant_resp, "sources", ()) or ()
        )
        citation_sources = (
            _citations_to_sources(knowledge_ctx)
            if knowledge_ctx is not None else []
        )
        sources = provider_sources + citation_sources
        # H7.8C — serialise the GenerationMeta into the
        # per-message ``generation_meta_json`` column so the
        # frontend can render the provenance disclosure on
        # refresh (the trust label persists across reloads).
        generation_payload = _generation_meta_to_payload(
            getattr(assistant_resp, "generation", None)
        )
        assistant_msg = self._repo.add_message(
            session=session,
            role="assistant",
            content=assistant_resp.body,
            kind="",
            sources=sources,
            # H7.8A P2 — persist the per-message fallback flag so the
            # frontend MessageBubble can render the right trust label.
            # ``assistant_resp.fallback_used`` is True when the
            # deterministic placeholder / safe provider answered, False
            # when a real OpenAI-compatible or Ollama response was
            # produced.
            fallback_used=assistant_resp.fallback_used,
            # H7.8C — provenance envelope persists on the message
            # row. The frontend re-reads it after page reload so the
            # "Generated by ollama:llama3.1" disclosure is stable.
            generation_meta=generation_payload,
        )

        # 6. Refresh the session meta. Only auto-derive
        #    the title from the first user message when
        #    the caller did not pass one — otherwise the
        #    caller's explicit title is preserved verbatim
        #    across every subsequent append.
        new_count = len(self._repo.get_messages(session=session))
        title = session.title or _derive_title(content)
        summary = _derive_summary(
            session_summary=session.summary,
            context=context,
            latest_user=content,
            latest_assistant=assistant_resp.body,
        )
        self._repo.touch_session(
            session=session,
            title=title,
            summary=summary,
            last_model=assistant_resp.model,
            fallback_used=assistant_resp.fallback_used,
            message_count=new_count,
        )

        return AppendResult(
            user_message=_message_payload(user_msg),
            assistant_message=_message_payload(assistant_msg),
            session=_session_detail(session),
        )

    # ---- internals --------------------------------------------------- #

    def _maybe_build_scenario_analysis(
        self,
        *,
        context: AssistantContext | None,
        prompt: str,
    ) -> dict | None:
        """AI-5 — return a scenario-envelope dict for "what if" prompts.

        Returns ``None`` when the prompt is not a scenario question
        (the LLM route runs unchanged) or when the analyzer raises
        (defensive — never crashes the chat endpoint).

        The returned dict is exactly the
        :meth:`ScenarioAnalysis.to_dict` shape (10 fields + the
        ``present`` helper flag) so the wire projection can
        serialise it verbatim.
        """
        try:
            analyzer = self._scenario_analyzer
            if analyzer is None:
                return None
            # Context can be None on the legacy mock-provider path.
            # The analyzer will fall back to defaults / missing_data
            # in that case.
            envelope = analyzer.analyze(prompt, context)
            if envelope is None:
                return None
            return envelope.to_dict()
        except Exception:  # pragma: no cover — defensive
            return None

    def _stamp_scenario_analysis(
        self,
        *,
        assistant_resp: Any,
        envelope: dict,
    ) -> None:
        """AI-5 — stamp the envelope onto ``assistant_resp.generation``.

        The provider's :class:`AssistantResponse` is a frozen dataclass
        so we use ``object.__setattr__`` to mutate the nested
        ``generation`` (also frozen) in place. The original
        GenerationMeta is replaced when ``generation`` is None
        (legacy mock-provider path).
        """
        try:
            gen = getattr(assistant_resp, "generation", None)
            if gen is None:
                # Legacy path — materialise a minimal GenerationMeta
                # just so the envelope has somewhere to live. Provider
                # / model / fallback_used are taken from the response.
                gen = GenerationMeta.empty(
                    mode="grounded",
                    provider_used=getattr(assistant_resp, "provider_used", ""),
                    model=getattr(assistant_resp, "model", ""),
                    provider_latency_ms=getattr(
                        assistant_resp, "provider_latency_ms", None
                    ),
                    fallback_used=bool(
                        getattr(assistant_resp, "fallback_used", False)
                    ),
                    scenario_analysis=envelope,
                )
                object.__setattr__(assistant_resp, "generation", gen)
                return
            # Re-build via dataclasses.replace so the frozen contract
            # holds for the rest of the response.
            from dataclasses import replace
            new_gen = replace(gen, scenario_analysis=envelope)
            object.__setattr__(assistant_resp, "generation", new_gen)
        except Exception:  # pragma: no cover — defensive
            return

    def _stamp_direct_answer(
        self,
        *,
        assistant_resp: Any,
        direct_answer: str,
    ) -> None:
        """AI-6 — stamp the Direct Answer string onto GenerationMeta.

        Same defensive pattern as ``_stamp_scenario_analysis``:
        create a minimal GenerationMeta when the legacy mock-provider
        path returned None, otherwise rebuild via
        ``dataclasses.replace`` to preserve the frozen contract.
        Never raises — a failure here would crash the chat endpoint
        for a UI-only field, which is unacceptable.
        """
        try:
            gen = getattr(assistant_resp, "generation", None)
            if gen is None:
                gen = GenerationMeta.empty(
                    mode="grounded",
                    provider_used=getattr(assistant_resp, "provider_used", ""),
                    model=getattr(assistant_resp, "model", ""),
                    provider_latency_ms=getattr(
                        assistant_resp, "provider_latency_ms", None
                    ),
                    fallback_used=bool(
                        getattr(assistant_resp, "fallback_used", False)
                    ),
                    direct_answer=direct_answer,
                )
                object.__setattr__(assistant_resp, "generation", gen)
                return
            from dataclasses import replace
            new_gen = replace(gen, direct_answer=direct_answer)
            object.__setattr__(assistant_resp, "generation", new_gen)
        except Exception:  # pragma: no cover — defensive
            return

    def _stamp_missing_data(
        self,
        *,
        assistant_resp: Any,
        missing_data: tuple[MissingDataObject, ...],
    ) -> None:
        """AI-7 — stamp the structured ``MissingDataObject`` rows onto GenerationMeta.

        Same defensive pattern as ``_stamp_scenario_analysis`` and
        ``_stamp_direct_answer``: when the legacy mock-provider
        path returned a None generation, build a minimal
        GenerationMeta just so the rows have somewhere to live;
        otherwise rebuild via ``dataclasses.replace`` to preserve
        the frozen contract. The rows are serialised to plain
        dicts before stamping so the dataclass tuple field
        ``missing_data`` carries JSON-safe content — the
        ``generation_meta_json`` column will write them back as a
        list of dicts at persistence time.

        Never raises — a failure here would crash the chat
        endpoint for a UI-only field, which is unacceptable.
        """
        try:
            payload = missing_data_to_payload(missing_data)
            gen = getattr(assistant_resp, "generation", None)
            if gen is None:
                gen = GenerationMeta.empty(
                    mode="grounded",
                    provider_used=getattr(assistant_resp, "provider_used", ""),
                    model=getattr(assistant_resp, "model", ""),
                    provider_latency_ms=getattr(
                        assistant_resp, "provider_latency_ms", None
                    ),
                    fallback_used=bool(
                        getattr(assistant_resp, "fallback_used", False)
                    ),
                    missing_data=tuple(payload),
                )
                object.__setattr__(assistant_resp, "generation", gen)
                return
            new_gen = replace(gen, missing_data=tuple(payload))
            object.__setattr__(assistant_resp, "generation", new_gen)
        except Exception:  # pragma: no cover — defensive
            return

    def _stamp_llm_tool_results(
        self,
        *,
        assistant_resp: Any,
        llm_tool_results: tuple[dict, ...] = (),
    ) -> None:
        """SPRINT AI-8 — stamp the validated tool-loop results onto
        ``GenerationMeta.llm_tool_results``.

        Mirrors the ``_stamp_missing_data`` defensive pattern:
        when the legacy mock-provider path returned a ``None``
        generation, build a minimal ``GenerationMeta`` so the
        field has somewhere to live; otherwise rebuild via
        ``dataclasses.replace`` to preserve the frozen contract.

        The router already sanitised each entry (no leaked
        secrets) — the stamper just preserves the existing
        dict shape and copies it verbatim onto the meta tuple.

        Never raises — a failure here would crash the chat
        endpoint for an audit-only field, which is unacceptable.
        """
        try:
            payload = tuple(
                dict(item) if isinstance(item, dict) else {}
                for item in (llm_tool_results or ())
            )
            gen = getattr(assistant_resp, "generation", None)
            if gen is None:
                gen = GenerationMeta.empty(
                    mode="grounded",
                    provider_used=getattr(assistant_resp, "provider_used", ""),
                    model=getattr(assistant_resp, "model", ""),
                    provider_latency_ms=getattr(
                        assistant_resp, "provider_latency_ms", None
                    ),
                    fallback_used=bool(
                        getattr(assistant_resp, "fallback_used", False)
                    ),
                    llm_tool_results=payload,
                )
                object.__setattr__(assistant_resp, "generation", gen)
                return
            new_gen = replace(gen, llm_tool_results=payload)
            object.__setattr__(assistant_resp, "generation", new_gen)
        except Exception:  # pragma: no cover — defensive
            return

    def _stamp_explanation(
        self,
        *,
        assistant_resp: Any,
        context_snapshot: Any = None,
        registry: Any = None,
    ) -> None:
        """SPRINT AI-10 — Explain My Answer. Build a
        :class:`DecisionTrace` per recommendation and stamp the
        resulting dict on ``GenerationMeta.explanation``.

        The builder is a pure function over
        ``Recommendation`` payload dicts + ``EvidenceRegistry``;
        no LLM is involved. The trace is keyed by
        ``recommendation_id`` so the frontend can look up the
        right trace without iterating the dict.

        Defensive pattern mirrors ``_stamp_missing_data``:
        when the legacy mock-provider path returned a ``None``
        generation, build a minimal ``GenerationMeta`` so the
        field has somewhere to live; otherwise rebuild via
        ``dataclasses.replace`` to preserve the frozen contract.

        Never raises — a failure here would crash the chat
        endpoint for an audit-only field, which is unacceptable.
        """
        try:
            from app.services.ai.trace import build_trace

            rec_payloads = self._collect_recommendation_payloads(
                assistant_resp=assistant_resp,
                context_snapshot=context_snapshot,
            )
            if not rec_payloads:
                return

            all_payloads = tuple(rec_payloads)
            trace_dict: dict[str, dict] = {}
            for rec_payload in all_payloads:
                rec_id = str(rec_payload.get("id", "") or "")
                if not rec_id:
                    continue
                trace = build_trace(
                    rec_payload,
                    ctx=context_snapshot,
                    registry=registry,
                    all_recs=all_payloads,
                )
                if not trace.is_empty():
                    trace_dict[rec_id] = trace.to_dict()

            if not trace_dict:
                return

            gen = getattr(assistant_resp, "generation", None)
            if gen is None:
                gen = GenerationMeta.empty(
                    mode="grounded",
                    provider_used=getattr(assistant_resp, "provider_used", ""),
                    model=getattr(assistant_resp, "model", ""),
                    provider_latency_ms=getattr(
                        assistant_resp, "provider_latency_ms", None
                    ),
                    fallback_used=bool(
                        getattr(assistant_resp, "fallback_used", False)
                    ),
                    explanation=trace_dict,
                )
                object.__setattr__(assistant_resp, "generation", gen)
                return
            new_gen = replace(gen, explanation=trace_dict)
            object.__setattr__(assistant_resp, "generation", new_gen)
        except Exception:  # pragma: no cover — defensive
            return

    # ------------------------------------------------------------------ #
    # SPRINT AI-12 — Universal Reasoning Layer stamping helpers.
    # ------------------------------------------------------------------ #
    # Three additive gates plus three audit-trail stampers. All
    # follow the same defensive pattern as the legacy
    # :meth:`_stamp_explanation` /
    # :meth:`_stamp_missing_data` helpers: when the legacy
    # mock-provider path returned a ``None`` generation, build a
    # minimal ``GenerationMeta`` so the field has somewhere to
    # live; otherwise rebuild via ``dataclasses.replace`` to
    # preserve the frozen contract. Never raises.

    def _stamp_evidence_requirements(
        self,
        *,
        assistant_resp: Any,
        evidence_requirements: Any,
    ) -> None:
        """SPRINT AI-12 — step 3.9. Stamp the
        :class:`EvidenceRequirements` the planner produced on
        ``GenerationMeta.evidence_requirements``."""
        try:
            if evidence_requirements is None:
                return
            payload = _safe_to_dict(evidence_requirements)
            if payload is None:
                return
            gen = getattr(assistant_resp, "generation", None)
            if gen is None:
                gen = GenerationMeta.empty(
                    mode="grounded",
                    provider_used=getattr(assistant_resp, "provider_used", ""),
                    model=getattr(assistant_resp, "model", ""),
                    provider_latency_ms=getattr(
                        assistant_resp, "provider_latency_ms", None
                    ),
                    fallback_used=bool(
                        getattr(assistant_resp, "fallback_used", False)
                    ),
                    evidence_requirements=payload,
                )
                object.__setattr__(assistant_resp, "generation", gen)
                return
            new_gen = replace(gen, evidence_requirements=payload)
            object.__setattr__(assistant_resp, "generation", new_gen)
        except Exception:  # pragma: no cover — defensive
            return

    def _stamp_contradiction_report(
        self,
        *,
        assistant_resp: Any,
        context_snapshot: Any,
        envelopes: tuple = (),
    ) -> None:
        """SPRINT AI-12 — step 4.5. Run the
        :class:`CrossSourceContradictionDetector` and stamp the
        resulting report on ``GenerationMeta.contradiction_report``.

        On ``severity == "high"`` the prompt is augmented with a
        ``CONTRADICTIONS:`` disclosure block — but the caller
        just stamps the audit row; the prompt-side augmentation
        is the responsibility of the prompt builder.
        """
        try:
            detector = CrossSourceContradictionDetector()
            report = detector.detect(context_snapshot, envelopes)
            payload = _safe_to_dict(report)
            if payload is None:
                return
            gen = getattr(assistant_resp, "generation", None)
            if gen is None:
                gen = GenerationMeta.empty(
                    mode="grounded",
                    provider_used=getattr(assistant_resp, "provider_used", ""),
                    model=getattr(assistant_resp, "model", ""),
                    provider_latency_ms=getattr(
                        assistant_resp, "provider_latency_ms", None
                    ),
                    fallback_used=bool(
                        getattr(assistant_resp, "fallback_used", False)
                    ),
                    contradiction_report=payload,
                )
                object.__setattr__(assistant_resp, "generation", gen)
                return
            new_gen = replace(gen, contradiction_report=payload)
            object.__setattr__(assistant_resp, "generation", new_gen)
        except Exception:  # pragma: no cover — defensive
            return

    def _stamp_answer_quality(
        self,
        *,
        assistant_resp: Any,
        body: str,
    ) -> None:
        """SPRINT AI-12 — step 5.5b. Score the assistant reply on
        the 8 quality axes and stamp the result on
        ``GenerationMeta.answer_quality``.
        """
        try:
            validator = AnswerQualityValidator()
            quality = validator.validate(body)
            payload = _safe_to_dict(quality)
            if payload is None:
                return
            gen = getattr(assistant_resp, "generation", None)
            if gen is None:
                gen = GenerationMeta.empty(
                    mode="grounded",
                    provider_used=getattr(assistant_resp, "provider_used", ""),
                    model=getattr(assistant_resp, "model", ""),
                    provider_latency_ms=getattr(
                        assistant_resp, "provider_latency_ms", None
                    ),
                    fallback_used=bool(
                        getattr(assistant_resp, "fallback_used", False)
                    ),
                    answer_quality=payload,
                )
                object.__setattr__(assistant_resp, "generation", gen)
                return
            new_gen = replace(gen, answer_quality=payload)
            object.__setattr__(assistant_resp, "generation", new_gen)
        except Exception:  # pragma: no cover — defensive
            return

    def _stamp_answer_evidence(
        self,
        *,
        assistant_resp: Any,
        question_understanding: Any | None,
        reasoning_plan: Any | None,
        envelopes: tuple = (),
        contradiction_report: Any | None = None,
        parsed_response: Any | None = None,
        context_snapshot: Any | None = None,
    ) -> None:
        """SPRINT AI-14 — defensive envelope stamper.

        Runs AFTER ``_stamp_answer_quality`` and BEFORE
        ``_message_payload`` so the wire envelope carries the
        AI-14 fields even when the provider layer was bypassed
        (legacy callers that pre-date the service.py hookups).
        Each derivation is a pure function — same inputs always
        return the same dict. Failures are silently swallowed so
        the chat path stays non-breaking.

        SPRINT AI-15 — also stamps the visualization + trust
        envelope when the service layer did not run the AI-15
        hookup.
        """
        try:
            from app.services.ai.reasoning.answer_requirements import (
                derive_answer_requirements,
            )
            from app.services.ai.reasoning.evidence_graph import (
                build_evidence_graph,
            )
            from app.services.ai.reasoning.calculation_lineage import (
                calculation_lineage_dicts,
                missing_data_state,
                unsupported_claims as _unsupported_claims,
                fabricated_sources as _fabricated_sources,
            )
            # SPRINT AI-15 — visualization + trust imports.
            from app.services.ai.reasoning.visualization_planner import (
                plan as _viz_plan,
            )
            from app.services.ai.reasoning.chart_data_builder import (
                build as _viz_build,
            )
            from app.services.ai.reasoning.trust_summary import (
                build_trust_summary as _build_trust,
            )
            gen = getattr(assistant_resp, "generation", None)
            ctx = context_snapshot
            envelopes_t = tuple(envelopes or ())
            answer_req = derive_answer_requirements(
                question_understanding=question_understanding,
                evidence_requirements=None,
                tool_plan=reasoning_plan,
                envelopes=envelopes_t,
                context=ctx,
            )
            graph = build_evidence_graph(
                question_understanding=question_understanding,
                reasoning_plan=reasoning_plan,
                envelopes=envelopes_t,
                context=ctx,
                contradiction_report=contradiction_report,
                parsed_response=parsed_response,
            )
            lineage = calculation_lineage_dicts(envelopes_t)
            missing = missing_data_state(graph=graph, proactive_rows=())
            unsupported = len(_unsupported_claims(graph))
            fabricated = len(_fabricated_sources(graph))
            # SPRINT AI-15 — visualization + trust envelope.
            ai15_plans = _viz_plan(
                question_understanding=question_understanding,
                answer_requirements=answer_req,
                envelopes=envelopes_t,
                evidence_graph=graph,
                contradiction_report=contradiction_report,
            ).plans
            ai15_payloads = [
                _viz_build(p, envelopes=envelopes_t).to_dict()
                for p in ai15_plans
            ]
            existing_quality = (
                gen.answer_quality if gen is not None else None
            )
            if not isinstance(existing_quality, dict):
                existing_quality = None
            ai15_trust = _build_trust(
                assistant_context=ctx,
                envelopes=envelopes_t,
                evidence_graph=graph,
                contradiction_report=contradiction_report,
                answer_quality=existing_quality,
                visualization_plans=ai15_plans,
                tool_traces=(),
            )
            ai15_quality_warning = {
                "needs_warning": bool(
                    (existing_quality or {}).get("needs_warning")
                ),
                "warning_message": str(
                    (existing_quality or {}).get("warning_message") or ""
                ),
            }
            if gen is None:
                gen = GenerationMeta.empty(
                    mode="grounded",
                    provider_used=getattr(assistant_resp, "provider_used", ""),
                    model=getattr(assistant_resp, "model", ""),
                    provider_latency_ms=getattr(
                        assistant_resp, "provider_latency_ms", None
                    ),
                    fallback_used=bool(
                        getattr(assistant_resp, "fallback_used", False)
                    ),
                    answer_requirements=answer_req.to_dict(),
                    evidence_graph=graph.to_dict(),
                    calculation_lineage=lineage,
                    missing_data_state=missing,
                    unsupported_claim_count=unsupported,
                    fabricated_source_count=fabricated,
                    # SPRINT AI-15 — visualization + trust.
                    visualization_plans=ai15_payloads,
                    quality_warning=ai15_quality_warning,
                    trust_summary=ai15_trust,
                )
                # SPRINT AI-16 — scheme card + mixed composition.
                # Both pure; failures swallowed defensively so
                # the AI-15 path stays non-breaking. We stamp the
                # fields onto the empty meta directly.
                try:
                    from app.services.ai.knowledge.ai16_scheme_composer import (
                        compose_scheme_card as _ai16_scheme,
                    )
                    from app.services.ai.knowledge.ai16_mixed_composer import (
                        compose_mixed_sections as _ai16_mixed,
                    )
                    scheme_payload = _ai16_scheme(
                        question_understanding=question_understanding,
                        context=ctx,
                    )
                    if scheme_payload is not None:
                        object.__setattr__(
                            gen,
                            "scheme_card",
                            scheme_payload.card.to_dict(),
                        )
                    mixed_blocks = _ai16_mixed(
                        question_understanding=question_understanding,
                        envelopes=envelopes_t,
                        context=ctx,
                    )
                    if mixed_blocks.is_mixed:
                        object.__setattr__(
                            gen,
                            "mixed_answer",
                            mixed_blocks.to_dict(),
                        )
                except Exception:  # pragma: no cover — defensive
                    pass
                # SPRINT AI-17 — Bounded Quality Repair + Claim
                # Lifecycle. The classifier + repair dispatcher
                # + bounded-retry gate run AFTER the AI-16
                # stamp and BEFORE the wire. The orchestrator
                # is pure; the retry itself is the caller's
                # responsibility, so we only mark
                # ``retry_recommended`` here and let the
                # upstream service decide.
                try:
                    from app.services.ai.knowledge.ai17_orchestrator import (
                        run_ai17_pipeline,
                        stamp_ai17_onto,
                    )
                    _ai17 = run_ai17_pipeline(
                        payload=gen,
                        starting_confidence=int(
                            gen.confidence
                            if gen.confidence is not None
                            else 70
                        ),
                        materially_useful=True,
                        budget_remaining_ms=15_000,
                        hard_call_timeout_ms=15_000,
                        retry_already_attempted=False,
                        original_prompt=str(
                            (getattr(
                                request, "context", None
                            ) and getattr(
                                request.context, "question_text", ""
                            )) or ""
                        ),
                    )
                    stamp_ai17_onto(gen, pipeline_result=_ai17)
                    new_conf = _ai17["adjusted_confidence"]
                    if (
                        new_conf is not None
                        and (gen.confidence is None or new_conf != gen.confidence)
                    ):
                        object.__setattr__(gen, "confidence", new_conf)
                except Exception:  # pragma: no cover — defensive
                    pass
                object.__setattr__(assistant_resp, "generation", gen)
                return
            new_gen = replace(
                gen,
                answer_requirements=answer_req.to_dict(),
                evidence_graph=graph.to_dict(),
                calculation_lineage=list(lineage),
                missing_data_state=missing,
                unsupported_claim_count=unsupported,
                fabricated_source_count=fabricated,
                # SPRINT AI-15 — visualization + trust.
                visualization_plans=ai15_payloads,
                quality_warning=ai15_quality_warning,
                trust_summary=ai15_trust,
            )
            # SPRINT AI-16 — scheme card + mixed composition
            # (overlays onto an existing GenerationMeta).
            try:
                from app.services.ai.knowledge.ai16_scheme_composer import (
                    compose_scheme_card as _ai16_scheme,
                )
                from app.services.ai.knowledge.ai16_mixed_composer import (
                    compose_mixed_sections as _ai16_mixed,
                )
                scheme_payload = _ai16_scheme(
                    question_understanding=question_understanding,
                    context=ctx,
                )
                scheme_card_dict = (
                    scheme_payload.card.to_dict()
                    if scheme_payload is not None
                    else None
                )
                mixed_blocks = _ai16_mixed(
                    question_understanding=question_understanding,
                    envelopes=envelopes_t,
                    context=ctx,
                )
                new_gen = replace(
                    new_gen,
                    scheme_card=scheme_card_dict,
                    mixed_answer=(
                        mixed_blocks.to_dict()
                        if mixed_blocks.is_mixed
                        else None
                    ),
                )
            except Exception:  # pragma: no cover — defensive
                pass
            # SPRINT AI-17 — Bounded Quality Repair + Claim
            # Lifecycle (overlay onto an existing GenerationMeta).
            # Same composition as the empty-path branch; the
            # orchestrator is pure, so we chain a second
            # ``replace(...)`` with the AI-17 envelope fields.
            try:
                from app.services.ai.knowledge.ai17_orchestrator import (
                    run_ai17_pipeline as _ai17_run,
                )
                _ai17_overlay = _ai17_run(
                    payload=new_gen,
                    starting_confidence=int(
                        new_gen.confidence
                        if new_gen.confidence is not None
                        else 70
                    ),
                    materially_useful=True,
                    budget_remaining_ms=15_000,
                    hard_call_timeout_ms=15_000,
                    retry_already_attempted=False,
                    original_prompt=str(
                        (getattr(
                            request, "context", None
                        ) and getattr(
                            request.context, "question_text", ""
                        )) or ""
                    ),
                )
                # ``numeric_corrections`` + ``repair_applied`` are
                # tuples so ``replace(...)`` accepts them directly.
                new_gen = replace(
                    new_gen,
                    failure_classification=_ai17_overlay[
                        "failure_classification"
                    ],
                    repair_applied=tuple(
                        _ai17_overlay["applied_repairs"] or ()
                    ),
                    retry_attempted=bool(
                        _ai17_overlay["retry_recommended"]
                    ),
                    retry_succeeded=None,
                    numeric_corrections=tuple(
                        r.to_dict()
                        for r in _ai17_overlay["audit_log"].rows
                    ),
                    claim_lifecycle=_ai17_overlay[
                        "lifecycle_store"
                    ].to_dict(),
                    bounded_repair_version=_ai17_overlay[
                        "bounded_repair_version"
                    ],
                    confidence=_ai17_overlay["adjusted_confidence"],
                )
            except Exception:  # pragma: no cover — defensive
                pass
            object.__setattr__(assistant_resp, "generation", new_gen)
        except Exception:  # pragma: no cover — defensive
            return

    def _collect_recommendation_payloads(
        self,
        *,
        assistant_resp: Any,
        context_snapshot: Any = None,
    ) -> list[dict]:
        """Collect every Recommendation payload available for tracing.

        Source order (first non-empty wins):

          1. ``generation.grounded_payload["recommendations"]`` —
             the LLM-authored list (real provider path).
          2. ``context_snapshot.recommendations`` — the upstream
             ``AssistantContextRecommendation`` projections (the
             deterministic fallback path; these lack provenance
             fields but ``build_trace`` will derive what it can).
          3. The ``claim_aware`` recommendations block — the
             AI-3 envelope also lists recs.

        Each source is normalised to the ``to_payload()`` dict
        shape so the builder has a uniform input.
        """
        payloads: list[dict] = []
        seen: set[str] = set()

        def _normalise(raw: dict) -> dict | None:
            """Return the payload dict or None if the input is malformed."""
            if not isinstance(raw, dict):
                return None
            rec_id = str(raw.get("id", "") or "")
            if not rec_id:
                return None
            if rec_id in seen:
                return None
            seen.add(rec_id)
            return dict(raw)

        # 1. LLM-authored recommendations (real provider path).
        gen = getattr(assistant_resp, "generation", None)
        if gen is not None:
            grounded = getattr(gen, "grounded_payload", None) or {}
            if isinstance(grounded, dict):
                for r in grounded.get("recommendations") or ():
                    norm = _normalise(r if isinstance(r, dict) else {})
                    if norm:
                        payloads.append(norm)
                # Also pull from claim_aware.recommendations.
                claim_aware = grounded.get("claim_aware") or {}
                if isinstance(claim_aware, dict):
                    for r in claim_aware.get("recommendations") or ():
                        if isinstance(r, dict) and r.get("recommendation_id"):
                            alt = dict(r)
                            alt["id"] = str(r.get("recommendation_id"))
                            norm = _normalise(alt)
                            if norm:
                                payloads.append(norm)

        # 2. Context-projected recommendations (fallback / narrow path).
        if context_snapshot is not None:
            for r in getattr(context_snapshot, "recommendations", ()) or ():
                norm = _normalise(
                    {
                        "id": getattr(r, "id", ""),
                        "title": getattr(r, "title", ""),
                        "category": getattr(r, "category", ""),
                        "priority": getattr(r, "priority", "Medium"),
                        "estimated_score_gain": getattr(
                            r, "estimated_score_gain", 0
                        ),
                        "estimated_roi": getattr(r, "estimated_roi", 0),
                        "estimated_timeline": getattr(r, "estimated_timeline", ""),
                    }
                )
                if norm:
                    payloads.append(norm)

        return payloads

    def _build_history(
        self,
        session,
        *,
        exclude_message_id: int | None = None,
    ) -> tuple[AssistantTurn, ...]:
        """Return the last N turns as AssistantTurn records.

        ``exclude_message_id`` is the id of the user message
        that was just appended. We must skip it because the
        provider is about to receive it as the live ``user_prompt``
        — repassing it as history would echo the same text back
        into the model and inflate the prompt with duplicate
        content. (H7.8C P3 — the previous filter compared
        ``m.id`` to ``session.id`` which almost never matched,
        so the just-inserted user message leaked into the
        rolling context.)
        """
        messages = self._repo.get_messages(session=session)
        # Exclude the message we just added (it's the user
        # message we're about to send as the prompt).
        prior = [
            m
            for m in messages
            if m.role in ("user", "assistant")
            and (exclude_message_id is None or m.id != exclude_message_id)
        ]
        if self._rolling_context_turns <= 0:
            return ()
        prior = prior[-self._rolling_context_turns:]
        return tuple(
            AssistantTurn(role=m.role, content=m.content) for m in prior
        )

    def _build_owner_context(self, context) -> dict:
        """Project the assembled AssistantContext into the
        per-business boost payload the retriever consumes.

        The projection is a degeneralization: the
        :class:`AssistantContext` is already a narrow
        projection of Twin + Recommendations, so we only
        forward the keys the retriever understands.

        Two calls with the same upstream state produce
        the same boost payload.
        """
        try:
            from app.services.knowledge_retrieval.service import (
                KnowledgeRetrievalService,
            )
        except ImportError:
            return {}
        low_score_keys: list[str] = []
        for score in getattr(context, "scores", ()) or ():
            try:
                if str(score.level).lower() == "low":
                    low_score_keys.append(str(score.key).lower())
            except AttributeError:
                continue
        rec_categories: list[str] = []
        for rec in getattr(context, "recommendations", ()) or ():
            try:
                cat = rec.category
                if isinstance(cat, str) and cat:
                    rec_categories.append(cat.lower())
            except AttributeError:
                continue
        return {
            "low_score_keys": tuple(sorted(set(low_score_keys))),
            "recommendation_categories": tuple(sorted(set(rec_categories))),
        }

    def _default_assistant_service(self) -> AssistantProviderService:
        """Build the default AssistantProviderService.

        Wires the Sprint 7 Part 2 context builder to call
        the five upstream engines (Twin, Recommendations,
        Roadmap, Rules, Insights) via a callable bridge that
        the endpoint will close over with the request's
        ``BusinessRepository``.
        """
        from app.config.settings import get_settings
        from app.repositories.business_repository import BusinessRepository
        from app.services.intelligence import IntelligenceService
        from app.services.recommendations import RecommendationService
        from app.services.roadmap import RoadmapService
        from app.services.rules import RuleEngineService
        from app.services.twin import TwinService
        from app.services.ai import AIDecisionService

        # NOTE: a real endpoint that owns a session
        #       will construct its own AssistantProviderService
        #       with a closure over BusinessRepository.
        #       This default is only used by callers that
        #       want a service for tests / scripts.
        raise RuntimeError(
            "ConversationService requires an explicit assistant_service. "
            "Build one with AssistantContextBuilder bound to the request's "
            "BusinessRepository and pass it in."
        )


# --------------------------------------------------------------------------- #
# Helpers — payload projection
# --------------------------------------------------------------------------- #


def _message_payload(msg) -> dict:
    try:
        sources_raw = json.loads(msg.sources_json or "[]")
    except json.JSONDecodeError:
        sources_raw = []
    sources: list[dict] = []
    for s in sources_raw:
        if not isinstance(s, dict):
            continue
        topic = str(s.get("topic", ""))
        detail = str(s.get("detail", ""))
        if topic and detail:
            sources.append({"topic": topic, "detail": detail})
    # H7.8C — re-hydrate the GenerationMeta envelope from the
    # ``generation_meta_json`` column so the frontend can render
    # the disclosure without a second fetch.
    generation = None
    try:
        raw = getattr(msg, "generation_meta_json", "") or ""
        if raw:
            parsed = json.loads(raw)
            if isinstance(parsed, dict) and parsed:
                generation = parsed
    except (json.JSONDecodeError, ValueError):
        generation = None

    # H7.8C — flatten the brief-mandated provenance fields to
    # the TOP level of the message payload. The frontend trust
    # disclosure (provider, model, runtime provider, grounding
    # score, evidence references, assumptions, limitations,
    # fallback active, mode, confidence) is now reachable
    # without parsing the ``generation`` block. All fields are
    # safe defaults so user turns and legacy rows remain
    # parseable.
    #
    # Source of truth priority: the live ``generation`` block
    # is authoritative. The pydantic ``ChatMessageOut`` schema
    # accepts the top-level fields verbatim — the brief value
    # is propagated and the ``generation`` block is kept for
    # any client that already reads it.
    fallback_used_flag = bool(getattr(msg, "fallback_used", False))
    gen_provider = str((generation or {}).get("provider") or "")
    gen_model = str((generation or {}).get("model") or "")
    gen_runtime_provider = str((generation or {}).get("runtime_provider") or gen_provider)
    gen_mode = (generation or {}).get("mode")
    gen_grounding_score = int((generation or {}).get("server_grounding_score") or 0)
    gen_evidence_refs = list((generation or {}).get("evidence_references") or [])
    gen_assumptions = list((generation or {}).get("assumptions") or [])
    gen_limitations = list((generation or {}).get("limitations") or [])
    gen_confidence = (generation or {}).get("confidence")
    # AI-1 — universal-assistant audit-trail fields surfaced
    # at the top level for the frontend trust disclosure. Each
    # default is a safe empty so user turns + legacy rows remain
    # parseable.
    gen_deterministic_services = list(
        (generation or {}).get("deterministic_services_used") or []
    )
    gen_calculations_used = list(
        (generation or {}).get("calculations_used") or []
    )
    gen_question_understanding = (generation or {}).get("question_understanding")
    gen_tool_calls = list((generation or {}).get("tool_calls") or [])
    gen_claim_categories = list(
        (generation or {}).get("claim_categories_used") or []
    )
    # AI-3 — claim-aware response contract mirrors. The
    # claim_aware_response is sourced from GenerationMeta
    # ``grounded_payload["claim_aware"]`` (set by the AI-3
    # pipeline in service.py) and projected to the top level
    # so the frontend can render the structured panel without
    # drilling into ``generation.*``.
    gen_grounded_payload = (
        (generation or {}).get("grounded_payload")
        if isinstance((generation or {}).get("grounded_payload"), dict)
        else None
    )
    gen_claim_aware = (
        gen_grounded_payload.get("claim_aware")
        if gen_grounded_payload is not None
        else None
    )
    gen_claim_aware_validated = bool(
        (generation or {}).get("claim_aware_validated") or False
    )
    gen_numeric_conflicts_count = int(
        (generation or {}).get("numeric_conflicts_count") or 0
    )
    gen_server_confidence = (generation or {}).get("server_confidence")
    gen_server_confidence_rationale = str(
        (generation or {}).get("server_confidence_rationale") or ""
    )
    # AI-4 — server-side claim auditor mirrors. The compact
    # claim trace is stashed on GenerationMeta.grounded_payload
    # by the AI-4 pipeline (service.py) and mirrored to the
    # wire as a top-level ``claim_audit`` field so the
    # frontend's "Why am I seeing this?" disclosure panel
    # renders without drilling into ``generation.*``.
    gen_claim_audit = (
        gen_grounded_payload.get("claim_audit")
        if gen_grounded_payload is not None
        and isinstance(gen_grounded_payload.get("claim_audit"), dict)
        else None
    )
    gen_claim_audit_rejected = bool(
        (generation or {}).get("claim_audit_rejected") or False
    )
    gen_claim_audit_soft_corrections = int(
        (generation or {}).get("claim_audit_soft_corrections") or 0
    )
    # AI-7 — Missing-data intelligence. The structured
    # ``missing_data`` rows the proactive detector (step 3.7)
    # plus the reactive enrichment pass (step 5.8) emitted.
    # Mirrored at the top level so the frontend's
    # MissingInfoCard can render the 4-section "What I can
    # tell / What I am missing / Why it matters / Next step"
    # layout without drilling into ``generation.*``. Empty
    # list on legacy rows + on intents without a required
    # field map (GENERAL, BIGGEST_WEAKNESS, TWELVE_MONTH_ROADMAP).
    gen_missing_data = list(
        (generation or {}).get("missing_data") or []
    )
    # SPRINT AI-8 — Controlled Business Tool Router. The
    # validated, sanitised, evidence-stamped results of the
    # (optional) 2nd-turn tool-loop. Each entry has the shape
    # ``{"tool", "status", "evidence_ids", "payload",
    #   "duration_ms", "error"}``. Empty list when the LLM
    # did not request any tools, or when the router rejected
    # every request. Mirrored at the top level so the
    # frontend ``ReasoningTrace`` can render the "used
    # tools" pill row without drilling into
    # ``generation.*``.
    gen_llm_tool_results = list(
        (generation or {}).get("llm_tool_results") or []
    )
    # SPRINT AI-10 — Explain My Answer. Per-recommendation
    # decision traces stamped on every assistant turn. The
    # dict is keyed by ``recommendation_id``; each value
    # carries the six-section trace built from structured
    # provenance metadata. ``None`` for legacy rows that
    # pre-date AI-10; the frontend ``ExplanationPanel``
    # falls back to "Explain this answer is unavailable for
    # this message" in that case. Backward-compatible: every
    # prior sprint's mirror block uses the same None-as-missing
    # pattern (see claim_audit, scenario_analysis, etc.).
    gen_explanation = (
        (generation or {}).get("explanation")
        if isinstance((generation or {}).get("explanation"), dict)
        else None
    )
    # AI-11 — Universal Business-Aware Assistant hardening.
    # Surface the capability tuple + business dependency
    # literal on the wire so the frontend can render the
    # universal-question classification without parsing the
    # structured ``generation`` envelope. Both default to
    # an empty list / ``"none"`` when missing.
    gen_capability = list(
        (generation or {}).get("capability") or []
    )
    gen_business_dependency = str(
        (generation or {}).get("business_dependency") or "none"
    )
    if gen_business_dependency not in {"none", "optional", "required"}:
        # Defensive normalisation — never let an unknown
        # value leak through the wire projection.
        gen_business_dependency = "none"

    # SPRINT AI-13 — per-tool observability + partial-failure
    # handling. Mirror the three AI-13 wire fields at the top
    # level so the frontend renderer can render the trust +
    # evidence UI without drilling into ``generation.*``.
    gen_tool_execution_traces = list(
        (generation or {}).get("tool_execution_traces") or []
    )
    gen_partial_failure_disclosure = (
        (generation or {}).get("partial_failure_disclosure")
        if (generation or {}).get("partial_failure_disclosure")
        else None
    )
    try:
        gen_confidence_penalty = int(
            (generation or {}).get("confidence_penalty") or 0
        )
    except (TypeError, ValueError):
        gen_confidence_penalty = 0
    # Defensive clamp — the wire field is 0..40 today; the
    # projector clamps to [0, 100] as a belt-and-braces guard.
    if gen_confidence_penalty < 0:
        gen_confidence_penalty = 0
    if gen_confidence_penalty > 100:
        gen_confidence_penalty = 100

    payload = {
        "id": int(msg.id),
        "role": str(msg.role),
        "kind": str(msg.kind or ""),
        "content": str(msg.content),
        "sources": sources,
        "created_at": _iso(msg.created_at),
        # H7.8A P2 — per-message fallback flag surfaced to the
        # frontend so MessageBubble can render the right trust label.
        "fallback_used": fallback_used_flag,
        # H7.8C — full provenance envelope. Always present on
        # assistant turns; None for user turns (the user has no
        # generation metadata).
        "generation": generation,
        # H7.8C — flat mirrors of the provenance envelope.
        # The frontend can render the trust disclosure from
        # these top-level fields without drilling into
        # ``generation.*``. Backward-compatible: every
        # field has a safe default so old clients still
        # parse.
        "provider": gen_provider,
        "model": gen_model,
        "runtime_provider": gen_runtime_provider,
        "grounding_score": gen_grounding_score,
        "evidence_references": gen_evidence_refs,
        "assumptions": gen_assumptions,
        "limitations": gen_limitations,
        "fallback_active": fallback_used_flag,
        "mode": gen_mode,
        "confidence": gen_confidence,
        # AI-1 — universal-assistant audit-trail mirrors at the
        # top level of the wire payload.
        "deterministic_services_used": gen_deterministic_services,
        "calculations_used": gen_calculations_used,
        "question_understanding": gen_question_understanding,
        "tool_calls": gen_tool_calls,
        "claim_categories_used": gen_claim_categories,
        # AI-3 — claim-aware contract mirrors. Backward-compatible:
        # claim_aware_response is None when the LLM did not fill the
        # schema or when this is a legacy row; the frontend renders
        # the old path. server_confidence is always populated when
        # the meta carries it (None on legacy rows).
        "claim_aware_response": gen_claim_aware,
        "claim_aware_validated": gen_claim_aware_validated,
        "numeric_conflicts_count": gen_numeric_conflicts_count,
        "server_confidence": gen_server_confidence,
        "server_confidence_rationale": gen_server_confidence_rationale,
        # AI-4 — claim-auditor mirrors. The compact trace
        # (``gen_claim_audit``) is what the "Why am I seeing
        # this?" disclosure panel renders; the two boolean
        # companions let the frontend stamp a top-level trust
        # badge without parsing the trace. Backward-compatible:
        # all three default to None / False / 0 on legacy rows.
        "claim_audit": gen_claim_audit,
        "claim_audit_rejected": gen_claim_audit_rejected,
        "claim_audit_soft_corrections": gen_claim_audit_soft_corrections,
        # AI-5 — Business Scenario Copilot envelope. Mirrored at
        # the top level so the frontend's ScenarioAnalysisCard
        # can render the 10-field "what if" card without
        # drilling into ``generation.*``. The envelope is always
        # None for non-scenario prompts (the LLM route runs
        # unchanged). Backward-compatible: legacy rows never
        # carry this key.
        "scenario_analysis": (generation or {}).get("scenario_analysis"),
        # AI-6 — Trust-first visual UI. The first 1-3 sentences
        # of the assistant's prose, server-extracted. Mirrored
        # at the top level so the frontend can render the
        # "Direct Answer" 10-second-read header without drilling
        # into ``generation.*``. ``None`` when the prose was
        # empty or when the legacy row pre-dates AI-6; the
        # projector in AssistantView falls back to
        # ``consultant.body`` / ``content`` in that case.
        "direct_answer": (generation or {}).get("direct_answer"),
        # AI-7 — Missing-data intelligence. The structured
        # MissingDataObject list the proactive detector +
        # reactive enrichment pass produced. Empty list
        # when the wire is empty (legacy rows or intents
        # without a required field map). The frontend's
        # MissingInfoCard reads this top-level field.
        "missing_data": gen_missing_data,
        # AI-8 — controlled tool router mirror. Empty for
        # legacy rows / first-turn LLMs that did not request
        # any tools. The frontend ``ReasoningTrace`` falls
        # back to the existing rendering when the list is
        # empty.
        "llm_tool_results": gen_llm_tool_results,
        # AI-10 — Explain My Answer. Mirrored at the top
        # level so the frontend ``ExplanationPanel`` can
        # render the 6-section trace without drilling into
        # ``generation.*``. ``None`` for legacy rows; the
        # panel hides itself entirely in that case.
        "explanation": gen_explanation,
        # AI-11 — Universal Business-Aware Assistant hardening.
        # Multi-label capability tuple + business dependency
        # literal mirrored at the top level. Empty list /
        # ``"none"`` for legacy rows so the renderer sees a
        # stable shape regardless of message age.
        "capability": gen_capability,
        "business_dependency": gen_business_dependency,
        # AI-13 — Production Orchestration wire mirror. The
        # three additive fields are flat-copied from the
        # generation envelope so the frontend trust + evidence
        # UI can render without drilling into ``generation.*``.
        "tool_execution_traces": gen_tool_execution_traces,
        "partial_failure_disclosure": gen_partial_failure_disclosure,
        "confidence_penalty": gen_confidence_penalty,
        # AI-14 — Universal Answer Intelligence + Evidence
        # Graph. Six additive wire mirrors. The first two
        # (``answer_requirements`` + ``evidence_graph``) are the
        # largest JSON shapes (16-field + multi-tuple dataclasses)
        # and are surfaced at the top level so the frontend
        # renderer can read them in a single TypeScript
        # destructure. The remaining four
        # (``calculation_lineage``, ``missing_data_state``,
        # ``unsupported_claim_count``, ``fabricated_source_count``)
        # are sourced from the ``generation`` envelope directly.
        "answer_requirements": (generation or {}).get(
            "answer_requirements"
        ),
        "evidence_graph": (generation or {}).get("evidence_graph"),
        "calculation_lineage": list(
            (generation or {}).get("calculation_lineage") or []
        ),
        "missing_data_state": (generation or {}).get(
            "missing_data_state"
        ),
        "unsupported_claim_count": _safe_int(
            (generation or {}).get("unsupported_claim_count"), 0
        ),
        "fabricated_source_count": _safe_int(
            (generation or {}).get("fabricated_source_count"), 0
        ),
        # SPRINT AI-15 — Intelligent Visualization + Trust-First
        # UX. Three additive top-level mirrors sourced from the
        # ``generation`` envelope. ``visualization_plans`` powers
        # the chart slots inside TrustFirstResponse.
        # ``quality_warning`` powers the concise low-quality
        # warning strip the brief mandates. ``trust_summary``
        # powers the "Why this answer?" disclosure panel.
        "visualization_plans": list(
            (generation or {}).get("visualization_plans") or []
        ),
        "quality_warning": (generation or {}).get("quality_warning"),
        "trust_summary": (generation or {}).get("trust_summary"),
        # SPRINT AI-16 — Verified External Knowledge + Freshness
        # Layer. Five additive top-level mirrors sourced from
        # the ``generation`` envelope. ``external_claims`` powers
        # the "Sources we consulted" disclosure;
        # ``freshness_warnings`` powers the "Stale source"
        # inline notice; ``scheme_card`` / ``external_answer``
        # / ``mixed_answer`` power their dedicated UI cards.
        "external_claims": list(
            (generation or {}).get("external_claims") or []
        ),
        "freshness_warnings": list(
            (generation or {}).get("freshness_warnings") or []
        ),
        "scheme_card": (generation or {}).get("scheme_card"),
        "external_answer": (generation or {}).get("external_answer"),
        "mixed_answer": (generation or {}).get("mixed_answer"),
        # SPRINT AI-17 — Bounded Quality Repair + Claim
        # Lifecycle. Eight additive top-level mirrors sourced
        # from the ``generation`` envelope. The renderer reads
        # ``failure_classification`` + ``retry_attempted`` to
        # surface the failure / retries badge; ``claim_lifecycle``
        # + ``numeric_corrections`` power the audit trail panel
        # in the trust disclosure.
        "failure_classification": (generation or {}).get(
            "failure_classification", "none"
        ),
        "repair_applied": list(
            (generation or {}).get("repair_applied") or []
        ),
        "retry_attempted": bool(
            (generation or {}).get("retry_attempted") or False
        ),
        "retry_succeeded": (generation or {}).get("retry_succeeded"),
        "numeric_corrections": list(
            (generation or {}).get("numeric_corrections") or []
        ),
        "claim_lifecycle": (generation or {}).get("claim_lifecycle"),
        "bounded_repair_version": (
            generation or {}
        ).get("bounded_repair_version", ""),
    }
    # H7.8C — leak guard. The serializer must never emit a
    # field name from the brief-mandated secret set
    # (``api_key``, ``authorization``, ``base_url``, etc.).
    # The audit fix changed the provider layer to never
    # include them; this guard catches any future regression
    # at the projection boundary.
    _assert_no_leaked_secrets(payload, where="_message_payload")
    return payload


def _session_summary(session) -> dict:
    return {
        "id": int(session.id),
        "title": str(session.title or ""),
        "summary": str(session.summary or ""),
        "message_count": int(session.message_count or 0),
        "last_model": str(session.last_model or ""),
        "fallback_used": bool(session.fallback_used),
        "created_at": _iso(session.created_at),
        "updated_at": _iso(session.updated_at),
    }


def _session_detail(session) -> dict:
    out = _session_summary(session)
    out["messages"] = [_message_payload(m) for m in session.messages]
    return out


def _sources_to_payload(sources) -> list[dict]:
    """Map provider sources (ChatSource dataclasses) to dict payload."""
    out: list[dict] = []
    for s in sources:
        topic = getattr(s, "topic", None)
        detail = getattr(s, "detail", None)
        if topic and detail:
            out.append({"topic": str(topic), "detail": str(detail)})
    return out


def _iso(value: Any) -> str:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    return str(value)


def _safe_int(value: Any, default: int) -> int:
    """Coerce ``value`` to int; return ``default`` on TypeError/ValueError.

    Used by the AI-14 projector to read the two integer counters
    (``unsupported_claim_count``, ``fabricated_source_count``)
    off the wire payload without crashing the chat path on a
    malformed legacy row.
    """
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return int(default)


def _safe_to_dict(value: Any) -> dict | None:
    """Return ``value.to_dict()`` if the value exposes one, else ``None``.

    Tolerant of missing ``to_dict`` — returns ``None`` so the
    AI-12 stamping helpers can no-op when the underlying
    dataclass is malformed. Never raises.
    """
    try:
        if value is None:
            return None
        to_dict = getattr(value, "to_dict", None)
        if not callable(to_dict):
            return None
        out = to_dict()
        return out if isinstance(out, dict) else None
    except Exception:  # pragma: no cover — defensive
        return None


# H7.8C — the brief-mandated list of fields that must NEVER
# appear in a wire payload. The service layer asserts this set
# is disjoint from every payload it emits. Adding a new
# sensitive key here is a non-breaking change (it just adds
# another field to the leak guard). Removing a key is a
# breaking change for the audit trail.
#
# SPRINT AI-8 — the canonical home for these constants +
# ``assert_no_leaked_secrets`` is now
# ``app.services.ai.sanitisation``. Re-exported here for
# backwards compatibility — every existing import keeps
# working byte-identical.
from app.services.ai.sanitisation import (
    LEAKED_FIELDS as _LEAKED_FIELDS,
    assert_no_leaked_secrets as _assert_no_leaked_secrets_impl,
    strip_leaked_secrets as _strip_leaked_secrets,
)


def _assert_no_leaked_secrets(payload: dict | None, *, where: str) -> None:
    """Backwards-compatible thin wrapper around the AI-8
    canonical implementation in
    :mod:`app.services.ai.sanitisation`. The function body
    lives there; this re-export preserves any code that
    imported ``_assert_no_leaked_secrets`` from this
    module by attribute name.
    """
    _assert_no_leaked_secrets_impl(payload, where=where)


def _generation_meta_to_payload(meta) -> dict | None:
    """Project a :class:`GenerationMeta` dataclass into a JSON-safe dict.

    Returns ``None`` when the provider did not stamp a
    ``GenerationMeta`` (e.g. the legacy mock-provider path).
    Tuples become lists so ``json.dumps`` round-trips cleanly.

    H7.8C — ``runtime_provider`` is filled from ``provider``
    when the dataclass did not stamp it explicitly. The
    short-circuit keeps the field always-present on the wire
    so the frontend can rely on it without checking for
    ``None``. The leak guard runs before returning so any
    future regression that pulls a config dict into the
    envelope is caught at the boundary.
    """
    if meta is None:
        return None
    try:
        from dataclasses import asdict
        out = asdict(meta)
    except Exception:
        return None
    # Tuples → lists for JSON.
    for key, value in list(out.items()):
        if isinstance(value, tuple):
            out[key] = list(value)
    # H7.8C — default runtime_provider to provider when the
    # upstream didn't set it. A real provider path always
    # sets it explicitly; the deterministic fallback path
    # leaves it empty so this default kicks in.
    if not out.get("runtime_provider"):
        out["runtime_provider"] = out.get("provider") or ""
    _assert_no_leaked_secrets(out, where="_generation_meta_to_payload")
    return out


def _extract_direct_answer(prose: str | None, *, max_sentences: int = 3) -> str | None:
    """SPRINT AI-6 — extract the "Direct Answer" first 1-3 sentences.

    The brief mandates that every assistant reply start with a
    1-3 sentence direct answer the user can read within 10
    seconds. The backend extracts this on the LLM path and
    stamps it onto :class:`GenerationMeta.direct_answer`; the
    frontend renders it as the top of every reply. The legacy
    fallback path returns ``None`` and the projector derives the
    direct answer from ``consultant.body`` / ``content``.

    Sentence boundary detection is intentionally minimal — we
    split on ``.``, ``!``, ``?`` followed by whitespace (or end
    of string) and trim markdown prefixes (``- ``, ``* ``,
    ``> ``). The function never returns more than
    ``max_sentences`` non-empty sentences, never returns more
    than 600 characters (the schema cap), and returns ``None``
    when the prose has no extractable sentences.

    The function is pure: same input → same output, no I/O, no
    logging. Verified by ``test_ai6_direct_answer.py``.
    """
    if not prose or not isinstance(prose, str):
        return None
    raw = prose.strip()
    if not raw:
        return None
    # Split on sentence-ending punctuation. Keep the
    # punctuation attached so the snippet reads naturally.
    import re

    parts = re.split(r"(?<=[.!?])\s+", raw)
    cleaned: list[str] = []
    for part in parts:
        # Strip leading markdown list / blockquote markers
        # so " - Sentence." reads as "Sentence.".
        stripped = part.lstrip(" \t-*>#").strip()
        # Drop empty entries (multiple whitespace, etc.).
        if not stripped:
            continue
        cleaned.append(stripped)
        if len(cleaned) >= max_sentences:
            break
    if not cleaned:
        return None
    out = " ".join(cleaned)
    # Schema cap — ChatGenerationMeta.direct_answer is
    # ``str | None`` with no explicit length but the
    # ChatMessageOut top-level mirror is documented as a
    # short 1-3 sentence string. Truncate to 600 chars
    # defensively so a long legacy body never blows the wire.
    if len(out) > 600:
        out = out[:597].rstrip() + "..."
    return out


def _derive_title(content: str) -> str:
    """First 80 chars of the user message, single-line, trimmed."""
    flat = " ".join((content or "").split())
    if not flat:
        return "New conversation"
    return flat[:_TITLE_CAP]


def _derive_summary(
    *,
    session_summary: str,
    context: AssistantContext,
    latest_user: str,
    latest_assistant: str,
) -> str:
    """Compose the conversation summary.

    The summary is a single line that names the score band +
    the DNA archetype + a short hint of the latest exchange.
    It is rebuilt on every append so the sidebar always
    shows the freshest state.
    """
    bits: list[str] = []
    bits.append(
        f"Score {context.overall_business_score}/100 ({context.band})"
    )
    if context.dna.archetype_title:
        bits.append(
            f"DNA: {context.dna.archetype_title} ({context.dna.match_score}%)"
        )
    rec = (latest_user or "").strip()
    if rec:
        flat_user = " ".join(rec.split())[:80]
        bits.append(f"Latest: {flat_user}")
    summary = " · ".join(bits)
    if len(summary) > _SUMMARY_CAP:
        summary = summary[: _SUMMARY_CAP - 1] + "…"
    return summary


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _citations_to_sources(knowledge_ctx) -> list[dict]:
    """Translate :class:`Citation` rows into the
    ``ChatSource`` payload the chat schema stores.

    The schema is the same shape the existing providers
    use:

      {
        "topic": <SourceCategory-as-string>,
        "detail": <Citation.detail>,
      }

    Citation ``article_id`` is preserved in the detail
    string so the UI can deep-link to the knowledge
    article once such a route exists.
    """
    if knowledge_ctx is None:
        return []
    out: list[dict] = []
    for c in getattr(knowledge_ctx, "citations", ()) or ():
        topic = getattr(c, "source_category", None) or "Knowledge"
        detail = getattr(c, "detail", None) or ""
        if detail:
            out.append({
                "topic": str(topic),
                "detail": f"{detail} (article {c.article_id})",
            })
    return out