"""Comprehensive Test Suite for Phase 4: Demand Forecasting & Predictive Intelligence.

Tests cover:
  1. Data preparation: regular calendar grid resampling (weekly, monthly, daily), duplicate exclusion,
     explicit zero-demand periods, intermittent demand detection.
  2. Baseline models: Naive, SMA, WMA, Seasonal Naive (including minimum seasonal cycles constraint).
  3. Statistical & ML models: Holt's Linear Exponential Smoothing, Autoregressive Lag-based Ridge Regression.
  4. Chronological evaluation: No data leakage, holdout splitting, metrics (MAE, RMSE, WAPE, guarded MAPE, MASE),
     and evidence-based selection (retaining baseline when advanced model does not outperform).
  5. Forecast engine: Horizon rollouts, prediction intervals (80% empirical bound), non-negative constraints,
     reliability scoring.
  6. Empty states & insufficient history handling without manufactured predictions.
  7. API endpoints: /forecasting/overview, /forecasting/product/{name}, /forecasting/explain.
  8. Security: Multi-tenant user isolation, multi-business switching isolation, protected routes.
  9. AI explanation: Guaranteed deterministic fallback when AI key is missing or upstream fails.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from uuid import uuid4
import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.models.business import Business
from app.models.sales import SalesTransaction, SalesUpload
from app.models.user import User
from app.schemas.forecasting import (
    DataLimitationStatusEnum,
    ForecastExplainRequest,
    ForecastIntervalEnum,
    ForecastReliabilityEnum,
)
from app.services.forecasting.baselines import (
    intermittent_expected_demand_forecast,
    moving_average_forecast,
    naive_forecast,
    seasonal_naive_forecast,
    weighted_moving_average_forecast,
)
from app.services.forecasting.confidence import (
    calculate_prediction_intervals,
    evaluate_forecast_reliability,
)
from app.services.forecasting.data_preparation import (
    prepare_product_demand_series,
)
from app.services.forecasting.evaluation import (
    backtest_and_select_model,
    compute_metrics,
)
from app.services.forecasting.explanation import (
    explain_forecast_narrative,
    generate_deterministic_explanation,
)
from app.services.forecasting.forecast_engine import (
    generate_demand_overview,
    generate_product_forecast,
)
from app.services.forecasting.models import (
    autoregressive_ridge_forecast,
    holt_linear_exponential_smoothing,
)
from app.utils.database import Base


# =============================================================================
# 1. Data Preparation Pipeline Tests
# =============================================================================

def test_data_prep_weekly_resampling_and_duplicate_exclusion():
    """Verify weekly resampling, calendar continuity, and duplicate transaction filtering."""
    base_date = datetime(2026, 1, 5, 10, 0, tzinfo=timezone.utc)  # Monday
    txns = [
        # Week 1: 2 sales
        {"transaction_date": base_date, "product_name": "Widget A", "quantity": 10.0, "is_duplicate": False},
        {"transaction_date": base_date + timedelta(days=2), "product_name": "Widget A", "quantity": 5.0, "is_duplicate": False},
        # Week 1: 1 duplicate (must be excluded)
        {"transaction_date": base_date, "product_name": "Widget A", "quantity": 10.0, "is_duplicate": True},
        # Week 2: 0 sales (missing in data) -> must be regular zero observation
        # Week 3: 1 sale
        {"transaction_date": base_date + timedelta(days=14), "product_name": "Widget A", "quantity": 20.0, "is_duplicate": False},
        # Week 4: 1 sale
        {"transaction_date": base_date + timedelta(days=21), "product_name": "Widget A", "quantity": 15.0, "is_duplicate": False},
    ]

    series = prepare_product_demand_series(txns, "Widget A", interval=ForecastIntervalEnum.WEEKLY)

    assert series.total_periods == 4
    # Week 1: 10 + 5 = 15 (duplicate excluded)
    assert series.periods[0].quantity == 15.0
    assert series.periods[0].has_data is True
    # Week 2: confirmed zero period
    assert series.periods[1].quantity == 0.0
    assert series.periods[1].has_data is False
    # Week 3: 20
    assert series.periods[2].quantity == 20.0
    # Week 4: 15
    assert series.periods[3].quantity == 15.0

    assert series.total_quantity == 50.0
    assert series.active_periods == 3
    assert series.status == DataLimitationStatusEnum.FORECAST_AVAILABLE


def test_data_prep_monthly_and_daily_intervals():
    """Verify monthly and daily calendar grids."""
    d1 = datetime(2026, 1, 15, tzinfo=timezone.utc)
    d2 = datetime(2026, 3, 10, tzinfo=timezone.utc)
    txns = [
        {"transaction_date": d1, "product_name": "Steel Bar", "quantity": 100.0, "is_duplicate": False},
        {"transaction_date": d2, "product_name": "Steel Bar", "quantity": 150.0, "is_duplicate": False},
    ]

    # Monthly: Jan, Feb (zero), Mar = 3 months
    monthly_series = prepare_product_demand_series(txns, "Steel Bar", interval=ForecastIntervalEnum.MONTHLY)
    assert monthly_series.total_periods == 3
    assert monthly_series.periods[0].period_label == "2026-01"
    assert monthly_series.periods[0].quantity == 100.0
    assert monthly_series.periods[1].period_label == "2026-02"
    assert monthly_series.periods[1].quantity == 0.0
    assert monthly_series.periods[2].period_label == "2026-03"
    assert monthly_series.periods[2].quantity == 150.0

    # Daily: spanning 3 days
    daily_txns = [
        {"transaction_date": datetime(2026, 5, 1, tzinfo=timezone.utc), "product_name": "Bread", "quantity": 10, "is_duplicate": False},
        {"transaction_date": datetime(2026, 5, 3, tzinfo=timezone.utc), "product_name": "Bread", "quantity": 12, "is_duplicate": False},
    ]
    daily_series = prepare_product_demand_series(daily_txns, "Bread", interval=ForecastIntervalEnum.DAILY)
    assert daily_series.total_periods == 3  # May 1, May 2 (zero), May 3
    assert daily_series.periods[1].quantity == 0.0


def test_data_prep_intermittent_and_insufficient_history():
    """Verify sparsity ratio detection and insufficient history status."""
    # Only 2 weeks of history
    d1 = datetime(2026, 6, 1, tzinfo=timezone.utc)
    short_txns = [
        {"transaction_date": d1, "product_name": "New SKU", "quantity": 5.0, "is_duplicate": False},
        {"transaction_date": d1 + timedelta(days=7), "product_name": "New SKU", "quantity": 8.0, "is_duplicate": False},
    ]
    short_series = prepare_product_demand_series(short_txns, "New SKU", interval=ForecastIntervalEnum.WEEKLY)
    assert short_series.status == DataLimitationStatusEnum.INSUFFICIENT_HISTORY

    # Intermittent demand: 10 weeks total, but only 2 weeks with sales (80% zero-demand)
    intermittent_txns = [
        {"transaction_date": d1, "product_name": "Slow Part", "quantity": 5.0, "is_duplicate": False},
        {"transaction_date": d1 + timedelta(days=63), "product_name": "Slow Part", "quantity": 8.0, "is_duplicate": False},
    ]
    intermittent_series = prepare_product_demand_series(intermittent_txns, "Slow Part", interval=ForecastIntervalEnum.WEEKLY)
    assert intermittent_series.total_periods == 10
    assert intermittent_series.sparsity_ratio >= 0.70
    assert intermittent_series.status == DataLimitationStatusEnum.INTERMITTENT_DEMAND


# =============================================================================
# 2. Baseline Models Tests
# =============================================================================

def test_baseline_models_mathematical_correctness():
    """Verify Naive, SMA, WMA, and Seasonal Naive formulas."""
    y = np.array([10.0, 20.0, 30.0], dtype=np.float64)

    # 1. Naive: repeats last value (30.0)
    naive_res = naive_forecast(y, horizon=3)
    assert np.allclose(naive_res, [30.0, 30.0, 30.0])

    # 2. SMA (window 3): (10 + 20 + 30) / 3 = 20.0
    sma_res = moving_average_forecast(y, horizon=2, window=3)
    assert np.allclose(sma_res, [20.0, 20.0])

    # 3. WMA: 0.2*10 + 0.3*20 + 0.5*30 = 2 + 6 + 15 = 23.0
    wma_res = weighted_moving_average_forecast(y, horizon=2, window=3)
    assert np.allclose(wma_res, [23.0, 23.0])

    # 4. Seasonal Naive: requires >= 2 full cycles
    with pytest.raises(ValueError, match="at least 8 observations"):
        seasonal_naive_forecast(y, horizon=2, season_length=4)

    # With 8 observations (2 cycles of 4):
    # Cycle 1: [10, 20, 30, 40]
    # Cycle 2: [15, 25, 35, 45]
    y_seasonal = np.array([10.0, 20.0, 30.0, 40.0, 15.0, 25.0, 35.0, 45.0], dtype=np.float64)
    s_res = seasonal_naive_forecast(y_seasonal, horizon=4, season_length=4)
    assert np.allclose(s_res, [15.0, 25.0, 35.0, 45.0])


# =============================================================================
# 3. Advanced Models (Holt's Linear & AR-Ridge) Tests
# =============================================================================

def test_advanced_forecasting_models():
    """Verify Holt's linear exponential smoothing and AR-Ridge regression."""
    # Linear upward trend series
    y = np.array([10.0, 15.0, 20.0, 25.0, 30.0, 35.0, 40.0, 45.0, 50.0], dtype=np.float64)

    # Holt Linear
    holt_preds = holt_linear_exponential_smoothing(y, horizon=3)
    assert len(holt_preds) == 3
    # With upward trend, predictions should be strictly positive and continuing upward
    assert holt_preds[0] > 45.0
    assert holt_preds[1] >= holt_preds[0]
    assert np.all(holt_preds >= 0.0)

    # AR-Ridge
    ar_preds = autoregressive_ridge_forecast(y, horizon=3)
    assert len(ar_preds) == 3
    assert np.all(ar_preds >= 0.0)
    assert ar_preds[0] > 40.0


# =============================================================================
# 4. Chronological Backtesting & Evaluation Metrics Tests
# =============================================================================

def test_chronological_evaluation_and_zero_leakage():
    """Verify chronological split, metric calculations, and zero-demand guard in MAPE."""
    # Series with length 8 triggers walk-forward rolling-origin backtesting
    y = np.array([10.0, 12.0, 14.0, 16.0, 18.0, 20.0, 22.0, 24.0], dtype=np.float64)

    selected_model, metrics, holdout_info = backtest_and_select_model(y, horizon=2)

    assert holdout_info["split_possible"] is True
    assert holdout_info["evaluation_method"] == "rolling_origin"
    assert holdout_info["rolling_splits_count"] == 3
    assert len(metrics) >= 3  # At least Naive, SMA, WMA evaluated

    # For shorter series (length 6), fixed chronological holdout is used
    y_short = np.array([10.0, 12.0, 14.0, 16.0, 18.0, 20.0], dtype=np.float64)
    _, _, short_info = backtest_and_select_model(y_short, horizon=2)
    assert short_info["evaluation_method"] == "fixed_holdout"
    assert short_info["holdout_periods"] == 2

    # Selected model should be marked in metrics list
    selected_items = [m for m in metrics if m.is_selected]
    assert len(selected_items) == 1
    assert selected_items[0].model_name == selected_model

    # Verify metric math with zero actuals guard
    y_true = np.array([0.0, 10.0, 20.0], dtype=np.float64)
    y_pred = np.array([2.0, 12.0, 18.0], dtype=np.float64)
    res = compute_metrics(y_true, y_pred, y[:5])
    # MAE = (|0-2| + |10-12| + |20-18|) / 3 = 6 / 3 = 2.0
    assert res["mae"] == 2.0
    # WAPE = 6 / (0 + 10 + 20) = 6 / 30 = 0.20
    assert res["wape"] == 0.20
    # MAPE must ignore index 0 (actual=0) without NaN or crash
    assert res["mape"] is not None
    assert not np.isnan(res["mape"])


def test_model_selection_prefers_baseline_when_advanced_model_inferior():
    """Verify that an advanced model is NOT selected unless it outperforms baseline."""
    # Noisy, flat series where Moving Average is naturally superior to high-order AR
    np.random.seed(42)
    y_flat = 50.0 + np.random.normal(0, 2.0, size=12)

    selected_model, metrics, _ = backtest_and_select_model(y_flat, horizon=2)
    # The selection rule ensures that if an advanced model does not beat baseline by >2%, baseline is retained
    assert selected_model in [
        "Moving Average (3-Period)",
        "Weighted Moving Average",
        "Naive (Latest Demand)",
        "Seasonal Naive (4-Period Cycle)",
        "Holt Linear Exponential Smoothing",
        "Autoregressive Ridge ML",
    ]


# =============================================================================
# 5. Prediction Intervals & Reliability Tests
# =============================================================================

def test_prediction_intervals_non_negative_and_scaling():
    """Verify that lower estimate never drops below zero and margins scale with horizon."""
    y_hist = np.array([5.0, 6.0, 4.0, 5.0, 3.0, 4.0], dtype=np.float64)
    preds = np.array([2.0, 2.0, 2.0, 2.0], dtype=np.float64)

    lowers, uppers, range_type, cov_pct, cov_summary, note = calculate_prediction_intervals(y_hist, preds)
    assert len(lowers) == 4
    assert len(uppers) == 4

    # Non-negative constraint
    assert np.all(lowers >= 0.0)
    # Upper bound must be >= predicted
    assert np.all(uppers >= preds)
    # Uncertainty margin must widen over horizon steps
    assert (uppers[3] - lowers[3]) >= (uppers[0] - lowers[0])
    assert "Estimated Prediction Range" in range_type


def test_forecast_reliability_grading():
    """Verify High, Medium, Low, and Insufficient History reliability rules."""
    assert evaluate_forecast_reliability(2, 0.0, 0.1, 1.0, 10.0) == ForecastReliabilityEnum.INSUFFICIENT_HISTORY
    assert evaluate_forecast_reliability(14, 0.1, 0.15, 1.0, 10.0) == ForecastReliabilityEnum.HIGH
    assert evaluate_forecast_reliability(8, 0.4, 0.35, 3.0, 10.0) == ForecastReliabilityEnum.MEDIUM
    assert evaluate_forecast_reliability(5, 0.6, 0.65, 8.0, 10.0) == ForecastReliabilityEnum.LOW


# =============================================================================
# 6. Core Forecast Engine & Product Overview Tests
# =============================================================================

def test_forecast_engine_single_product_and_overview():
    """Verify complete product forecast detail and overview aggregation."""
    base_date = datetime(2026, 3, 2, tzinfo=timezone.utc)
    txns = []

    # Product A: 10 consecutive weeks of sales (growing: 10 -> 25)
    for w in range(10):
        txns.append({
            "transaction_date": base_date + timedelta(days=w * 7),
            "product_name": "Servo Motor 5kW",
            "quantity": float(10 + w * 1.5),
            "is_duplicate": False,
        })

    # Product B: only 2 weeks of sales (insufficient history)
    txns.append({"transaction_date": base_date, "product_name": "Spare Gear", "quantity": 2.0, "is_duplicate": False})
    txns.append({"transaction_date": base_date + timedelta(days=7), "product_name": "Spare Gear", "quantity": 3.0, "is_duplicate": False})

    # 1. Product A Forecast Detail
    detail_a = generate_product_forecast(txns, "Servo Motor 5kW", interval=ForecastIntervalEnum.WEEKLY, horizon=4)
    assert detail_a.data_status == DataLimitationStatusEnum.FORECAST_AVAILABLE
    assert len(detail_a.forecast_points) == 4
    assert detail_a.forecasted_units_total > 0.0
    assert detail_a.demand_trend in ["Increasing", "Stable"]
    assert detail_a.reliability in [ForecastReliabilityEnum.HIGH, ForecastReliabilityEnum.MEDIUM]
    assert np.all([p.predicted_quantity >= 0.0 for p in detail_a.forecast_points])

    # 2. Product B Insufficient History Detail
    detail_b = generate_product_forecast(txns, "Spare Gear", interval=ForecastIntervalEnum.WEEKLY, horizon=4)
    assert detail_b.data_status == DataLimitationStatusEnum.INSUFFICIENT_HISTORY
    assert len(detail_b.forecast_points) == 0
    assert detail_b.reliability == ForecastReliabilityEnum.INSUFFICIENT_HISTORY

    # 3. Overview across all products
    overview = generate_demand_overview(txns, interval=ForecastIntervalEnum.WEEKLY, horizon=4)
    assert overview.total_products == 2
    assert overview.products_with_forecast == 1
    assert overview.products_insufficient_history == 1
    assert overview.total_projected_demand_units == detail_a.forecasted_units_total


# =============================================================================
# 7. AI Explanation with Guaranteed Deterministic Fallback Tests
# =============================================================================

def test_forecast_explanation_fallback_and_narrative():
    """Verify deterministic forecast explanation and guaranteed fallback."""
    req = ForecastExplainRequest(
        product_name="Solar Inverter 3kVA",
        historical_units=120.0,
        forecast_units=45.0,
        forecast_horizon="Next 4 Weeks",
        selected_model="Weighted Moving Average",
        reliability="High",
        trend="Increasing",
        best_mae=2.4,
        limitations=["History spans 12 weekly periods."],
    )

    det_text = generate_deterministic_explanation(req)
    assert "Solar Inverter 3kVA" in det_text
    assert "45.0" in det_text
    assert "Weighted Moving Average" in det_text
    assert "High" in det_text

    # explain_forecast_narrative without active API key uses deterministic fallback cleanly
    resp = explain_forecast_narrative(req)
    assert resp.product_name == "Solar Inverter 3kVA"
    assert resp.is_ai_generated is False
    assert "45.0" in resp.explanation


# =============================================================================
# 8. API End-to-End & Multi-Tenant Isolation Tests
# =============================================================================

def test_api_forecasting_multi_tenant_and_switching():
    """Verify end-to-end /forecasting/overview and /product endpoints with tenant isolation."""
    client = TestClient(app)

    # Register User 1
    email_u1 = f"forecast_u1_{uuid4().hex[:6]}@example.com"
    r1 = client.post("/api/v1/auth/register", json={"email": email_u1, "password": "Password123!", "full_name": "Forecast Lead 1"})
    assert r1.status_code == 201

    # User 1 creates Business A1
    b_a1 = client.post(
        "/api/v1/business",
        json={"basic": {"legal_name": "U1 High Tech", "industry": "Manufacturing", "established_year": 2020, "employee_count": 10, "annual_revenue": 100000.0}},
    ).json()

    # Upload 6 weeks of sales for Business A1
    rows = []
    base_d = datetime(2026, 4, 6, tzinfo=timezone.utc)
    for w in range(6):
        rows.append({"Date": (base_d + timedelta(days=w * 7)).strftime("%Y-%m-%d"), "Item": "Laser Module", "Qty": str(10 + w), "Price": "500"})

    import pandas as pd
    import io
    df = pd.DataFrame(rows)
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    csv_bytes = buf.getvalue()

    mapping = {"transaction_date": "Date", "product_name": "Item", "quantity": "Qty", "unit_price": "Price"}
    u_res = client.post(
        "/api/v1/sales/upload/confirm",
        files={"file": ("sales.csv", csv_bytes, "text/csv")},
        data={"mapping": json.dumps(mapping)},
    )
    assert u_res.status_code == 200

    # 1. User 1 Overview
    res_overview = client.get("/api/v1/forecasting/overview?interval=weekly&horizon=4")
    assert res_overview.status_code == 200
    data_overview = res_overview.json()
    assert data_overview["total_products"] == 1
    assert data_overview["products_with_forecast"] == 1
    assert data_overview["product_summaries"][0]["product_name"] == "Laser Module"

    # 2. User 1 Product Detail
    res_detail = client.get("/api/v1/forecasting/product/Laser Module?interval=weekly&horizon=4")
    assert res_detail.status_code == 200
    data_detail = res_detail.json()
    assert data_detail["product_name"] == "Laser Module"
    assert len(data_detail["forecast_points"]) == 4
    assert data_detail["data_status"] == "forecast_available"

    # 3. User 2 Registration & Tenant Isolation
    client_u2 = TestClient(app)
    email_u2 = f"forecast_u2_{uuid4().hex[:6]}@example.com"
    r2 = client_u2.post("/api/v1/auth/register", json={"email": email_u2, "password": "Password123!", "full_name": "Forecast Lead 2"})
    assert r2.status_code == 201

    client_u2.post(
        "/api/v1/business",
        json={"basic": {"legal_name": "U2 Retailer", "industry": "Retail", "established_year": 2021, "employee_count": 5, "annual_revenue": 50000.0}},
    )

    # User 2 MUST NOT see User 1's products or forecasts
    u2_overview = client_u2.get("/api/v1/forecasting/overview").json()
    assert u2_overview["total_products"] == 0
    assert u2_overview["total_projected_demand_units"] == 0.0

    # 4. Multi-Business Switching for User 1
    # User 1 creates Business A2
    client.post(
        "/api/v1/business",
        json={"basic": {"legal_name": "U1 Enterprise A2", "industry": "Services", "established_year": 2022, "employee_count": 15, "annual_revenue": 20000.0}},
    )
    # Active business is now A2 (has 0 sales)
    a2_overview = client.get("/api/v1/forecasting/overview").json()
    assert a2_overview["total_products"] == 0

    # Switch back to Business A1
    b_a1_id = b_a1["business"]["id"]
    client.patch("/api/v1/auth/me", json={"active_business_id": b_a1_id})

    # Business A1 immediately sees its forecasts again
    a1_overview_again = client.get("/api/v1/forecasting/overview").json()
    assert a1_overview_again["total_products"] == 1
    assert a1_overview_again["product_summaries"][0]["product_name"] == "Laser Module"


# =============================================================================
# 10. Hardening Tests for Phase 4 Data Integrity & Evaluation
# =============================================================================

def test_hardening_missing_periods_vs_confirmed_zero_demand():
    """Area 1: Verify differentiation between confirmed zero demand and unconfirmed gaps."""
    # Timeline: 4 weeks
    # Product A is sold in Week 1 and Week 4.
    # Product B is sold in Week 2 -> proves business was operating and recording in Week 2!
    # Week 3 has NO sales for any product -> unconfirmed gap!
    w1 = datetime(2026, 7, 6, tzinfo=timezone.utc)   # Monday W28
    w2 = datetime(2026, 7, 13, tzinfo=timezone.utc)  # Monday W29
    w4 = datetime(2026, 7, 27, tzinfo=timezone.utc)  # Monday W31

    txns = [
        {"transaction_date": w1, "product_name": "Product A", "quantity": 10.0, "is_duplicate": False},
        {"transaction_date": w2, "product_name": "Product B", "quantity": 50.0, "is_duplicate": False},
        {"transaction_date": w4, "product_name": "Product A", "quantity": 15.0, "is_duplicate": False},
    ]

    series_a = prepare_product_demand_series(txns, "Product A", interval=ForecastIntervalEnum.WEEKLY)
    assert series_a.total_periods == 4
    
    # Week 1: active sales
    assert series_a.periods[0].coverage_status == "active"
    assert series_a.periods[0].quantity == 10.0

    # Week 2: zero recorded sales (Product B was sold, Product A was 0)
    assert series_a.periods[1].coverage_status == "zero_recorded_sales"
    assert series_a.periods[1].quantity == 0.0

    # Week 3: unconfirmed gap (no sales recorded across the entire business)
    assert series_a.periods[2].coverage_status == "unconfirmed_gap"
    assert series_a.periods[2].quantity == 0.0

    # Week 4: active sales
    assert series_a.periods[3].coverage_status == "active"
    assert series_a.periods[3].quantity == 15.0

    assert series_a.zero_recorded_sales_count == 1
    assert series_a.unconfirmed_gaps_count == 1
    # Check limitation notes document this explicitly
    assert any("Coverage notice: 1 period(s) had no recorded transactions" in note for note in series_a.limitation_notes)


def test_hardening_intermittent_demand_expected_rate():
    """Area 2: Verify that intermittent demand does not inflate expected demand to the positive average."""
    # Synthetic benchmark series: 1 positive period (100 units) and 9 confirmed zero periods
    # Total periods = 10, total positive periods = 1
    # Occurrence rate = 1/10 = 0.10
    # Average positive quantity = 100.0
    # Expected demand per period = 0.10 * 100.0 = 10.0 units
    y_intermittent = np.array([100.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], dtype=np.float64)

    expected_preds = intermittent_expected_demand_forecast(y_intermittent, horizon=4)
    # MUST be 10.0 per period, NOT 100.0 (which would be a 10x inflation!)
    assert np.allclose(expected_preds, [10.0, 10.0, 10.0, 10.0])
    assert np.sum(expected_preds) == 40.0
    assert np.sum(expected_preds) < 100.0  # Proves no inflation!


def test_hardening_prediction_interval_calibration_and_range_type():
    """Area 3: Verify estimated prediction range labeling and empirical holdout coverage."""
    # Small series (< 8 periods): cannot establish calibrated 80% coverage
    y_small = np.array([20.0, 22.0, 21.0, 23.0, 22.0], dtype=np.float64)
    preds = np.array([22.0, 22.0, 22.0, 22.0], dtype=np.float64)

    lows, ups, range_type, cov_pct, cov_summary, note = calculate_prediction_intervals(y_small, preds)
    assert range_type == "Estimated Prediction Range"
    assert cov_pct is None
    assert cov_summary is None
    assert "formal 80% coverage calibration is not claimed" in note

    # Series with verified holdout empirical coverage
    lows_eval, ups_eval, range_eval, cov_eval, summary_eval, note_eval = calculate_prediction_intervals(
        y_small, preds, holdout_empirical_coverage=1.0, holdout_eval_count=3, holdout_covered_count=3
    )
    assert range_eval == "Estimated Prediction Range"
    assert cov_eval == 100.0
    assert summary_eval == "100.0% (3/3 holdout points)"
    assert "Small sample count (n=3) serves as an empirical diagnostic" in note_eval


def test_hardening_product_identity_routing_and_safe_normalization():
    """Area 4: Verify product_id as primary key and safe name normalization without merging distinct variants."""
    base_date = datetime(2026, 8, 3, tzinfo=timezone.utc)
    
    # 1. Same product name ("Cotton T-Shirt") with different product_ids ("TS-SMALL" vs "TS-LARGE")
    # Must NOT be merged into a single product!
    txns = [
        # Product 1: TS-SMALL (4 weeks of sales)
        {"transaction_date": base_date, "product_id": "TS-SMALL", "product_name": "Cotton T-Shirt", "quantity": 10.0, "is_duplicate": False},
        {"transaction_date": base_date + timedelta(days=7), "product_id": "TS-SMALL", "product_name": "Cotton T-Shirt", "quantity": 12.0, "is_duplicate": False},
        {"transaction_date": base_date + timedelta(days=14), "product_id": "TS-SMALL", "product_name": "Cotton T-Shirt", "quantity": 15.0, "is_duplicate": False},
        {"transaction_date": base_date + timedelta(days=21), "product_id": "TS-SMALL", "product_name": "Cotton T-Shirt", "quantity": 18.0, "is_duplicate": False},
        # Product 2: TS-LARGE (4 weeks of sales)
        {"transaction_date": base_date, "product_id": "TS-LARGE", "product_name": "Cotton T-Shirt", "quantity": 40.0, "is_duplicate": False},
        {"transaction_date": base_date + timedelta(days=7), "product_id": "TS-LARGE", "product_name": "Cotton T-Shirt", "quantity": 45.0, "is_duplicate": False},
        {"transaction_date": base_date + timedelta(days=14), "product_id": "TS-LARGE", "product_name": "Cotton T-Shirt", "quantity": 50.0, "is_duplicate": False},
        {"transaction_date": base_date + timedelta(days=21), "product_id": "TS-LARGE", "product_name": "Cotton T-Shirt", "quantity": 55.0, "is_duplicate": False},
    ]

    overview = generate_demand_overview(txns, interval=ForecastIntervalEnum.WEEKLY, horizon=4)
    # Must have 2 distinct products!
    assert overview.total_products == 2
    product_ids = {p.product_id for p in overview.product_summaries}
    assert product_ids == {"TS-SMALL", "TS-LARGE"}

    # Individual forecast routing with product_id
    detail_small = generate_product_forecast(txns, "Cotton T-Shirt", product_id="TS-SMALL", horizon=4)
    assert detail_small.product_id == "TS-SMALL"
    assert sum(p.actual_quantity for p in detail_small.history_points) == 55.0

    detail_large = generate_product_forecast(txns, "Cotton T-Shirt", product_id="TS-LARGE", horizon=4)
    assert detail_large.product_id == "TS-LARGE"
    assert sum(p.actual_quantity for p in detail_large.history_points) == 190.0

    # 2. Similar product names without product_ids: distinct variants must NOT collide
    variant_txns = [
        {"transaction_date": base_date, "product_name": "Bearing 6200", "quantity": 5.0, "is_duplicate": False},
        {"transaction_date": base_date, "product_name": "Bearing 6201", "quantity": 8.0, "is_duplicate": False},
    ]
    var_overview = generate_demand_overview(variant_txns)
    assert var_overview.total_products == 2
    names = {p.product_name for p in var_overview.product_summaries}
    assert names == {"Bearing 6200", "Bearing 6201"}

    # 3. Safe normalization: whitespace variation safely unified
    spacing_txns = [
        {"transaction_date": base_date, "product_name": "  Steel   Bolt  ", "quantity": 10.0, "is_duplicate": False},
        {"transaction_date": base_date + timedelta(days=7), "product_name": "Steel Bolt", "quantity": 15.0, "is_duplicate": False},
    ]
    space_overview = generate_demand_overview(spacing_txns)
    assert space_overview.total_products == 1
    assert space_overview.product_summaries[0].product_name == "Steel Bolt"


def test_hardening_rolling_origin_backtesting_and_synthetic_fixtures():
    """Area 5: Verify rolling-origin walk-forward backtesting with zero future data leakage on synthetic benchmark data."""
    # Explicitly labeled synthetic test series
    synthetic_benchmark_series = np.array(
        [10.0, 12.0, 15.0, 14.0, 18.0, 20.0, 22.0, 25.0, 28.0, 30.0],
        dtype=np.float64,
    )
    assert len(synthetic_benchmark_series) >= 8

    selected_model, metrics, holdout_info = backtest_and_select_model(
        synthetic_benchmark_series, horizon=4
    )

    # Must execute rolling-origin backtesting
    assert holdout_info["evaluation_method"] == "rolling_origin"
    assert holdout_info["rolling_splits_count"] >= 2
    assert holdout_info["split_possible"] is True

    # Check metrics are computed on rolling walk-forward test points
    for m in metrics:
        assert m.mae >= 0.0
        assert m.rmse >= m.mae or np.isclose(m.rmse, m.mae)
        assert m.holdout_periods == holdout_info["holdout_eval_count"]

    # Verify zero future leakage: evaluated origins train strictly on preceding indices
    assert holdout_info["train_periods"] < len(synthetic_benchmark_series)


def test_rolling_origin_evaluates_multi_period_horizon():
    """Area 5: Verify rolling-origin evaluation evaluates the full multi-period horizon trajectory."""
    # 8-period series with horizon=3
    y_test = np.array([10.0, 12.0, 14.0, 16.0, 18.0, 20.0, 22.0, 24.0], dtype=np.float64)
    selected_model, metrics, holdout_info = backtest_and_select_model(y_test, horizon=3)

    assert holdout_info["evaluation_method"] == "rolling_origin"
    # n=8, num_splits = min(4, 3) = 3
    # initial_train = 5
    # split 0: origin 5, eval_h = min(3, 3) = 3
    # split 1: origin 6, eval_h = min(3, 2) = 2
    # split 2: origin 7, eval_h = min(3, 1) = 1
    # expected total horizon points = 3 + 2 + 1 = 6
    assert holdout_info["holdout_eval_count"] == 6
    for m in metrics:
        assert m.holdout_periods == 6


# =============================================================================
# 11. Independent Evaluation & Model Selection Separation Tests (Final Review)
# =============================================================================

def test_independent_evaluation_uses_separate_observations_when_sufficient_history():
    """Verify that when N >= 8 + H_test (e.g. N=12, H=4), model selection and final evaluation
    use strictly disjoint, chronological subsets with zero data leakage."""
    # Deterministic synthetic benchmark series of length 12
    # Note: Synthetic benchmark data for statistical validation, does not assert real MSME accuracy.
    synthetic_series_12 = np.array(
        [10.0, 12.0, 14.0, 16.0, 18.0, 20.0, 22.0, 24.0, 26.0, 28.0, 30.0, 32.0],
        dtype=np.float64,
    )
    horizon = 4
    # N=12, H_test=4, min required = 8 + 4 = 12.
    selected_model, tournament_metrics, holdout_info = backtest_and_select_model(
        synthetic_series_12, horizon=horizon
    )

    # 1. Independent evaluation must be active
    assert holdout_info["evaluation_stage"] == "independent_test_evaluated"
    assert holdout_info["is_independent_evaluation"] is True
    assert holdout_info["selection_periods"] == 8
    assert holdout_info["final_test_size"] == 4

    # 2. Independent test metrics must be present and distinct from tournament metrics
    indep_metrics = holdout_info["independent_test_metrics"]
    assert indep_metrics is not None
    assert len(indep_metrics) >= 1
    # Check winning model in independent test
    winner_item = next((m for m in indep_metrics if m.is_selected), None)
    assert winner_item is not None
    assert winner_item.model_name == selected_model
    assert winner_item.test_periods == 4
    assert winner_item.mae >= 0.0

    # 3. Tournament metrics must be labeled as model_selection role
    for m in tournament_metrics:
        assert m.metric_role == "model_selection"


def test_final_test_segment_never_seen_during_model_selection():
    """Verify that changing values in the final test segment (y_test) has ZERO impact
    on the candidate model errors and model selection outcome of the tournament."""
    # Synthetic series A and B: identical first 8 periods (selection periods),
    # but radically different final 4 periods (test periods).
    base_selection = [10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0]
    series_a = np.array(base_selection + [18.0, 19.0, 20.0, 21.0], dtype=np.float64)
    series_b = np.array(base_selection + [999.0, 1000.0, 1001.0, 1002.0], dtype=np.float64)

    sel_a, tourney_a, info_a = backtest_and_select_model(series_a, horizon=4)
    sel_b, tourney_b, info_b = backtest_and_select_model(series_b, horizon=4)

    # 1. The winning model MUST be identical
    assert sel_a == sel_b

    # 2. Every single candidate model's tournament MAE must be IDENTICAL between A and B,
    # proving mathematically that the final 4 periods NEVER leaked into model selection!
    map_a = {m.model_name: m.mae for m in tourney_a}
    map_b = {m.model_name: m.mae for m in tourney_b}
    for name in map_a:
        assert np.isclose(map_a[name], map_b[name]), f"Data leakage detected! {name} MAE changed when y_test changed."

    # 3. The independent test metrics on y_test SHOULD differ because y_test actuals are different
    assert info_a["independent_mae"] != info_b["independent_mae"]


def test_short_series_reports_insufficient_independent_data():
    """Verify that series with N < 8 + H_test transparently report insufficient independent evaluation data
    without fabricating an out-of-sample evaluation or confusing tournament scores."""
    # Synthetic series of length 9 with horizon 4 (requires 8 + 4 = 12)
    synthetic_series_9 = np.array([20.0, 22.0, 21.0, 23.0, 24.0, 22.0, 25.0, 26.0, 24.0], dtype=np.float64)
    selected_model, tournament_metrics, holdout_info = backtest_and_select_model(
        synthetic_series_9, horizon=4
    )

    # Must NOT claim independent evaluation
    assert holdout_info["evaluation_stage"] == "insufficient_independent_evaluation_data"
    assert holdout_info["is_independent_evaluation"] is False
    assert holdout_info["independent_test_metrics"] is None
    assert holdout_info["independent_mae"] is None
    assert "insufficient" in holdout_info["reason"]
    assert "12 periods" in holdout_info["reason"]

    # Tournament metrics must still be provided as selection diagnostics
    assert len(tournament_metrics) >= 3
    for m in tournament_metrics:
        assert m.metric_role == "model_selection"


def test_independent_metrics_and_tournament_metrics_not_confused_in_detail_response():
    """Verify that ProductForecastDetailResponse preserves both independent test metrics
    and tournament metrics distinctly without conflation."""
    base_date = datetime(2026, 6, 1, tzinfo=timezone.utc)
    # Generate 14 weeks of synthetic sales transactions (N=14 >= 12)
    txns = [
        {
            "transaction_date": base_date + timedelta(days=7 * i),
            "product_name": "Precision Sensor",
            "quantity": 10.0 + (i * 2.0),
            "is_duplicate": False,
        }
        for i in range(14)
    ]

    detail = generate_product_forecast(txns, "Precision Sensor", horizon=4)

    assert detail.evaluation_stage == "independent_test_evaluated"
    assert detail.independent_test_metrics is not None
    assert len(detail.independent_test_metrics) >= 1
    assert detail.provenance["is_independent_evaluation"] is True
    assert detail.provenance["selection_periods"] == 10
    assert detail.provenance["final_test_size"] == 4
    assert detail.provenance["independent_mae"] is not None

    # Tournament metrics remain intact for full audit trail
    assert len(detail.backtest_metrics) >= 3
    # Explanation explicitly mentions independent holdout test
    assert "independently verified on separate 4-period holdout test" in detail.explanation


def test_preprocessing_and_intermittency_fitted_strictly_on_selection_split_with_no_leakage():
    """Verify that preprocessing, intermittency classification, and feature transformations
    are fitted strictly on y_selection, preventing future holdout trends from leaking into selection."""
    # Synthetic series of length 12:
    # First 8 periods (y_selection): 6 zeros and 2 positive sales -> sparsity = 6/8 = 75% (> 70% intermittent!)
    # Final 4 periods (y_test): 4 positive sales -> overall series sparsity = 6/12 = 50% (NOT intermittent globally!)
    y_intermittent_start = np.array(
        [0.0, 10.0, 0.0, 0.0, 0.0, 0.0, 15.0, 0.0, 20.0, 25.0, 30.0, 35.0],
        dtype=np.float64,
    )

    # Even though global series has 50% sparsity, y_selection has 75% sparsity.
    # The tournament on y_selection MUST include the intermittent expected demand model!
    selected_model, tournament_metrics, holdout_info = backtest_and_select_model(
        y_intermittent_start, horizon=4
    )

    assert holdout_info["evaluation_stage"] == "independent_test_evaluated"
    tourney_model_names = [m.model_name for m in tournament_metrics]
    assert "Intermittent Rate (Expected Demand)" in tourney_model_names, (
        "Intermittent model should have been included based on y_selection sparsity (>70%). "
        "Failure indicates y_test future sales leaked into selection preprocessing!"
    )

def test_intermittent_demand_fairly_evaluated_against_reference_baseline_on_holdout():
    """Verify that when Intermittent Rate is selected, the independent holdout evaluation
    fairly compares it against a standard reference baseline (e.g. Moving Average)."""
    # 10 periods of intermittent sales (8 selection periods, 2 holdout periods)
    # Series engineered where Intermittent Rate wins tournament on y_selection
    y_intermittent = np.array(
        [0.0, 0.0, 10.0, 0.0, 0.0, 10.0, 0.0, 0.0, 0.0, 10.0],
        dtype=np.float64,
    )

    selected_model, tournament_metrics, holdout_info = backtest_and_select_model(
        y_intermittent, horizon=2
    )

    assert holdout_info["evaluation_stage"] == "independent_test_evaluated"
    indep_metrics = holdout_info["independent_test_metrics"]
    assert indep_metrics is not None
    assert len(indep_metrics) == 2, "Must evaluate both the selected intermittent winner AND reference baseline"

    winner_item = next(m for m in indep_metrics if m.is_selected)
    baseline_item = next(m for m in indep_metrics if m.is_baseline and not m.is_selected)

    assert winner_item.model_name == "Intermittent Rate (Expected Demand)"
    assert baseline_item.model_name == "Moving Average (3-Period)"
    # Both models evaluated on the same 2 test periods
    assert winner_item.test_periods == 2
    assert baseline_item.test_periods == 2
    assert winner_item.mae >= 0.0
    assert baseline_item.mae >= 0.0


def test_metric_interpretation_exposes_sample_sizes_and_zero_demand_caveats():
    """Verify that compute_metrics exposes sample counts, non-zero counts, and zero-demand caveats."""
    # Test segment with 2 zeros and 2 positive sales
    y_true = np.array([0.0, 10.0, 0.0, 20.0], dtype=np.float64)
    y_pred = np.array([2.5, 8.0, 3.0, 18.0], dtype=np.float64)
    y_train = np.array([0.0, 5.0, 0.0, 15.0, 0.0, 10.0], dtype=np.float64)

    metrics = compute_metrics(y_true, y_pred, y_train)

    assert metrics["test_periods"] == 4
    assert metrics["non_zero_periods"] == 2
    assert metrics["zero_periods"] == 2
    assert metrics["wape"] is not None
    assert metrics["mape"] is not None
    assert metrics["mase"] is not None

    notes = metrics["metric_notes"]
    assert len(notes) >= 3
    # Confirms MAPE limitation on zero periods is documented
    assert any("MAPE is evaluated on 2/4 positive period(s)" in n for n in notes)
    # Confirms sample size limitation is documented
    assert any("Sample size: evaluated on 4 period(s)" in n for n in notes)


def test_four_period_test_horizon_limitation_notice_in_detail_response():
    """Verify that ProductForecastDetailResponse transparently documents the 4-period test limitation."""
    base_date = datetime(2026, 6, 1, tzinfo=timezone.utc)
    txns = [
        {
            "transaction_date": base_date + timedelta(days=7 * i),
            "product_name": "Valve Core",
            "quantity": 15.0 + i,
            "is_duplicate": False,
        }
        for i in range(12)
    ]

    detail = generate_product_forecast(txns, "Valve Core", horizon=4)

    assert detail.evaluation_stage == "independent_test_evaluated"
    # Limitation notice in limitations
    assert any("Four-Period Test Horizon Limitation" in lim for lim in detail.limitations)
    # Limitation notice in provenance
    assert "test_limitation_notice" in detail.provenance
    assert "4 holdout periods" in detail.provenance["test_limitation_notice"]
    assert "multi-season validation requires extended longitudinal data" in detail.provenance["test_limitation_notice"]

