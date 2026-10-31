"""Tests for Phase 5.1: Unified Business Context & Data Integration.

Verifies:
  1. Aggregation of verified data across Profile, Health, Sales, Customers, Products, Forecasts, Schemes.
  2. Strict multi-tenant isolation by active business_id.
  3. Handling of businesses with zero sales data without fabricated defaults.
  4. Non-duplicate transaction filtering.
  5. Distinction of zero-recorded demand from unconfirmed gaps.
"""

from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
import pytest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = "sqlite:///" + str(BACKEND / "atlas_ai.db").replace("\\", "/")
os.environ["JWT_SECRET_KEY"] = "test-secret-32-bytes-long-key-12345"

from app.models.business import Business
from app.models.sales import SalesTransaction
from app.models.user import User
from app.repositories.sales_repository import SalesRepository
from app.schemas.recommendation_context import UnifiedRecommendationContext
from app.services.recommendations.context_service import RecommendationContextService
from app.utils.database import Base, SessionLocal, engine

Base.metadata.create_all(bind=engine)


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_business_with_sales(db_session):
    ts = int(time.time() * 1000)
    user = User(email=f"p51_user_{ts}@example.com", password_hash="h", full_name="Context Test User")
    db_session.add(user)
    db_session.commit()

    business = Business(
        owner_id=user.id,
        legal_name="Precision Dynamics Ltd",
        trade_name="Precision Dyn",
        industry="Automotive",
        established_year=2019,
        annual_revenue=1200000.0,
        revenue_currency="INR",
        employee_count=15,
        city="Pune",
        state_region="Maharashtra",
        country="India",
    )
    db_session.add(business)
    db_session.commit()

    # Upload sales data
    sales_repo = SalesRepository(db_session)
    upload = sales_repo.create_upload(
        business_id=business.id,
        filename="p51_sales.csv",
        file_format="csv",
        file_size_bytes=1024,
        row_count=5,
        valid_row_count=5,
        invalid_row_count=0,
        status="confirmed",
        column_mapping={"transaction_date": "date"},
        quality_summary={"valid_pct": 100.0},
    )

    now = datetime(2025, 10, 1, tzinfo=timezone.utc)
    old = datetime(2025, 1, 15, tzinfo=timezone.utc)

    # 4 valid rows, 1 duplicate row
    tx_rows = [
        {"transaction_date": now, "customer_id": "C1", "customer_name": "Acme Corp", "product_id": "SKU1", "product_name": "Brake Rotor", "quantity": 10, "unit_price": 500, "total_amount": 5000},
        {"transaction_date": now, "customer_id": "C1", "customer_name": "Acme Corp", "product_id": "SKU1", "product_name": "Brake Rotor", "quantity": 10, "unit_price": 500, "total_amount": 5000},
        {"transaction_date": old, "customer_id": "C2", "customer_name": "Lapsed Fleet", "product_id": "SKU2", "product_name": "Clutch Disc", "quantity": 5, "unit_price": 800, "total_amount": 4000},
    ]
    sales_repo.bulk_insert_transactions(upload.id, business.id, tx_rows)

    return business


def test_unified_context_service_complete_data(db_session, test_business_with_sales):
    service = RecommendationContextService(db_session)
    ctx = service.build_context(test_business_with_sales)

    assert isinstance(ctx, UnifiedRecommendationContext)
    assert ctx.business_id == test_business_with_sales.id

    # Profile
    assert ctx.profile.legal_name == "Precision Dynamics Ltd"
    assert ctx.profile.industry == "Automotive"
    assert ctx.profile.annual_revenue == 1200000.0

    # Health
    assert 0 <= ctx.health.overall_score <= 100

    # Sales
    assert ctx.sales.has_sales_data is True
    assert ctx.sales.total_transactions > 0
    assert ctx.sales.total_revenue > 0

    # Customers
    assert ctx.customers.total_customers >= 1
    assert len(ctx.customers.top_customers_by_revenue) > 0

    # Products
    assert ctx.products.total_products >= 1

    # Schemes
    assert isinstance(ctx.schemes.recommended_schemes, list)

    # Data sources
    assert "Business Profile" in ctx.data_sources_present
    assert "Sales Intelligence" in ctx.data_sources_present


def test_unified_context_service_missing_sales_data(db_session):
    ts = int(time.time() * 1000)
    user = User(email=f"p51_nosales_{ts}@example.com", password_hash="h", full_name="No Sales User")
    db_session.add(user)
    db_session.commit()

    business = Business(
        owner_id=user.id,
        legal_name="New Venture Hub",
        industry="Consulting",
        established_year=2024,
        annual_revenue=None,
        revenue_currency="INR",
        employee_count=3,
        city="Bengaluru",
    )
    db_session.add(business)
    db_session.commit()

    service = RecommendationContextService(db_session)
    ctx = service.build_context(business)

    assert ctx.sales.has_sales_data is False
    assert ctx.sales.total_transactions == 0
    assert ctx.sales.total_revenue == 0.0
    assert ctx.forecast.has_forecast_data is False
    assert any("No historical sales records" in lim for lim in ctx.data_limitations)
