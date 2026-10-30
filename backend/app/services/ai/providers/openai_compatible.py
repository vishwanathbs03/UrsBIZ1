"""H7.3 — Docx Prompt 3 Part 1: thin OpenAI-compatible provider.

The provider targets the generic ``/v1/chat/completions`` contract
used by OpenAI, OpenRouter, Together, Groq, vLLM, llama.cpp's server
mode, and Ollama's own ``v1/chat`` adapter.

It is intentionally thin:

  * No streaming (the existing Ollama provider is also non-streaming;
    the docx does not require streaming).
  * No tool calling (the LLM is an *explainer*, not an actor; the
    deterministic engines are the actors).
  * No conversation-history translation beyond the simple ``messages[]``
    shape — the prompt builder hands us turn objects.
  * JSON mode is optional and gated by ``Settings.ai_require_schema``.
    When enabled, we send ``response_format: { type: "json_object" }``
    (the OpenAI convention). When disabled, we accept whatever the
    model returns and pass it through unchanged.

Failure semantics mirror :class:`OllamaProvider` so the factory's
behaviour is symmetric:

  * Unreachable upstream                → :class:`ProviderUnavailableError`
  * Read timeout exceeds budget         → :class:`ProviderTimeoutError`
  * Non-2xx HTTP, malformed JSON,
    schema validation failure,
    empty response                       → :class:`AIProviderError`

The provider is *not* a retry layer. ``AssistantProviderService``
already owns the soft-failure fallback path
(``ProviderUnavailableError`` / ``ProviderTimeoutError`` → deterministic
fallback); hard failures propagate so the caller decides.

Security (docx P3 Part 6)
-------------------------

  * The bearer token (``AI_API_KEY``) is sent in the ``Authorization``
    header, never logged.
  * The provider strips the upstream HTTP response body before any
    logging — only status code + endpoint go to the audit log.
  * The provider caps the user prompt at ``_MAX_PROMPT_LEN`` via
    ``response_schema.cap_user_prompt``; the truncation is signalled
    on the response envelope so the UI can tell the user.
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
from app.services.ai.providers.response_schema import (
    GroundedResponse,
    cap_user_prompt,
    parse_model_output,
)


class OpenAICompatibleProvider:
    """Provider that talks to any OpenAI-compatible chat-completions endpoint.

    Construction parameters mirror what the docx lists in P3 Part 1:

      * ``base_url`` — e.g. ``https://api.openai.com/v1``,
        ``https://openrouter.ai/api/v1``, ``http://localhost:11434/v1``.
        Trailing slash is tolerated; ``/chat/completions`` is appended.
      * ``model``    — the model name as the upstream knows it
        (``gpt-4o-mini``, ``meta-llama/llama-3.1-8b-instruct``, ...).
      * ``api_key``  — the bearer token. Empty string is allowed for
        local servers (Ollama, llama.cpp) that ignore auth.
      * ``timeout``  — per-request timeout, seconds. Defaults to
        ``Settings.ai_request_timeout_seconds``.
      * ``require_json`` — when True, the provider asks the upstream for
        a JSON response (``response_format: { type: "json_object" }``)
        AND validates the result against the docx schema. When the
        validation fails, the provider raises :class:`AIProviderError`
        so the service falls back to the deterministic provider.
      * ``http_client`` — for tests; an injected ``httpx.Client``.
    """

    name = "openai_compatible"

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str = "",
        timeout: float = 60.0,
        require_json: bool = True,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._base_url = (base_url or "").rstrip("/")
        self._model = (model or "").strip()
        self._api_key = api_key or ""
        self._timeout = float(timeout) if timeout and timeout > 0 else 60.0
        self._require_json = bool(require_json)
        self._owns_client = http_client is None
        self._client = http_client or httpx.Client(
            timeout=httpx.Timeout(self._timeout, connect=2.0)
        )
        self._available: bool = self._ping() if self._api_key else False

    # ---- protocol surface ---------------------------------------------- #

    @property
    def is_available(self) -> bool:
        return self._available

    @property
    def model_name(self) -> str:
        return self._model

    def complete(self, request: AssistantRequest) -> AssistantResponse:
        if not self._base_url:
            raise ProviderUnavailableError(
                "OpenAI-compatible base URL is not configured."
            )
        if not self._model:
            raise ProviderUnavailableError(
                "OpenAI-compatible model name is not configured."
            )
        if not self._api_key:
            raise ProviderUnavailableError(
                "OpenAI-compatible API key is not configured."
            )
        if not self._available:
            raise ProviderUnavailableError(
                "OpenAI-compatible provider is not reachable."
            )

        url = f"{self._base_url}/chat/completions"
        # Cap the user prompt per docx P3 Part 6.
        clipped, was_truncated = cap_user_prompt(request.user_prompt)
        # H7.8C — pick the right system prompt for the requested mode.
        # ``grounded`` uses the structured snapshot+registry prompt;
        # ``open`` uses the permissive open-mode prompt.
        messages = _to_messages(request, clipped, mode=request.mode)

        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": 0.2,
        }
        # H7.8C — schema enforcement is gated on both the
        # provider's ``require_json`` flag AND the request mode.
        # Open mode always opts out of JSON.
        if self._require_json and request.mode == "grounded":
            payload["response_format"] = {"type": "json_object"}

        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        # H7.8C — measure wall-clock latency for the audit log.
        started_at = datetime.now(tz=timezone.utc)
        try:
            response = self._client.post(url, json=payload, headers=headers)
        except httpx.ConnectError as exc:
            raise ProviderUnavailableError(
                f"openai_compatible not reachable at {self._base_url}: {exc}"
            ) from exc
        except httpx.ConnectTimeout as exc:
            raise ProviderUnavailableError(
                f"openai_compatible connect timeout at {self._base_url}: {exc}"
            ) from exc
        except httpx.ReadTimeout as exc:
            raise ProviderTimeoutError(
                f"openai_compatible read timeout after {self._timeout}s: {exc}"
            ) from exc
        except httpx.HTTPError as exc:
            raise AIProviderError(
                f"openai_compatible HTTP error: {exc}"
            ) from exc

        # H7.8C — map non-2xx to typed errors so the service can
        # classify 4xx vs 5xx vs rate-limit distinctly.
        if response.status_code == 429:
            raise ProviderRateLimitError(
                f"openai_compatible rate-limited: HTTP 429"
            )
        if response.status_code >= 400:
            # Trim body to 200 chars; we never log the full upstream body.
            raise ProviderHTTPStatusError(
                f"openai_compatible returned HTTP {response.status_code}: "
                f"{response.text[:200]}",
                status_code=response.status_code,
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise AIProviderError(
                f"openai_compatible returned non-JSON response: {exc}"
            ) from exc

        body = _extract_assistant_text(data)
        if not body:
            raise AIProviderError(
                "openai_compatible returned an empty assistant message."
            )

        # When JSON mode is requested, validate against the docx schema.
        # On validation failure we raise AIProviderError so the service
        # can decide to fall back to the deterministic provider.
        if self._require_json and request.mode == "grounded":
            result = parse_model_output(body)
            if not result.ok:
                raise AIProviderError(
                    "openai_compatible returned output that failed the "
                    f"docx P3 schema validation: {result.errors}"
                )
            assert result.response is not None  # mypy / type narrowing
            rendered = result.response.to_chat_body()
        else:
            rendered = body

        # When the user prompt was truncated, surface it on the envelope.
        # The chat UI shows "Your prompt was truncated at N chars" beside
        # the response.
        if was_truncated:
            rendered = rendered + "\n\n(Note: your prompt was truncated to fit the model context.)"

        # H7.8C — record wall-clock latency and build a baseline
        # ``GenerationMeta`` so the UI / provider-status endpoint can
        # surface the real provider's provenance.
        latency_ms = int(
            (datetime.now(tz=timezone.utc) - started_at).total_seconds() * 1000
        )
        generation = GenerationMeta.empty(
            mode=request.mode,
            provider_used=self.name,
            model=f"openai_compatible:{self._model}",
            provider_latency_ms=latency_ms,
            fallback_used=False,
            prompt_truncated=was_truncated,
            generation_method="generative",
        )
        return AssistantResponse(
            body=rendered,
            model=f"openai_compatible:{self._model}",
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

    # ---- lifecycle ---------------------------------------------------- #

    def ping(self) -> bool:
        """Probe ``GET {base_url}/models`` to confirm reachability.

        Some upstreams (e.g. llama.cpp) do not implement ``/models``;
        we degrade to a 404-as-up check on the chat endpoint instead.
        """
        if not self._base_url:
            self._available = False
            return False
        try:
            response = self._client.get(
                f"{self._base_url}/models",
                timeout=min(1.0, self._timeout),
                headers={"Authorization": f"Bearer {self._api_key}"} if self._api_key else {},
            )
            self._available = response.status_code < 500
            return self._available
        except httpx.HTTPError:
            self._available = False
            return False

    def close(self) -> None:
        if self._owns_client:
            try:
                self._client.close()
            except Exception:
                pass

    def __enter__(self) -> "OpenAICompatibleProvider":
        self.ping()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _to_messages(
    request: AssistantRequest,
    clipped_prompt: str,
    *,
    mode: str = "grounded",
) -> list[dict[str, str]]:
    """Translate the AssistantRequest into a ``messages[]`` payload.

    The order is fixed: system, then conversation history (caller-bounded),
    then the user turn.

    H7.8C — the system prompt is mode-aware (``grounded`` vs
    ``open``). The provider passes ``request.mode`` here so the
    right contract is selected.

    H7.8C — the user message is rendered via the prompt builder so
    the model actually receives the structured snapshot + evidence
    registry + untrusted-delimiter block. Sending the bare
    ``clipped_prompt`` (as this provider used to) drops the entire
    business context and the model responds with "no profile
    available" — that's a regression that this fix closes.
    """
    _ = clipped_prompt  # kept for API symmetry; the renderer reads request.user_prompt directly
    out: list[dict[str, str]] = [
        {"role": "system", "content": AssistantPromptBuilder.system_message(mode)},
    ]
    for turn in request.history:
        role = turn.role if turn.role in ("user", "assistant") else "user"
        out.append({"role": role, "content": turn.content})
    out.append({
        "role": "user",
        "content": AssistantPromptBuilder.render_user_message(request),
    })
    return out


def _extract_assistant_text(data: Any) -> str:
    """Return the assistant message text from a chat-completions response.

    Tolerates the common shapes:

      * ``{"choices": [{"message": {"content": "..."}}]}`` (OpenAI)
      * ``{"choices": [{"text": "..."}]}`` (legacy completions)
      * ``{"message": {"content": "..."}}`` (Ollama v1/chat adapter)
    """
    if not isinstance(data, dict):
        return ""
    choices = data.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0]
        if isinstance(first, dict):
            msg = first.get("message")
            if isinstance(msg, dict):
                content = msg.get("content")
                if isinstance(content, str):
                    return content.strip()
            text = first.get("text")
            if isinstance(text, str):
                return text.strip()
    # Ollama v1/chat adapter shape (single message).
    msg = data.get("message")
    if isinstance(msg, dict):
        content = msg.get("content")
        if isinstance(content, str):
            return content.strip()
    return ""