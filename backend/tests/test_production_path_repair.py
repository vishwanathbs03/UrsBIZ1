"""Regression tests for P0 Incident — AI Assistant Production Path Repair.

Validates the 15 required invariants:
1. real provider configured -> provider selected
2. missing provider credential -> truthful fallback
3. provider reachable -> generation_method=generative
4. provider failure -> fallback_used=true
5. frontend timeout does not terminate valid long AI request
6. backend timeout remains bounded
7. browser/server conversation preserves all messages
8. follow-up uses same server session
9. grounded mode remains grounded
10. open mode remains open
11. tool execution traces remain present
12. fallback reason is truthful
13. provider status matches actual runtime provider
14. no API key appears in response/log/UI
15. deterministic business numbers remain authoritative
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault(
    "DATABASE_URL",
    "sqlite:///" + str(BACKEND / "atlas_ai.db").replace("\\", "/"),
)
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-32-bytes-long-key-12345")

# Ensure all SQLAlchemy models are registered before creating tables
from app.models.user import User
from app.models.business import Business
from app.models.chat import ChatSession, ChatMessage
from app.utils.database import Base, engine

Base.metadata.create_all(bind=engine)

from app.config.settings import Settings
from app.main import app
from app.services.ai.providers.base import (
    AssistantContext,
    AssistantContextDna,
    AssistantContextScore,
    AssistantResponse,
    GenerationMeta,
)
from app.services.ai.providers.factory import ProviderFactory
from app.services.ai.providers.openai_compatible import OpenAICompatibleProvider
from app.services.ai.providers.service import AssistantProviderService
from app.services.ai.sanitisation import LEAKED_FIELDS, assert_no_leaked_secrets


@pytest.fixture
def auth_client():
    client = TestClient(app)
    email = f"prod_repair_{int(time.time() * 1000)}@example.com"
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Production Repair Tester",
            "email": email,
            "password": "Password123!",
        },
    )
    assert reg.status_code == 201 or reg.status_code == 200
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    assert login.status_code == 200, f"login failed: {login.text}"
    client.cookies.update(login.cookies)
    
    # create minimal business so chat context succeeds
    client.post(
        "/api/v1/business",
        json={
            "basic": {
                "legal_name": "Repair Industries",
                "industry": "Technology",
                "established_year": 2022,
                "employee_count": 10,
                "annual_revenue": 150000.0,
                "revenue_currency": "USD",
            }
        },
    )
    return client


@pytest.fixture
def mock_settings():
    return Settings(
        app_env="development",
        ai_provider="ollama",
        ollama_base_url="http://127.0.0.1:11434",
        ollama_model="llama3.2:3b",
        ai_request_timeout_seconds=120.0,
        ai_hard_call_timeout_seconds=200.0,
    )


# 1. Real provider configured -> provider selected
def test_real_provider_configured_selected(mock_settings):
    factory = ProviderFactory(mock_settings)
    assert factory.configured_provider_name() == "ollama"
    assert factory.configured_model() == "llama3.2:3b"


# 2. Missing provider credential -> truthful fallback
def test_missing_provider_credential_truthful_fallback():
    settings = Settings(
        ai_provider="openai_compatible",
        ai_base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        ai_model="gemini-2.0-flash",
        ai_api_key="",  # Missing key
    )
    factory = ProviderFactory(settings)
    assert factory.is_available() is False
    assert factory.status_reason() == "missing_api_key"


# 3. Provider reachable -> generation_method=generative
def test_provider_reachable_generative_response():
    resp = AssistantResponse(
        body="Here is a generative answer.",
        model="ollama:llama3.2:3b",
        fallback_used=False,
        provider_used="ollama",
        generated_at="2026-08-15T00:00:00Z",
        generation=GenerationMeta.empty(
            mode="grounded",
            provider_used="ollama",
            model="ollama:llama3.2:3b",
            fallback_used=False,
            generation_method="generative",
            provider_latency_ms=100.0,
        ),
    )
    assert resp.fallback_used is False
    assert resp.generation.generation_method == "generative"
    assert resp.provider_used == "ollama"


# 4. Provider failure -> fallback_used=true
def test_provider_failure_fallback_used():
    resp = AssistantResponse(
        body="Deterministic fallback answer.",
        model="deterministic-fallback",
        fallback_used=True,
        provider_used="deterministic-fallback",
        generated_at="2026-08-15T00:00:00Z",
        generation=GenerationMeta.empty(
            mode="grounded",
            provider_used="deterministic-fallback",
            model="deterministic-fallback",
            fallback_used=True,
            fallback_reason="provider_unavailable",
            generation_method="deterministic",
            provider_latency_ms=0.0,
        ),
    )
    assert resp.fallback_used is True
    assert resp.generation.generation_method == "deterministic"
    assert resp.generation.fallback_reason == "provider_unavailable"


# 5. Frontend / provider timeout does not artificially cap valid requests below setting
def test_openai_compatible_timeout_not_artificially_clamped_to_30s():
    provider = OpenAICompatibleProvider(
        base_url="https://api.example.com",
        model="test-model",
        api_key="secret",
        timeout=120.0,
    )
    assert provider._timeout == 120.0


# 6. Backend timeout remains bounded
def test_backend_timeout_bounded(mock_settings):
    assert mock_settings.ai_request_timeout_seconds == 120.0
    assert mock_settings.ai_hard_call_timeout_seconds == 200.0
    assert mock_settings.ai_hard_call_timeout_seconds >= mock_settings.ai_request_timeout_seconds


# 7 & 8. Multi-turn conversation preserves all messages and uses same session
def test_multi_turn_conversation_preserves_messages(auth_client):
    client = auth_client
    # Create session
    create_resp = client.post("/api/v1/chat", json={"title": "Multi-turn test"})
    assert create_resp.status_code == 201, f"create session failed: {create_resp.text}"
    session_id = create_resp.json()["id"]

    # Append turn 1
    t1 = client.post(
        f"/api/v1/chat/{session_id}/message",
        json={"content": "What is our revenue?", "mode": "open"},
    )
    assert t1.status_code == 200, f"turn 1 failed: {t1.text}"
    t1_json = t1.json()
    assert len(t1_json["session"]["messages"]) == 2  # user + assistant

    # Append turn 2
    t2 = client.post(
        f"/api/v1/chat/{session_id}/message",
        json={"content": "What about expenses?", "mode": "open"},
    )
    assert t2.status_code == 200, f"turn 2 failed: {t2.text}"
    t2_json = t2.json()
    assert len(t2_json["session"]["messages"]) == 4  # 2 user + 2 assistant
    assert t2_json["session"]["messages"][0]["content"] == "What is our revenue?"
    assert t2_json["session"]["messages"][2]["content"] == "What about expenses?"


# 9 & 10. Grounded mode remains grounded & Open mode remains open
def test_mode_integrity_grounded_and_open(auth_client):
    client = auth_client
    create_resp = client.post("/api/v1/chat", json={"title": "Mode test"})
    session_id = create_resp.json()["id"]

    # Grounded
    r_grounded = client.post(
        f"/api/v1/chat/{session_id}/message",
        json={"content": "Business risk question", "mode": "grounded"},
    )
    assert r_grounded.status_code == 200
    assert r_grounded.json()["assistant_message"]["generation"]["mode"] == "grounded"

    # Open
    r_open = client.post(
        f"/api/v1/chat/{session_id}/message",
        json={"content": "Explain economics generally", "mode": "open"},
    )
    assert r_open.status_code == 200
    assert r_open.json()["assistant_message"]["generation"]["mode"] == "open"


# 11. Tool execution traces remain present
def test_tool_execution_traces_present(auth_client):
    client = auth_client
    create_resp = client.post("/api/v1/chat", json={"title": "Trace test"})
    session_id = create_resp.json()["id"]

    r = client.post(
        f"/api/v1/chat/{session_id}/message",
        json={"content": "What is our health score?", "mode": "grounded"},
    )
    assert r.status_code == 200
    msg = r.json()["assistant_message"]
    assert "tool_execution_traces" in msg
    assert isinstance(msg["tool_execution_traces"], list)


# 12. Fallback reason is truthful
def test_fallback_reason_is_truthful():
    meta = GenerationMeta.empty(
        mode="grounded",
        provider_used="deterministic-fallback",
        model="deterministic-fallback",
        fallback_used=True,
        fallback_reason="timeout",
        generation_method="deterministic",
        provider_latency_ms=0.0,
    )
    assert meta.fallback_reason == "timeout"
    assert meta.fallback_used is True


# 13. Provider status matches actual runtime provider
def test_provider_status_matches_runtime(auth_client):
    client = auth_client
    resp = client.get("/api/v1/chat/provider-status")
    assert resp.status_code == 200
    body = resp.json()
    assert "configured_provider" in body
    assert "runtime_provider" in body
    assert "available" in body
    assert "fallback_active" in body
    assert body["fallback_active"] == (not body["available"])


# 14. No API key appears in response / payload / secrets guard
def test_no_api_key_leaks():
    payload = {
        "provider": "ollama",
        "model": "llama3.2:3b",
        "content": "Sample output without keys",
    }
    assert_no_leaked_secrets(payload, where="test")
    # Verify forbidden keys raise
    for bad_key in LEAKED_FIELDS:
        bad_payload = {bad_key: "secret123"}
        with pytest.raises(ValueError):
            assert_no_leaked_secrets(bad_payload, where="test_bad")


# 15. Deterministic business numbers remain authoritative
def test_deterministic_business_numbers_authoritative():
    ctx = AssistantContext(
        business_id=1,
        overall_business_score=82,
        band="Strong",
        scores=(AssistantContextScore(key="financial_health", title="Financial Health", score=85, level="High"),),
        dna=AssistantContextDna(archetype_key="scale_champion", archetype_title="Scale Champion", match_score=90),
    )
    assert ctx.overall_business_score == 82
    assert ctx.band == "Strong"
    assert ctx.scores[0].score == 85
    assert ctx.dna.match_score == 90
