"""Core Demand Forecasting Engine (Phase 4).

Coordinates data preparation, chronological backtesting, model selection,
prediction interval generation, and structured API responses.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Sequence
import numpy as np

from app.models.sales import SalesTransaction
from app.schemas.forecasting import (
    BacktestMetricItem,
    DataLimitationStatusEnum,
    DemandForecastOverviewResponse,
    ForecastIntervalEnum,
    ForecastPeriodPoint,
    ForecastReliabilityEnum,
    HistoricalPeriodPoint,
    ProductForecastDetailResponse,
    ProductForecastSummaryItem,
)
from app.services.forecasting.baselines import (
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
    PreparedProductSeries,
    prepare_product_demand_series,
)
from app.services.forecasting.evaluation import backtest_and_select_model
from app.services.forecasting.models import (
    autoregressive_ridge_forecast,
    holt_linear_exponential_smoothing,
)


def _generate_future_period_labels(
    last_end_date_str: str,
    interval: ForecastIntervalEnum,
    horizon: int,
) -> list[tuple[str, str, str]]:
    """Generate (label, start_date_str, end_date_str) for future forecast periods."""
    last_end = datetime.strptime(last_end_date_str, "%Y-%m-%d").date()
    results = []

    if interval == ForecastIntervalEnum.DAILY:
        curr = last_end + timedelta(days=1)
        for i in range(horizon):
            d_str = curr.strftime("%Y-%m-%d")
            results.append((d_str, d_str, d_str))
            curr += timedelta(days=1)

    elif interval == ForecastIntervalEnum.MONTHLY:
        # Determine next month start
        curr_y = last_end.year
        curr_m = last_end.month + 1
        if curr_m > 12:
            curr_y += 1
            curr_m = 1

        for i in range(horizon):
            key = f"{curr_y:04d}-{curr_m:02d}"
            start_str = f"{key}-01"
            next_m = curr_m + 1 if curr_m < 12 else 1
            next_y = curr_y if curr_m < 12 else curr_y + 1
            last_day = (datetime(next_y, next_m, 1) - timedelta(days=1)).day
            end_str = f"{key}-{last_day:02d}"
            results.append((key, start_str, end_str))

            if curr_m == 12:
                curr_y += 1
                curr_m = 1
            else:
                curr_m += 1

    else:
        # WEEKLY (default standard)
        curr_start = last_end + timedelta(days=1)
        for i in range(horizon):
            curr_end = curr_start + timedelta(days=6)
            iso_year, iso_week, _ = curr_start.isocalendar()
            label = f"{iso_year}-W{iso_week:02d}"
            results.append(
                (label, curr_start.strftime("%Y-%m-%d"), curr_end.strftime("%Y-%m-%d"))
            )
            curr_start = curr_end + timedelta(days=1)

    return results


def _fit_and_project(model_name: str, y: np.ndarray, horizon: int) -> np.ndarray:
    """Project future periods using the selected model on full historical data."""
    if "Naive" in model_name and "Seasonal" not in model_name:
        return naive_forecast(y, horizon)
    elif "Weighted" in model_name:
        return weighted_moving_average_forecast(y, horizon, window=3)
    elif "Seasonal" in model_name:
        return seasonal_naive_forecast(y, horizon, season_length=4)
    elif "Holt" in model_name:
        return holt_linear_exponential_smoothing(y, horizon)
    elif "Ridge" in model_name:
        return autoregressive_ridge_forecast(y, horizon, l2_reg=1.0)
    else:
        # Default Moving Average
        return moving_average_forecast(y, horizon, window=3)


def generate_product_forecast(
    transactions: Sequence[SalesTransaction | dict[str, Any]],
    product_name: str,
    interval: ForecastIntervalEnum = ForecastIntervalEnum.WEEKLY,
    horizon: int = 4,
) -> ProductForecastDetailResponse:
    """Generate complete demand forecast for a single product with full backtesting evaluation."""
    series = prepare_product_demand_series(transactions, product_name, interval=interval)

    # Convert history into schema points
    history_points = [
        HistoricalPeriodPoint(
            period_label=p.period_label,
            period_start=p.period_start,
            period_end=p.period_end,
            actual_quantity=p.quantity,
            has_data=p.has_data,
        )
        for p in series.periods
    ]

    # Handle insufficient or zero history
    if series.status in [
        DataLimitationStatusEnum.NO_SALES_HISTORY,
        DataLimitationStatusEnum.INSUFFICIENT_HISTORY,
    ]:
        return ProductForecastDetailResponse(
            product_name=series.product_name,
            product_id=series.product_id,
            data_status=series.status,
            selected_model="Insufficient Data Baseline",
            reliability=ForecastReliabilityEnum.INSUFFICIENT_HISTORY,
            aggregation_interval=interval,
            forecast_horizon_periods=horizon,
            forecasted_units_total=0.0,
            demand_trend="Insufficient History",
            trend_delta_pct=None,
            history_points=history_points,
            forecast_points=[],
            backtest_metrics=[],
            explanation=(
                f"Demand forecast cannot be calculated for '{series.product_name}'. "
                + " ".join(series.limitation_notes)
            ),
            limitations=series.limitation_notes,
            provenance={
                "data_source": "sales_transactions",
                "observations_count": series.total_periods,
                "active_observations": series.active_periods,
                "holdout_evaluated": False,
            },
        )

    # 1. Backtest candidates on chronological holdout
    selected_model, backtest_metrics, holdout_info = backtest_and_select_model(
        series.quantities, horizon=min(horizon, 4)
    )

    # 2. Fit selected model on full historical series to project future horizon
    future_preds = _fit_and_project(selected_model, series.quantities, horizon)
    # Guarantee non-negative demand
    future_preds = np.maximum(0.0, future_preds)

    # 3. Prediction intervals
    best_item = next((m for m in backtest_metrics if m.is_selected), None)
    best_mae = best_item.mae if best_item else None
    best_wape = best_item.wape if best_item else None

    lowers, uppers = calculate_prediction_intervals(
        series.quantities, future_preds, backtest_mae=best_mae
    )

    # 4. Generate future period labels
    last_p = series.periods[-1]
    future_labels = _generate_future_period_labels(last_p.period_end, interval, horizon)

    forecast_points = [
        ForecastPeriodPoint(
            period_index=i + 1,
            period_label=future_labels[i][0],
            period_start=future_labels[i][1],
            period_end=future_labels[i][2],
            predicted_quantity=round(float(future_preds[i]), 2),
            lower_estimate=round(float(lowers[i]), 2),
            upper_estimate=round(float(uppers[i]), 2),
        )
        for i in range(horizon)
    ]

    total_forecasted = round(float(np.sum(future_preds)), 2)

    # 5. Determine demand trajectory vs historical pace
    hist_avg = float(np.mean(series.quantities)) if len(series.quantities) > 0 else 0.0
    pred_avg = float(np.mean(future_preds)) if len(future_preds) > 0 else 0.0

    if hist_avg > 0:
        delta_pct = round(((pred_avg - hist_avg) / hist_avg) * 100.0, 1)
    else:
        delta_pct = 100.0 if pred_avg > 0 else 0.0

    if delta_pct >= 10.0:
        demand_trend = "Increasing"
    elif delta_pct <= -10.0:
        demand_trend = "Decreasing"
    else:
        demand_trend = "Stable"

    # 6. Reliability classification
    reliability = evaluate_forecast_reliability(
        total_periods=series.total_periods,
        sparsity_ratio=series.sparsity_ratio,
        best_wape=best_wape,
        best_mae=best_mae,
        mean_demand=hist_avg,
    )

    # 7. Generate explanation and limitations
    explanation = (
        f"Based on {series.total_periods} historical {interval.value} periods, demand for '{product_name}' "
        f"is projected to be {total_forecasted} total units over the next {horizon} {interval.value}s "
        f"(average {round(pred_avg, 1)} units/{interval.value}). "
        f"Selected {selected_model} via chronological holdout evaluation"
        + (f" (MAE: {best_mae}, WAPE: {best_wape})." if best_mae is not None else ".")
    )

    limitations = list(series.limitation_notes)
    if series.total_periods < 12:
        limitations.append(
            f"History spans {series.total_periods} periods. Longer time series will improve accuracy."
        )
    limitations.append(
        "Forecast estimates customer demand only and does not reflect current inventory or supplier lead times."
    )

    provenance = {
        "data_source": "sales_transactions",
        "observations_count": series.total_periods,
        "active_observations": series.active_periods,
        "sparsity_ratio": series.sparsity_ratio,
        "selected_model": selected_model,
        "holdout_evaluated": holdout_info.get("split_possible", False),
        "holdout_periods": holdout_info.get("holdout_periods", 0),
        "backtest_models_count": len(backtest_metrics),
    }

    return ProductForecastDetailResponse(
        product_name=series.product_name,
        product_id=series.product_id,
        data_status=series.status,
        selected_model=selected_model,
        reliability=reliability,
        aggregation_interval=interval,
        forecast_horizon_periods=horizon,
        forecasted_units_total=total_forecasted,
        demand_trend=demand_trend,
        trend_delta_pct=delta_pct,
        history_points=history_points,
        forecast_points=forecast_points,
        backtest_metrics=backtest_metrics,
        explanation=explanation,
        limitations=limitations,
        provenance=provenance,
    )


def generate_demand_overview(
    transactions: Sequence[SalesTransaction | dict[str, Any]],
    interval: ForecastIntervalEnum = ForecastIntervalEnum.WEEKLY,
    horizon: int = 4,
) -> DemandForecastOverviewResponse:
    """Generate high-level demand forecast overview across all products for a business."""
    # Collect unique product names (non-duplicate transactions only)
    distinct_products: set[str] = set()
    dates: list[datetime] = []

    for t in transactions:
        t_is_dup = getattr(t, "is_duplicate", False) if hasattr(t, "is_duplicate") else t.get("is_duplicate", False)
        if t_is_dup:
            continue
        p_name = getattr(t, "product_name", None) if hasattr(t, "product_name") else t.get("product_name")
        if p_name and p_name.strip():
            distinct_products.add(p_name.strip())
        t_date = getattr(t, "transaction_date", None) if hasattr(t, "transaction_date") else t.get("transaction_date")
        if t_date:
            dates.append(t_date if isinstance(t_date, datetime) else pd.to_datetime(t_date).to_pydatetime())

    if not distinct_products or not dates:
        return DemandForecastOverviewResponse(
            total_products=0,
            products_with_forecast=0,
            products_insufficient_history=0,
            products_increasing_demand=0,
            products_declining_demand=0,
            products_stable_demand=0,
            total_projected_demand_units=0.0,
            forecast_horizon=f"Next {horizon} {interval.value.capitalize()}s",
            aggregation_interval=interval,
            product_summaries=[],
            dataset_span_days=0,
            earliest_transaction_date=None,
            latest_transaction_date=None,
            inactivity_anchor_date=None,
        )

    min_date = min(dates)
    max_date = max(dates)
    span_days = (max_date - min_date).days

    summaries: list[ProductForecastSummaryItem] = []
    with_forecast = 0
    insufficient_count = 0
    increasing_count = 0
    declining_count = 0
    stable_count = 0
    total_projected = 0.0

    # Sort products alphabetically for deterministic ordering
    for p_name in sorted(distinct_products):
        detail = generate_product_forecast(
            transactions, p_name, interval=interval, horizon=horizon
        )

        best_m = next((m for m in detail.backtest_metrics if m.is_selected), None)
        hist_units = sum(p.actual_quantity for p in detail.history_points)

        summary_item = ProductForecastSummaryItem(
            product_name=detail.product_name,
            product_id=detail.product_id,
            data_status=detail.data_status,
            selected_model=detail.selected_model,
            reliability=detail.reliability,
            historical_periods_count=len(detail.history_points),
            historical_units_total=round(hist_units, 2),
            forecast_horizon_periods=horizon,
            forecasted_units_total=detail.forecasted_units_total,
            demand_trend=detail.demand_trend,
            trend_delta_pct=detail.trend_delta_pct,
            best_mae=best_m.mae if best_m else None,
            best_wape=best_m.wape if best_m else None,
            limitation_notes=detail.limitations,
        )
        summaries.append(summary_item)

        if detail.data_status in [
            DataLimitationStatusEnum.FORECAST_AVAILABLE,
            DataLimitationStatusEnum.INTERMITTENT_DEMAND,
        ]:
            with_forecast += 1
            total_projected += detail.forecasted_units_total
            if detail.demand_trend == "Increasing":
                increasing_count += 1
            elif detail.demand_trend == "Decreasing":
                declining_count += 1
            else:
                stable_count += 1
        else:
            insufficient_count += 1

    return DemandForecastOverviewResponse(
        total_products=len(distinct_products),
        products_with_forecast=with_forecast,
        products_insufficient_history=insufficient_count,
        products_increasing_demand=increasing_count,
        products_declining_demand=declining_count,
        products_stable_demand=stable_count,
        total_projected_demand_units=round(total_projected, 2),
        forecast_horizon=f"Next {horizon} {interval.value.capitalize()}s",
        aggregation_interval=interval,
        product_summaries=summaries,
        dataset_span_days=span_days,
        earliest_transaction_date=min_date.strftime("%Y-%m-%d"),
        latest_transaction_date=max_date.strftime("%Y-%m-%d"),
        inactivity_anchor_date=max_date.strftime("%Y-%m-%d"),
    )
