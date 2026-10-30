"""Master Test Suite for Sprint 16 — Government Scheme Recommendation Engine.

Verifies end-to-end functionality for:
  * Sprint 16.1: Government Scheme Recommendation API (/api/v1/business/schemes)
  * Sprint 16.3: Scheme Recommendation & Ranking Engine (recommended, eligible, partiallyEligible, notEligible)
  * Sprint 16.4: Master Verification (401, 404, 200 OK)
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
from app.models.user import User
from app.repositories.business_repository import BusinessNotFound, BusinessRepository
from app.services.schemes_sprint16_service import SchemeRecommendationEngine
from app.utils.database import Base, SessionLocal, engine

Base.metadata.create_all(bind=engine)


def test_sprint16_schemes_unit():
    db = SessionLocal()
    try:
        ts = int(time.time())
        user = User(
            email=f"schemeuser_{ts}@example.com",
            password_hash="hash",
            full_name="Scheme Test User",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        repo = BusinessRepository(db)
        engine_svc = SchemeRecommendationEngine(repo)

        # 1. Empty profile -> raises BusinessNotFound
        raised = False
        try:
            engine_svc.compute(user.id)
        except BusinessNotFound:
            raised = True
        assert raised, "[FAIL] Expected BusinessNotFound when profile does not exist"

        # 2. Create business profile
        biz = repo.create(
            owner_id=user.id,
            legal_name="Apex Green Manufacturing",
            industry="Manufacturing",
            established_year=2021,
            employee_count=15,
            annual_revenue=400000.0,
            revenue_currency="USD",
            country="US",
            state_region="OH",
            city="Cleveland",
        )
        db.commit()

        fresh = repo.get_by_owner(user.id)
        assert fresh is not None

        # 3. Categorized Scheme Recommendations
        categorized = engine_svc.recommend_schemes(fresh)
        assert len(categorized.eligible) > 0
        assert len(categorized.recommended) > 0
        assert all(s.eligibility_status == "matching" for s in categorized.eligible)

        print("[PASS] Sprint 16 Unit Scheme Recommendation test passed cleanly!")

    finally:
        db.close()


def test_sprint16_schemes_api():
    client = TestClient(app)
    ts = int(time.time())

    # 1. Unauthenticated -> 401
    res = client.get("/api/v1/business/schemes")
    assert res.status_code == 401

    # 2. Register & login user with business profile
    email = f"scheme_api_{ts}@example.com"
    client.post(
        "/api/v1/auth/register",
        json={"full_name": "Scheme API User", "email": email, "password": "Password123!"},
    )
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    cookies = login.cookies

    # 3. Registered user without business -> 404
    assert client.get("/api/v1/business/schemes", cookies=cookies).status_code == 404

    # 4. Create business -> 200 OK
    client.post(
        "/api/v1/business",
        json={
            "basic": {
                "legal_name": "Apex Robotics & Automation",
                "industry": "Robotics",
                "established_year": 2020,
                "employee_count": 22,
                "annual_revenue": 750000.0,
                "revenue_currency": "USD",
            }
        },
        cookies=cookies,
    )

    get_res = client.get("/api/v1/business/schemes", cookies=cookies)
    assert get_res.status_code == 200
    body = get_res.json()
    assert "generated_at" in body
    assert body["total_schemes"] > 0
    assert "schemes" in body
    assert "recommended" in body["schemes"]

    print("[PASS] Sprint 16 Integration Scheme API test passed cleanly!")


if __name__ == "__main__":
    test_sprint16_schemes_unit()
    test_sprint16_schemes_api()
