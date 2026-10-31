"""Unit test for Business Health Score Engine (Sprint 10 Task 10.4)."""

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
from app.repositories.business_repository import BusinessRepository
from app.services.health_score_service import HealthScoreService
from app.utils.database import Base, SessionLocal, engine

Base.metadata.create_all(bind=engine)


def test_health_score_engine():
    # 1. Test None business -> score=0, grade='F', status='Critical'
    report_none = HealthScoreService.compute(None)
    assert report_none.score == 0
    assert report_none.grade == "F"
    assert report_none.status == "Critical"
    assert "business_profile" in report_none.missing_fields

    # 2. Test incomplete business model
    import uuid
    test_email = f"healthuser_{uuid.uuid4().hex[:8]}@example.com"
    db = SessionLocal()
    try:
        user = User(email=test_email, password_hash="hash", full_name="Health User")
        db.add(user)
        db.commit()
        db.refresh(user)

        repo = BusinessRepository(db)
        biz = repo.create(
            owner_id=user.id,
            legal_name="Health Check Co",
            industry="Healthcare",
            established_year=2021,
            employee_count=15,
            annual_revenue=250000.0,
            revenue_currency="USD",
            business_type="private_limited",
            country="US",
        )
        db.commit()

        fresh_biz = repo.get_by_owner(user.id)
        assert fresh_biz is not None

        report = HealthScoreService.compute(fresh_biz)

        assert 0 <= report.score <= 100
        assert report.grade in ["A", "B", "C", "D", "E", "F"]
        assert report.status in ["Excellent", "Good", "Fair", "Needs Improvement", "Critical"]
        assert isinstance(report.missing_fields, list)

        print("[SUCCESS] HealthScoreService unit tests passed cleanly!")

    finally:
        db.close()


if __name__ == "__main__":
    test_health_score_engine()
