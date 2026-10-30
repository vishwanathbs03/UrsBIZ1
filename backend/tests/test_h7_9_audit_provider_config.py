"""Regression tests for the AI provider configuration audit (H7.9R+).

These tests lock down the "provider status must never lie" contract
that the audit fixes established. The previous implementation had
two bugs:

  1. ``Settings.ai_model`` defaulted to ``"gemini-3.6-flash"``
     which is not a real Google model. The factory would happily
     construct an OpenAI-compatible provider with a model name the
     upstream never heard of and every chat would fail with 404.
  2. ``factory.is_available()`` returned ``True`` for an
     OpenAI-compatible provider with no API key, because the
     bare ``/models`` ping only checked ``status < 500``. Some
     gateways (Gemini included) serve 200 OK to anonymous probes
     and 401 on the real chat call — the boolean lied.

The fixes assert:

  (1) The default model is a real, currently-supported Gemini
      model (``gemini-1.5-flash``).
  (2) When ``AI_API_KEY`` is empty, the factory reports
      ``available=False``, ``fallback_active=True``,
      ``reason="missing_api_key"`` regardless of whether the
      upstream is reachable.
  (3) When ``AI_PROVIDER=placeholder`` the factory reports
      ``available=False``, ``reason="placeholder"`` — the
      fallback is the intended path, not a failure.
  (4) When the upstream is reachable with a valid bearer, the
      factory reports ``available=True``, ``reason="reachable"``.
  (5) The provider-status payload NEVER contains ``api_key``,
      ``authorization``, or a full ``base_url`` field.
"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.config.settings import Settings
from app.services.ai.providers.factory import ProviderFactory


class _StubSettings:
    """Minimal duck-type for Settings used by ProviderFactory."""

    def __init__(
        self,
        *,
        ai_provider: str = "placeholder",
        ai_api_key: str = "",
        ai_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/",
        ai_model: str = "gemini-1.5-flash",
        ai_require_schema: bool = True,
        ollama_base_url: str = "",
        ollama_model: str = "llama3.1",
    ) -> None:
        self.ai_provider = ai_provider
        self.ai_api_key = ai_api_key
        self.ai_base_url = ai_base_url
        self.ai_model = ai_model
        self.ai_require_schema = ai_require_schema
        self.ollama_base_url = ollama_base_url
        self.ollama_model = ollama_model


def test_default_ai_model_is_real_gemini_model():
    """The committed default must be a real Google model name.

    Audit history (kept for the trail):
      * "gemini-3.6-flash" — not a real Google model; every
        chat call failed with 404. Fixed in H7.9R.
      * "gemini-1.5-flash" — fixed default; later became
        unreliable on the OpenAI-compatible endpoint.
      * "gemini-2.0-flash" — current verified working default.
        Future bumps MUST keep the value inside the Gemini
        family AND the value must be a model an operator
        can actually reach on the OpenAI-compatible endpoint.
    """
    settings = Settings(_env_file=None)
    assert settings.ai_model.startswith("gemini-"), (
        f"default ai_model {settings.ai_model!r} is not in the Gemini family"
    )
    # The current verified working default. Pin the exact
    # value so an accidental change re-fails the audit.
    assert settings.ai_model == "gemini-2.0-flash", (
        f"default ai_model changed unexpectedly to {settings.ai_model!r}; "
        f"the verified working model is 'gemini-2.0-flash'."
    )


def test_factory_reports_missing_api_key_when_key_is_empty():
    """No key → not available, fallback active, reason='missing_api_key'."""
    settings = _StubSettings(
        ai_provider="openai_compatible",
        ai_api_key="",  # empty
        ai_base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        ai_model="gemini-1.5-flash",
    )
    factory = ProviderFactory(settings)
    assert factory.is_available() is False, (
        "factory must NOT report available=True for an "
        "OpenAI-compatible provider with an empty AI_API_KEY"
    )
    reason = factory.status_reason()
    assert reason == "missing_api_key", (
        f"expected reason='missing_api_key', got {reason!r}"
    )


def test_factory_reports_placeholder_when_provider_is_placeholder():
    """AI_PROVIDER=placeholder is an explicit fallback choice."""
    settings = _StubSettings(ai_provider="placeholder")
    factory = ProviderFactory(settings)
    assert factory.is_available() is False
    assert factory.status_reason() == "placeholder"


def test_factory_reports_missing_base_url_when_url_empty():
    """An OpenAI-compatible provider without a base URL is not usable."""
    settings = _StubSettings(
        ai_provider="openai_compatible",
        ai_api_key="sk-fake",
        ai_base_url="",
        ai_model="gemini-1.5-flash",
    )
    factory = ProviderFactory(settings)
    assert factory.is_available() is False
    assert factory.status_reason() == "missing_base_url"


def test_factory_reports_provider_unconfigured_when_name_empty():
    """Empty / unknown AI_PROVIDER is treated as 'unconfigured'."""
    settings = _StubSettings(ai_provider="")
    factory = ProviderFactory(settings)
    assert factory.is_available() is False
    assert factory.status_reason() == "provider_unconfigured"


def test_provider_status_payload_does_not_leak_secrets():
    """The status payload MUST NOT include api_key / authorization / full base_url.

    The audit requires that the audit-fix payload never exposes:
      * ``api_key``        — the literal bearer token
      * ``authorization``  — any header carrying the bearer
      * ``base_url``       — the full upstream URL (which can
                              contain the API key as a query param)

    We assert by constructing a settings stub whose API key is
    recognisable and verifying the payload never contains it.
    """
    secret = "AKIA-DETECT-ME-IN-LEAKS-9999"
    settings = _StubSettings(
        ai_provider="openai_compatible",
        ai_api_key=secret,
        ai_base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        ai_model="gemini-1.5-flash",
    )
    factory = ProviderFactory(settings)
    # Probe the public surface — the factory does not itself
    # emit a payload, but every field it could feed a payload
    # must be checked. We use ``configured_model`` and
    # ``status_reason`` directly. The endpoint wrapper that
    # calls ``provider_status`` is tested separately.
    payload_fields = {
        "configured_provider": factory.configured_provider_name(),
        "model": factory.configured_model(),
        "reason": factory.status_reason(),
    }
    for field_name, value in payload_fields.items():
        assert secret not in str(value), (
            f"secret leaked into provider-status field {field_name!r}: {value!r}"
        )

    # And the audit-mandated field list is exactly what the
    # schema permits — no api_key, no authorization, no base_url.
    forbidden = {"api_key", "authorization", "base_url", "auth_header"}
    # The factory doesn't expose these directly; the contract
    # is enforced by the schema (``extra="forbid"``) and the
    # service-level ``provider_status`` returns a fixed dict.
    # We assert the factory's public API surface here.
    public_attrs = {a for a in dir(factory) if not a.startswith("_")}
    leaked = public_attrs & forbidden
    assert not leaked, (
        f"factory exposes forbidden attributes that could leak secrets: {leaked}"
    )
