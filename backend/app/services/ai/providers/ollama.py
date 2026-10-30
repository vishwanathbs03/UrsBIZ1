"""OllamaProvider — Sprint 7 Part 2.

Real LLM provider that calls a local Ollama HTTP server.

The provider uses Ollama's ``/api/generate`` endpoint (the
non-streaming chat-completion equivalent) and a configurable
model (default ``llama3.1``). It is honest about being the
real model — ``name`` is ``"ollama"`` and ``model_used``
echoes the configured model name so the verifier can prove
the ollama path was taken.

Failure semantics
-----------------

The provider raises the soft-failure errors that the
:class:`ProviderFactory` knows how to handle:

  * :class:`ProviderUnavailableError` — Ollama is offline
    (``httpx.ConnectError``, ``httpx.ConnectTimeout``,
    DNS failure, refused connection).
  * :class:`ProviderTimeoutError` — Ollama accepted the
    request but did not respond within
    :attr:`Settings.ai_request_timeout_seconds`
    (``httpx.ReadTimeout``).
  * :class:`AIProviderError` — every other transport-level
    failure (non-2xx HTTP status, malformed JSON, empty
    response). The factory treats this as a hard failure
    and surfaces it; callers can decide.

The provider does NOT do retries. A real retry policy is
the next milestone's problem.

Determinism note
----------------

A real LLM is non-deterministic by nature. The two-call
byte-equality check is the verifier's *fallback* gate, not
its ollama gate. When Ollama is reachable and configured,
the verifier only checks:

  * the response body is non-empty,
  * ``model`` starts with ``"ollama:"``,
  * ``fallback_used`` is False.

The determinism gate (two-call byte-equality) only applies
when the deterministic fallback is in use.

KV-cache pinning
----------------

The provider pins ``options.num_ctx=512`` on every request
as a belt-and-braces measure alongside the daemon-level
``OLLAMA_CONTEXT_LENGTH`` env var. The default ``num_ctx`` in
Ollama is 2048, which on a 5.9 GB host with a 4B-class model
needs ~38 GB of system RAM for the KV cache and crashes with
``ggml_backend_cpu_buffer_type_alloc_buffer: failed to
allocate buffer``. Pinning to 512 keeps the cache small
enough for memory-constrained hosts while still being long
enough for the ~12-turn UrsBiz chat history replayed into
the prompt.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from app.services.ai.providers.base import (
    AIProviderError,
    AssistantRequest,
    AssistantResponse,
    GenerationMeta,
    Provider,
    ProviderHTTPStatusError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from app.services.ai.providers.prompt_builder import AssistantPromptBuilder


class OllamaProvider:
    """Ollama HTTP provider.

    Constructed with the three Ollama-specific settings:

      * ``base_url`` — typically ``http://localhost:11434``
      * ``model``    — the Ollama model tag
                        (``llama3.1``, ``mistral``, etc.)
      * ``timeout``  — per-request timeout, in seconds

    The constructor *pings* the host (``GET /api/tags``)
    to set ``is_available``. A failure is recorded but does
    not raise — the factory decides what to do.
    """

    name = "ollama"

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        timeout: float = 60.0,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._base_url = (base_url or "").rstrip("/")
        self._model = model or "llama3.2:3b"
        self._timeout = float(timeout) if timeout and timeout > 0 else 60.0
        self._owns_client = http_client is None
        self._client = http_client or httpx.Client(
            timeout=httpx.Timeout(self._timeout, connect=1.0)
        )
        self._available: bool = self.ping()

    # ---- protocol surface ----------------------------------------------- #

    @property
    def is_available(self) -> bool:
        return self._available

    @property
    def model_name(self) -> str:
        return self._model

    def complete(self, request: AssistantRequest) -> AssistantResponse:
        """Call Ollama's ``/api/generate`` and return the response."""
        if not self._base_url:
            raise ProviderUnavailableError(
                "Ollama base URL is not configured."
            )
        if not self._available:
            raise ProviderUnavailableError(
                f"Ollama not reachable at {self._base_url}."
            )
        url = f"{self._base_url}/api/generate"
        # H7.8C — mode-aware system prompt + user message.
        system = AssistantPromptBuilder.system_message(request.mode)
        user = AssistantPromptBuilder.render_user_message(request)
        payload: dict[str, Any] = {
            "model": self._model,
            "prompt": user,
            "system": system,
            "stream": False,
            # Pin num_ctx to fit on memory-constrained hosts.
            # Default num_ctx=2048 needs tens of GB of RAM for
            # the KV cache — see the KV-cache pinning block in
            # this module's docstring.
            "options": {
                "num_ctx": 1024,
                "num_predict": 384,
            },
        }
        # H7.8C — measure wall-clock latency for the audit log.
        started_at = datetime.now(tz=timezone.utc)
        try:
            response = self._client.post(url, json=payload)
        except httpx.ConnectError as exc:
            raise ProviderUnavailableError(
                f"Ollama not reachable at {self._base_url}: {exc}"
            ) from exc
        except httpx.ConnectTimeout as exc:
            raise ProviderUnavailableError(
                f"Ollama connect timeout at {self._base_url}: {exc}"
            ) from exc
        except httpx.ReadTimeout as exc:
            raise ProviderTimeoutError(
                f"Ollama read timeout after {self._timeout}s: {exc}"
            ) from exc
        except httpx.HTTPError as exc:
            raise AIProviderError(
                f"Ollama HTTP error: {exc}"
            ) from exc

        # H7.8C — map non-2xx to typed errors so the service can
        # classify 4xx vs 5xx vs rate-limit distinctly.
        if response.status_code == 429:
            raise ProviderRateLimitError(
                f"Ollama rate-limited: HTTP 429"
            )
        if response.status_code >= 400:
            raise ProviderHTTPStatusError(
                f"Ollama returned HTTP {response.status_code}: "
                f"{response.text[:200]}",
                status_code=response.status_code,
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise AIProviderError(
                f"Ollama returned non-JSON response: {exc}"
            ) from exc

        body = str(data.get("response", "") or "").strip()
        if not body:
            raise AIProviderError(
                "Ollama returned an empty 'response' field."
            )

        # H7.8C — record wall-clock latency and build a baseline
        # ``GenerationMeta`` so the UI / provider-status endpoint
        # can surface the real provider's provenance.
        latency_ms = int(
            (datetime.now(tz=timezone.utc) - started_at).total_seconds() * 1000
        )
        generation = GenerationMeta.empty(
            mode=request.mode,
            provider_used=self.name,
            model=f"ollama:{self._model}",
            provider_latency_ms=latency_ms,
            fallback_used=False,
            generation_method="generative",
        )
        return AssistantResponse(
            body=body,
            model=f"ollama:{self._model}",
            fallback_used=False,
            provider_used=self.name,
            generated_at=datetime.now(tz=timezone.utc).isoformat(),
            provider_latency_ms=latency_ms,
            generation=generation,
            twin_generated_at=request.context.twin_generated_at,
            recommendations_generated_at=request.context.recommendations_generated_at,
            roadmap_generated_at=request.context.roadmap_generated_at,
            rules_generated_at=request.context.rules_generated_at,
            insights_generated_at=request.context.insights_generated_at,
            schemes_generated_at=request.context.schemes_generated_at,
            forecasts_generated_at=request.context.forecasts_generated_at,
            action_items_generated_at=request.context.action_items_generated_at,
        )

    # ---- lifecycle ------------------------------------------------------- #

    def ping(self) -> bool:
        """Probe Ollama's ``/api/tags`` and update ``is_available``.

        Returns True if Ollama answered with HTTP 200. A False
        return is not an error — the factory treats it as
        "Ollama is offline, fall back". Callers that want to
        surface the failure should catch
        :class:`AIProviderError` from :meth:`complete`.
        """
        if not self._base_url:
            self._available = False
            return False
        try:
            response = self._client.get(
                f"{self._base_url}/api/tags",
                timeout=min(0.5, self._timeout),
            )
        except httpx.HTTPError:
            self._available = False
            return False
        self._available = response.status_code < 400
        return self._available

    def close(self) -> None:
        """Close the owned HTTP client. Safe to call repeatedly."""
        if self._owns_client:
            try:
                self._client.close()
            except Exception:
                pass

    def __enter__(self) -> "OllamaProvider":
        self.ping()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()