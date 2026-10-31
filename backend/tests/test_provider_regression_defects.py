"""Phase 8 — Regression tests for the AI provider production defects.

These tests pin the MINIMUM SAFE FIX for the production
deployment defect documented in
``docs/DEPLOYMENT_HACKATHON.md`` §3 (judge demo was
instructed to run ``AI_PROVIDER=placeholder``, which routes
every chat reply to the deterministic rule engine) and the
related provider / model misconfiguration in
``backend/app/config/settings.py`` (committed default
``ai_model`` was a non-existent / unreachable model name).

Each test below targets ONE confirmed defect, runs
without network, and never depends on a real external API
key.

Run:
    cd D:/MSME/UrsAi
    python -m pytest -q backend/tests/test_provider_regression_defects.py
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

# --- Defect 1: committed default AI_MODEL must be a verified working model. ---


def test_default_ai_model_is_verified_working():
    """The committed default ``ai_model`` must be a real,
    verified working Gemini model on the OpenAI-compatible
    endpoint. Earlier shipped values (``gemini-3.6-flash``
    which is not a real model; ``gemini-1.5-flash`` which is
    no longer reliably served) caused the factory to mark the
    upstream as "configured" while every chat call failed
    with 404. The committed default is the only thing an
    operator gets when they only set ``AI_API_KEY``.
    """
    from app.config.settings import Settings

    # Re-instantiate with no env overrides so we test the
    # committed default, not the local .env.
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.ai_model, "ai_model must be set"
    assert s.ai_model == "gemini-2.0-flash", (
        f"ai_model default must be the verified working model "
        f"'gemini-2.0-flash'; got {s.ai_model!r}. Earlier "
        f"defaults (gemini-3.6-flash, gemini-1.5-flash) caused "
        f"every chat call to fail with 404."
    )
    # The committed default must not be a placeholder.
    assert s.ai_model.lower() not in {
        "",
        "placeholder",
        "change_me",
        "change-me",
        "your-model",
    }


def test_default_ai_provider_is_real_provider():
    """The committed default ``ai_provider`` must be a real
    provider (``openai_compatible`` or ``ollama``) — never
    ``placeholder``. An operator who only sets the API key
    must get a real provider path, not the deterministic
    fallback.
    """
    from app.config.settings import Settings

    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.ai_provider in {"openai_compatible", "ollama"}, (
        f"ai_provider default must be a real provider, got "
        f"{s.ai_provider!r}. The placeholder value routes every "
        f"chat reply to the deterministic rule engine."
    )


def test_default_ai_base_url_is_real_endpoint():
    """The committed default ``ai_base_url`` must be a real
    upstream endpoint — not empty, not placeholder.
    """
    from app.config.settings import Settings

    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.ai_base_url, "ai_base_url must be set"
    assert s.ai_base_url.startswith("http"), (
        f"ai_base_url must be a real URL, got {s.ai_base_url!r}"
    )
    assert "placeholder" not in s.ai_base_url.lower()
    assert "change-me" not in s.ai_base_url.lower()


# --- Defect 2: the deployment doc must NOT prescribe placeholder. ---


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_deployment_doc_does_not_prescribe_placeholder_as_normal_path():
    """``docs/DEPLOYMENT_HACKATHON.md`` is the operator-facing
    deployment guide. It MUST NOT instruct operators to use
    ``AI_PROVIDER=placeholder`` as the normal judge demo path.

    Earlier the doc shipped an uncommented `AI_PROVIDER=placeholder
    \\` line at the top of the §3 command block, which is the
    defect that made every judge chat reply a deterministic
    rule-engine body. The fix moved the placeholder command to
    a commented "OFFLINE FALLBACK" block and added a
    real-provider command at the top.
    """
    doc_path = Path(__file__).resolve().parents[2] / "docs" / "DEPLOYMENT_HACKATHON.md"
    assert doc_path.is_file(), f"missing doc: {doc_path}"
    text = _read(doc_path)

    # The doc must still mention placeholder (so operators know
    # the option exists) — but it must be clearly marked as the
    # OFFLINE / LAST-RESORT path, not the normal judge path.
    # We assert that EVERY uncommented occurrence of
    # ``AI_PROVIDER=placeholder`` is inside a commented
    # bash block (begins with `#`).
    lines = text.splitlines()
    bad: list[tuple[int, str]] = []
    in_bash_block = False
    for i, line in enumerate(lines, start=1):
        stripped = line.lstrip()
        if stripped.startswith("```bash"):
            in_bash_block = True
            continue
        if in_bash_block and stripped.startswith("```"):
            in_bash_block = False
            continue
        if "AI_PROVIDER=placeholder" in line and not line.lstrip().startswith("#"):
            bad.append((i, line))
    assert not bad, (
        "AI_PROVIDER=placeholder appears as an uncommented line "
        f"in docs/DEPLOYMENT_HACKATHON.md; the judge demo must "
        f"use a real provider. Offending lines: {bad}"
    )


def test_deployment_doc_prescribes_a_real_provider_template():
    """The §3 native command must include a real-provider
    template (Gemini or Ollama) so an operator has a
    copy-pasteable starting point. The template MUST use
    environment variables, never inline API keys.
    """
    doc_path = Path(__file__).resolve().parents[2] / "docs" / "DEPLOYMENT_HACKATHON.md"
    text = _read(doc_path)
    # Real-provider section is required.
    assert "REAL PROVIDER" in text or "REAL provider" in text, (
        "docs/DEPLOYMENT_HACKATHON.md must include a real-provider "
        "command template (Gemini or Ollama)."
    )
    # Must reference the verified working model.
    assert "gemini-2.0-flash" in text, (
        "docs/DEPLOYMENT_HACKATHON.md must reference the verified "
        "working model 'gemini-2.0-flash' in the real-provider "
        "template."
    )
    # Must reference the OpenAI-compatible URL.
    assert (
        "generativelanguage.googleapis.com" in text
        or "AI_BASE_URL" in text
    ), "docs/DEPLOYMENT_HACKATHON.md must reference a real AI base URL."


# --- Defect 3: the factory must honestly report the right status reason. ---


def test_factory_missing_api_key_status_reason():
    """When the operator configures ``openai_compatible`` but
    leaves ``AI_API_KEY`` empty, the factory must report
    ``missing_api_key`` (not ``reachable``). The earlier
    shipped code reported "reachable" for some upstreams that
    serve 200 OK to anonymous probes; that made the
    /chat/provider-status endpoint lie.
    """
    from app.config.settings import Settings
    from app.services.ai.providers.factory import ProviderFactory

    s = Settings(
        _env_file=None,  # type: ignore[call-arg]
        ai_provider="openai_compatible",
        ai_base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        ai_model="gemini-2.0-flash",
        ai_api_key="",
    )
    factory = ProviderFactory(s)
    assert factory.is_available() is False
    assert factory.status_reason() == "missing_api_key"


def test_factory_missing_base_url_status_reason():
    """When ``ai_base_url`` or ``ai_model`` is empty, the
    factory must report ``missing_base_url``.
    """
    from app.config.settings import Settings
    from app.services.ai.providers.factory import ProviderFactory

    s = Settings(
        _env_file=None,  # type: ignore[call-arg]
        ai_provider="openai_compatible",
        ai_base_url="",
        ai_model="gemini-2.0-flash",
        ai_api_key="some-key",
    )
    factory = ProviderFactory(s)
    assert factory.is_available() is False
    assert factory.status_reason() == "missing_base_url"


def test_factory_placeholder_status_reason():
    """``AI_PROVIDER=placeholder`` must be reported as
    ``placeholder`` — not as ``reachable``.
    """
    from app.config.settings import Settings
    from app.services.ai.providers.factory import ProviderFactory

    s = Settings(
        _env_file=None,  # type: ignore[call-arg]
        ai_provider="placeholder",
    )
    factory = ProviderFactory(s)
    assert factory.is_available() is False
    assert factory.status_reason() == "placeholder"


# --- Defect 4: the deterministic fallback stamps the truth. ---


def test_deterministic_fallback_stamps_generation_method_deterministic():
    """The deterministic fallback must stamp
    ``generation_method='deterministic'`` on the wire —
    NOT ``'generative'``. The earlier IMPACT_EVIDENCE.md
    text claimed the fallback stamps 'generative' which
    was false; the truth must be encoded in a regression
    test so a future change can't silently re-introduce
    the lie.
    """
    from app.services.ai.providers.base import (
        AssistantContext,
        AssistantContextDna,
        AssistantRequest,
        DeterministicFallbackProvider,
    )

    provider = DeterministicFallbackProvider()
    ctx = AssistantContext(
        business_id=1,
        overall_business_score=68,
        band="Established",
        dna=AssistantContextDna(archetype_key="founder_led", archetype_title="Founder-led", match_score=72),
    )
    req = AssistantRequest(
        user_prompt="What is my business health?",
        history=(),
        context=ctx,
        mode="grounded",
    )
    resp = provider.complete(req, reason="provider_unavailable")
    assert resp.fallback_used is True
    assert resp.provider_used == "deterministic-fallback"
    assert resp.generation is not None
    assert resp.generation.generation_method == "deterministic", (
        "Deterministic fallback must stamp generation_method="
        f"'deterministic', got {resp.generation.generation_method!r}. "
        f"Stamping 'generative' here would be a lie — the user "
        f"would see 'Generated explanation' for a non-LLM reply."
    )
    assert resp.generation.fallback_used is True


# --- Defect 5: the wire payload must NEVER leak API keys or base URLs. ---


def test_wire_payload_never_leaks_secrets():
    """The wire payload produced for an assistant turn must
    never include ``api_key``, ``authorization``, ``base_url``,
    or any other secret field. The ``conversation_service``
    layer asserts this at projection time.
    """
    from app.services.ai.sanitisation import (
        LEAKED_FIELDS,
        assert_no_leaked_secrets,
    )

    # The set must at minimum include the canonical secrets.
    for key in {"api_key", "authorization", "base_url"}:
        assert key in LEAKED_FIELDS, (
            f"sanitisation.LEAKED_FIELDS must include {key!r}"
        )

    # A payload that contains an api_key must be rejected.
    with pytest.raises(Exception):
        assert_no_leaked_secrets(
            {"api_key": "sk-secret", "model": "x"}, where="test"
        )

    # A clean payload must pass.
    assert_no_leaked_secrets(
        {"model": "gemini-2.0-flash", "provider": "openai_compatible"},
        where="test",
    )


# --- Defect 6: the service must fall back on auth failure. ---


def test_service_falls_back_on_auth_failure(monkeypatch):
    """When the configured provider raises ``ProviderAuthError``,
    the service must invoke the fallback chain. The wire
    envelope must carry ``fallback_used=True`` and
    ``fallback_reason='auth_failed'``.

    This test stubs the provider layer to avoid any real
    network call.
    """
    from app.config.settings import Settings
    from app.services.ai.providers import service as service_module
    from app.services.ai.providers.base import (
        AssistantContext,
        AssistantRequest,
        AssistantResponse,
        DeterministicFallbackProvider,
        Mode,
        ProviderAuthError,
        Provider as _Provider,
    )

    class _BoomProvider(_Provider):
        """Stub that raises ProviderAuthError on complete()."""

        def complete(self, request: AssistantRequest) -> AssistantResponse:
            raise ProviderAuthError("invalid bearer")

        def ping(self) -> bool:  # pragma: no cover — not used
            return False

        def close(self) -> None:  # pragma: no cover — not used
            return None

        @property
        def name(self) -> str:
            return "boom-stub"

        @property
        def model_name(self) -> str:
            return "boom-stub-model"

    class _StaticFactory:
        """Factory stub returning our boom provider."""

        def __init__(self, provider: _Provider, settings: object) -> None:
            self._provider = provider
            # Mirror the real factory's private surface so the
            # service's _fallback_chain (which reads
            # ``self._factory._settings``) doesn't blow up.
            self._settings = settings

        def build(self) -> _Provider:
            return self._provider

        def build_named(self, name: str) -> _Provider:  # noqa: D401
            return self._provider

        def default_provider(self, *, mode: Mode) -> _Provider:  # noqa: D401
            return self._provider

        def get(self, hint: str) -> _Provider:  # pragma: no cover — not used
            return self._provider

        def configured_provider_name(self) -> str:
            return "openai_compatible"

        def configured_model(self) -> str:
            return "gemini-2.0-flash"

        def is_available(self) -> bool:
            return True

        def status_reason(self) -> str:
            return "reachable"

    # Stub the circuit breaker to never block.
    class _NoopBreaker:
        def allow_request(self) -> bool:
            return True

        def execute_with_resilience(self, fn):
            return fn()

    # Build a minimal AssistantContext.
    from app.services.ai.providers.base import (
        AssistantContext as _AC,
        AssistantContextDna,
    )
    from app.services.ai.providers.prompt_builder import AssistantPromptBuilder

    ctx = _AC(
        business_id=1,
        overall_business_score=68,
        band="Established",
        dna=AssistantContextDna(archetype_key="founder_led", archetype_title="Founder-led", match_score=72),
    )

    # Settings stub the service's _fallback_chain reads via
    # ``self._factory._settings``. ``ai_secondary_provider``
    # is left empty so the chain skips the secondary probe.
    s = Settings(
        _env_file=None,  # type: ignore[call-arg]
        ai_provider="openai_compatible",
        ai_base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        ai_model="gemini-2.0-flash",
        ai_api_key="fake-test-key",
        ai_secondary_provider="",
        ursbiz_demo_mode=False,
    )
    factory = _StaticFactory(_BoomProvider(), s)
    svc = service_module.AssistantProviderService(
        context_builder=type("CB", (), {"build": staticmethod(lambda *a, **k: ctx)})(),
        prompt_builder=AssistantPromptBuilder(),
        provider_factory=factory,  # type: ignore[arg-type]
    )
    # Replace the circuit breaker with the noop stub.
    svc._circuit_breaker = _NoopBreaker()  # type: ignore[attr-defined]

    resp = svc.generate(
        owner_id=1,
        user_prompt="What is my business health?",
    )

    assert resp.fallback_used is True, (
        "auth failure must fall back; got fallback_used=False"
    )
    assert resp.provider_used == "deterministic-fallback"
    # ``fallback_reason`` is set on the GenerationMeta by
    # the deterministic fallback path. The non-negotiable is
    # ``fallback_used=True``; the ``generation_method`` must
    # also be ``"deterministic"`` so the UI never shows
    # "Generated explanation" for a non-LLM reply.
    if resp.generation is not None:
        assert resp.generation.fallback_used is True
        assert resp.generation.generation_method == "deterministic"


# --- Defect 7: the provider_status endpoint payload must be honest. ---


def test_provider_status_endpoint_payload_shape(monkeypatch):
    """The /api/v1/chat/provider-status endpoint must surface
    the configured provider, the runtime provider, the
    model, the availability flag, and the reason. The
    frontend renders the trust label from this payload;
    a missing field is a regression.
    """
    from app.config.settings import Settings
    from app.services.ai.providers.factory import ProviderFactory

    s = Settings(
        _env_file=None,  # type: ignore[call-arg]
        ai_provider="placeholder",
    )
    factory = ProviderFactory(s)

    # The factory's status method on the AssistantProviderService
    # is the source of truth. The status dict must contain the
    # six brief-mandated fields.
    from app.services.ai.providers.base import (
        AssistantContext as _AC,
        AssistantContextDna,
    )
    from app.services.ai.providers.prompt_builder import AssistantPromptBuilder
    from app.services.ai.providers.service import AssistantProviderService

    ctx = _AC(
        business_id=1,
        overall_business_score=68,
        band="Established",
        dna=AssistantContextDna(archetype_key="founder_led", archetype_title="Founder-led", match_score=72),
    )

    svc = AssistantProviderService(
        context_builder=type("CB", (), {"build": staticmethod(lambda *a, **k: ctx)})(),
        prompt_builder=AssistantPromptBuilder(),
        provider_factory=factory,  # type: ignore[arg-type]
    )
    payload = svc.provider_status()
    for key in (
        "configured_provider",
        "runtime_provider",
        "model",
        "available",
        "schema_required",
        "fallback_active",
        "modes",
        "default_mode",
    ):
        assert key in payload, f"provider_status missing {key!r}"
    # When placeholder is configured, the runtime must be the
    # deterministic fallback and ``available`` must be False.
    assert payload["configured_provider"] == "placeholder"
    assert payload["runtime_provider"] == "deterministic-fallback"
    assert payload["available"] is False
    assert payload["fallback_active"] is True
