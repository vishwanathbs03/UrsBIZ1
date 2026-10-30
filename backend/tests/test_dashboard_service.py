"""Unit test for DashboardService (Sprint 10 Task 10.2)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = "sqlite:///" + str(BACKEND / "atlas_ai.db").replace("\\", "/")
os.environ["JWT_SECRET_KEY"] = "test-secret-32-bytes-long-key-12345"

from app.models.user import User
from app.repositories.business_repository import BusinessNotFound, BusinessRepository
from app.services.dashboard_service import DashboardService
from app.utils.database import Base, SessionLocal, engine

Base.metadata.create_all(bind=engine)


def test_dashboard_service_unit():
    db = SessionLocal()
    try:
        # Create test user
        user = User(email="serviceuser@example.com", password_hash="hash", full_name="Service User")
        db.add(user)
        db.commit()
        db.refresh(user)

        repo = BusinessRepository(db)
        service = DashboardService(repo)

        # 1. No business -> raises BusinessNotFound
        raised = False
        try:
            service.get_dashboard(user.id)
        except BusinessNotFound:
            raised = True
        assert raised, "Expected BusinessNotFound when user has no business"

        # 2. Create business row
        biz = repo.create(
            owner_id=user.id,
            legal_name="Service Test Ltd",
            industry="Manufacturing",
            established_year=2019,
            employee_count=30,
            annual_revenue=500000.0,
            revenue_currency="USD",
        )
        db.commit()

        # 3. Call DashboardService
        res = service.get_dashboard(user.id)

        assert res.business is not None
        assert res.business.legal_name == "Service Test Ltd"
        assert (res.kpis.get("employees") or res.kpis.get("employee_count")) == 30
        assert res.health_score in (50, 60)
        assert "Service Test Ltd" in res.ai_summary
        assert isinstance(res.recent_activity, list)
        assert isinstance(res.quick_actions, list)

        print("[SUCCESS] DashboardService unit test passed cleanly!")

    finally:
        db.close()


if __name__ == "__main__":
    test_dashboard_service_unit()
