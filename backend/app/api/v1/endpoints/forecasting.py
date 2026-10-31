"""API endpoints for Product Demand Forecasting & Predictive Intelligence (Phase 4)."""

from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.middleware.auth_deps import get_current_user
from app.models.sales import SalesTransaction
from app.models.user import User
from app.repositories.business_repository import BusinessRepository
from app.schemas.forecasting import (
    DemandForecastOverviewResponse,
    ForecastExplainRequest,
    ForecastExplainResponse,
    ForecastIntervalEnum,
    ProductForecastDetailResponse,
)
from app.services.forecasting.explanation import explain_forecast_narrative
from app.services.forecasting.forecast_engine import (
    generate_demand_overview,
    generate_product_forecast,
)
from app.utils.database import get_db

router = APIRouter(prefix="/forecasting", tags=["demand-forecasting"])


def _get_active_business(user: User, db: Session):
    """Resolve active business for the authenticated user, enforcing authorization."""
    repo = BusinessRepository(db)
    business = repo.get_by_owner(user.id)
    if not business:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active business profile found for user.",
        )
    return business


@router.get(
    "/overview",
    response_model=DemandForecastOverviewResponse,
    summary="Get demand forecast overview across all products for the active business",
)
def get_demand_forecast_overview(
    interval: ForecastIntervalEnum = Query(ForecastIntervalEnum.WEEKLY, description="Aggregation interval"),
    horizon: int = Query(4, ge=1, le=12, description="Forecast horizon in interval units (e.g. 4, 8, 12)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Computes product-level demand forecasts using historical sales transactions."""
    business = _get_active_business(current_user, db)

    # Fetch non-duplicate transactions strictly scoped to active business
    txns = (
        db.query(SalesTransaction)
        .filter(
            SalesTransaction.business_id == business.id,
            SalesTransaction.is_duplicate.is_(False),
        )
        .order_by(SalesTransaction.transaction_date.asc())
        .all()
    )

    return generate_demand_overview(txns, interval=interval, horizon=horizon)


@router.get(
    "/product/{product_name}",
    response_model=ProductForecastDetailResponse,
    summary="Get detailed historical demand vs forecast trajectory for a specific product",
)
def get_single_product_forecast(
    product_name: str,
    interval: ForecastIntervalEnum = Query(ForecastIntervalEnum.WEEKLY, description="Aggregation interval"),
    horizon: int = Query(4, ge=1, le=12, description="Forecast horizon in interval units"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Returns chronological history, backtest comparison metrics, and prediction intervals."""
    business = _get_active_business(current_user, db)

    txns = (
        db.query(SalesTransaction)
        .filter(
            SalesTransaction.business_id == business.id,
            SalesTransaction.is_duplicate.is_(False),
        )
        .order_by(SalesTransaction.transaction_date.asc())
        .all()
    )

    return generate_product_forecast(
        txns, product_name=product_name, interval=interval, horizon=horizon
    )


@router.post(
    "/explain",
    response_model=ForecastExplainResponse,
    summary="Get AI-grounded business narrative explaining a verified forecast",
)
def explain_forecast(
    request: ForecastExplainRequest,
    current_user: User = Depends(get_current_user),
):
    """Explains verified forecast results in simple business language with guaranteed fallback."""
    return explain_forecast_narrative(request)
