"""ProviderFactory — Sprint 7 Part 2 + H7.3.

Selects the concrete provider at runtime from
``Settings.ai_provider``. Always returns a usable provider —
when the configured provider is unavailable, the factory
returns the deterministic fallback rather than raising.

Selection rules
---------------

  * ``ai_provider == "ollama"``             -> construct :class:`OllamaProvider`
                                                and ping it. If the ping fails,
                                                return the deterministic
                                                fallback instead.
  * ``ai_provider == "openai_compatible"``  -> construct
                                                :class:`OpenAICompatibleProvider`
                                                (the H7.3 generic path that
                                                covers OpenAI, OpenRouter,
                                                Together, Groq, vLLM, llama.cpp
                                                server mode, and Ollama's
                                                ``/v1/chat`` adapter). If the
                                                ping fails, return the
                                                deterministic fallback.
  * anything else (including ``"placeholder"``, ``"disabled"``,
    ``""``, ``None``)                      -> return the deterministic
                                                fallback directly.

The factory is the *only* place in the layer that decides
which provider to use. The :class:`AssistantProviderService`
takes the factory's output and treats it as an opaque
:class:`Provider` — it never asks which concrete class it got.
That separation is what keeps the verifier simple: it asks
the factory for "the configured provider or fallback", looks at
``provider_used`` on the response, and the rest is opaque.
"""
from __future__ import annotations

from typing import Any

from app.services.ai.providers.base import (
    AIProviderError,
    AssistantContext,
    AssistantRequest,
    AssistantResponse,
    DeterministicFallbackProvider,
    Provider,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from app.services.ai.providers.ollama import OllamaProvider
from app.services.ai.providers.openai_compatible import OpenAICompatibleProvider


class ProviderFactory:
    """Construct a :class:`Provider` from a Settings-like object.

    The factory accepts any object with the relevant attributes
    (``ai_provider``, ``ollama_base_url``, ``ollama_model``,
    ``ai_base_url``, ``ai_model``, ``ai_api_key``,
    ``ai_request_timeout_seconds``, ``ai_require_schema``) — this is
    the same shape :class:`app.config.settings.Settings` exposes.
    Tests can pass a tiny stub.
    """

    def __init__(self, settings: Any | None = None) -> None:
        self._settings = settings

    # ---- public API -------------------------------------------------- #

    def build(self) -> Provider:
        """Build the configured provider, falling back on failure."""
        provider_name = self._provider_name()
        if provider_name == "ollama":
            return self._build_ollama_or_fallback()
        if provider_name == "openai_compatible":
            return self._build_openai_compatible_or_fallback()
        # Any other value: deterministic fallback only.
        return DeterministicFallbackProvider()

    def fallback(self) -> Provider:
        """Return the deterministic fallback unconditionally."""
        return DeterministicFallbackProvider()

    # ---- internal ---------------------------------------------------- #

    def _provider_name(self) -> str:
        if self._settings is None:
            return ""
        return str(getattr(self._settings, "ai_provider", "") or "").strip().lower()

    def _build_ollama_or_fallback(self) -> Provider:
        base_url = str(
            getattr(self._settings, "ollama_base_url", "") or ""
        ).strip()
        model = str(
            getattr(self._settings, "ollama_model", "") or "llama3.1"
        ).strip()
        timeout = float(
            getattr(self._settings, "ai_request_timeout_seconds", 60.0) or 60.0
        )
        provider = OllamaProvider(
            base_url=base_url,
            model=model,
            timeout=timeout,
        )
        # A successful ping means Ollama is reachable; the
        # factory hands the real provider to the service. A
        # failed ping is *not* an error — we just fall back.
        if provider.ping():
            return provider
        # Make sure the unused client is closed so the test
        # runner doesn't leak sockets.
        provider.close()
        return DeterministicFallbackProvider()

    def _build_openai_compatible_or_fallback(self) -> Provider:
        """Build the OpenAI-compatible provider, falling back on failure.

        The settings consumed are the four H7.3 keys:

          * ``ai_base_url``  — required for the real provider.
          * ``ai_model``     — required for the real provider.
          * ``ai_api_key``   — optional (local servers ignore auth).
          * ``ai_require_schema`` — toggle JSON-mode validation.

        If ``ai_base_url`` or ``ai_model`` is empty, the configurable
        provider is treated as "not configured" and the factory
        returns the deterministic fallback. Same for any ping failure.
        """
        base_url = str(
            getattr(self._settings, "ai_base_url", "") or ""
        ).strip()
        model = str(
            getattr(self._settings, "ai_model", "") or ""
        ).strip()
        api_key = str(
            getattr(self._settings, "ai_api_key", "") or ""
        ).strip()
        timeout = float(
            getattr(self._settings, "ai_request_timeout_seconds", 60.0) or 60.0
        )
        require_json = bool(
            getattr(self._settings, "ai_require_schema", True)
        )
        is_local = any(loc in base_url for loc in ("localhost", "127.0.0.1", "0.0.0.0", "::1"))
        if not base_url or not model or (not is_local and not api_key):
            # Not configured (or remote endpoint with no API key) -> fall back silently.
            return DeterministicFallbackProvider()
        provider = OpenAICompatibleProvider(
            base_url=base_url,
            model=model,
            api_key=api_key,
            timeout=timeout,
            require_json=require_json,
        )
        if provider.ping():
            return provider
        provider.close()
        return DeterministicFallbackProvider()

    # ---- convenience for callers that want to inspect the name ------- #

    def configured_provider_name(self) -> str:
        """Return the configured provider name (lower-cased).

        Useful for logging and for the verifier. The actual
        runtime provider may be the fallback — check
        ``AssistantResponse.provider_used`` for that.
        """
        return self._provider_name()

    def configured_model(self) -> str:
        """Return the configured model identifier.

        ``"ollama"`` → ``Settings.ollama_model`` (default
        ``"llama3.1"``). ``"openai_compatible"`` →
        ``Settings.ai_model``. Any other provider name → ``""``.
        """
        name = self._provider_name()
        if name == "ollama":
            return str(
                getattr(self._settings, "ollama_model", "llama3.1") or "llama3.1"
            ).strip()
        if name == "openai_compatible":
            return str(
                getattr(self._settings, "ai_model", "") or ""
            ).strip()
        return ""

    def is_available(self) -> bool:
        """Return True iff the configured real provider can be reached.

        The check runs the same path ``build()`` would: a real
        Ollama / OpenAI-compatible ping. A failed ping returns
        False; the factory's ``build()`` will return the
        deterministic fallback in that case.

        H7.9R+ — the check is now HONEST. An empty
        ``ai_api_key`` on an OpenAI-compatible provider is
        treated as "missing_api_key" and returns False even if
        the upstream's ``/models`` endpoint returns 2xx (some
        gateways happily serve 200 OK to anonymous probes).
        ``status_reason()`` exposes the precise reason so the
        ``/chat/provider-status`` endpoint can tell the
        frontend why the provider is down.

        This is the signal the
        ``GET /api/v1/chat/provider-status`` endpoint surfaces.
        """
        name = self._provider_name()
        if name == "ollama":
            base_url = str(
                getattr(self._settings, "ollama_base_url", "") or ""
            ).strip()
            if not base_url:
                return False
            try:
                provider = OllamaProvider(
                    base_url=base_url,
                    model=str(
                        getattr(self._settings, "ollama_model", "llama3.1")
                        or "llama3.1"
                    ).strip(),
                    timeout=5.0,
                )
                ok = provider.ping()
                provider.close()
                return ok
            except Exception:
                return False
        if name == "openai_compatible":
            base_url = str(
                getattr(self._settings, "ai_base_url", "") or ""
            ).strip()
            model = str(
                getattr(self._settings, "ai_model", "") or ""
            ).strip()
            api_key = str(
                getattr(self._settings, "ai_api_key", "") or ""
            ).strip()
            if not base_url or not model:
                return False
            # H7.9R+ — without a key, the OpenAI-compatible
            # provider cannot make a single authenticated call.
            # Gemini, OpenAI, OpenRouter, etc. all reject
            # requests without a bearer token. We refuse to
            # report "available" for an upstream we know will
            # 401 on the first chat message — that would be a
            # lie the frontend would render as "Ollama
            # connected" while every chat hangs.
            if not api_key:
                return False
            try:
                provider = OpenAICompatibleProvider(
                    base_url=base_url,
                    model=model,
                    api_key=api_key,
                    timeout=5.0,
                    require_json=bool(
                        getattr(self._settings, "ai_require_schema", True)
                    ),
                )
                # H7.9R+ — the ping MUST validate the
                # bearer token, not just TCP reachability.
                # /v1/models on most OpenAI-compatible upstreams
                # returns 401 when the bearer is invalid; we
                # treat 401/403 the same as "unreachable".
                ok = provider.ping()
                provider.close()
                if not ok:
                    return False
                # H7.9R+ — second-line check: re-ping with the
                # bearer header on the same endpoint and
                # confirm we got a 2xx. A 200 with an empty
                # body, or a 200 with the wrong schema, is
                # still "not usable".
                return _probe_bearer_ok(base_url, api_key)
            except Exception:
                return False
        return False

    def status_reason(self) -> str:
        """Return a short, frontend-safe reason for the current state.

        Possible values:

          * ``"reachable"``         — provider pinged OK
          * ``"missing_api_key"``   — OpenAI-compatible configured
                                       but ``AI_API_KEY`` is empty
          * ``"missing_base_url"``  — OpenAI-compatible configured
                                       but ``AI_BASE_URL`` / ``AI_MODEL``
                                       is empty
          * ``"ping_failed"``       — upstream is unreachable or
                                       the bearer token was rejected
                                       (401/403)
          * ``"placeholder"``       — ``AI_PROVIDER=placeholder`` is
                                       explicit, the deterministic
                                       fallback is the intended path
          * ``"provider_unconfigured"`` — empty / unknown
                                       ``AI_PROVIDER`` value

        H7.9R+ — never leaks API keys, base URLs, or model
        identifiers (those are user-visible in the existing
        ``configured_provider`` / ``model`` fields, but never
        with secrets).
        """
        name = self._provider_name()
        if not name or name == "placeholder":
            if name == "placeholder":
                return "placeholder"
            return "provider_unconfigured"
        if name == "ollama":
            base_url = str(
                getattr(self._settings, "ollama_base_url", "") or ""
            ).strip()
            if not base_url:
                return "missing_base_url"
            try:
                provider = OllamaProvider(
                    base_url=base_url,
                    model=str(
                        getattr(self._settings, "ollama_model", "llama3.1")
                        or "llama3.1"
                    ).strip(),
                    timeout=5.0,
                )
                ok = provider.ping()
                provider.close()
                return "reachable" if ok else "ping_failed"
            except Exception:
                return "ping_failed"
        if name == "openai_compatible":
            base_url = str(
                getattr(self._settings, "ai_base_url", "") or ""
            ).strip()
            model = str(
                getattr(self._settings, "ai_model", "") or ""
            ).strip()
            api_key = str(
                getattr(self._settings, "ai_api_key", "") or ""
            ).strip()
            if not base_url or not model:
                return "missing_base_url"
            if not api_key:
                return "missing_api_key"
            try:
                provider = OpenAICompatibleProvider(
                    base_url=base_url,
                    model=model,
                    api_key=api_key,
                    timeout=5.0,
                    require_json=bool(
                        getattr(self._settings, "ai_require_schema", True)
                    ),
                )
                ok = provider.ping()
                provider.close()
                if not ok:
                    return "ping_failed"
                return (
                    "reachable"
                    if _probe_bearer_ok(base_url, api_key)
                    else "ping_failed"
                )
            except Exception:
                return "ping_failed"
        return "provider_unconfigured"


def _probe_bearer_ok(base_url: str, api_key: str) -> bool:
    """Probe ``GET {base_url}/models`` with the real bearer header.

    H7.9R+ — the bare ping only validates TCP reachability;
    some upstreams serve 200 OK to anonymous probes and then
    401 on the real chat call. We send the bearer header and
    accept only 2xx with a JSON body. Returns False on any
    non-2xx, timeout, or non-JSON response. Used by the
    factory's ``is_available`` and ``status_reason`` paths so
    they can never lie about a keyless upstream.

    Note: this is the same call the bare ping makes, just
    with a stricter success criterion (200 + JSON, not just
    ``status < 500``).
    """
    import httpx as _httpx

    if not base_url or not api_key:
        return False
    try:
        with _httpx.Client(timeout=5.0) as client:
            response = client.get(
                f"{base_url.rstrip('/')}/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )
        if response.status_code < 200 or response.status_code >= 300:
            return False
        # Body must parse as JSON; some proxies return HTML
        # 200 pages that look healthy but yield nothing.
        try:
            response.json()
        except ValueError:
            return False
        return True
    except _httpx.HTTPError:
        return False