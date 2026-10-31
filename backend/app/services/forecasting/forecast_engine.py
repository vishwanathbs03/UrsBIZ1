"""Core Demand Forecasting Engine (Phase 4 Hardening).

Coordinates:
  1. Data preparation with confirmed zero vs. unconfirmed gap separation.
  2. Safe product identification with product_id as primary key and safe name normalization.
  3. Intermittent demand rate modeling (occurrence rate * positive average).
  4. Rolling-origin backtesting and empirical interval calibration validation.
  5. Multi-product overview with tenant isolation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Sequence
import numpy as np
import pandas as pd

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
    PreparedProductSeries,
    prepare_product_demand_series,
    safe_normalize_product_name,
)
from app.services.forecasting.evaluation import (
    backtest_and_select_model,
    fit_and_project,
)
from app.services.forecasting.models import (
    autoregressive_ridge_forecast,
    holt_linear_exponential_smoothing,
)


@dataclass(frozen=True)
class ProductIdentityKey:
    """Safe product identification key distinguishing products with same name but different IDs."""
    product_id: str | None
    product_name: str
    display_label: str


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


_fit_and_project = fit_and_project


def generate_product_forecast(
    transactions: Sequence[SalesTransaction | dict[str, Any]],
    product_name: str,
    product_id: str | None = None,
    interval: ForecastIntervalEnum = ForecastIntervalEnum.WEEKLY,
    horizon: int = 4,
    business_active_periods: set[str] | None = None,
) -> ProductForecastDetailResponse:
    """Generate complete demand forecast for a single product with full backtesting evaluation."""
    series = prepare_product_demand_series(
        transactions,
        product_name=product_name,
        product_id=product_id,
        interval=interval,
        business_active_periods=business_active_periods,
    )

    # Convert history into schema points with explicit coverage classification
    history_points = [
        HistoricalPeriodPoint(
            period_label=p.period_label,
            period_start=p.period_start,
            period_end=p.period_end,
            actual_quantity=p.quantity,
            has_data=p.has_data,
            coverage_status=p.coverage_status,
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
            evaluation_stage="insufficient_independent_evaluation_data",
            independent_test_metrics=None,
            range_type="Estimated Prediction Range (Uncalibrated)",
            empirical_coverage_pct=None,
            explanation=(
                f"Demand forecast cannot be calculated for '{series.product_name}'. "
                + " ".join(series.limitation_notes)
            ),
            limitations=series.limitation_notes,
            provenance={
                "data_source": "sales_transactions",
                "observations_count": series.total_periods,
                "active_observations": series.active_periods,
                "zero_recorded_sales_count": series.zero_recorded_sales_count,
                "unconfirmed_gaps_count": series.unconfirmed_gaps_count,
                "holdout_evaluated": False,
                "evaluation_method": "none",
            },
        )

    # 1. Backtest candidates on chronological holdout (or rolling-origin if >= 8 periods)
    is_intermittent = (series.status == DataLimitationStatusEnum.INTERMITTENT_DEMAND)
    selected_model, backtest_metrics, holdout_info = backtest_and_select_model(
        series.quantities,
        horizon=min(horizon, 4),
        is_intermittent=is_intermittent,
    )

    # 2. Fit selected model on full historical series to project future horizon
    future_preds = _fit_and_project(selected_model, series.quantities, horizon)
    # Guarantee non-negative demand
    future_preds = np.maximum(0.0, future_preds)

    # 3. Prediction intervals with calibration assessment
    best_item = next((m for m in backtest_metrics if m.is_selected), None)
    eval_stage = holdout_info.get("evaluation_stage", "insufficient_independent_evaluation_data")
    is_indep = holdout_info.get("is_independent_evaluation", False)

    if is_indep and holdout_info.get("independent_mae") is not None:
        best_mae = holdout_info.get("independent_mae")
        best_wape = holdout_info.get("independent_wape")
    else:
        best_mae = holdout_info.get("selection_mae", best_item.mae if best_item else None)
        best_wape = holdout_info.get("selection_wape", best_item.wape if best_item else None)

    emp_cov = holdout_info.get("empirical_coverage")
    holdout_eval_count = holdout_info.get("holdout_eval_count", 0)
    holdout_covered_count = holdout_info.get("holdout_covered_count", 0)

    lowers, uppers, range_type, cov_pct, cov_summary, calib_note = calculate_prediction_intervals(
        series.quantities,
        future_preds,
        backtest_mae=best_mae,
        holdout_empirical_coverage=emp_cov,
        holdout_eval_count=holdout_eval_count,
        holdout_covered_count=holdout_covered_count,
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

    # 6. Reliability classification (accounting for unconfirmed gaps)
    reliability = evaluate_forecast_reliability(
        total_periods=series.total_periods,
        sparsity_ratio=series.sparsity_ratio,
        best_wape=best_wape,
        best_mae=best_mae,
        mean_demand=hist_avg,
        unconfirmed_gaps=series.unconfirmed_gaps_count,
    )

    # 7. Generate explanation and limitations
    if is_indep:
        eval_desc = (
            f"Selected {selected_model} via walk-forward tournament on preceding history, "
            f"independently verified on separate {holdout_info.get('final_test_size', 4)}-period holdout test "
            f"(Test MAE: {best_mae}, Test WAPE: {best_wape})."
        )
    else:
        tourn_mae = holdout_info.get("selection_mae", best_item.mae if best_item else None)
        tourn_wape = holdout_info.get("selection_wape", best_item.wape if best_item else None)
        eval_desc = (
            f"Selected {selected_model} via {holdout_info.get('evaluation_method', 'backtest')} tournament "
            f"(Tournament MAE: {tourn_mae}, WAPE: {tourn_wape}). "
            f"Note: Evaluated as internal model-selection diagnostic (series under {holdout_info.get('required_periods', 12)} periods for separate test holdout)."
        )

    explanation = (
        f"Based on {series.total_periods} historical {interval.value} periods, demand for '{product_name}' "
        f"is projected to be {total_forecasted} total units over the next {horizon} {interval.value}s "
        f"(average {round(pred_avg, 1)} units/{interval.value}). {eval_desc}"
    )

    limitations = list(series.limitation_notes)
    limitations.append(calib_note)
    if is_indep:
        limitations.append(
            f"Model was selected on {holdout_info.get('selection_periods', 8)} earlier periods and independently tested on {holdout_info.get('final_test_size', 4)} separate holdout periods."
        )
    elif series.total_periods >= 4:
        limitations.append(
            f"Model performance represents internal tournament selection diagnostics. "
            f"Independent out-of-sample test evaluation requires at least {holdout_info.get('required_periods', 12)} historical periods "
            f"(current series has {series.total_periods} periods)."
        )
    limitations.append(
        "Forecast estimates customer demand only and does not reflect current inventory or supplier lead times."
    )

    provenance = {
        "data_source": "sales_transactions",
        "observations_count": series.total_periods,
        "active_observations": series.active_periods,
        "zero_recorded_sales_count": series.zero_recorded_sales_count,
        "unconfirmed_gaps_count": series.unconfirmed_gaps_count,
        "sparsity_ratio": series.sparsity_ratio,
        "selected_model": selected_model,
        "evaluation_stage": eval_stage,
        "is_independent_evaluation": is_indep,
        "independent_mae": holdout_info.get("independent_mae"),
        "independent_wape": holdout_info.get("independent_wape"),
        "selection_mae": holdout_info.get("selection_mae"),
        "selection_wape": holdout_info.get("selection_wape"),
        "evaluation_method": holdout_info.get("evaluation_method", "fixed_holdout"),
        "rolling_splits_count": holdout_info.get("rolling_splits_count", 0),
        "selection_periods": holdout_info.get("selection_periods", series.total_periods),
        "final_test_size": holdout_info.get("final_test_size", 0),
        "holdout_evaluated": holdout_info.get("split_possible", False),
        "holdout_periods": holdout_info.get("holdout_periods", 0),
        "empirical_coverage_pct": cov_pct,
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
        evaluation_stage=eval_stage,
        independent_test_metrics=holdout_info.get("independent_test_metrics"),
        range_type=range_type,
        empirical_coverage_summary=cov_summary,
        empirical_coverage_pct=cov_pct,
        empirical_coverage_samples=holdout_eval_count if holdout_eval_count > 0 else None,
        explanation=explanation,
        limitations=limitations,
        provenance=provenance,
    )


def _extract_product_keys(
    transactions: Sequence[SalesTransaction | dict[str, Any]],
) -> list[ProductIdentityKey]:
    """Extract distinct products using product_id as primary key, or safe name normalization.
    
    Guarantees:
      1. If product_id is present and non-empty, (product_id, clean_name) is unique.
         Different product_ids with identical names (e.g. size/color variants) are NOT merged.
      2. If product_id is absent, clean_name is the key.
         Clean name strips leading/trailing whitespace and collapses internal multiple spaces,
         preserving letter case and distinct variant descriptors (e.g. 'Bolt 10mm' != 'Bolt 12mm').
    """
    seen_keys: dict[tuple[str | None, str], ProductIdentityKey] = {}

    for t in transactions:
        t_is_dup = getattr(t, "is_duplicate", False) if hasattr(t, "is_duplicate") else t.get("is_duplicate", False)
        if t_is_dup:
            continue

        raw_name = getattr(t, "product_name", None) if hasattr(t, "product_name") else t.get("product_name")
        clean_name = safe_normalize_product_name(raw_name)
        if not clean_name:
            continue

        raw_id = getattr(t, "product_id", None) if hasattr(t, "product_id") else t.get("product_id")
        p_id_str = str(raw_id).strip() if raw_id is not None and str(raw_id).strip() else None

        combo_key = (p_id_str, clean_name.lower())
        if combo_key not in seen_keys:
            display_label = f"{clean_name} ({p_id_str})" if p_id_str else clean_name
            seen_keys[combo_key] = ProductIdentityKey(
                product_id=p_id_str,
                product_name=clean_name,
                display_label=display_label,
            )

    return sorted(seen_keys.values(), key=lambda k: (k.product_name.lower(), k.product_id or ""))


def generate_demand_overview(
    transactions: Sequence[SalesTransaction | dict[str, Any]],
    interval: ForecastIntervalEnum = ForecastIntervalEnum.WEEKLY,
    horizon: int = 4,
) -> DemandForecastOverviewResponse:
    """Generate high-level demand forecast overview across all products for a business."""
    product_keys = _extract_product_keys(transactions)

    # Collect all business active periods across transactions to identify verified zeros vs gaps
    dates: list[datetime] = []
    business_active_periods: set[str] = set()

    for t in transactions:
        t_is_dup = getattr(t, "is_duplicate", False) if hasattr(t, "is_duplicate") else t.get("is_duplicate", False)
        if t_is_dup:
            continue
        t_date = getattr(t, "transaction_date", None) if hasattr(t, "transaction_date") else t.get("transaction_date")
        if t_date:
            dt = t_date if isinstance(t_date, datetime) else pd.to_datetime(t_date).to_pydatetime()
            dates.append(dt)
            # Grouping key
            if interval == ForecastIntervalEnum.DAILY:
                business_active_periods.add(dt.strftime("%Y-%m-%d"))
            elif interval == ForecastIntervalEnum.MONTHLY:
                business_active_periods.add(dt.strftime("%Y-%m"))
            else:
                monday = dt.date() - timedelta(days=dt.weekday())
                business_active_periods.add(monday.strftime("%Y-%m-%d"))

    if not product_keys or not dates:
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

    for p_key in product_keys:
        detail = generate_product_forecast(
            transactions,
            product_name=p_key.product_name,
            product_id=p_key.product_id,
            interval=interval,
            horizon=horizon,
            business_active_periods=business_active_periods,
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
            evaluation_stage=detail.evaluation_stage,
            best_mae=detail.provenance.get("independent_mae", best_m.mae if best_m else None),
            best_wape=detail.provenance.get("independent_wape", best_m.wape if best_m else None),
            independent_test_mae=detail.provenance.get("independent_mae"),
            independent_test_wape=detail.provenance.get("independent_wape"),
            tournament_mae=detail.provenance.get("selection_mae", best_m.mae if best_m else None),
            tournament_wape=detail.provenance.get("selection_wape", best_m.wape if best_m else None),
            range_type=detail.range_type,
            empirical_coverage_summary=detail.empirical_coverage_summary,
            empirical_coverage_pct=detail.empirical_coverage_pct,
            empirical_coverage_samples=detail.empirical_coverage_samples,
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
        total_products=len(product_keys),
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
