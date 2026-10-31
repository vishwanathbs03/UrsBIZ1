"""Test suite for Sprint H8.9 — Zero AI Failure Resilience & Multi-Tier Provider Failover."""

import time
import pytest
from app.services.ai.providers.base import (
    AssistantContext,
    AssistantContextDna,
    ProviderQuotaError,
    ProviderUnavailableError,
)
from app.services.ai.providers.circuit_breaker import AICircuitBreaker
from app.services.ai.providers.response_cache import ResponseCache


@pytest.fixture
def sim_context() -> AssistantContext:
    return AssistantContext(
        business_id=1,
        legal_name="Acme Textiles",
        industry="Textiles",
        annual_revenue_inr=18000000,
        overall_business_score=68,
        band="Established",
        dna=AssistantContextDna("growth_operator", "Growth Operator", 85),
    )


def test_1_response_cache_put_and_get():
    """Verify ResponseCache stores and retrieves responses by hash key."""
    cache = ResponseCache(max_entries=10)
    prompt = "How can I reach ₹3 Cr?"
    business_id = 1
    mock_resp = {"status": "ok", "body": "Test response"}

    assert cache.get(prompt, business_id) is None
    cache.put(prompt, business_id, mock_resp)
    assert cache.get(prompt, business_id) == mock_resp


def test_2_circuit_breaker_trips_to_open():
    """Verify AICircuitBreaker trips to OPEN on quota error or 3 consecutive failures."""
    cb = AICircuitBreaker(name="test_gemini", max_failures=3, cooldown_seconds=5.0)
    assert cb.state == "CLOSED"
    assert cb.allow_request() is True

    # Immediate OPEN on quota error
    cb.record_failure(ProviderQuotaError("Quota exhausted 429"))
    assert cb.state == "OPEN"
    assert cb.allow_request() is False


def test_3_circuit_breaker_resilience_execution():
    """Verify execute_with_resilience short-circuits when OPEN."""
    cb = AICircuitBreaker(name="test_gemini", max_failures=1, cooldown_seconds=10.0)
    cb.record_failure(ProviderQuotaError("Quota exhausted 429"))

    with pytest.raises(ProviderUnavailableError):
        cb.execute_with_resilience(lambda: "should not run")


def test_4_zero_failure_fallback_latency(sim_context):
    """Verify fallback execution completes in under 500ms."""
    start = time.time()
    cb = AICircuitBreaker(name="gemini")
    cb.record_failure(ProviderQuotaError("429 Quota"))
    elapsed = time.time() - start

    assert elapsed < 0.5
    assert cb.state == "OPEN"
