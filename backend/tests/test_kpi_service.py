"""Unit test for KPI Engine (Sprint 10 Task 10.3)."""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = "sqlite:///" + str(BACKEND / "atlas_ai.db").replace("\\", "/")
os.environ["JWT_SECRET_KEY"] = "test-secret-32-bytes-long-key-12345"

from app.models.user import User
from app.repositories.business_repository import BusinessRepository
from app.services.kpi_service import KpiService
from app.utils.database import Base, SessionLocal, engine

Base.metadata.create_all(bind=engine)


def test_kpi_engine():
    # 1. Test None business -> defaults (0 or None)
    kpi_none = KpiService.compute(None)
    assert kpi_none.businessName is None or kpi_none.business_name is None
    assert kpi_none.industry is None
    assert kpi_none.employees == 0
    assert kpi_none.products == 0
    assert kpi_none.services == 0
    assert kpi_none.locations == 0
    assert kpi_none.yearsInBusiness == 0 or kpi_none.years_in_business == 0
    assert kpi_none.profileCompletion == 0 or kpi_none.profile_completion == 0

    # 2. Test active business model computation
    import uuid
    test_email = f"kpiuser_{uuid.uuid4().hex[:8]}@example.com"
    db = SessionLocal()
    try:
        user = User(email=test_email, password_hash="hash", full_name="KPI User")
        db.add(user)
        db.commit()
        db.refresh(user)

        repo = BusinessRepository(db)
        biz = repo.create(
            owner_id=user.id,
            legal_name="Acme Tech Global",
            industry="Software",
            established_year=2020,
            employee_count=45,
            annual_revenue=1000000.0,
            revenue_currency="USD",
            city="San Francisco",
            state_region="California",
            country="US",
        )
        repo.replace_products(
            biz,
            [
                {"name": "Database Software", "category": "Product", "unit_price": 100.0},
                {"name": "Cloud Maintenance Service", "category": "Managed Service", "unit_price": 500.0},
            ],
        )
        repo.replace_export_history(
            biz,
            [
                {"destination_country": "Japan", "product_category": "Software"},
            ],
        )
        db.commit()

        fresh_biz = repo.get_by_owner(user.id)
        assert fresh_biz is not None

        kpis = KpiService.compute(fresh_biz)

        current_year = datetime.now().year
        expected_years = current_year - 2020

        assert kpis.businessName == "Acme Tech Global" or kpis.business_name == "Acme Tech Global"
        assert kpis.industry == "Software"
        assert kpis.employees == 45
        assert kpis.products == 2
        assert kpis.services == 1
        assert kpis.locations >= 1  # SF, CA, US, Japan distinct locations
        assert kpis.yearsInBusiness == expected_years or kpis.years_in_business == expected_years
        assert kpis.profileCompletion > 0 or kpis.profile_completion > 0

        print("[SUCCESS] KPI Engine unit tests passed cleanly!")

    finally:
        db.close()


if __name__ == "__main__":
    test_kpi_engine()
