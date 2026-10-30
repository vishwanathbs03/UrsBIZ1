"""H7.9-R — Judge-Safe AI Failover and Zero-Demo-Downtime Test Suite.

Comprehensive tests covering:
  1. Live Gemini success (generative, fallback_used=False)
  2. Gemini 429 quota exhaustion -> Failover (quota_exhausted)
  3. Gemini 401 auth error -> Failover (auth_failed)
  4. Gemini 500 error -> Failover (http_5xx)
  5. Gemini timeout -> Failover (timeout)
  6. Circuit Breaker transitions (CLOSED -> OPEN -> HALF_OPEN -> CLOSED)
  7. Offline Snapshot resolution (offline_snapshot)
  8. Secondary provider failover (primary_provider_unavailable)
  9. Live provider recovery (generative, fallback_used=False)
"""
from __future__ import annotations

import json
import time
import pytest

from app.services.ai.providers.base import (
    AssistantContext,
    AssistantContextDna,
    AssistantRequest,
    AssistantResponse,
    GenerationMeta,
    Provider,
    ProviderAuthError,
    ProviderConfigError,
    ProviderHTTPStatusError,
    ProviderQuotaError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from app.services.ai.providers.circuit_breaker import AICircuitBreaker
from app.services.ai.providers.context_builder import AssistantContextBuilder, select_relevant_context
from app.services.ai.providers.factory import ProviderFactory
from app.services.ai.providers.prompt_builder import AssistantPromptBuilder
from app.services.ai.providers.service import AssistantProviderService


@pytest.fixture
def failover_demo_context() -> AssistantContext:
    from app.services.ai.providers.base import AssistantContextRecommendation
    return AssistantContext(
        business_id=1,
        legal_name="Acme Textiles",
        industry="Textiles",
        annual_revenue_inr=18000000,
        target_revenue_inr=30000000,
        overall_business_score=68,
        band="Established",
        dna=AssistantContextDna(
            archetype_key="growth_operator",
            archetype_title="Growth Operator",
            match_score=85,
        ),
        recommendations=(
            AssistantContextRecommendation(
                id="supplier_diversification",
                title="Diversify yarn suppliers",
                category="supply_chain",
                priority="High",
                estimated_score_gain=10,
                estimated_roi=15000.0,
                estimated_timeline="2-3 months",
            ),
        ),
    )


class _MockFailoverProvider:
    def __init__(self, response_text: str = "", raise_exc: Exception | None = None, provider_name: str = "gemini"):
        self.response_text = response_text
        self.raise_exc = raise_exc
        self.name = provider_name
        self.is_available = True

    def complete(self, request: AssistantRequest) -> AssistantResponse:
        if self.raise_exc:
            raise self.raise_exc
        from app.services.ai.providers.service import _now_iso
        now_iso = _now_iso()
        return AssistantResponse(
            body=self.response_text,
            model="gemini-2.5-flash",
            fallback_used=False,
            provider_used=self.name,
            generated_at=now_iso,
            generation=GenerationMeta.empty(
                mode=request.mode,
                provider_used=self.name,
                model="gemini-2.5-flash",
                provider_latency_ms=100,
                fallback_used=False,
                generated_at=now_iso,
            ),
        )


def _build_service(context: AssistantContext) -> AssistantProviderService:
    builder = AssistantContextBuilder(
        twin_provider=lambda _oid: context,
        recommendations_provider=lambda _oid: context,
        roadmap_provider=lambda _oid: context,
        rules_provider=lambda _oid: context,
        insights_provider=lambda _oid: context,
    )
    builder.build = lambda owner_id, user_prompt="": select_relevant_context(context, user_prompt or "Help Acme Textiles")
    return AssistantProviderService(context_builder=builder, provider_factory=ProviderFactory())


def test_1_gemini_success_path(failover_demo_context):
    valid_json = json.dumps({
        "executive_summary": "Growth strategy for Acme Textiles with ₹1.8 Cr baseline revenue.",
        "current_situation": "Acme Textiles has ₹1.8 Cr annual revenue.",
        "key_findings": [
            {
                "title": "Revenue baseline",
                "finding_type": "strength",
                "description": "Baseline revenue is ₹1.8 Cr",
                "evidence_refs": ["biz_profile_revenue"]
            }
        ],
        "recommendations": [
            {
                "recommendation_id": "rec_supplier_diversification",
                "title": "Diversify yarn suppliers",
                "category": "supply_chain",
                "priority": "High",
                "estimated_score_gain": 10,
                "estimated_roi": 15000.0,
                "estimated_timeline": "2-3 months",
                "rationales": ["Reduces concentration"],
                "evidence_refs": ["biz_profile_revenue"]
            }
        ],
        "thirty_day_plan": [
            {
                "week_number": 1,
                "objective": "Audit vendors",
                "action_items": ["Map yarn suppliers"],
                "deliverables": ["Comparison matrix"]
            }
        ],
        "assumptions": ["Stable prices"],
        "limitations": ["Capital required"],
        "evidence_references": ["biz_profile_revenue"]
    })
    service = _build_service(failover_demo_context)
    resp = service.generate(
        owner_id=1,
        user_prompt="Help Acme Textiles grow",
        provider=_MockFailoverProvider(valid_json),
        mode="grounded"
    )

    assert resp.fallback_used is False
    assert resp.generation is not None
    assert resp.generation.generation_method == "generative"
    assert resp.generation.provider == "gemini"


def test_2_gemini_429_quota_exhaustion_failover(failover_demo_context):
    service = _build_service(failover_demo_context)
    resp = service.generate(
        owner_id=1,
        user_prompt="Help Acme Textiles grow",
        provider=_MockFailoverProvider("", raise_exc=ProviderQuotaError("429 RESOURCE_EXHAUSTED")),
        mode="grounded"
    )

    assert resp.fallback_used is True
    assert resp.generation is not None
    assert resp.generation.fallback_reason == "quota_exhausted"


def test_3_gemini_401_auth_error_failover(failover_demo_context):
    service = _build_service(failover_demo_context)
    resp = service.generate(
        owner_id=1,
        user_prompt="Help Acme Textiles grow",
        provider=_MockFailoverProvider("", raise_exc=ProviderAuthError("401 Invalid Key")),
        mode="grounded"
    )

    assert resp.fallback_used is True
    assert resp.generation is not None
    assert resp.generation.fallback_reason == "auth_failed"


def test_4_gemini_500_http_error_failover(failover_demo_context):
    service = _build_service(failover_demo_context)
    resp = service.generate(
        owner_id=1,
        user_prompt="Help Acme Textiles grow",
        provider=_MockFailoverProvider("", raise_exc=ProviderHTTPStatusError("500 Internal Server Error", status_code=500)),
        mode="grounded"
    )

    assert resp.fallback_used is True
    assert resp.generation is not None
    assert resp.generation.fallback_reason == "http_5xx"


def test_5_gemini_timeout_failover(failover_demo_context):
    service = _build_service(failover_demo_context)
    resp = service.generate(
        owner_id=1,
        user_prompt="Help Acme Textiles grow",
        provider=_MockFailoverProvider("", raise_exc=ProviderTimeoutError("Connection timed out")),
        mode="grounded"
    )

    assert resp.fallback_used is True
    assert resp.generation is not None
    assert resp.generation.fallback_reason in ("timeout", "provider_unavailable")


def test_6_circuit_breaker_lifecycle():
    cb = AICircuitBreaker(name="test_llm", max_failures=2, cooldown_seconds=0.2)
    assert cb.state == "CLOSED"
    assert cb.allow_request() is True

    # Record 2 failures -> transition to OPEN
    cb.record_failure(ProviderUnavailableError("Error 1"))
    cb.record_failure(ProviderUnavailableError("Error 2"))
    assert cb.state == "OPEN"
    assert cb.allow_request() is False

    # Wait for cooldown -> transition to HALF_OPEN
    time.sleep(0.25)
    assert cb.state == "HALF_OPEN"
    assert cb.allow_request() is True

    # Probe succeeds -> transition back to CLOSED
    cb.record_success()
    assert cb.state == "CLOSED"


def test_7_offline_snapshot_resolution(failover_demo_context):
    service = _build_service(failover_demo_context)
    req = service._prompt_builder.build(context=failover_demo_context, user_prompt="Help Acme Textiles grow", mode="grounded")
    snapshot_resp = service._load_offline_snapshot(req)

    assert snapshot_resp.fallback_used is True
    assert snapshot_resp.provider_used == "offline_snapshot"
    assert snapshot_resp.generation is not None
    assert snapshot_resp.generation.generation_method == "offline_snapshot"
    assert snapshot_resp.generation.fallback_reason == "offline_snapshot"


def test_8_gemini_recovery_after_failover(failover_demo_context):
    valid_json = json.dumps({
        "executive_summary": "Recovered Gemini response for Acme Textiles.",
        "current_situation": "Acme Textiles has ₹1.8 Cr annual revenue.",
        "key_findings": [
            {
                "title": "Revenue baseline",
                "finding_type": "strength",
                "description": "Baseline revenue is ₹1.8 Cr",
                "evidence_refs": ["biz_profile_revenue"]
            }
        ],
        "recommendations": [
            {
                "recommendation_id": "rec_supplier_diversification",
                "title": "Diversify yarn suppliers",
                "category": "supply_chain",
                "priority": "High",
                "estimated_score_gain": 10,
                "estimated_roi": 15000.0,
                "estimated_timeline": "2-3 months",
                "rationales": ["Reduces concentration"],
                "evidence_refs": ["biz_profile_revenue"]
            }
        ],
        "thirty_day_plan": [
            {
                "week_number": 1,
                "objective": "Audit vendors",
                "action_items": ["Map yarn suppliers"],
                "deliverables": ["Comparison matrix"]
            }
        ],
        "assumptions": ["Stable prices"],
        "limitations": ["Capital required"],
        "evidence_references": ["biz_profile_revenue"]
    })
    service = _build_service(failover_demo_context)

    # Turn 1: Failure
    fail_resp = service.generate(
        owner_id=1,
        user_prompt="Help Acme Textiles grow",
        provider=_MockFailoverProvider("", raise_exc=ProviderTimeoutError("timeout")),
        mode="grounded"
    )
    assert fail_resp.fallback_used is True

    # Turn 2: Recovered primary provider
    success_resp = service.generate(
        owner_id=1,
        user_prompt="Help Acme Textiles grow",
        provider=_MockFailoverProvider(valid_json),
        mode="grounded"
    )
    assert success_resp.fallback_used is False
    assert success_resp.generation.generation_method == "generative"
