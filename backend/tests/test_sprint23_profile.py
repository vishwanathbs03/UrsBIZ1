"""Sprint 23 — Profile Panel + Multi-Business backend tests.

Exercises the new endpoints and the active-business promotion
that ``BusinessService.create`` performs:

    GET   /auth/me                  — returns active_business_id
    POST  /business                 — creates + sets active
    POST  /business                 — twice — active flips to new row
    POST  /business/minimal         — inline panel path
    GET   /business/list            — returns every owned business
    GET   /business                 — returns the active row
    PATCH /auth/me {active_business_id}        — switcher
    PATCH /auth/me {active_business_id=other}  — 403
    PATCH /auth/me {active_business_id=99999}  — 404
    DELETE /business/{id} for the only row     — 409
    DELETE /business/{id} for a non-active row — 200, active unchanged
    DELETE /business/{id} for the active row   — 200, active falls back

Run standalone:

    python tests/test_sprint23_profile.py

or under pytest:

    pytest tests/test_sprint23_profile.py -v
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = (
    "sqlite:///" + str(BACKEND / "atlas_ai.db").replace("\\", "/")
)
os.environ["JWT_SECRET_KEY"] = "test-secret-32-bytes-long-key-12345"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.utils.database import Base, engine  # noqa: E402

# Rebuild the schema for the in-process app (the conftest wipes
# the SQLite file before any module is imported).
Base.metadata.create_all(bind=engine)


def _basic(employee_count: int = 10, legal_name: str = "Persist Co") -> dict:
    """Minimal-but-complete BusinessCreate payload."""
    return {
        "basic": {
            "legal_name": legal_name,
            "industry": "Manufacturing",
            "established_year": 2020,
            "employee_count": employee_count,
            "annual_revenue": 1000.0,
            "revenue_currency": "INR",
        }
    }


def _register_and_login(client: TestClient, email: str) -> dict:
    """Register and log in the test user. Returns the parsed
    register JSON (which contains the JWT)."""
    register = client.post(
        "/api/v1/auth/register",
        json={"full_name": "Sprint23 User", "email": email, "password": "SprintPass1"},
    )
    assert register.status_code == 201, f"register failed: {register.text}"
    return register.json()


def test_register_active_business_id_is_null() -> None:
    """A freshly registered user has no business yet."""
    client = TestClient(app)
    email = f"s23_active_null_{int(time.time() * 1000)}@example.com"
    _register_and_login(client, email)
    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["active_business_id"] is None


def test_create_business_sets_active() -> None:
    """POST /business promotes the new row to active."""
    client = TestClient(app)
    email = f"s23_create_active_{int(time.time() * 1000)}@example.com"
    _register_and_login(client, email)

    created = client.post("/api/v1/business", json=_basic())
    assert created.status_code == 201, created.text
    created_id = created.json()["business"]["id"]

    me = client.get("/api/v1/auth/me")
    assert me.json()["active_business_id"] == created_id


def test_second_create_flips_active() -> None:
    """The second POST flips the active id to the new row."""
    client = TestClient(app)
    email = f"s23_second_create_{int(time.time() * 1000)}@example.com"
    _register_and_login(client, email)

    first = client.post("/api/v1/business", json=_basic(legal_name="First Co"))
    second = client.post("/api/v1/business", json=_basic(legal_name="Second Co"))
    assert first.status_code == 201
    assert second.status_code == 201

    me = client.get("/api/v1/auth/me")
    assert me.json()["active_business_id"] == second.json()["business"]["id"]


def test_minimal_create_route() -> None:
    """POST /business/minimal accepts the 6 required fields only."""
    client = TestClient(app)
    email = f"s23_minimal_{int(time.time() * 1000)}@example.com"
    _register_and_login(client, email)

    payload = {
        "legal_name": "Minimal Co",
        "industry": "Retail",
        "established_year": 2019,
        "employee_count": 5,
        "annual_revenue": 250.0,
        "revenue_currency": "USD",
    }
    response = client.post("/api/v1/business/minimal", json=payload)
    assert response.status_code == 201, response.text
    me = client.get("/api/v1/auth/me")
    assert me.json()["active_business_id"] == response.json()["business"]["id"]


def test_list_returns_all_owned() -> None:
    """GET /business/list returns every business the user owns."""
    client = TestClient(app)
    email = f"s23_list_{int(time.time() * 1000)}@example.com"
    _register_and_login(client, email)

    client.post("/api/v1/business", json=_basic(legal_name="Alpha Co"))
    client.post("/api/v1/business", json=_basic(legal_name="Beta Co"))
    client.post("/api/v1/business", json=_basic(legal_name="Gamma Co"))

    listing = client.get("/api/v1/business/list")
    assert listing.status_code == 200, listing.text
    body = listing.json()
    assert body["count"] == 3
    names = [item["legal_name"] for item in body["items"]]
    assert names == ["Alpha Co", "Beta Co", "Gamma Co"]
    assert body["active_business_id"] == body["items"][-1]["id"]


def test_get_business_returns_active() -> None:
    """GET /business returns the active business, not a stale one."""
    client = TestClient(app)
    email = f"s23_get_active_{int(time.time() * 1000)}@example.com"
    _register_and_login(client, email)

    first = client.post("/api/v1/business", json=_basic(legal_name="First Co"))
    second = client.post("/api/v1/business", json=_basic(legal_name="Second Co"))
    first_id = first.json()["business"]["id"]
    second_id = second.json()["business"]["id"]

    # Switch back to the first business.
    switch = client.patch(
        "/api/v1/auth/me", json={"active_business_id": first_id}
    )
    assert switch.status_code == 200, switch.text

    fetched = client.get("/api/v1/business")
    assert fetched.status_code == 200
    assert fetched.json()["business"]["id"] == first_id
    assert fetched.json()["business"]["id"] != second_id


def test_patch_active_with_foreign_business_returns_403() -> None:
    """A user cannot mark someone else's business as active."""
    client = TestClient(app)
    email_a = f"s23_owner_a_{int(time.time() * 1000)}@example.com"
    email_b = f"s23_owner_b_{int(time.time() * 1000)}@example.com"
    _register_and_login(client, email_a)
    foreign = client.post("/api/v1/business", json=_basic(legal_name="Foreign Co"))
    foreign_id = foreign.json()["business"]["id"]

    # Sign in as user B (overwrites cookie state on the same client).
    _register_and_login(client, email_b)
    me_b = client.get("/api/v1/auth/me")
    # User B should not see user A's business in their own list.
    listing_b = client.get("/api/v1/business/list")
    assert listing_b.json()["count"] == 0

    # Now try to point B's active id at A's business.
    response = client.patch(
        "/api/v1/auth/me", json={"active_business_id": foreign_id}
    )
    assert response.status_code == 403, response.text
    # Confirm the active id was NOT changed.
    me_after = client.get("/api/v1/auth/me")
    assert me_after.json()["active_business_id"] is None


def test_patch_active_with_missing_business_returns_404() -> None:
    """An unknown business id returns 404, not 403."""
    client = TestClient(app)
    email = f"s23_missing_{int(time.time() * 1000)}@example.com"
    _register_and_login(client, email)
    response = client.patch(
        "/api/v1/auth/me", json={"active_business_id": 999999}
    )
    assert response.status_code == 404, response.text


def test_delete_only_business_returns_409() -> None:
    """The user cannot delete their only remaining business."""
    client = TestClient(app)
    email = f"s23_only_delete_{int(time.time() * 1000)}@example.com"
    _register_and_login(client, email)
    created = client.post("/api/v1/business", json=_basic())
    business_id = created.json()["business"]["id"]
    response = client.delete(f"/api/v1/business/{business_id}")
    assert response.status_code == 409, response.text
    # Confirm the row is still present.
    after = client.get("/api/v1/business")
    assert after.status_code == 200
    assert after.json()["business"]["id"] == business_id


def test_delete_non_active_business_succeeds() -> None:
    """Deleting a non-active business leaves the active id untouched."""
    client = TestClient(app)
    email = f"s23_nonactive_delete_{int(time.time() * 1000)}@example.com"
    _register_and_login(client, email)
    first = client.post("/api/v1/business", json=_basic(legal_name="First Co"))
    second = client.post("/api/v1/business", json=_basic(legal_name="Second Co"))
    first_id = first.json()["business"]["id"]
    second_id = second.json()["business"]["id"]

    # Delete the non-active (older) business.
    response = client.delete(f"/api/v1/business/{first_id}")
    assert response.status_code == 200, response.text

    me = client.get("/api/v1/auth/me")
    # Active id must still point at the second (still-alive) row.
    assert me.json()["active_business_id"] == second_id
    listing = client.get("/api/v1/business/list")
    assert listing.json()["count"] == 1
    assert listing.json()["items"][0]["id"] == second_id


def test_delete_active_business_falls_back() -> None:
    """Deleting the active business promotes another to active."""
    client = TestClient(app)
    email = f"s23_active_delete_{int(time.time() * 1000)}@example.com"
    _register_and_login(client, email)
    first = client.post("/api/v1/business", json=_basic(legal_name="First Co"))
    second = client.post("/api/v1/business", json=_basic(legal_name="Second Co"))
    second_id = second.json()["business"]["id"]

    # Currently active is the second (newest) row.
    response = client.delete(f"/api/v1/business/{second_id}")
    assert response.status_code == 200, response.text

    me = client.get("/api/v1/auth/me")
    # Active id must fall back to the remaining (first) row.
    assert me.json()["active_business_id"] == first.json()["business"]["id"]


if __name__ == "__main__":  # pragma: no cover - manual smoke runner
    import pytest

    sys.exit(pytest.main([__file__, "-v"]))
