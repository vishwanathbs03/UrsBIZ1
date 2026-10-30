"""Regression test — Sprint H7.1 business update persistence.

Root-cause target
-----------------
``BusinessService.update()`` mutated the ORM row but never flushed before
the ``populate_existing`` re-read inside ``get_by_owner`` that computes
completeness. With ``autoflush=False`` that re-read reloaded the STALE
committed state over the staged edits, so PUT /business returned 200 with
the OLD values and the database was never updated.

This test fails on the pre-fix code (update silently lost) and passes
after the fix (``BusinessService.update`` now calls ``repo.flush()``
before the read-back).

Run standalone:

    python tests/test_h7_1_business_persistence.py

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
os.environ["DATABASE_URL"] = "sqlite:///" + str(BACKEND / "atlas_ai.db").replace("\\", "/")
os.environ["JWT_SECRET_KEY"] = "test-secret-32-bytes-long-key-12345"

from fastapi.testclient import TestClient

from app.main import app
from app.utils.database import Base, engine

# Ensure the schema exists in ``atlas_ai.db`` so the in-process
# FastAPI app can register/login/create/update without raising
# ``no such table: users``. The conftest wipes the persisted
# SQLite file before any test module is imported; this call
# rebuilds the schema the test relies on.
Base.metadata.create_all(bind=engine)


def _basic(employee_count: int, description: str) -> dict:
    return {
        "basic": {
            "legal_name": "Persist Co",
            "industry": "Manufacturing",
            "established_year": 2020,
            "employee_count": employee_count,
            "annual_revenue": 1000.0,
            "revenue_currency": "INR",
            "description": description,
        }
    }


def test_business_update_persists() -> None:
    client = TestClient(app)
    email = f"h7persist_{int(time.time() * 1000)}@example.com"
    client.post(
        "/api/v1/auth/register",
        json={"full_name": "Persist User", "email": email, "password": "PersistPass1"},
    )

    # Create with employee_count=10.
    create = client.post("/api/v1/business", json=_basic(10, "original"))
    assert create.status_code == 201, f"create failed: {create.text}"
    assert create.json()["business"]["employee_count"] == 10

    # Update to employee_count=70 — must persist (the H7.1 regression point).
    put = client.put("/api/v1/business", json=_basic(70, "updated"))
    assert put.status_code == 200, f"update failed: {put.text}"

    # 1. The PUT response itself must reflect the new values (not stale).
    assert put.json()["business"]["employee_count"] == 70, (
        "PUT response carried the stale value — update was not applied "
        "before serialization."
    )
    assert put.json()["business"]["description"] == "updated"

    # 2. A fresh GET in the same session must agree.
    get_same = client.get("/api/v1/business")
    assert get_same.json()["business"]["employee_count"] == 70, (
        "GET after PUT returned stale data in the same session."
    )

    # 3. Log out then log back in — the update must survive a session change
    #    (equivalent to a browser refresh + re-auth).
    client.post("/api/v1/auth/logout")
    client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "PersistPass1"},
    )
    get_fresh = client.get("/api/v1/business")
    assert get_fresh.json()["business"]["employee_count"] == 70, (
        "After refresh + re-login the update was lost — the database write "
        "never happened."
    )


def test_update_then_relogin_persists() -> None:
    client = TestClient(app)
    email = f"h7relogin_{int(time.time() * 1000)}@example.com"
    client.post(
        "/api/v1/auth/register",
        json={"full_name": "Relogin User", "email": email, "password": "ReloginPass1"},
    )
    client.post("/api/v1/business", json=_basic(20, "v1"))

    # Update scalar + nested collection.
    upd = _basic(33, "v2")
    upd["products"] = [
        {"name": "PersistedWidget", "category": "Widgets", "unit_price": 10.0, "currency": "INR"}
    ]
    put = client.put("/api/v1/business", json=upd)
    assert put.status_code == 200
    assert put.json()["business"]["employee_count"] == 33

    # Log out → auth cookie cleared → 401 proves session ended.
    logout = client.post("/api/v1/auth/logout")
    assert logout.status_code == 204
    assert client.get("/api/v1/business").status_code == 401

    # Log in again (fresh session) → profile must still carry the update.
    client.post("/api/v1/auth/login", json={"email": email, "password": "ReloginPass1"})
    get = client.get("/api/v1/business")
    assert get.status_code == 200
    biz = get.json()["business"]
    assert biz["employee_count"] == 33, (
        f"After re-login, employee_count={biz['employee_count']} — the update "
        "did NOT persist to the database."
    )
    assert biz["description"] == "v2"
    assert [p["name"] for p in biz["products"]] == ["PersistedWidget"], (
        "Nested product collection did not persist across re-login."
    )


if __name__ == "__main__":
    test_business_update_persists()
    print("[PASS] test_business_update_persists")
    test_update_then_relogin_persists()
    print("[PASS] test_update_then_relogin_persists")
    print("[SUCCESS] H7.1 business persistence regression suite passed.")
