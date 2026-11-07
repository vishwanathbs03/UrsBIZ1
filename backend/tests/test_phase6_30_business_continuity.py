"""Phase 6.30 — Business Continuity & Graceful Degradation Test Suite.

Verifies:
1. Circuit Breaker transitions (CLOSED -> OPEN -> HALF_OPEN -> CLOSED), short-circuiting,
   metrics tracking, and manual trip/reset mechanics.
2. Global circuit breaker sharing across AssistantProviderService and ResilientGeminiClient.
3. Immediate, transparent failover to DeterministicFallbackProvider upon timeouts, rate limits (429),
   or 5xx provider errors, stamping fallback_used=True and exact provenance with zero hallucination.
4. Dashboard graceful degradation under database failure (serving cached historical snapshots
   or safe baselines with is_degraded=True, eliminating unhandled 500 errors).
5. ContinuityService multi-subsystem aggregation and health endpoints (/api/v1/health/continuity,
   /api/v1/health/continuity/simulate).
6. Multilingual parity (English & Kannada) across all operational continuity notices.
"""

from __future__ import annotations

import time
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.repositories.business_repository import BusinessRepository
from app.schemas.dashboard import DashboardResponse
from app.services.ai.providers.base import (
    AssistantContext,
    AssistantContextDna,
    AssistantResponse,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from app.services.ai.providers.circuit_breaker import (
    AICircuitBreaker,
    CircuitState,
)
from app.services.ai.providers.context_builder import (
    AssistantContextBuilder,
    select_relevant_context,
)
from app.services.ai.providers.service import AssistantProviderService
from app.services.ai.resilient_client import get_gemini_circuit_breaker
from app.services.continuity_service import (
    ContinuityMode,
    ContinuityService,
    SystemContinuityStatus,
)
from app.services.dashboard_service import DashboardService


def _make_dummy_context_builder(context: AssistantContext | None = None) -> AssistantContextBuilder:
    if context is None:
        context = AssistantContext(
            business_id=1,
            legal_name="Mysore Silk Weavers",
            industry="Textiles",
            annual_revenue_inr=500000.0,
            target_revenue_inr=1000000.0,
            overall_business_score=75,
            band="Established",
            dna=AssistantContextDna(
                archetype_key="growth_operator",
                archetype_title="Growth Operator",
                match_score=85,
            ),
        )
    builder = AssistantContextBuilder(
        twin_provider=lambda _oid: context,
        recommendations_provider=lambda _oid: context,
        roadmap_provider=lambda _oid: context,
        rules_provider=lambda _oid: context,
        insights_provider=lambda _oid: context,
    )
    builder.build = lambda owner_id, user_prompt="": select_relevant_context(
        context, user_prompt or "Analyze my business"
    )
    return builder


# Fixture for clean circuit breaker and continuity state
@pytest.fixture(autouse=True)
def reset_continuity_state():
    """Ensure every test begins with a clean, CLOSED circuit breaker and unsimulated DB."""
    cb = get_gemini_circuit_breaker()
    cb.reset()
    ContinuityService.simulate_action("reset_all")
    DashboardService._SNAPSHOT_CACHE.clear()
    yield
    cb.reset()
    ContinuityService.simulate_action("reset_all")
    DashboardService._SNAPSHOT_CACHE.clear()


@pytest.fixture
def client():
    return TestClient(app)


# --------------------------------------------------------------------------- #
# 1. Circuit Breaker Mechanics & State Transitions
# --------------------------------------------------------------------------- #


def test_circuit_breaker_initial_state():
    cb = AICircuitBreaker(name="test_cb", max_failures=3, cooldown_seconds=10.0)
    assert cb.state == "CLOSED"
    assert cb.allow_request() is True
    metrics = cb.get_metrics()
    assert metrics["state"] == "CLOSED"
    assert metrics["failure_count"] == 0
    assert metrics["success_count"] == 0
    assert metrics["is_available"] is True
    assert metrics["last_failure_reason"] is None


def test_circuit_breaker_trips_to_open_after_failure_threshold():
    cb = AICircuitBreaker(name="test_cb", max_failures=3, cooldown_seconds=10.0)

    cb.record_failure(RuntimeError("HTTP 503 Service Unavailable"))
    assert cb.state == "CLOSED"
    assert cb._failure_count == 1

    cb.record_failure(RuntimeError("HTTP 429 Resource Exhausted"))
    assert cb.state == "CLOSED"
    assert cb._failure_count == 2

    cb.record_failure(TimeoutError("ReadTimeout"))
    assert cb.state == "OPEN"
    assert cb._failure_count == 3
    assert cb.allow_request() is False

    metrics = cb.get_metrics()
    assert metrics["state"] == "OPEN"
    assert "ReadTimeout" in (metrics["last_failure_reason"] or "")
    assert metrics["cooldown_remaining_seconds"] > 0


def test_circuit_breaker_short_circuits_when_open():
    cb = AICircuitBreaker(name="test_cb", max_failures=2, cooldown_seconds=30.0)
    cb.record_failure(RuntimeError("Fail 1"))
    cb.record_failure(RuntimeError("Fail 2"))
    assert cb.state == "OPEN"
    assert cb.allow_request() is False

    with pytest.raises(ProviderUnavailableError) as exc_info:
        cb.execute_with_resilience(lambda: 42)
    assert "Circuit breaker for test_cb is OPEN" in str(exc_info.value)
    assert "Fail 2" in str(exc_info.value)


def test_circuit_breaker_transitions_to_half_open_and_recovers():
    cb = AICircuitBreaker(name="test_cb", max_failures=2, cooldown_seconds=0.2)
    cb.record_failure(RuntimeError("Fail 1"))
    cb.record_failure(RuntimeError("Fail 2"))
    assert cb.state == "OPEN"

    time.sleep(0.25)
    assert cb.state == "HALF_OPEN"
    assert cb.allow_request() is True

    cb.record_success()
    assert cb.state == "CLOSED"
    assert cb._failure_count == 0
    assert cb._success_count == 1


def test_circuit_breaker_half_open_re_trips_on_failure():
    cb = AICircuitBreaker(name="test_cb", max_failures=2, cooldown_seconds=0.2)
    cb.record_failure(RuntimeError("Fail 1"))
    cb.record_failure(RuntimeError("Fail 2"))
    assert cb.state == "OPEN"

    time.sleep(0.25)
    assert cb.state == "HALF_OPEN"

    cb.record_failure(RuntimeError("Fail during probe"))
    assert cb.state == "OPEN"
    assert cb._failure_count >= 1


def test_circuit_breaker_manual_trip_and_reset():
    cb = AICircuitBreaker(name="test_cb", max_failures=5, cooldown_seconds=60.0)
    assert cb.state == "CLOSED"

    cb.trip(reason="Manual drill simulation")
    assert cb.state == "OPEN"
    assert cb.allow_request() is False
    assert cb.get_metrics()["last_failure_reason"] == "Manual drill simulation"

    cb.reset()
    assert cb.state == "CLOSED"
    assert cb._failure_count == 0
    assert cb.allow_request() is True
    assert cb.get_metrics()["last_failure_reason"] is None


# --------------------------------------------------------------------------- #
# 2. Assistant Provider Service & Transparent Fallback
# --------------------------------------------------------------------------- #


def test_assistant_provider_service_shares_global_circuit_breaker():
    builder = _make_dummy_context_builder()
    service = AssistantProviderService(context_builder=builder)
    global_cb = get_gemini_circuit_breaker()
    assert service._circuit_breaker is global_cb


def test_assistant_service_transparent_fallback_when_circuit_open():
    """When the circuit breaker is OPEN, AssistantProviderService automatically fails over

    to DeterministicFallbackProvider with zero hallucination and provenance stamps.
    """
    global_cb = get_gemini_circuit_breaker()
    global_cb.trip(reason="Simulated Gemini outage for business continuity")

    builder = _make_dummy_context_builder()
    service = AssistantProviderService(context_builder=builder)

    response = service.generate(
        owner_id=1,
        user_prompt="Analyze my business health and cash flow",
        language="en",
    )

    # Fallback guarantees
    assert response.fallback_used is True
    assert response.provider_used == "deterministic-fallback"
    assert response.fallback_reason == "circuit_open"
    assert response.body is not None
    assert len(response.body) > 0
    assert response.generation is not None
    assert response.generation.fallback_used is True
    assert response.generation.generation_method == "deterministic"
    assert response.generation.grounding_validated is True


def test_assistant_service_transparent_fallback_on_gemini_timeout():
    """Verify provider timeout triggers immediate fallback to deterministic rules."""
    class _TimingOutProvider:
        name = "mock_timeout_gemini"
        model_name = "gemini-2.5-flash"
        is_available = True

        def complete(self, request):
            raise ProviderTimeoutError("Request timed out after 15s")

    builder = _make_dummy_context_builder()
    service = AssistantProviderService(context_builder=builder)

    response = service.generate(
        owner_id=1,
        user_prompt="What is my working capital ratio?",
        provider=_TimingOutProvider(),
        language="en",
    )

    assert response.fallback_used is True
    assert response.provider_used == "deterministic-fallback"
    assert response.fallback_reason in ("timeout", "provider_unavailable")


def test_assistant_service_kannada_fallback_when_circuit_open():
    """Verify Kannada language requests produce natural Kannada deterministic fallback."""
    global_cb = get_gemini_circuit_breaker()
    global_cb.trip(reason="Gemini quota exhausted (429)")

    builder = _make_dummy_context_builder()
    service = AssistantProviderService(context_builder=builder)

    response = service.generate(
        owner_id=1,
        user_prompt="ನನ್ನ ವ್ಯಾಪಾರದ ದ್ರವ್ಯತೆ ಸ್ಥಿತಿಯನ್ನು ತಿಳಿಸಿ",
        language="kn",
    )

    assert response.fallback_used is True
    assert response.provider_used == "deterministic-fallback"
    assert response.body is not None
    # Verify authentic Kannada glyph content is returned
    assert any(0x0C80 <= ord(c) <= 0x0CFF for c in response.body)


# --------------------------------------------------------------------------- #
# 3. Dashboard Graceful Degradation & Snapshot Caching
# --------------------------------------------------------------------------- #


def test_dashboard_service_snapshot_caching_and_graceful_degradation():
    mock_repo = MagicMock(spec=BusinessRepository)
    service = DashboardService(mock_repo)

    # 1. Populate verified snapshot in cache
    initial_res = DashboardResponse(
        business=None,
        kpis={
            "total_revenue": 100000.0,
            "active_projects": 5,
            "efficiency_score": 85,
            "health_index": "Good",
        },
        health_score=85,
        ai_summary="Baseline healthy dashboard snapshot.",
        is_degraded=False,
    )
    DashboardService._SNAPSHOT_CACHE[42] = initial_res

    # 2. Simulate database failure
    mock_repo.get_by_owner.side_effect = ConnectionError("PostgreSQL pool connection timeout")

    # 3. Subsequent fetch serves cached snapshot with is_degraded=True
    degraded_res = service.get_dashboard(owner_id=42)
    assert degraded_res.is_degraded is True
    assert degraded_res.continuity_notice is not None
    assert "Serving last-verified snapshot" in degraded_res.continuity_notice
    assert degraded_res.kpis["efficiency_score"] == 85
    assert degraded_res.health_score == 85


def test_dashboard_service_safe_baseline_when_no_prior_snapshot():
    mock_repo = MagicMock(spec=BusinessRepository)
    mock_repo.get_by_owner.side_effect = RuntimeError("Database unreachable")

    service = DashboardService(mock_repo)
    # Owner 999 has never accessed dashboard before
    baseline_res = service.get_dashboard(owner_id=999)

    assert baseline_res.is_degraded is True
    assert baseline_res.continuity_notice is not None
    assert "Operating in resilient read-only mode" in baseline_res.continuity_notice
    assert baseline_res.kpis["efficiency_score"] == 75
    assert baseline_res.health_score == 75


# --------------------------------------------------------------------------- #
# 4. Continuity Service Holistic Status & Simulation
# --------------------------------------------------------------------------- #


def test_continuity_service_status_operational():
    status = ContinuityService.get_status()
    assert status.system_mode == "OPERATIONAL"
    assert status.database.status == "ok"
    assert status.database.mode == "read_write"
    assert status.ai_subsystem.status == "operational"
    assert status.ai_subsystem.circuit_breaker == "CLOSED"
    assert status.ai_subsystem.fallback_active is False
    assert status.can_read is True
    assert status.can_write is True
    assert "All platform subsystems operational" in status.notice_en
    assert "ಸುಸ್ಥಿತಿಯಲ್ಲಿ" in status.notice_kn


def test_continuity_service_status_when_circuit_tripped():
    ContinuityService.simulate_action("trip_ai_circuit")
    status = ContinuityService.get_status()

    assert status.system_mode == "RULE_ENGINE_FALLBACK"
    assert status.ai_subsystem.status == "degraded"
    assert status.ai_subsystem.circuit_breaker == "OPEN"
    assert status.ai_subsystem.fallback_active is True
    assert "LLM_CIRCUIT_BREAKER_ACTIVE" in status.active_safeguards
    assert "ZERO_HALLUCINATION_GUARANTEE" in status.active_safeguards
    assert "Rule Engine Mode" in status.notice_en
    assert "ನಿಯಮ ಎಂಜಿನ್ ಮೋಡ್" in status.notice_kn


def test_continuity_service_status_when_db_degraded():
    ContinuityService.simulate_action("simulate_db_degraded")
    status = ContinuityService.get_status()

    assert status.system_mode == "DEGRADED_READONLY"
    assert status.database.status == "degraded"
    assert status.database.mode == "read_only"
    assert status.can_write is False
    assert "STALE_SNAPSHOT_DASHBOARD_FALLBACK" in status.active_safeguards
    assert "Database is degraded" in status.notice_en
    assert "ಡೇಟಾಬೇಸ್ ವ್ಯತ್ಯಯವಾಗಿದೆ" in status.notice_kn


def test_continuity_service_reset_all():
    ContinuityService.simulate_action("trip_ai_circuit")
    ContinuityService.simulate_action("simulate_db_degraded")
    degraded = ContinuityService.get_status()
    assert degraded.system_mode == "DEGRADED_READONLY"

    restored = ContinuityService.simulate_action("reset_all")
    assert restored.system_mode == "OPERATIONAL"
    assert restored.database.mode == "read_write"
    assert restored.ai_subsystem.circuit_breaker == "CLOSED"


# --------------------------------------------------------------------------- #
# 5. Continuity Health REST API Endpoints
# --------------------------------------------------------------------------- #


def test_api_get_continuity_health(client: TestClient):
    response = client.get("/api/v1/health/continuity")
    assert response.status_code == 200
    data = response.json()

    assert "system_mode" in data
    assert "database" in data
    assert "ai_subsystem" in data
    assert "knowledge" in data
    assert "active_safeguards" in data
    assert "notice_en" in data
    assert "notice_kn" in data
    assert "can_read" in data
    assert "can_write" in data


def test_api_post_continuity_simulate_trip_and_reset(client: TestClient):
    # 1. Trip circuit via REST
    resp_trip = client.post("/api/v1/health/continuity/simulate", json={"action": "trip_ai_circuit"})
    assert resp_trip.status_code == 200
    data_trip = resp_trip.json()
    assert data_trip["system_mode"] == "RULE_ENGINE_FALLBACK"
    assert data_trip["ai_subsystem"]["circuit_breaker"] == "OPEN"

    # 2. Reset circuit via REST
    resp_reset = client.post("/api/v1/health/continuity/simulate", json={"action": "reset_ai_circuit"})
    assert resp_reset.status_code == 200
    data_reset = resp_reset.json()
    assert data_reset["system_mode"] == "OPERATIONAL"
    assert data_reset["ai_subsystem"]["circuit_breaker"] == "CLOSED"


def test_api_post_continuity_simulate_invalid_action(client: TestClient):
    resp = client.post("/api/v1/health/continuity/simulate", json={"action": "invalid_action"})
    assert resp.status_code == 422  # Pydantic validation error for Literal


# --------------------------------------------------------------------------- #
# 6. Bilingual Notice Semantics & Glyph Encoding Parity
# --------------------------------------------------------------------------- #


def test_continuity_bilingual_notices_parity():
    status = ContinuityService.get_status()
    # Ensure neither notice is empty
    assert len(status.notice_en.strip()) > 0
    assert len(status.notice_kn.strip()) > 0
    # Ensure Kannada notice contains valid Kannada Unicode block characters (U+0C80 - U+0CFF)
    assert any(0x0C80 <= ord(c) <= 0x0CFF for c in status.notice_kn)
    # Ensure no mojibake question marks or replacement characters in Kannada notices
    assert "\ufffd" not in status.notice_kn
    assert "??" not in status.notice_kn
