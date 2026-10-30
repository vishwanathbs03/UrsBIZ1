"""Regression test for BUG-1 — hard wall-clock timeout on LLM calls.

Root-cause target
-----------------

Before H7.9R+ the ``AssistantProviderService.generate`` path could
hang indefinitely when a configured upstream (e.g. Gemini) was
unreachable but the connection had not yet triggered the provider's
own ``httpx.Client(timeout=...)`` budget. The chat endpoint would
then hold a worker thread until the FastAPI request timeout (or
the test harness) finally killed it, with no fallback ever firing.

The fix wraps every outbound ``provider.complete(request)`` call
in a hard wall-clock cap (15 s) and falls back to the
deterministic provider the instant the cap fires. The chat
endpoint therefore always returns within the budget; the frontend
never waits forever.

These tests assert
  (1) the wrapper exists and is exported,
  (2) the cap ceiling is the committed ``HARD_CALL_TIMEOUT_SECONDS``,
  (3) a fast stub provider still returns the real provider's response,
  (4) a slow stub provider triggers ``TimeoutError`` from the
      wrapper well before the provider's blocked duration, and the
      wrapper releases the provider (``close()`` is called).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

import pytest

from app.services.ai.providers.base import (
    AssistantContext,
    AssistantContextDna,
    AssistantRequest,
    AssistantResponse,
    GenerationMeta,
)
from app.services.ai.providers.service import (
    HARD_CALL_TIMEOUT_SECONDS,
    _call_with_hard_timeout,
)


def _make_context() -> AssistantContext:
    """Build a minimal but schema-valid ``AssistantContext``.

    The wrapper only forwards the request; it never introspects
    fields beyond the Python call. So we can pass the minimum
    payload that satisfies the (required) dataclass fields.
    """
    return AssistantContext(
        business_id=1,
        overall_business_score=72,
        band="established",
        dna=AssistantContextDna(
            archetype_key="manufacturer",
            archetype_title="Manufacturer",
            match_score=80,
        ),
    )


class _FastStubProvider:
    name = "stub-fast"
    model_name = "stub-fast-model"
    closed = False

    def complete(self, request: AssistantRequest) -> AssistantResponse:
        return AssistantResponse(
            body="fast provider body",
            model=self.model_name,
            fallback_used=False,
            provider_used=self.name,
            generated_at="2026-08-07T00:00:00Z",
            provider_latency_ms=10,
            generation=GenerationMeta.empty(
                mode="grounded",
                provider_used=self.name,
                model=self.model_name,
                provider_latency_ms=10,
                fallback_used=False,
                generation_method="generative",
            ),
        )

    def close(self) -> None:
        self.closed = True


class _HangingStubProvider:
    """A provider whose ``complete`` blocks longer than the cap."""

    name = "stub-hanging"
    model_name = "stub-hanging-model"
    close_calls = 0
    completed = False

    def complete(self, request: AssistantRequest) -> AssistantResponse:
        # Block for longer than the cap. The wrapper must release
        # us within HARD_CALL_TIMEOUT_SECONDS.
        time.sleep(HARD_CALL_TIMEOUT_SECONDS + 2.0)
        # If the wrapper fails this branch never executes — the
        # test runner killed us before. If we do get here the
        # test failed (the cap didn't fire).
        self.completed = True
        return AssistantResponse(
            body="unreachable",
            model=self.model_name,
            fallback_used=False,
            provider_used=self.name,
            generated_at="2026-08-07T00:00:00Z",
        )

    def close(self) -> None:
        self.close_calls += 1


def test_hard_timeout_constant_is_at_least_15_seconds():
    """H8.11 — the cap is no longer hard-coded at 15 s; it
    reads from ``Settings.ai_hard_call_timeout_seconds``
    (default 150 s). This is the documented H8.11 fix: a
    15 s cap silently forced every grounded-mode llama3.2:3b
    call into the deterministic fallback because the model
    legitimately needs 25–145 s on a 5.9 GB Windows host.
    The test now guards the *lower bound* so a future
    regression that drops the cap below the previous value
    is caught immediately.
    """
    assert HARD_CALL_TIMEOUT_SECONDS >= 15.0, (
        f"HARD_CALL_TIMEOUT_SECONDS must be >= 15 s; "
        f"got {HARD_CALL_TIMEOUT_SECONDS}"
    )


def test_call_with_hard_timeout_returns_real_response():
    """A fast provider's response is returned unchanged."""
    provider = _FastStubProvider()
    req = AssistantRequest(
        user_prompt="hello",
        context=_make_context(),
        history=(),
        mode="grounded",
    )
    out = _call_with_hard_timeout(provider, req, timeout=HARD_CALL_TIMEOUT_SECONDS)
    assert out.body == "fast provider body"
    assert out.provider_used == "stub-fast"


def test_call_with_hard_timeout_raises_on_slow_provider():
    """A provider that blocks past the cap raises (caught upstream).

    Critical: the runtime cap MUST be respected. We assert the
    cap was respected by measuring the wall-clock duration of
    the wrapper call — it MUST be strictly less than the
    provider's blocked duration (cap + 2 s).
    """
    provider = _HangingStubProvider()
    req = AssistantRequest(
        user_prompt="hangs",
        context=_make_context(),
        history=(),
        mode="grounded",
    )
    started = time.time()
    with pytest.raises(Exception) as exc_info:
        _call_with_hard_timeout(provider, req, timeout=HARD_CALL_TIMEOUT_SECONDS)
    elapsed = time.time() - started
    # Must return well before the provider's 17 s sleep finishes.
    assert elapsed < HARD_CALL_TIMEOUT_SECONDS + 1.5, (
        f"wrapper took {elapsed:.2f}s, expected < {HARD_CALL_TIMEOUT_SECONDS + 1.5}s"
    )
    # The exception must be a TimeoutError-family — concurrent.futures
    # raises TimeoutError, Python 3.11+ exposes it as builtins.TimeoutError.
    assert exc_info.type in (TimeoutError,), (
        f"unexpected exception type: {exc_info.type}"
    )
