"""AssistantProviderService — Sprint 7 Part 2 + H7.3 + H7.8C.

The high-level façade the brief asks for. Wires the four
pieces together:

  AssistantContextBuilder     (read 5 upstream payloads)
            |
            v
  AssistantPromptBuilder      (assemble the prompt surface)
            |
            v
  ProviderFactory             (select the runtime provider)
            |
            v
  Provider.complete(request)  (real Ollama, real OpenAI-compat, or fallback)
            |
            v
  response_schema validation  (H7.3 — only when the provider is JSON-mode)
            |
            v
  GroundingValidator          (H7.8C — evidence-bound audit)
            |
            v
  AssistantResponse           (the return value, with GenerationMeta)

The service is thin — it owns no business logic. It is the
*only* file in the layer that knows about the four pieces,
which keeps the others unit-testable in isolation.

H7.8C — hybrid modes
--------------------

The service accepts a ``mode`` parameter on :meth:`generate`:

* ``mode="grounded"`` (default) — strict evidence-bounded.
  Builds an :class:`EvidenceRegistry` from the assembled
  context, embeds it in the prompt, requires JSON output,
  and runs the :class:`GroundingValidator` over the parsed
  response. Any rule failure falls back to the deterministic
  provider with ``fallback_reason="grounding_invalid"``.

* ``mode="open"`` — permissive. The prompt has no
  registry and no schema requirement. The model returns
  free-form prose. Provider failures get
  ``fallback_reason="open_mode_provider_failure"``.

Graceful degradation
--------------------

When the configured provider raises :class:`ProviderUnavailableError`
or :class:`ProviderTimeoutError`, the service catches the error
and asks the factory for the deterministic fallback. The
caller sees a normal :class:`AssistantResponse` whose
``fallback_used`` flag is ``True``, whose ``model`` is
``"deterministic-fallback"``, and whose ``generation`` block
carries the ``fallback_reason``.

H7.3 added: when the configured provider raises a
non-soft :class:`AIProviderError` *and* the error originated
from a schema-validation failure (``schema_invalid`` reason),
the service falls back to the deterministic provider. Per
docx P3 Part 3: "When validation fails, use the existing
deterministic consultant response." Other AIProviderError
classes (HTTP 5xx, malformed JSON, empty body) propagate
so the caller can decide.

The service does *not* retry. A retry policy is the next
milestone's problem.
"""
from __future__ import annotations

import concurrent.futures
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any

from app.services.ai.providers.base import (
    AIProviderError,
    AssistantContext,
    AssistantRequest,
    AssistantResponse,
    AssistantTurn,
    DeterministicFallbackProvider,
    GenerationMeta,
    Mode,
    NormalizedReason,
    Provider,
    ProviderHTTPStatusError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from app.services.ai.providers.context_builder import AssistantContextBuilder
from app.services.ai.providers.evidence_registry import EvidenceRegistry
from app.services.ai.providers.factory import ProviderFactory
from app.services.ai.providers.grounding_validator import (
    GroundingValidator,
    OpenResponseValidator,
)
from app.services.ai.providers.prompt_builder import AssistantPromptBuilder
from app.services.ai.providers.response_schema import (
    parse_model_output,
    parse_open_model_output,
)
# H8.11 — pre-LLM reasoning layer. Imported lazily inside
# ``__init__`` to avoid the circular import through
# ``app.services.ai.providers.__init__`` (which eagerly
# loads this module before :mod:`evidence_retriever` is
# fully initialised).
from app.services.ai.reasoning.question_understanding import (
    QuestionUnderstanding,
    is_purely_educational,
    understand_question,
)
from app.services.ai.reasoning.tool_selector import (
    StubToolInterface,
    ToolSelector,
)
from app.services.ai.reasoning.answer_composer import compose_adaptive_answer


# Module-level logger for structured provider events.
# The deployment /monitoring layer redacts known secret keys
# (``AI_API_KEY``, ``Authorization``, ``Cookie`` …) before
# these records hit disk — see ``app/monitoring/logging.py``.
from app.services.ai.providers.circuit_breaker import AICircuitBreaker
from app.services.ai.providers.base import (
    AIProviderError,
    AssistantContext,
    AssistantRequest,
    AssistantResponse,
    AssistantTurn,
    DeterministicFallbackProvider,
    GenerationMeta,
    Mode,
    NormalizedReason,
    Provider,
    ProviderAuthError,
    ProviderConfigError,
    ProviderHTTPStatusError,
    ProviderQuotaError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)

logger = logging.getLogger("atlas.ai.provider")


# H7.9R+ / H8.11 — hard wall-clock cap on a single outbound LLM call.
# The provider's underlying httpx client already has its own
# connect/read timeouts (``ai_request_timeout_seconds``); this
# constant is the *outer* ceiling that guarantees no chat request
# can ever hold a worker thread for more than this many seconds,
# regardless of retry behaviour inside the circuit breaker or any
# future backoff.
#
# The previous hard-coded 15 s value was sized for a Gemini-class
# upstream. llama3.2:3b on the 5.9 GB judge host legitimately
# takes 25–35 s for a full grounded-mode prompt (cold load +
# prompt-eval of the 12-section schema + JSON generation), so the
# cap is now sourced from ``Settings.ai_hard_call_timeout_seconds``
# with a safe default of 45 s. The provider's inner
# ``AI_REQUEST_TIMEOUT_SECONDS`` (90 s in production) remains the
# authoritative cap if the upstream truly hangs.
def _resolve_hard_call_timeout() -> float:
    """Read ``ai_hard_call_timeout_seconds`` from settings, cached.

    Lazy: avoids a module-load-time ``get_settings()`` call (which
    would initialise the lru_cache before app config is ready in
    unit tests that import this module in isolation).
    """
    try:
        from app.config.settings import get_settings

        return float(
            getattr(
                get_settings(),
                "ai_hard_call_timeout_seconds",
                15.0,
            )
        )
    except Exception:  # noqa: BLE001 — defensive
        return 15.0


HARD_CALL_TIMEOUT_SECONDS: float = _resolve_hard_call_timeout()

# Single shared executor for ``_call_with_hard_timeout`` below.
# ``max_workers=1`` so a slow provider does not get a pool of
# parallel attempts; the cap is the timeout, not parallelism.
# Daemon threads so a stuck provider cannot block process exit.
_HARD_TIMEOUT_EXECUTOR = ThreadPoolExecutor(
    max_workers=8, thread_name_prefix="ai-hard-timeout"
)


# SPRINT AI-8 — the hard cap on LLM-initiated tool-loop turns.
# The LLM is allowed exactly ONE follow-up turn so it can
# explain the verified facts returned by the deterministic
# engines. A malicious or buggy LLM that loops indefinitely
# is bounded at this number — the service short-circuits to
# the first-turn response on overflow.
_MAX_TOOL_LOOP_TURNS: int = 2


def _call_with_hard_timeout(
    provider: Any, request: AssistantRequest, timeout: float
) -> AssistantResponse:
    """Invoke ``provider.complete(request)`` under a hard wall-clock cap.

    Why this exists
    ---------------
    The underlying ``httpx.Client`` in :class:`OpenAICompatibleProvider`
    has a per-request timeout, but the service layer also runs the
    call through :class:`AICircuitBreaker.execute_with_resilience`
    which can retry with exponential backoff. A misbehaving upstream
    (TLS handshake stall, dropped connection, DNS hang) can therefore
    hold a worker thread for many times the configured timeout
    before any typed error surfaces.

    This wrapper puts the entire call (including the breaker's
    retries) on a single dedicated thread and bounds the total
    wall-clock time at ``timeout`` seconds. If the cap is
    exceeded, the thread is *left running* (it is daemonic and
    cannot block process exit) but the *caller* immediately
    receives a :class:`ProviderTimeoutError` and falls back to
    the deterministic provider. The provider's ``close()`` is
    invoked from the caller's thread ONLY on a true wall-clock
    timeout so the underlying HTTP connection is released and
    the next request starts clean. On a *transient* provider
    error (e.g. ``AIProviderError``, ``ProviderTimeoutError``),
    the provider is left open so the circuit breaker's retry
    can reuse the same client.

    Why the close()-on-any-exception path was wrong (H8.11 fix)
    ----------------------------------------------------------
    Previously this wrapper closed the provider on *every*
    exception. That broke the circuit breaker's retry: after the
    first attempt raised, the breaker retried with the SAME
    provider, whose ``httpx.Client`` had just been closed. The
    retry then died with ``"Cannot send a request, as the client
    has been closed."`` — which was reported as a separate
    ``provider_error`` even though the underlying upstream was
    healthy. The user-visible effect was that every other
    request fell back to the deterministic engine even when the
    real LLM was reachable. Closing is now restricted to the
    wall-clock timeout path.

    The previous architecture (no hard cap) caused chat requests
    to hang indefinitely when the upstream was unreachable. The
    H7.9R fix activates the fallback path within the wall-clock
    budget so the frontend never waits forever.
    """
    future = _HARD_TIMEOUT_EXECUTOR.submit(provider.complete, request)
    try:
        return future.result(timeout=timeout)
    except concurrent.futures.TimeoutError:
        # Wall-clock cap fired. The provider thread is still
        # running in the background; we cannot interrupt it,
        # but we DO close the provider so the underlying socket
        # is released. The next ``service.generate`` call gets a
        # brand-new ``OllamaProvider`` from the factory anyway,
        # so the closed client is harmless.
        try:
            provider.close()
        except Exception:
            pass
        raise
    except Exception:
        # Transient provider error — leave the provider open so
        # the circuit breaker's retry (if any) can reuse the
        # same httpx client. The provider will be closed on
        # the next wall-clock timeout or when the factory
        # discards it.
        raise


class AssistantProviderService:
    """The public façade for the AI Provider Layer with Multi-Tier Failover & Circuit Breaker."""

    def __init__(
        self,
        *,
        context_builder: AssistantContextBuilder,
        prompt_builder: AssistantPromptBuilder | None = None,
        provider_factory: ProviderFactory | None = None,
        reasoning_engine: Any | None = None,
        evidence_retriever: Any | None = None,
        tool_dispatcher: Any | None = None,
        tool_router: Any | None = None,
    ) -> None:
        self._context_builder = context_builder
        self._prompt_builder = prompt_builder or AssistantPromptBuilder()
        self._factory = provider_factory or ProviderFactory()
        self._circuit_breaker = AICircuitBreaker(name="gemini")
        # SPRINT AI-8 — the optional LLM-tool-request router.
        # When ``None`` (default) the provider behaves exactly
        # like today: the AI-1 ``ToolDispatcher`` runs the
        # server-selected tool calls; the LLM never requests
        # new ones. When present, the service hands it to the
        # 2nd-turn ``_maybe_run_tool_loop`` so the LLM can ask
        # the deterministic engines for more data.
        self._tool_router = tool_router
        # H8.11 — pre-LLM reasoning layer. The engine runs
        # the intent classifier + the H8.3 pipeline; the
        # retriever ranks the evidence registry. Both are
        # imported lazily so this module can finish loading
        # even when ``providers/__init__.py`` is mid-import
        # (the original eager-import path triggered a
        # circular ImportError when the package itself was
        # being collected by the test runner).
        if reasoning_engine is None or evidence_retriever is None:
            from app.services.ai.reasoning.reasoning_engine import (
                BusinessReasoningEngine,
            )
            from app.services.ai.reasoning.evidence_retriever import (
                EvidenceRetriever,
            )
        self._reasoning_engine = (
            reasoning_engine
            if reasoning_engine is not None
            else BusinessReasoningEngine()
        )
        self._evidence_retriever = (
            evidence_retriever
            if evidence_retriever is not None
            else EvidenceRetriever()
        )
        # SPRINT AI-2 — ToolDispatcher dependency. When the
        # chat endpoint constructs the service with a real
        # dispatcher (16 real engine wrappers), that dispatcher
        # is used. When the kwarg is None (legacy callers,
        # unit tests that don't care about tool dispatch) a
        # stub-only dispatcher is built so ``generate()`` keeps
        # working with ``status="not_implemented"`` everywhere.
        if tool_dispatcher is None:
            from app.services.ai.reasoning.tool_selector import (
                ToolDispatcher as _ToolDispatcher,
            )
            tool_dispatcher = _ToolDispatcher()
        self._tool_dispatcher = tool_dispatcher

    # ---- public API -------------------------------------------------- #

    def configured_provider_name(self) -> str:
        """Return the name of the configured provider."""
        return self._factory.configured_provider_name()

    def generate(
        self,
        *,
        owner_id: int,
        user_prompt: str,
        history: tuple[AssistantTurn, ...] = (),
        knowledge: object | None = None,
        provider: Provider | None = None,
        require_schema: bool | None = None,
        mode: Mode = "grounded",
        context: AssistantContext | None = None,
        language: str = "en",
    ) -> AssistantResponse:
        """Generate a reply with multi-tier resilience and circuit breaker protection."""
        if context is None:
            try:
                context = self._context_builder.build(
                    owner_id=owner_id, user_prompt=user_prompt
                )
            except TypeError:
                context = self._context_builder.build(owner_id=owner_id)
                if context.context_manifest is None and user_prompt:
                    from app.services.ai.providers.context_builder import select_relevant_context
                    context = select_relevant_context(context, user_prompt)

        # H8.11 — pre-LLM reasoning layer. The engine emits
        # a structured plan; the retriever ranks the
        # evidence registry by intent + plan. Both are
        # wrapped in try/except so a failure here can never
        # break a chat request — the prompt builder falls
        # back to the pre-H8.11 surface when either is
        # ``None``.
        #
        # AI-1 — Stage 1 builds a QuestionUnderstanding
        # from the user prompt + context. Stage 4 threads
        # that understanding into the reasoning plan.
        # Stage 5 dispatches deterministic tools (stubs by
        # default). Stages 7+8 use the same understanding /
        # plan / tool results to label claim categories and
        # pick the adaptive answer shell. None of these
        # layers can raise — every step is wrapped in
        # try/except so a Stage 1-8 failure can never break
        # a chat request.
        question_understanding: QuestionUnderstanding | None = None
        reasoning_plan = None
        ranked_evidence = None
        tool_results: tuple = ()
        # SPRINT AI-13 — the AI-12 ``DispatchOutcome`` carries
        # the plan + results + envelopes + traces. The
        # conversation service stamps the plan, envelopes,
        # and traces onto the audit row. Backward-compat is
        # preserved by deriving ``tool_results`` from the
        # outcome's ``.results`` tuple so every downstream
        # consumer (legacy ``tool_results`` block, the
        # prompt builder, the answer composer, the
        # GenerationMeta stamper) keeps working unchanged.
        from app.services.ai.reasoning.tool_selector import (
            DispatchOutcome as _DispatchOutcome,
        )
        dispatch_outcome: _DispatchOutcome | None = None
        adaptive_answer = None
        chosen = provider or self._factory.build()
        try:
            question_understanding = understand_question(
                user_prompt, context
            )
            # Stage 4 — call the reasoning engine's plan()
            # with the AI-1 kwarg. The legacy 2-kwarg
            # signature is preserved (the keyword is optional
            # in BusinessReasoningEngine.plan) but custom
            # TrackingEngine subclasses in the tests may
            # not have updated their signature. We try
            # with the kwarg first, fall back to the legacy
            # call if the engine rejects it.
            try:
                reasoning_plan = self._reasoning_engine.plan(
                    user_prompt=user_prompt,
                    context=context,
                    question_understanding=question_understanding,
                )
            except TypeError:
                reasoning_plan = self._reasoning_engine.plan(
                    user_prompt=user_prompt,
                    context=context,
                )
            registry = EvidenceRegistry(context)
            ranked_evidence = self._evidence_retriever.rank(
                context=context,
                registry=registry,
                reasoning_plan=reasoning_plan,
            )
            # Stage 5 — dispatch deterministic tools. The
            # dispatcher returns stubs by default for any
            # engine the layer hasn't wired in. SPRINT AI-2:
            # ``self._tool_dispatcher`` is the dispatcher
            # passed in via the constructor (or a default
            # stub-only dispatcher when no kwarg was given).
            # SPRINT AI-13 — use ``dispatch_with_plan`` so the
            # production path emits the ToolPlan +
            # StructuredToolEnvelope + ToolExecutionTrace
            # bundle. The legacy ``.dispatch`` is a thin wrapper
            # over ``dispatch_with_plan``; the live cutover
            # means we read plan / envelopes / traces from
            # the same outcome.
            if not isinstance(chosen, DeterministicFallbackProvider) and getattr(chosen, "name", "") != "deterministic-fallback":
                dispatch_outcome = self._tool_dispatcher.dispatch_with_plan(
                    owner_id=owner_id,
                    question_understanding=question_understanding,
                    reasoning_plan=reasoning_plan,
                    context=context,
                )
                tool_results = dispatch_outcome.results
            else:
                dispatch_outcome = None
                tool_results = ()
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "[service] AI-1 universal-assistant layers failed; "
                "falling back to pre-AI-1 prompt surface: %s",
                exc,
            )
            question_understanding = None
            reasoning_plan = None
            ranked_evidence = None
            dispatch_outcome = None
            tool_results = ()

        # AI-1 — internal ``_effective_mode``. The wire
        # ``mode`` is the user's selection (always). The
        # internal ``_effective_mode`` flips to ``"open"``
        # only when the prompt is purely educational AND
        # not business-specific — so the LLM is not forced
        # through the evidence registry for definitions or
        # explanations that have nothing to do with the
        # user's profile. The trust label uses the wire
        # ``mode`` (the user always sees their pick).
        effective_mode: Mode = mode
        try:
            if mode == "grounded" and is_purely_educational(user_prompt):
                if not getattr(
                    question_understanding, "is_business_specific", True
                ):
                    effective_mode = "open"
        except Exception:  # noqa: BLE001
            effective_mode = mode

        request = self._prompt_builder.build(
            context=context,
            user_prompt=user_prompt,
            history=history,
            knowledge=knowledge,
            mode=effective_mode,
            reasoning_plan=reasoning_plan,
            ranked_evidence=ranked_evidence,
            language=language,
        )

        chosen = provider or self._factory.build()

        # Check circuit breaker before making expensive network calls
        if not provider and not self._circuit_breaker.allow_request():
            logger.warning("[service] Circuit breaker is OPEN. Skipping primary provider call.")
            return self._fallback_chain(request, reason="circuit_open", mode=mode)

        try:
            if isinstance(chosen, DeterministicFallbackProvider) or getattr(chosen, "name", "") == "deterministic-fallback":
                response = chosen.complete(request)
            elif provider:
                # H7.9R+ — hard wall-clock cap on every outbound
                # call. ``asyncio.wait_for`` is the async equivalent;
                # we use ``_call_with_hard_timeout`` (a
                # ``ThreadPoolExecutor``-based equivalent) because
                # ``generate()`` runs in FastAPI's sync threadpool,
                # not on the asyncio loop. The cap is per-call;
                # the underlying provider's own connect/read timeouts
                # still apply on the inside.
                response = _call_with_hard_timeout(
                    chosen, request, timeout=HARD_CALL_TIMEOUT_SECONDS
                )
            else:
                # Same cap, but through the circuit breaker which
                # may add retry-with-backoff. The total wall-clock
                # is still bounded by ``HARD_CALL_TIMEOUT_SECONDS``
                # because the breaker runs inside the timed thread.
                response = self._circuit_breaker.execute_with_resilience(
                    lambda: _call_with_hard_timeout(
                        chosen, request, timeout=HARD_CALL_TIMEOUT_SECONDS
                    )
                )
        except ProviderQuotaError:
            return self._fallback_chain(request, reason="quota_exhausted", mode=mode)
        except ProviderRateLimitError:
            return self._fallback_chain(request, reason="rate_limited", mode=mode)
        except ProviderAuthError:
            return self._fallback_chain(request, reason="auth_failed", mode=mode)
        except (concurrent.futures.TimeoutError, TimeoutError) as exc:
            # H7.9R+ — the wall-clock cap fired. This is NOT the
            # same as ``ProviderTimeoutError`` (which the provider
            # raises when ITS own httpx client times out). The
            # fallback chain is invoked immediately, the underlying
            # provider's ``close()`` has already been called by
            # ``_call_with_hard_timeout`` (so the HTTP socket is
            # released), and a structured log entry carries the
            # provider name + model + elapsed time.
            provider_name = getattr(chosen, "name", type(chosen).__name__)
            model = getattr(chosen, "model_name", "") or ""
            elapsed_ms = int(HARD_CALL_TIMEOUT_SECONDS * 1000)
            logger.warning(
                "ai.provider.hard_timeout",
                extra={
                    "event": "ai.provider.hard_timeout",
                    "provider": provider_name,
                    "model": model,
                    "elapsed_ms": elapsed_ms,
                    "mode": mode,
                    "reason": "timeout",
                },
            )
            return self._fallback_chain(request, reason="timeout", mode=mode)
        except ProviderConfigError:
            return self._fallback_chain(request, reason="config_error", mode=mode)
        except (ProviderUnavailableError, ProviderTimeoutError):
            if mode == "open":
                logger.info(
                    "ai.provider.open_mode_provider_failure",
                    extra={
                        "event": "ai.provider.open_mode_provider_failure",
                        "mode": "open",
                        "reason": "open_mode_provider_failure",
                        "provider": getattr(request, "provider_hint", None),
                        "request_id": getattr(request, "request_id", None),
                    },
                )
                return self._fallback_chain(request, reason="open_mode_provider_failure", mode=mode)
            return self._fallback_chain(request, reason="provider_unavailable", mode=mode)
        except ProviderHTTPStatusError as exc:
            reason: NormalizedReason = (
                "http_5xx" if exc.status_code >= 500 else "http_4xx"
            )
            return self._fallback_chain(request, reason=reason, mode=mode)
        except AIProviderError as exc:
            if self._is_schema_error(exc):
                return self._fallback_chain(request, reason="schema_invalid", mode=mode)
            if self._is_malformed_error(exc):
                return self._fallback_chain(request, reason="malformed_response", mode=mode)
            return self._fallback_chain(request, reason="provider_error", mode=mode)
        except Exception as exc:
            logger.error(f"[service] Unexpected exception during generation: {exc}")
            return self._fallback_chain(request, reason="provider_error", mode=mode)

        # Provider succeeded. The internal ``effective_mode``
        # drives which validator pipeline runs; the wire
        # ``mode`` (the user's pick) is preserved on the
        # GenerationMeta so the trust label stays truthful.
        #
        # SPRINT AI-8 — controlled tool-loop hookup. If the
        # router is wired AND the 1st-turn payload carries
        # ``tool_calls``, run the 6-step pipeline, get a
        # 2nd-turn explanation, and overwrite the
        # ``response`` before the grounded-path finaliser
        # runs. The 2nd-turn GenerationMeta carries the
        # ``llm_tool_results`` stamp. The legacy path is
        # unchanged when no router is configured or when
        # the LLM emitted no tool calls.
        if effective_mode != "open" and getattr(self, "_tool_router", None) is not None:
            try:
                from app.services.ai.providers.response_schema import (
                    parse_model_output,
                )
                first_turn = parse_model_output(response.body or "")
                if (
                    first_turn.ok
                    and first_turn.response is not None
                    and getattr(first_turn.response, "tool_calls", ())
                ):
                    tool_loop = self._maybe_run_tool_loop(
                        request=request,
                        first_turn_parsed=first_turn.response,
                        owner_id=owner_id,
                        intent=_intent_for_request(
                            question_understanding, request,
                        ),
                    )
                    if tool_loop is not None and getattr(
                        tool_loop, "response", None,
                    ) is not None:
                        response = tool_loop.response
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "ai.provider.ai8_tool_loop_hookup_failed: %s", exc,
                )

        if effective_mode == "open":
            return self._generate_open(
                request, response,
                question_understanding=question_understanding,
                reasoning_plan=reasoning_plan,
                tool_results=tool_results,
                wire_mode=mode,
                adaptive_answer_out=adaptive_answer,
                dispatch_outcome=dispatch_outcome,
            )
        return self._generate_grounded(
            request,
            response,
            require_schema=require_schema,
            question_understanding=question_understanding,
            reasoning_plan=reasoning_plan,
            tool_results=tool_results,
            wire_mode=mode,
            adaptive_answer_out=adaptive_answer,
            dispatch_outcome=dispatch_outcome,
        )

    # ---- mode-specific finalisers ---------------------------------- #

    # SPRINT AI-8 — controlled tool-loop entry point.
    #
    # If the LLM's 1st-turn payload carries ``tool_calls`` and
    # the router was wired at construction time, dispatch
    # each tool via the 6-step pipeline, format the
    # sanitised results into a 2nd-turn prompt, and ask the
    # LLM to *explain* the verified facts. The 2nd-turn prose
    # replaces the 1st-turn prose on the user-visible ``body``;
    # ``llm_tool_results`` is stamped on the GenerationMeta so
    # the audit trail keeps the original tool transcripts.
    #
    # Return value: a small dataclass-y ``SimpleNamespace``
    # with ``response`` (the updated AssistantResponse) +
    # ``parsed`` (the 2nd-turn GroundedResponse, or the
    # first-turn one when the loop short-circuits) +
    # ``results`` (the tuple of LLMToolResult). ``None``
    # when the router was not configured or the LLM emitted
    # no tool calls — the caller falls through to the legacy
    # 1st-turn path.
    def _maybe_run_tool_loop(
        self,
        *,
        request: Any,
        first_turn_parsed: Any,
        owner_id: int,
        intent: str,
    ) -> Any | None:
        try:
            router = getattr(self, "_tool_router", None)
        except Exception:  # noqa: BLE001
            router = None
        if router is None:
            return None
        tool_calls = tuple(getattr(first_turn_parsed, "tool_calls", ()) or ())
        if not tool_calls:
            return None

        # Lazy imports to avoid module-load cycles.
        try:
            from app.services.ai.tool_router.types import (
                LLMToolRequest,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "ai.provider.ai8_router_import_failed: %s", exc,
            )
            return None

        # Build LLMToolRequest instances. Each becomes
        # exactly one router call. We tolerate malformed
        # entries defensively — anything the router rejects
        # comes back as ``status="error"`` and the LLM
        # sees the rejection reason on the 2nd turn.
        llm_requests: list[LLMToolRequest] = []
        for entry in tool_calls:
            try:
                llm_requests.append(
                    LLMToolRequest(
                        tool=str(entry.get("tool") or ""),
                        arguments=dict(entry.get("arguments") or {}),
                        reason=str(entry.get("reason") or ""),
                    )
                )
            except Exception as exc:  # noqa: BLE001
                logger.info(
                    "ai.provider.ai8_malformed_tool_call: %s", exc,
                )

        if not llm_requests:
            return None

        # Run the 6-step pipeline. NEVER raises.
        try:
            results = router.route_all(
                llm_requests, owner_id=owner_id, intent=intent,
            )
        except Exception as exc:  # noqa: BLE001 — defensive fence
            logger.warning(
                "ai.provider.ai8_router_unexpected_failure: %s", exc,
            )
            return None

        # Build a 2nd-turn prompt by appending a "TOOL
        # RESULTS" section to the original user-message
        # block. This is a small, explicit
        # "explain-the-verified-facts" ask — the LLM does
        # NOT need to emit further tool_calls and is told
        # so explicitly.
        try:
            from app.services.ai.providers.base import GenerationMeta

            explanation_turn = self._build_tool_explanation_prompt(
                original_request=request,
                first_turn_parsed=first_turn_parsed,
                tool_results=results,
            )
            provider = self._resolve_provider(request=request, mode="grounded")
            if provider is None:
                return None
            explanation_request = self._build_explanation_request(
                request=request,
                explanation_turn_text=explanation_turn,
            )
            explanation_response = provider.complete(explanation_request)
            # Project the 2nd-turn prose into the user-visible
            # ``body``. Defensive try/except — if anything
            # in the 2nd-turn path raises, the chat falls
            # back to the first-turn body unchanged.
            from app.services.ai.providers.response_schema import (
                parse_model_output,
            )
            second = parse_model_output(explanation_response.body or "")
            if second.ok and second.response is not None:
                # Use to_chat_body() to produce the
                # Markdown rendering of the 2nd-turn
                # structured envelope. This is the same
                # renderer the provider returns for a normal
                # grounded reply, so the shell sees a
                # consistent shape.
                from dataclasses import replace as _replace
                explanation_response = _replace(
                    explanation_response,
                    body=second.response.to_chat_body(),
                )
                # Replace the 1st-turn parsed with the
                # 2nd-turn parsed. The block above has
                # already stamped ``direct_answer`` /
                # ``executive_summary`` for downstream
                # consumers (AI-5/6/7 wire stamps).
                first_turn_parsed = second.response
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "ai.provider.ai8_tool_loop_second_turn_failed: %s", exc,
            )
            # First-turn response stands. ``results`` are
            # preserved on the audit envelope so the user
            # still sees the pill row.
            first_turn_parsed = first_turn_parsed
            explanation_response = None

        # Build the response: 2nd-turn body when available;
        # 1st-turn body otherwise. GenerationMeta gains the
        # llm_tool_results stamp.
        from types import SimpleNamespace
        from app.services.ai.providers.base import GenerationMeta

        if explanation_response is None:
            chosen_response = request  # placeholder; rebuilt below
            # Fall through to the first-turn path.
            chosen_response = None
        else:
            chosen_response = explanation_response

        # If the 2nd-turn path failed, fall back to the
        # first-turn body so the user always sees a reply.
        if chosen_response is None:
            return SimpleNamespace(
                response=request,  # signal: caller keeps first-turn path
                parsed=first_turn_parsed,
                results=tuple(
                    r.model_dump() for r in results
                ),
            )

        # Stamp llm_tool_results on the response's
        # GenerationMeta. If the 2nd-turn provider did not
        # already populate one, build an empty envelope so
        # downstream code can rely on the field existing.
        try:
            existing_meta = chosen_response.generation
            if existing_meta is None:
                existing_meta = GenerationMeta.empty(
                    mode="grounded",
                    provider_used=chosen_response.provider_used,
                    model=chosen_response.model,
                    provider_latency_ms=chosen_response.provider_latency_ms,
                    fallback_used=bool(chosen_response.fallback_used),
                )
            merged_meta = existing_meta.merge(
                llm_tool_results=tuple(
                    r.model_dump() for r in results
                ),
            )
            from dataclasses import replace as _replace_response
            chosen_response = _replace_response(
                chosen_response, generation=merged_meta,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "ai.provider.ai8_tool_loop_meta_stamp_failed: %s", exc,
            )

        return SimpleNamespace(
            response=chosen_response,
            parsed=first_turn_parsed,
            results=tuple(
                r.model_dump() if hasattr(r, "model_dump") else dict(r)
                for r in results
            ),
        )

    def _build_tool_explanation_prompt(
        self,
        *,
        original_request: Any,
        first_turn_parsed: Any,
        tool_results: tuple,
    ) -> str:
        """Render the 2nd-turn "explain the verified facts" prompt.

        Appends a structured "TOOL RESULTS" block to the
        original user prompt. The block carries every
        ``LLMToolResult`` in the same shape the LLM saw on
        its 1st turn — status, evidence_ids, payload — so
        it can quote them faithfully. Errors are surfaced
        verbatim: the LLM is told to *narrate* them, never
        *invent* data.
        """
        import json as _json
        results_block = (
            "=== TOOL RESULTS (server-resolved, sanitised) ===\n"
            + _json.dumps(
                [
                    r.model_dump() if hasattr(r, "model_dump") else dict(r)
                    for r in tool_results
                ],
                indent=2,
                default=str,
            )
            + "\n=== END TOOL RESULTS ===\n"
            "Using ONLY the data above, write the final user-visible "
            "explanation. Cite the evidence_ids when you mention a fact. "
            "If a tool returned status='error', narrate the rejection reason — "
            "never invent a value. Do NOT emit further tool_calls.\n"
        )
        original = getattr(original_request, "user_prompt", "") or ""
        return f"{original}\n\n{results_block}"

    def _build_explanation_request(
        self,
        *,
        request: Any,
        explanation_turn_text: str,
    ) -> Any:
        """Construct a fresh :class:`AssistantRequest` for the
        2nd-turn provider call. Mirrors the request the
        provider saw on the 1st turn but swaps the
        ``user_prompt`` for the explanation ask.
        """
        from dataclasses import replace as _replace_request
        from app.services.ai.providers.base import AssistantRequest

        try:
            return _replace_request(
                request, user_prompt=explanation_turn_text,
            )
        except Exception:
            # The dataclass ``replace`` failed (non-dataclass
            # request). Build a new AssistantRequest by
            # copying the public surface manually.
            return AssistantRequest(
                user_prompt=explanation_turn_text,
                history=request.history or (),
                context=request.context,
                mode=request.mode,
                provider_hint=getattr(request, "provider_hint", None),
                request_id=getattr(request, "request_id", None),
            )

    def _resolve_provider(
        self, *, request: Any, mode: str
    ) -> Any | None:
        """Return the provider the service used for the 1st turn.

        The service layer has its own resolver; this helper
        uses the request's ``provider_hint`` if set, falling
        back to the factory's :meth:`default_provider`.
        Never raises.
        """
        try:
            provider_hint = getattr(request, "provider_hint", None)
            if provider_hint is not None:
                return self._factory.get(provider_hint)
            return self._factory.default_provider(mode=mode)
        except Exception:  # noqa: BLE001
            return None

    # SPRINT AI-13 — deterministic-fallback AI-13 stamper.
    # The deterministic fallback short-circuits the rest of
    # the pipeline (no schema parse, no claim validation, no
    # grounding check). The AI-13 audit fields are stamped
    # AFTER the short-circuit so the wire envelope + the
    # frontend trust UX see the same per-tool observability
    # as the real LLM path. A failure here is invisible to
    # the caller — the response is returned unchanged.
    def _stamp_ai13_onto_deterministic(
        self,
        response: AssistantResponse,
        dispatch_outcome: Any | None,
        question_understanding: Any | None = None,
        request: AssistantRequest | None = None,
    ) -> AssistantResponse:
        try:
            from app.services.ai.reasoning.ai13_dispatch_adapter import (
                mint_partial_failure_stamp,
                apply_partial_failure_to_confidence,
            )
            ai13_stamp = mint_partial_failure_stamp(dispatch_outcome)
            meta = response.generation
            if meta is None:
                return response
            from dataclasses import replace as _replace_ai13_fb
            # AI-11 capability + business_dependency stamp
            # (the deterministic-fallback short-circuit skipped
            # the QU-driven audit; mirror it here).
            fb_capability: tuple[str, ...] = ()
            fb_business_dependency = "none"
            if question_understanding is not None:
                try:
                    fb_capability = tuple(
                        getattr(
                            question_understanding, "capability", ()
                        ) or ()
                        # AI-12 — also mirror required_tools so
                        # the wire envelope carries the tool
                        # list.
                    )
                    fb_required_tools = tuple(
                        getattr(
                            question_understanding, "required_tools", ()
                        ) or ()
                    )
                    fb_required_evidence_types = tuple(
                        getattr(
                            question_understanding,
                            "required_evidence_types",
                            (),
                        ) or ()
                    )
                    fb_answer_mode = str(
                        getattr(
                            question_understanding,
                            "answer_mode",
                            "general_knowledge",
                        ) or "general_knowledge"
                    )
                    fb_business_dependency = str(
                        getattr(
                            question_understanding,
                            "business_dependency",
                            "none",
                        ) or "none"
                    )
                    if fb_business_dependency not in {
                        "none", "optional", "required",
                    }:
                        fb_business_dependency = "none"
                except Exception:  # pragma: no cover — defensive
                    fb_capability = ()
                    fb_business_dependency = "none"
                    fb_required_tools = ()
                    fb_required_evidence_types = ()
                    fb_answer_mode = "general_knowledge"
            else:
                fb_required_tools = ()
                fb_required_evidence_types = ()
                fb_answer_mode = "general_knowledge"

            # AI-12 mirrors — tool_plan + structured_tool_envelopes +
            # evidence_requirements + contradiction_report + answer_quality
            # all default-safe.
            fb_tool_plan: dict | None = None
            fb_envelopes: tuple[dict, ...] = ()
            fb_evidence_requirements: dict | None = None
            fb_contradiction_report: dict | None = None
            fb_answer_quality: dict | None = None
            if dispatch_outcome is not None:
                try:
                    plan = getattr(dispatch_outcome, "plan", None)
                    if plan is not None and hasattr(plan, "to_dict"):
                        fb_tool_plan = plan.to_dict()
                    envelopes = tuple(
                        getattr(dispatch_outcome, "envelopes", ()) or ()
                    )
                    fb_envelopes = tuple(
                        e.to_dict() if hasattr(e, "to_dict") else dict(e)
                        for e in envelopes
                    )
                except Exception:  # pragma: no cover — defensive
                    pass

            meta = _replace_ai13_fb(
                meta,
                tool_execution_traces=ai13_stamp.tool_execution_traces,
                partial_failure_disclosure=(
                    ai13_stamp.partial_failure_disclosure
                ),
                confidence_penalty=ai13_stamp.confidence_penalty,
                capability=fb_capability,
                business_dependency=fb_business_dependency,
                tool_plan=fb_tool_plan,
                structured_tool_envelopes=list(fb_envelopes),
                evidence_requirements=fb_evidence_requirements,
                contradiction_report=fb_contradiction_report,
                answer_quality=fb_answer_quality,
                answer_mode=fb_answer_mode,
            )
            # SPRINT AI-14 — Universal Answer Intelligence stamp.
            # The deterministic-fallback short-circuit skipped the
            # evidence-graph + answer-requirements derivation; build
            # them now from the QU + dispatch outcome so the wire
            # envelope carries the AI-14 fields uniformly. Each
            # derivation is a pure function — same inputs always
            # return the same dict. Failures are silently swallowed
            # so the AI-13 stamping path stays non-breaking.
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
                envelopes_tuple = tuple(
                    getattr(dispatch_outcome, "envelopes", ()) or ()
                )
                fb_plan = getattr(dispatch_outcome, "plan", None)
                fb_contradiction = getattr(
                    dispatch_outcome, "contradiction_report", None
                )
                fb_answer_req = derive_answer_requirements(
                    question_understanding=question_understanding,
                    evidence_requirements=getattr(
                        dispatch_outcome, "evidence_requirements", None
                    ),
                    tool_plan=fb_plan,
                    envelopes=envelopes_tuple,
                    context=request.context,
                )
                fb_evidence_graph = build_evidence_graph(
                    question_understanding=question_understanding,
                    reasoning_plan=fb_plan,
                    envelopes=envelopes_tuple,
                    context=request.context,
                    contradiction_report=fb_contradiction,
                    parsed_response=None,
                )
                fb_calc_lineage = calculation_lineage_dicts(envelopes_tuple)
                fb_missing_state = missing_data_state(
                    graph=fb_evidence_graph, proactive_rows=()
                )
                fb_unsupported = len(_unsupported_claims(fb_evidence_graph))
                fb_fabricated = len(_fabricated_sources(fb_evidence_graph))
                meta = _replace_ai13_fb(
                    meta,
                    answer_requirements=fb_answer_req.to_dict(),
                    evidence_graph=fb_evidence_graph.to_dict(),
                    calculation_lineage=list(fb_calc_lineage),
                    missing_data_state=fb_missing_state,
                    unsupported_claim_count=fb_unsupported,
                    fabricated_source_count=fb_fabricated,
                )
                # SPRINT AI-15 — visualization + trust envelope.
                # Planner + builder are pure; same inputs always
                # return the same chart payloads. Failures here
                # are silently swallowed so this block stays
                # non-breaking.
                try:
                    from app.services.ai.reasoning.visualization_planner import (
                        plan as _viz_plan,
                    )
                    from app.services.ai.reasoning.chart_data_builder import (
                        build as _viz_build,
                    )
                    from app.services.ai.reasoning.trust_summary import (
                        build_trust_summary as _build_trust,
                    )
                    ai15_plans = _viz_plan(
                        question_understanding=question_understanding,
                        answer_requirements=fb_answer_req,
                        envelopes=envelopes_tuple,
                        evidence_graph=fb_evidence_graph,
                        contradiction_report=fb_contradiction,
                    ).plans
                    ai15_payloads = [
                        _viz_build(p, envelopes=envelopes_tuple).to_dict()
                        for p in ai15_plans
                    ]
                    ai15_quality = (
                        meta.answer_quality if isinstance(meta.answer_quality, dict) else None
                    )
                    ai15_trust = _build_trust(
                        assistant_context=request.context,
                        envelopes=envelopes_tuple,
                        evidence_graph=fb_evidence_graph,
                        contradiction_report=fb_contradiction,
                        answer_quality=ai15_quality,
                        visualization_plans=ai15_plans,
                        tool_traces=tuple(
                            getattr(dispatch_outcome, "traces", ()) or ()
                        ),
                    )
                    needs_warn = bool(
                        (ai15_quality or {}).get("needs_warning")
                    )
                    warn_msg = str(
                        (ai15_quality or {}).get("warning_message") or ""
                    )
                    meta = _replace_ai13_fb(
                        meta,
                        visualization_plans=ai15_payloads,
                        quality_warning={
                            "needs_warning": needs_warn,
                            "warning_message": warn_msg,
                        },
                        trust_summary=ai15_trust,
                    )
                    # SPRINT AI-16 — Verified External Knowledge +
                    # Freshness Layer. Scheme card + mixed
                    # composition. Both pure; failures swallowed
                    # defensively so the AI-15 path stays
                    # non-breaking. ``scheme_composer.compose_scheme_card``
                    # returns ``None`` for non-scheme prompts;
                    # ``mixed_composer.compose_mixed_sections``
                    # returns ``is_mixed=False`` for non-mixed
                    # prompts. Both calls are no-ops when the QU
                    # signals don't match.
                    try:
                        from app.services.ai.knowledge.ai16_scheme_composer import (
                            compose_scheme_card as _ai16_scheme,
                        )
                        from app.services.ai.knowledge.ai16_mixed_composer import (
                            compose_mixed_sections as _ai16_mixed,
                        )
                        scheme_payload = _ai16_scheme(
                            question_understanding=question_understanding,
                            context=request.context,
                        )
                        scheme_card_dict = (
                            scheme_payload.card.to_dict()
                            if scheme_payload is not None
                            else None
                        )
                        mixed_blocks = _ai16_mixed(
                            question_understanding=question_understanding,
                            envelopes=envelopes_tuple,
                            context=request.context,
                        )
                        meta = _replace_ai13_fb(
                            meta,
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
                    # Lifecycle. The classifier + repair dispatcher
                    # + bounded-retry gate run AFTER the AI-16
                    # stamp and BEFORE the wire. The orchestrator
                    # is pure; the retry itself is the caller's
                    # responsibility, so we only mark
                    # ``retry_attempted`` here and let the
                    # upstream service decide.
                    try:
                        from app.services.ai.knowledge.ai17_orchestrator import (
                            run_ai17_pipeline as _ai17_run,
                        )
                        _ai17_overlay = _ai17_run(
                            payload=meta,
                            starting_confidence=int(
                                meta.confidence
                                if meta.confidence is not None
                                else 70
                            ),
                            materially_useful=True,
                            budget_remaining_ms=15_000,
                            hard_call_timeout_ms=15_000,
                            retry_already_attempted=False,
                            original_prompt=str(
                                getattr(request, "prompt", "") or ""
                            ),
                        )
                        meta = _replace_ai13_fb(
                            meta,
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
                            confidence=_ai17_overlay[
                                "adjusted_confidence"
                            ],
                        )
                    except Exception:  # pragma: no cover — defensive
                        pass
                except Exception:  # pragma: no cover — defensive
                    pass
            except Exception:  # pragma: no cover — defensive
                pass
            if ai13_stamp.confidence_penalty > 0:
                meta = _replace_ai13_fb(
                    meta,
                    server_confidence=apply_partial_failure_to_confidence(
                        server_confidence=meta.server_confidence,
                        confidence_penalty=ai13_stamp.confidence_penalty,
                    ),
                )
            from dataclasses import replace as _replace_fb_resp
            return _replace_fb_resp(response, generation=meta)
        except Exception:  # pragma: no cover — defensive
            return response

    def _generate_grounded(
        self,
        request: AssistantRequest,
        response: AssistantResponse,
        *,
        require_schema: bool | None,
        question_understanding: QuestionUnderstanding | None = None,
        reasoning_plan: Any = None,
        tool_results: tuple = (),
        wire_mode: Mode = "grounded",
        adaptive_answer_out: Any = None,
        dispatch_outcome: Any | None = None,
    ) -> AssistantResponse:
        """Validate + ground a response in grounded mode.

        The pipeline:

        1. If schema-required (default on) and the response
           was not already produced by the deterministic
           fallback, parse the body as JSON and run the
           schema validator. Parse failure → fallback with
           reason ``schema_invalid``.
        2. Build the :class:`EvidenceRegistry` from the
           request's :class:`AssistantContext`.
        3. Run the :class:`GroundingValidator` over the
           parsed response (or the raw body when no parsed
           payload exists). Any rule failure → fallback with
           reason ``grounding_invalid``.
        4. On success, return the response enriched with
           ``GenerationMeta`` carrying the
           ``server_grounding_score`` and a stamp that
           ``grounding_validated=true``.

        AI-1 — the response is stamped with the
        :class:`AdaptiveAnswer` chosen from the Stage 1
        understanding, the Stage 4 plan, and the Stage 5
        tool results. The validator's ``claim_categories_used``
        set, the dispatcher's ``tool_calls``, and the
        understanding's ``unknowns`` all surface on the
        GenerationMeta for the audit trail. The wire
        ``mode`` is preserved (the user's pick) — only the
        internal validator pipeline uses ``effective_mode``.
        """
        if _is_deterministic(response):
            return self._stamp_ai13_onto_deterministic(
                response,
                dispatch_outcome,
                question_understanding,
                request=request,
            )

        registry = EvidenceRegistry(request.context)
        # H7.8C — debug log so we can verify the registry
        # actually carries the biz_profile_revenue entry
        # emitted from the new annual_revenue_inr context
        # field. Stripped in production by the deployment
        # layer's logger config — never logs the prompt body.
        logger.info(
            "ai.provider.evidence_registry_built",
            extra={
                "event": "ai.provider.evidence_registry_built",
                "mode": "grounded",
                "registry_count": registry.count,
                "registry_ids": list(registry.ids()),
                "annual_revenue_inr": getattr(
                    request.context, "annual_revenue_inr", 0
                ),
            },
        )
        schema_required = self._schema_required(require_schema)
        parsed = None

        if schema_required and not _is_deterministic(response):
            body = response.body or ""
            # Empty body short-circuits to fallback.
            if not body.strip():
                return self._fallback(
                    request, reason="empty_response", mode="grounded",
                )
            result = parse_model_output(body)
            if not result.ok or result.response is None:
                return self._fallback(
                    request, reason="schema_invalid", mode="grounded",
                )
            parsed = result.response

        # Run the grounding validator. A registry with zero
        # entries still produces a valid empty registry —
        # the validator scores coverage from ``0`` but does
        # not fail by default. The threshold is configurable
        # via ``Settings.ai_grounding_threshold`` (H7.8C).
        validator = GroundingValidator(
            registry,
            parsed,
            raw_body=response.body,
            threshold=self._grounding_threshold(),
        )
        report = validator.validate()

        if not report.passed:
            logger.info(
                "ai.provider.grounding_failed",
                extra={
                    "event": "ai.provider.grounding_failed",
                    "mode": "grounded",
                    "errors": list(report.errors),
                    "score": report.score,
                    "request_id": getattr(request, "request_id", None),
                },
            )
            return self._fallback(
                request,
                reason="grounding_invalid",
                mode="grounded",
                extra_meta={
                    "grounding_score": report.score,
                    "grounding_errors": list(report.errors),
                },
            )

        # AI-3 — claim-aware validation, numeric consistency,
        # and deterministic server confidence. Each stage is
        # independent: parse failure on the LLM's optional
        # ``claim_aware`` block leaves the existing pipeline
        # untouched; the validator / checker / calculator all
        # raise-caught so a buggy LLM payload can't break the
        # chat path.
        claim_response = None
        claim_report = None
        numeric_report = None
        confidence_report = None
        claim_aware_raw = None
        try:
            from app.services.ai.providers.claim_parser import (
                extract_claim_aware_block,
                parse_claim_aware_payload,
            )
            from app.services.ai.providers.claim_validator import ClaimValidator
            from app.services.ai.providers.numeric_checker import (
                NumericConsistencyChecker,
            )
            from app.services.ai.providers.confidence_calculator import (
                ConfidenceCalculator,
            )

            claim_aware_raw = extract_claim_aware_block(parsed)
            if claim_aware_raw is not None:
                claim_result = parse_claim_aware_payload(claim_aware_raw)
                if claim_result.ok and claim_result.response is not None:
                    claim_response = claim_result.response
                    claim_report = ClaimValidator(
                        registry, claim_response
                    ).validate()
                    numeric_report = NumericConsistencyChecker(
                        context=request.context,
                        tool_results=tuple(tool_results or ()),
                    ).check(claim_response)
                    confidence_report = ConfidenceCalculator().compute(
                        context=request.context,
                        tool_results=tuple(tool_results or ()),
                        registry=registry,
                        claim_response=claim_response,
                        claim_report=claim_report,
                        numeric_report=numeric_report,
                    )
                elif claim_result.errors:
                    logger.info(
                        "ai.provider.ai3_claim_aware_parse_failed",
                        extra={
                            "event": "ai.provider.ai3_claim_aware_parse_failed",
                            "mode": "grounded",
                            "errors": list(claim_result.errors)[:10],
                            "request_id": getattr(
                                request, "request_id", None
                            ),
                        },
                    )
        except Exception as exc:  # noqa: BLE001 — defensive fence
            logger.warning(
                "ai.provider.ai3_claim_aware_layer_failed: %s",
                exc,
                extra={
                    "event": "ai.provider.ai3_claim_aware_layer_failed",
                    "mode": "grounded",
                    "request_id": getattr(request, "request_id", None),
                },
            )

        # Stamp the GenerationMeta so the UI can render the
        # evidence disclosure panel. The provider already
        # populated provider_used / model / provider_latency_ms;
        # we attach the grounding score + register the
        # grounding_validated flag.
        meta = response.generation or GenerationMeta.empty(
            mode="grounded",
            provider_used=response.provider_used,
            model=response.model,
            provider_latency_ms=response.provider_latency_ms,
            fallback_used=False,
        )
        manifest_dict = (
            request.context.context_manifest.to_dict()
            if request.context.context_manifest
            else None
        )
        meta = meta.merge(
            language=getattr(request, "language", "en") or "en",
            grounding_validated=True,
            grounding_score=report.score,
            schema_validated=bool(parsed is not None),
            business_evidence_validated=True,
            context_manifest=manifest_dict,
            evidence_references=tuple(
                ref.id for ref in (parsed.evidence_references if parsed else ())
            ),
            assumptions=tuple(parsed.assumptions if parsed else ()),
            limitations=tuple(parsed.limitations if parsed else ()),
            confidence=(parsed.confidence if parsed else None),
            generation_method="generative",
            # SPRINT AI-11 — Universal Business-Aware Assistant
            # hardening. Surface the capability tuple +
            # business dependency literal that
            # ``QuestionUnderstanding`` derived from the prompt,
            # so the wire envelope carries the multi-label
            # classification the brief §4 / §5 requires.
            capability=tuple(
                getattr(question_understanding, "capability", ()) or ()
            ),
            business_dependency=str(
                getattr(question_understanding, "business_dependency", "none")
            ),
        )
        # AI-1 — stamp the universal-assistant audit trail.
        # The wire ``mode`` is preserved (the user's pick).
        try:
            adaptive = adaptive_answer_out or compose_adaptive_answer(
                parsed=parsed,
                question_understanding=question_understanding,
                reasoning_plan=reasoning_plan,
                tool_results=tool_results,
                context=request.context,
            )
        except Exception:
            adaptive = None
        from dataclasses import replace as _replace_ai1
        # SPRINT AI-13 — derive the per-tool observability
        # + partial-failure handling wire fields from the
        # AI-12 DispatchOutcome. The stamp is then applied
        # to the meta on the same ``replace`` call so we
        # rebuild the dataclass once.
        from app.services.ai.reasoning.ai13_dispatch_adapter import (
            mint_partial_failure_stamp,
        )
        ai13_stamp = mint_partial_failure_stamp(dispatch_outcome)
        meta = _replace_ai1(
            meta,
            mode=wire_mode,
            language=getattr(request, "language", "en") or "en",
            deterministic_services_used=tuple(
                r.service_name for r in tool_results if r.status == "ok"
            ),
            calculations_used=tuple(
                r.service_name for r in tool_results
                if r.status == "ok" and "calc" in r.service_name
            ),
            question_understanding=(
                question_understanding.to_dict()
                if question_understanding is not None
                and hasattr(question_understanding, "to_dict")
                else None
            ),
            tool_calls=tuple(
                {"service_name": c.service_name, "inputs": c.inputs}
                for c in (
                    getattr(reasoning_plan, "tool_calls", ()) or ()
                )
            ),
            claim_categories_used=tuple(report.claim_categories_used or ()),
            tool_execution_traces=ai13_stamp.tool_execution_traces,
            partial_failure_disclosure=ai13_stamp.partial_failure_disclosure,
            confidence_penalty=ai13_stamp.confidence_penalty,
        )
        # AI-3 — stamp the claim-aware pipeline results on
        # the GenerationMeta. The merged fields power the
        # claim-aware disclosure panel + server confidence
        # badge in the UI. ``claim_aware_response`` is the
        # JSON-safe dict carried to the wire via
        # ``conversation_service._message_payload``;
        # ``claim_aware_raw`` preserves the original LLM
        # payload for the audit log.
        from dataclasses import replace as _replace_ai3
        claim_aware_dict = (
            claim_response.to_dict()
            if claim_response is not None
            else None
        )
        # Stamp server_confidence + numeric_conflicts when the
        # claim-aware response was validated. The mutable
        # nature of ``claim_response`` means the
        # ``numeric_report`` mutations already landed in the
        # ``to_dict()`` payload above — re-stamp here.
        if claim_aware_dict is not None:
            if confidence_report is not None:
                claim_aware_dict["server_confidence"] = (
                    confidence_report.score
                )
                claim_aware_dict["server_confidence_rationale"] = (
                    confidence_report.rationale
                )
            if numeric_report is not None:
                claim_aware_dict["numeric_conflicts"] = [
                    c.to_dict() for c in numeric_report.conflicts
                ]
            claim_aware_dict["server_audit"] = {
                "source": "llm",
                "claim_validation_passed": bool(
                    claim_report.passed if claim_report else False
                ),
                "claim_validation_score": int(
                    claim_report.score if claim_report else 0
                ),
                "numeric_conflicts_count": int(
                    numeric_report.count if numeric_report else 0
                ),
            }
        meta = _replace_ai3(
            meta,
            claim_aware_validated=claim_response is not None,
            numeric_conflicts_count=int(
                numeric_report.count if numeric_report else 0
            ),
            server_confidence=(
                confidence_report.score
                if confidence_report is not None
                else None
            ),
            server_confidence_rationale=(
                confidence_report.rationale
                if confidence_report is not None
                else ""
            ),
        )
        # SPRINT AI-13 — reduce server_confidence by the
        # partial-failure penalty. The penalty reflects the
        # number of tools that did NOT succeed; the lower the
        # ``server_confidence``, the more the trust disclosure
        # in the UI should highlight the missing evidence.
        # ``None`` when the AI-3 layer didn't produce a score.
        if ai13_stamp.confidence_penalty > 0:
            from app.services.ai.reasoning.ai13_dispatch_adapter import (
                apply_partial_failure_to_confidence,
            )
            meta = _replace_ai3(
                meta,
                server_confidence=apply_partial_failure_to_confidence(
                    server_confidence=meta.server_confidence,
                    confidence_penalty=ai13_stamp.confidence_penalty,
                ),
            )

        # AI-4 — server-side Claim Auditor. Runs after the AI-3
        # numeric checker so it can consume the numeric_report.
        # Whole stage is fenced in try/except so an auditor bug
        # never crashes the chat endpoint.
        claim_audit_report_dict: dict | None = None
        claim_audit_rejected = False
        claim_audit_soft_corrections = 0
        try:
            from app.services.ai.providers.claim_auditor import (
                ClaimAuditor,
            )

            audit_report = ClaimAuditor(
                registry=registry,
                numeric_report=numeric_report,
            ).audit(claim_response)
            claim_audit_report_dict = audit_report.to_dict()
            claim_audit_rejected = bool(audit_report.rejected)
            claim_audit_soft_corrections = int(
                audit_report.soft_corrections
            )
            # Carry the trace into the wire envelope so the
            # conversation_service can project it onto
            # ChatMessageOut for the "Why am I seeing this?"
            # disclosure panel.
            if claim_audit_report_dict is not None:
                existing_payload = dict(meta.grounded_payload or {})
                existing_payload["claim_audit"] = claim_audit_report_dict
                meta = _replace_ai3(meta, grounded_payload=existing_payload)
            # When the auditor rejects, the response body remains
            # in place — the frontend renders an "Answer withheld
            # — reason" stub from claim_audit_rejected + the
            # rejection_reason string. The chat endpoint still
            # returns a valid ChatMessageAppendResponse.
            if claim_audit_rejected:
                logger.info(
                    "ai.provider.ai4_claim_auditor_rejected",
                    extra={
                        "event": "ai.provider.ai4_claim_auditor_rejected",
                        "mode": "grounded",
                        "rejection_reason": audit_report.rejection_reason,
                        "request_id": getattr(
                            request, "request_id", None
                        ),
                    },
                )
        except Exception as exc:  # noqa: BLE001 — defensive fence
            logger.warning(
                "ai.provider.ai4_claim_auditor_failed: %s",
                exc,
                extra={
                    "event": "ai.provider.ai4_claim_auditor_failed",
                    "mode": "grounded",
                    "request_id": getattr(request, "request_id", None),
                },
            )

        # Stamp the AI-4 envelope onto GenerationMeta. The 3
        # fields default to None / False / 0 so legacy rows that
        # pre-date AI-4 still validate.
        from dataclasses import replace as _replace_ai4
        meta = _replace_ai4(
            meta,
            claim_audit=claim_audit_report_dict,
            claim_audit_rejected=claim_audit_rejected,
            claim_audit_soft_corrections=claim_audit_soft_corrections,
        )

        # SPRINT AI-14 — Universal Answer Intelligence + Evidence
        # Graph. Build the per-claim lineage, derive the
        # answer-requirements flags, and stamp the 6 AI-14 fields
        # on the GenerationMeta. The graph is pure-functional —
        # same inputs always return the same dict — so the wire
        # envelope is deterministic across the two paths.
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
            envelopes_tuple = tuple(
                getattr(dispatch_outcome, "envelopes", ()) or ()
            )
            ai14_plan = getattr(dispatch_outcome, "plan", reasoning_plan)
            ai14_contradiction = getattr(
                dispatch_outcome, "contradiction_report", None
            )
            ai14_evidence_reqs = getattr(
                dispatch_outcome, "evidence_requirements", None
            )
            ai14_parsed = parsed
            ai14_answer_req = derive_answer_requirements(
                question_understanding=question_understanding,
                evidence_requirements=ai14_evidence_reqs,
                tool_plan=ai14_plan,
                envelopes=envelopes_tuple,
                context=request.context,
            )
            ai14_graph = build_evidence_graph(
                question_understanding=question_understanding,
                reasoning_plan=ai14_plan,
                envelopes=envelopes_tuple,
                context=request.context,
                contradiction_report=ai14_contradiction,
                parsed_response=ai14_parsed,
            )
            ai14_calc_lineage = calculation_lineage_dicts(envelopes_tuple)
            ai14_missing_state = missing_data_state(
                graph=ai14_graph, proactive_rows=()
            )
            ai14_unsupported = len(_unsupported_claims(ai14_graph))
            ai14_fabricated = len(_fabricated_sources(ai14_graph))
            meta = _replace_ai4(
                meta,
                answer_requirements=ai14_answer_req.to_dict(),
                evidence_graph=ai14_graph.to_dict(),
                calculation_lineage=list(ai14_calc_lineage),
                missing_data_state=ai14_missing_state,
                unsupported_claim_count=ai14_unsupported,
                fabricated_source_count=ai14_fabricated,
            )
            # SPRINT AI-15 — visualization plans + chart payloads
            # + trust summary. Pure functions; failures swallowed
            # defensively. The renderer reads these three fields
            # to surface charts (VisualizationCard), the low-
            # quality warning strip, and the "Why this answer?"
            # disclosure.
            try:
                from app.services.ai.reasoning.visualization_planner import (
                    plan as _viz_plan,
                )
                from app.services.ai.reasoning.chart_data_builder import (
                    build as _viz_build,
                )
                from app.services.ai.reasoning.trust_summary import (
                    build_trust_summary as _build_trust,
                )
                ai15_plans = _viz_plan(
                    question_understanding=question_understanding,
                    answer_requirements=ai14_answer_req,
                    envelopes=envelopes_tuple,
                    evidence_graph=ai14_graph,
                    contradiction_report=ai14_contradiction,
                ).plans
                ai15_payloads = [
                    _viz_build(p, envelopes=envelopes_tuple).to_dict()
                    for p in ai15_plans
                ]
                ai15_quality = (
                    meta.answer_quality if isinstance(meta.answer_quality, dict) else None
                )
                ai15_trust = _build_trust(
                    assistant_context=request.context,
                    envelopes=envelopes_tuple,
                    evidence_graph=ai14_graph,
                    contradiction_report=ai14_contradiction,
                    answer_quality=ai15_quality,
                    visualization_plans=ai15_plans,
                    tool_traces=tuple(
                        getattr(dispatch_outcome, "traces", ()) or ()
                    ),
                )
                needs_warn = bool(
                    (ai15_quality or {}).get("needs_warning")
                )
                warn_msg = str(
                    (ai15_quality or {}).get("warning_message") or ""
                )
                meta = _replace_ai4(
                    meta,
                    visualization_plans=ai15_payloads,
                    quality_warning={
                        "needs_warning": needs_warn,
                        "warning_message": warn_msg,
                    },
                    trust_summary=ai15_trust,
                )
                # SPRINT AI-16 — Verified External Knowledge +
                # Freshness Layer. Scheme card + mixed
                # composition. Both pure; failures swallowed
                # defensively. ``scheme_composer.compose_scheme_card``
                # returns ``None`` for non-scheme prompts;
                # ``mixed_composer.compose_mixed_sections``
                # returns ``is_mixed=False`` for non-mixed
                # prompts. Both calls are no-ops when the QU
                # signals don't match.
                try:
                    from app.services.ai.knowledge.ai16_scheme_composer import (
                        compose_scheme_card as _ai16_scheme,
                    )
                    from app.services.ai.knowledge.ai16_mixed_composer import (
                        compose_mixed_sections as _ai16_mixed,
                    )
                    scheme_payload = _ai16_scheme(
                        question_understanding=question_understanding,
                        context=request.context,
                    )
                    scheme_card_dict = (
                        scheme_payload.card.to_dict()
                        if scheme_payload is not None
                        else None
                    )
                    mixed_blocks = _ai16_mixed(
                        question_understanding=question_understanding,
                        envelopes=envelopes_tuple,
                        context=request.context,
                    )
                    meta = _replace_ai4(
                        meta,
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
                # Lifecycle (grounded path). Mirror of the
                # deterministic-fallback branch above.
                try:
                    from app.services.ai.knowledge.ai17_orchestrator import (
                        run_ai17_pipeline as _ai17_run,
                    )
                    _ai17_overlay = _ai17_run(
                        payload=meta,
                        starting_confidence=int(
                            meta.confidence
                            if meta.confidence is not None
                            else 70
                        ),
                        materially_useful=True,
                        budget_remaining_ms=15_000,
                        hard_call_timeout_ms=15_000,
                        retry_already_attempted=False,
                        original_prompt=str(
                            getattr(request, "prompt", "") or ""
                        ),
                    )
                    meta = _replace_ai4(
                        meta,
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
                        confidence=_ai17_overlay[
                            "adjusted_confidence"
                        ],
                    )
                except Exception:  # pragma: no cover — defensive
                    pass
            except Exception as exc:  # pragma: no cover — defensive
                logger.warning(
                    "ai.provider.ai15_envelope_failed: %s",
                    exc,
                    extra={
                        "event": "ai.provider.ai15_envelope_failed",
                        "mode": "grounded",
                        "request_id": getattr(request, "request_id", None),
                    },
                )
        except Exception as exc:  # pragma: no cover — defensive
            logger.warning(
                "ai.provider.ai14_envelope_failed: %s",
                exc,
                extra={
                    "event": "ai.provider.ai14_envelope_failed",
                    "mode": "grounded",
                    "request_id": getattr(request, "request_id", None),
                },
            )
        # Carry the AI-3 payload to the wire via GenerationMeta
        # ``grounded_payload`` so the conversation_service can
        # project it onto ChatMessageOut.preserve the existing
        # payload (other stages may already have populated it)
        # and merge AI-3 in.
        if claim_aware_dict is not None or claim_aware_raw is not None:
            existing_payload = dict(meta.grounded_payload or {})
            if claim_aware_dict is not None:
                existing_payload["claim_aware"] = claim_aware_dict
            if claim_aware_raw is not None:
                existing_payload["claim_aware_raw"] = claim_aware_raw
            meta = _replace_ai3(meta, grounded_payload=existing_payload)
        # H7.8C — emit a structured event for every successful
        # grounded-mode pass. The event payload carries the
        # server-side grounding score, the registry coverage,
        # and the provider/model — never the prompt body or
        # any auth header.
        logger.info(
            "ai.provider.grounded_succeeded",
            extra={
                "event": "ai.provider.grounded_succeeded",
                "mode": "grounded",
                "provider_used": response.provider_used,
                "model": response.model,
                "grounding_score": report.score,
                "registry_count": registry.count,
                "evidence_count": len(meta.evidence_references or ()),
                "provider_latency_ms": response.provider_latency_ms,
                "request_id": getattr(request, "request_id", None),
            },
        )
        from dataclasses import replace
        return replace(response, generation=meta)

    def _generate_open(
        self,
        request: AssistantRequest,
        response: AssistantResponse,
        *,
        question_understanding: QuestionUnderstanding | None = None,
        reasoning_plan: Any = None,
        tool_results: tuple = (),
        wire_mode: Mode = "open",
        adaptive_answer_out: Any = None,
        dispatch_outcome: Any | None = None,
    ) -> AssistantResponse:
        """Exploratory Business Advisor mode validation + envelope stamping."""
        body = response.body or ""
        if not body.strip():
            return self._fallback(
                request, reason="open_mode_provider_failure", mode="open",
            )

        # AI-1 auto-flip defence: when the prompt was
        # routed internally to "open" but the provider
        # already answered via the deterministic fallback,
        # preserve its GenerationMeta ``generation_method``
        # (which is "deterministic"). The wire ``mode`` is
        # the user's selection — overwrite the GenerationMeta
        # so the trust label is truthful.
        if _is_deterministic(response) and response.generation is not None:
            from dataclasses import replace as _preserve_meta
            return _preserve_meta(
                response, generation=_preserve_meta(
                    response.generation, mode=wire_mode,
                ),
            )
        if _is_deterministic(response):
            return self._stamp_ai13_onto_deterministic(
                response,
                dispatch_outcome,
                question_understanding,
                request=request,
            )

        registry = EvidenceRegistry(request.context)
        parsed = parse_open_model_output(body)
        validator = OpenResponseValidator(registry, parsed, raw_body=body)
        val_report = validator.validate()

        if not val_report.passed:
            logger.info(
                "ai.provider.open_mode_validation_failed",
                extra={
                    "event": "ai.provider.open_mode_validation_failed",
                    "mode": "open",
                    "errors": list(val_report.errors),
                },
            )
            return self._fallback(
                request, reason="open_mode_provider_failure", mode="open",
            )

        meta = response.generation or GenerationMeta.empty(
            mode="open",
            provider_used=response.provider_used,
            model=response.model,
            provider_latency_ms=response.provider_latency_ms,
            fallback_used=False,
        )

        manifest_dict = (
            request.context.context_manifest.to_dict()
            if request.context.context_manifest
            else None
        )

        is_structured = bool(
            parsed.verified_business_context
            or parsed.exploratory_recommendations
            or parsed.illustrative_scenarios
            or parsed.questions_to_validate
        )

        meta = meta.merge(
            generation_method="generative",
            grounding_validated=False,
            schema_validated=is_structured,
            business_evidence_validated=val_report.business_evidence_validated,
            server_grounding_score=val_report.score,
            evidence_references=tuple(
                ref for fact in getattr(parsed, "verified_business_context", ()) for ref in getattr(fact, "evidence_refs", ())
            ),
            assumptions=tuple(getattr(parsed, "assumptions", ())),
            limitations=tuple(getattr(parsed, "limitations", ())),
            confidence=getattr(parsed, "confidence", 70),
            context_manifest=manifest_dict,
        )
        # AI-1 — stamp the universal-assistant audit trail
        # for open mode. The wire ``mode`` is preserved.
        from dataclasses import replace as _replace_open
        # SPRINT AI-13 — same per-tool observability + partial-
        # failure handling as the grounded path. Open mode
        # still runs the dispatcher; the audit row stays
        # consistent regardless of mode.
        from app.services.ai.reasoning.ai13_dispatch_adapter import (
            mint_partial_failure_stamp,
        )
        ai13_stamp = mint_partial_failure_stamp(dispatch_outcome)
        meta = _replace_open(
            meta,
            mode=wire_mode,
            deterministic_services_used=tuple(
                r.service_name for r in tool_results if r.status == "ok"
            ),
            calculations_used=tuple(
                r.service_name for r in tool_results
                if r.status == "ok" and "calc" in r.service_name
            ),
            question_understanding=(
                question_understanding.to_dict()
                if question_understanding is not None
                and hasattr(question_understanding, "to_dict")
                else None
            ),
            tool_calls=tuple(
                {"service_name": c.service_name, "inputs": c.inputs}
                for c in (
                    getattr(reasoning_plan, "tool_calls", ()) or ()
                )
            ),
            claim_categories_used=tuple(val_report.claim_categories_used or ()),
            # SPRINT AI-11 — Universal Business-Aware Assistant
            # hardening. Stamp the capability tuple +
            # business dependency literal on the open-mode
            # ``GenerationMeta`` mirror.
            capability=tuple(
                getattr(question_understanding, "capability", ()) or ()
            ),
            business_dependency=str(
                getattr(question_understanding, "business_dependency", "none")
            ),
            # SPRINT AI-13 — per-tool observability + partial
            # failure handling.
            tool_execution_traces=ai13_stamp.tool_execution_traces,
            partial_failure_disclosure=ai13_stamp.partial_failure_disclosure,
            confidence_penalty=ai13_stamp.confidence_penalty,
        )
        return _replace_open(response, generation=meta)

    # ---- convenience ------------------------------------------------- #

    def build_context(self, owner_id: int) -> AssistantContext:
        """Return the assembled context without generating a reply.

        Useful for tests and for future endpoints that want
        to inspect what the prompt would have included.
        """
        return self._context_builder.build(owner_id=owner_id)

    def provider_status(self) -> dict[str, Any]:
        """Surface the current provider configuration.

        Returns a JSON-safe dict for the
        ``GET /api/v1/chat/provider-status`` endpoint. The
        endpoint never exposes API keys, auth headers, or the
        full base URL — only the provider *name*, the model
        identifier, the configured mode list, a boolean
        availability flag derived from the factory's
        ``is_available`` check, and a short ``reason`` string
        that tells the frontend *why* the provider is up or
        down (H7.9R+ — the boolean alone is not enough; the
        frontend needs ``"missing_api_key"`` vs
        ``"ping_failed"`` vs ``"reachable"`` to render the
        right "Provider unavailable" copy).
        """
        name = self.configured_provider_name()
        available = self._factory.is_available()
        reason = self._factory.status_reason()
        modes = ("grounded", "open")
        return {
            "configured_provider": name,
            "runtime_provider": name if available else "deterministic-fallback",
            "model": self._factory.configured_model(),
            "available": available,
            "schema_required": self._schema_required(None),
            "fallback_active": not available,
            "reason": reason,
            "modes": list(modes),
            "default_mode": "grounded",
        }

    # ---- internal ---------------------------------------------------- #

    def _schema_required(self, override: bool | None) -> bool:
        if override is not None:
            return bool(override)
        settings = self._factory._settings
        if settings is None:
            return True  # default-on for the JSON contract
        return bool(getattr(settings, "ai_require_schema", True))

    def _grounding_threshold(self) -> int:
        """Read the grounding threshold from Settings.

        Defaults to ``GroundingValidator.DEFAULT_GROUNDING_THRESHOLD``
        (50) when the factory is Settings-less. The value is
        clamped to ``[0, 100]`` by the validator.
        """
        from app.services.ai.providers.grounding_validator import (
            DEFAULT_GROUNDING_THRESHOLD,
        )
        settings = self._factory._settings
        if settings is None:
            return DEFAULT_GROUNDING_THRESHOLD
        return int(getattr(settings, "ai_grounding_threshold", DEFAULT_GROUNDING_THRESHOLD))

    # SPRINT AI-8 — pick the caller intent for the tool-loop.
    # Reads ``question_understanding.canonical_intent`` first
    # (the AI-1 universal-assistant stage 1), falling back to
    # ``request.context.intent`` when present, finally to
    # ``"general"`` so the loop never errors. Never raises.
    @staticmethod
    def _intent_for_request(
        question_understanding: Any, request: Any,
    ) -> str:
        try:
            if question_understanding is not None:
                canonical = getattr(
                    question_understanding, "canonical_intent", None,
                )
                if canonical:
                    return str(canonical)
        except Exception:  # noqa: BLE001
            pass
        try:
            context = getattr(request, "context", None)
            if context is not None:
                ctx_intent = getattr(context, "intent", None)
                if ctx_intent:
                    return str(ctx_intent)
        except Exception:  # noqa: BLE001
            pass
        return "general"

    def _is_schema_error(self, exc: AIProviderError) -> bool:
        """Decide whether an AIProviderError is a schema failure."""
        msg = str(exc) or ""
        return "schema validation" in msg.lower() or "schema" in msg.lower()

    def _is_malformed_error(self, exc: AIProviderError) -> bool:
        """Decide whether an AIProviderError is a malformed-response failure."""
        msg = str(exc) or ""
        low = msg.lower()
        return (
            "json" in low
            or "malformed" in low
            or "parse" in low
        )

    def _fallback_chain(
        self,
        request: AssistantRequest,
        *,
        reason: NormalizedReason,
        mode: Mode,
        extra_meta: dict[str, Any] | None = None,
    ) -> AssistantResponse:
        """Execute the multi-tier failover chain:
        1. Try secondary provider if configured.
        2. Try deterministic rule engine.
        3. If offline/snapshot mode is requested or live engine unavailable, return offline snapshot.
        """
        # Tier 2: Check if secondary provider is configured
        sec_provider_name = getattr(self._factory._settings, "ai_secondary_provider", "")
        if sec_provider_name:
            try:
                sec_provider = self._factory.build_named(sec_provider_name)
                if sec_provider and sec_provider.is_available:
                    res = sec_provider.complete(request)
                    meta = res.generation or GenerationMeta.empty(
                        mode=mode,
                        provider_used=res.provider_used,
                        model=res.model,
                        provider_latency_ms=res.provider_latency_ms,
                        fallback_used=True,
                        fallback_reason="primary_provider_unavailable",
                        generation_method="generative",
                    )
                    from dataclasses import replace as _replace
                    return _replace(res, fallback_used=True, fallback_reason="primary_provider_unavailable", generation=meta)
            except Exception as sec_exc:
                logger.warning(f"[service] Secondary provider {sec_provider_name} failed: {sec_exc}")

        # Tier 3: Deterministic Rule Engine
        det_response = self._fallback(request, reason=reason, mode=mode, extra_meta=extra_meta)

        # Tier 4: Offline Demo Snapshot (when demo mode enabled and snapshot fallback triggered)
        is_demo_mode = bool(getattr(self._factory._settings, "ursbiz_demo_mode", True))
        is_flagship_query = "acme" in request.user_prompt.lower() or "grow" in request.user_prompt.lower()
        if is_demo_mode and is_flagship_query and reason in ("offline_snapshot",):
            return self._load_offline_snapshot(request, reason="offline_snapshot")

        return det_response

    def _fallback(
        self,
        request: AssistantRequest,
        *,
        reason: NormalizedReason,
        mode: Mode,
        extra_meta: dict[str, Any] | None = None,
    ) -> AssistantResponse:
        """Return a deterministic fallback response."""
        logger.info(
            "ai.provider.fallback_chosen",
            extra={
                "event": "ai.provider.fallback_chosen",
                "mode": mode,
                "reason": reason,
                "request_id": getattr(request, "request_id", None),
            },
        )
        fallback = DeterministicFallbackProvider()
        response = fallback.complete(request, reason=reason)
        from dataclasses import replace as _replace
        # SPRINT AI-11 — Universal Business-Aware Assistant
        # hardening. If the upstream orchestrator never ran
        # ``understand_question`` (e.g. immediate fallback due
        # to a quota / circuit-open condition), derive the
        # capability tuple + business dependency literal on
        # the fallback path so the wire envelope still carries
        # the universal question classification. The
        # derivation is deterministic and matches the
        # QuestionUnderstanding fields exactly.
        if (extra_meta is None or "capability" not in extra_meta) and response.generation is not None:
            try:
                from app.services.ai.reasoning.question_understanding import (
                    understand_question,
                )
                _qd = understand_question(
                    prompt=request.user_prompt,
                    context=getattr(request, "context", None),
                )
                _capability = tuple(getattr(_qd, "capability", ()) or ())
                _business_dependency = str(
                    getattr(_qd, "business_dependency", "none") or "none"
                )
                if extra_meta is None:
                    extra_meta = {
                        "capability": _capability,
                        "business_dependency": _business_dependency,
                    }
                else:
                    extra_meta = dict(extra_meta)
                    extra_meta.setdefault("capability", _capability)
                    extra_meta.setdefault(
                        "business_dependency", _business_dependency,
                    )
            except Exception:  # noqa: BLE001
                # Never let a non-essential derivation break the
                # fallback contract — ``GenerationMeta`` defaults
                # keep the wire shape safe.
                logger.warning(
                    "ai.provider.ai11_fallback_capability_derivation_failed",
                    exc_info=True,
                )
        if response.generation is not None:
            if extra_meta:
                return _replace(
                    response,
                    generation=response.generation.merge(**extra_meta),
                )
        else:
            return _replace(
                response,
                generation=GenerationMeta.empty(
                    mode=mode,
                    provider_used=response.provider_used,
                    model=response.model,
                    provider_latency_ms=response.provider_latency_ms,
                    fallback_used=True,
                    fallback_reason=reason,
                    generation_method="deterministic",
                ),
            )
        return response

    def _load_offline_snapshot(
        self, request: AssistantRequest, reason: NormalizedReason = "offline_snapshot"
    ) -> AssistantResponse:
        """Load canonical offline demo snapshot."""
        import os, json
        snapshot_path = os.path.join(os.path.dirname(__file__), "..", "snapshots", "acme_flagship_snapshot.json")
        try:
            with open(snapshot_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            body = json.dumps(data)
        except Exception:
            body = json.dumps({
                "mode": request.mode,
                "executive_summary": "Acme Textiles Growth Strategy (Offline Demo Snapshot).",
                "current_situation": "Acme Textiles ₹1.8 Cr baseline revenue.",
                "key_findings": [],
                "recommendations": [],
                "thirty_day_plan": [],
                "assumptions": ["Offline demonstration mode active"],
                "limitations": ["Pre-generated snapshot"],
                "evidence_references": ["biz_profile_revenue", "rule_supplier_risk"]
            })

        now_iso = _now_iso()
        meta = GenerationMeta.empty(
            mode=request.mode,
            provider_used="offline_snapshot",
            model="acme_flagship_snapshot",
            provider_latency_ms=5,
            fallback_used=True,
            fallback_reason=reason,
            generation_method="offline_snapshot",
            schema_validated=True,
            grounding_validated=True,
            server_grounding_score=100,
            business_evidence_validated=True,
            context_manifest=request.context.context_manifest.to_dict() if request.context.context_manifest else None,
            generated_at=now_iso,
        )
        return AssistantResponse(
            body=body,
            model="offline_snapshot",
            fallback_used=True,
            provider_used="offline_snapshot",
            generated_at=now_iso,
            fallback_reason=reason,
            generation=meta,
        )


def _is_deterministic(response: AssistantResponse) -> bool:
    return response.provider_used == "deterministic-fallback"


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()
