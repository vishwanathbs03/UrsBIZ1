"""H7.8C — authenticated provider-status route ordering regression test.

Root-cause target
-----------------

``GET /api/v1/chat/provider-status`` was being shadowed by
``GET /api/v1/chat/{session_id}``. FastAPI matches routes in
declaration order, so the literal path ``provider-status``
was being captured by the ``/{session_id}`` route and rejected
by the ``Path(ge=1)`` int validator with HTTP 422 — even when
the request carried a valid ``atlas_access_token`` cookie.

This test fails on the pre-fix code (always 422) and passes
after the fix (200 when authenticated, 401 when not).

Run standalone:

    python tests/test_h7_8c_provider_status_auth.py

or under pytest.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

os.environ["APP_ENV"] = "test"
# Use the SAME database the dev server uses so the test sees
# the same tables/migrations (SQLite is file-backed; running
# ``pytest`` against an empty file would require running
# migrations first, which the dev DB already has).
_TEST_DB = BACKEND / "hackathon_demo.db"
if not _TEST_DB.exists():
    _TEST_DB = BACKEND / "atlas_ai.db"
os.environ["DATABASE_URL"] = "sqlite:///" + str(_TEST_DB).replace("\\", "/")
os.environ["JWT_SECRET_KEY"] = "test-secret-32-bytes-long-key-12345"

from fastapi.testclient import TestClient

from app.main import app


def _register_and_login(client: TestClient, suffix: str) -> dict:
    email = f"h78c_status_{suffix}@example.com"
    password = "H78cPass123"
    r = client.post(
        "/api/v1/auth/register",
        json={"full_name": "H7.8C Status", "email": email, "password": password},
    )
    assert r.status_code == 201, f"register failed: {r.text}"
    return {"email": email, "password": password}


def test_provider_status_unauthenticated_returns_401() -> None:
    """Defensive: the endpoint must NOT become public.

    The user-facing contract is "provider-status is auth-gated
    like every other chat endpoint". A regression that exposed
    it would surface here as a 200 instead of a 401.
    """
    client = TestClient(app)
    r = client.get("/api/v1/chat/provider-status")
    assert r.status_code == 401, (
        f"unauthenticated provider-status must be 401, got {r.status_code}: {r.text}"
    )


def test_provider_status_authenticated_returns_200() -> None:
    """The H7.8C fix — ``/provider-status`` MUST be matched BEFORE
    ``/{session_id}`` so the literal path is not captured by the
    int-validating ``session_id`` parameter."""
    client = TestClient(app)
    creds = _register_and_login(client, str(int(time.time() * 1000)))

    # The TestClient preserves the cookie set by the register
    # call (it set atlas_access_token as part of the response).
    r = client.get("/api/v1/chat/provider-status")
    assert r.status_code == 200, (
        f"authenticated provider-status must be 200, got {r.status_code}: {r.text}"
    )
    payload = r.json()
    # Canonical envelope — never contains secrets.
    assert "configured_provider" in payload
    assert "runtime_provider" in payload
    assert "model" in payload
    assert "available" in payload
    assert "fallback_active" in payload
    # Hard rule: secrets MUST NOT leak through this endpoint.
    for forbidden in ("api_key", "authorization", "base_url", "endpoint", "secret"):
        assert forbidden not in payload, (
            f"provider-status payload must not include {forbidden!r}, got {payload!r}"
        )


def test_provider_status_does_not_collide_with_session_route() -> None:
    """Defensive — the route-ordering regression must not return.

    Both ``GET /provider-status`` and ``GET /{session_id}`` must
    continue to work independently.
    """
    client = TestClient(app)
    creds = _register_and_login(client, str(int(time.time() * 1000)))

    # provider-status — the literal path
    r1 = client.get("/api/v1/chat/provider-status")
    assert r1.status_code == 200, r1.text

    # Integer session id — must still go to the get_conversation
    # route, which 404s because the session does not exist.
    r2 = client.get("/api/v1/chat/12345")
    assert r2.status_code == 404, (
        f"non-existent session_id must 404, got {r2.status_code}: {r2.text}"
    )

    # A non-integer literal would have been captured by
    # ``/{session_id}`` BEFORE the fix — that route must still
    # reject "abc" with 422, but "provider-status" MUST NOT be
    # captured by it.
    r3 = client.get("/api/v1/chat/abc")
    assert r3.status_code == 422, (
        f"non-integer session_id must still be 422, got {r3.status_code}"
    )


def test_other_chat_auth_endpoints_unchanged() -> None:
    """Regression net — make sure the route reordering did not
    break the other auth-gated chat endpoints."""
    client = TestClient(app)
    _register_and_login(client, str(int(time.time() * 1000)))

    # Empty list for a fresh user — must be 200.
    r_list = client.get("/api/v1/chat")
    assert r_list.status_code == 200, r_list.text

    # Unauthenticated access to other chat endpoints must still
    # be 401.
    anon = TestClient(app)
    for path in ("/api/v1/chat", "/api/v1/chat/1"):
        r = anon.get(path)
        assert r.status_code == 401, (
            f"{path} must be 401 when unauthenticated, got {r.status_code}"
        )