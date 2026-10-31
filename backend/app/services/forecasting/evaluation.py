"""Chronological Backtesting & Forecast Evaluation Engine (Phase 4 Hardening).

Enforces strict chronological train/test splitting with zero future data leakage.
Implements:
  1. Rolling-origin backtesting (walk-forward cross-validation) for series with >= 8 periods.
  2. Fixed chronological holdout evaluation for shorter series (4-7 periods) with documented limitations.
  3. Evidence-based model selection: advanced models win only if they beat the best baseline by > 2% MAE.
  4. Empirical prediction interval coverage tracking on holdout observations.
"""

from __future__ import annotations

import math
from typing import Any, Callable
import numpy as np

from app.schemas.forecasting import BacktestMetricItem
from app.services.forecasting.baselines import (
    intermittent_expected_demand_forecast,
    moving_average_forecast,
    naive_forecast,
    seasonal_naive_forecast,
    weighted_moving_average_forecast,
)
from app.services.forecasting.confidence import (
    calculate_prediction_intervals,
    evaluate_holdout_interval_coverage,
)
from app.services.forecasting.models import (
    autoregressive_ridge_forecast,
    holt_linear_exponential_smoothing,
)


def compute_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_train: np.ndarray,
) -> dict[str, float | None]:
    """Calculate MAE, RMSE, WAPE, guarded MAPE, and MASE."""
    errors = y_true - y_pred
    abs_errors = np.abs(errors)

    mae = float(np.mean(abs_errors))
    rmse = float(np.sqrt(np.mean(errors**2)))

    # WAPE = sum(|actual - pred|) / sum(actual)
    sum_actual = float(np.sum(y_true))
    wape = round(float(np.sum(abs_errors) / sum_actual), 4) if sum_actual > 0 else None

    # Guarded MAPE: evaluate only on non-zero actuals to prevent divide-by-zero or infinity
    non_zero_mask = y_true > 0
    if np.any(non_zero_mask):
        pct_errors = abs_errors[non_zero_mask] / y_true[non_zero_mask]
        mape = round(float(np.mean(pct_errors) * 100.0), 2)
    else:
        mape = None

    # MASE: Scaled by in-sample 1-step naive error on training data
    if len(y_train) > 1:
        naive_in_sample_err = np.mean(np.abs(np.diff(y_train)))
        if naive_in_sample_err > 1e-6:
            mase = round(float(mae / naive_in_sample_err), 4)
        else:
            mase = None
    else:
        mase = None

    return {
        "mae": round(mae, 4),
        "rmse": round(rmse, 4),
        "wape": wape,
        "mape": mape,
        "mase": mase,
    }


def _get_candidate_models(
    train_size: int,
    season_length: int = 4,
    is_intermittent: bool = False,
) -> list[tuple[str, bool, Callable[[np.ndarray, int], np.ndarray]]]:
    """Return eligible candidate forecasting models based on available training depth."""
    candidates: list[tuple[str, bool, Callable[[np.ndarray, int], np.ndarray]]] = [
        ("Naive (Latest Demand)", True, lambda hist, h: naive_forecast(hist, h)),
        ("Moving Average (3-Period)", True, lambda hist, h: moving_average_forecast(hist, h, window=3)),
        ("Weighted Moving Average", True, lambda hist, h: weighted_moving_average_forecast(hist, h, window=3)),
    ]

    # Intermittent Demand Model
    if is_intermittent:
        candidates.append(
            (
                "Intermittent Rate (Expected Demand)",
                True,
                lambda hist, h: intermittent_expected_demand_forecast(hist, h),
            )
        )

    # Seasonal Naive: strictly eligible only if training series has >= 2 full seasonal cycles
    if train_size >= 2 * season_length:
        candidates.append(
            (
                f"Seasonal Naive ({season_length}-Period Cycle)",
                True,
                lambda hist, h: seasonal_naive_forecast(hist, h, season_length=season_length),
            )
        )

    # Holt Linear: eligible if train_size >= 5
    if train_size >= 5:
        candidates.append(
            (
                "Holt Linear Exponential Smoothing",
                False,
                lambda hist, h: holt_linear_exponential_smoothing(hist, h, alpha=0.3, beta=0.1, phi=0.9),
            )
        )

    # Autoregressive Ridge: eligible if train_size >= 8
    if train_size >= 8:
        candidates.append(
            (
                "Autoregressive Ridge ML",
                False,
                lambda hist, h: autoregressive_ridge_forecast(hist, h, l2_reg=1.0),
            )
        )

    return candidates


def backtest_and_select_model(
    y: np.ndarray,
    horizon: int = 4,
    season_length: int = 4,
    is_intermittent: bool = False,
) -> tuple[str, list[BacktestMetricItem], dict[str, Any]]:
    """Perform out-of-sample backtesting, evaluate all eligible models, and select best method.
    
    Uses:
      - Rolling-Origin Backtesting if len(y) >= 8.
      - Fixed Holdout Backtesting if 4 <= len(y) < 8.
    
    Returns:
      (selected_model_name, list_of_backtest_metrics, holdout_info)
    """
    n = len(y)
    if n < 4:
        return (
            "Intermittent Rate (Expected Demand)" if is_intermittent else "Moving Average (3-Period)",
            [],
            {
                "train_periods": n,
                "holdout_periods": 0,
                "split_possible": False,
                "evaluation_method": "none",
                "reason": "Insufficient history (< 4 periods) for holdout backtesting.",
            },
        )

    # -------------------------------------------------------------------------
    # Path A: Rolling-Origin Backtesting (for series with >= 8 periods)
    # -------------------------------------------------------------------------
    if n >= 8:
        # Determine number of rolling origin splits: min 2, max 4
        num_splits = min(4, n - 5)
        # Candidates eligible for the initial origin training window
        initial_train_size = n - num_splits
        candidates = _get_candidate_models(
            initial_train_size, season_length=season_length, is_intermittent=is_intermittent
        )

        model_results: dict[str, dict[str, Any]] = {}
        for name, is_baseline, _ in candidates:
            model_results[name] = {
                "is_baseline": is_baseline,
                "abs_errors": [],
                "sq_errors": [],
                "actuals": [],
                "preds": [],
                "interval_covered": [],
            }

        # Step through each rolling origin chronologically (expanding window)
        for split_idx in range(num_splits):
            origin_t = initial_train_size + split_idx
            y_train_curr = y[:origin_t]
            y_actual_step = y[origin_t]

            for name, is_baseline, func in candidates:
                try:
                    # Predict 1 step ahead with ZERO data leakage
                    pred_step = float(func(y_train_curr, 1)[0])
                    # Non-negative clamp
                    pred_step = max(0.0, pred_step)
                    
                    err = y_actual_step - pred_step
                    abs_err = abs(err)
                    
                    # Compute prediction range for coverage check
                    lows, ups, _, _, _ = calculate_prediction_intervals(
                        y_train_curr, np.array([pred_step])
                    )
                    covered = (y_actual_step >= lows[0]) and (y_actual_step <= ups[0])

                    model_results[name]["abs_errors"].append(abs_err)
                    model_results[name]["sq_errors"].append(err**2)
                    model_results[name]["actuals"].append(y_actual_step)
                    model_results[name]["preds"].append(pred_step)
                    model_results[name]["interval_covered"].append(covered)
                except Exception:
                    continue

        evaluated_metrics: list[tuple[str, bool, dict[str, float | None], float | None]] = []
        for name, data in model_results.items():
            if len(data["abs_errors"]) == num_splits:
                mae = float(np.mean(data["abs_errors"]))
                rmse = float(np.sqrt(np.mean(data["sq_errors"])))
                sum_act = float(np.sum(data["actuals"]))
                wape = round(float(np.sum(data["abs_errors"]) / sum_act), 4) if sum_act > 0 else None
                
                # Guarded MAPE
                acts = np.array(data["actuals"])
                preds = np.array(data["preds"])
                nz = acts > 0
                mape = round(float(np.mean(np.abs(acts[nz] - preds[nz]) / acts[nz]) * 100.0), 2) if np.any(nz) else None
                
                # Scaled error
                naive_in_sample = np.mean(np.abs(np.diff(y[:initial_train_size])))
                mase = round(float(mae / naive_in_sample), 4) if naive_in_sample > 1e-6 else None
                
                emp_coverage = float(np.mean(data["interval_covered"])) if data["interval_covered"] else None

                metrics_dict = {
                    "mae": round(mae, 4),
                    "rmse": round(rmse, 4),
                    "wape": wape,
                    "mape": mape,
                    "mase": mase,
                }
                evaluated_metrics.append((name, data["is_baseline"], metrics_dict, emp_coverage))

        holdout_info = {
            "evaluation_method": "rolling_origin",
            "rolling_splits_count": num_splits,
            "train_periods": initial_train_size,
            "holdout_periods": num_splits,
            "split_possible": True,
        }

    # -------------------------------------------------------------------------
    # Path B: Fixed Holdout Backtesting (for shorter series: 4 to 7 periods)
    # -------------------------------------------------------------------------
    else:
        holdout_size = max(1, min(2, int(math.ceil(n * 0.25))))
        train_size = n - holdout_size
        y_train = y[:train_size]
        y_test = y[train_size:]

        candidates = _get_candidate_models(
            train_size, season_length=season_length, is_intermittent=is_intermittent
        )

        evaluated_metrics = []
        for name, is_baseline, func in candidates:
            try:
                preds = func(y_train, holdout_size)
                preds = np.maximum(0.0, preds)
                metrics = compute_metrics(y_test, preds, y_train)

                # Check empirical coverage on holdout points
                lows, ups, _, _, _ = calculate_prediction_intervals(y_train, preds)
                emp_cov = evaluate_holdout_interval_coverage(y_test, lows, ups)

                evaluated_metrics.append((name, is_baseline, metrics, emp_cov))
            except Exception:
                continue

        holdout_info = {
            "evaluation_method": "fixed_holdout",
            "train_periods": train_size,
            "holdout_periods": holdout_size,
            "split_possible": True,
            "reason": (
                f"Historical series has {n} periods; insufficient depth for rolling-origin splits "
                "(minimum 8 periods required)."
            ),
        }

    if not evaluated_metrics:
        fallback_model = "Intermittent Rate (Expected Demand)" if is_intermittent else "Moving Average (3-Period)"
        return fallback_model, [], holdout_info

    # -------------------------------------------------------------------------
    # Baseline Superiority Selection: Advanced models win only if > 2% MAE improvement
    # -------------------------------------------------------------------------
    baseline_evals = [m for m in evaluated_metrics if m[1]]
    advanced_evals = [m for m in evaluated_metrics if not m[1]]

    best_baseline = min(baseline_evals, key=lambda x: x[2]["mae"])
    selected_name = best_baseline[0]
    best_mae = best_baseline[2]["mae"]
    selected_cov = best_baseline[3]

    if advanced_evals:
        best_advanced = min(advanced_evals, key=lambda x: x[2]["mae"])
        adv_mae = best_advanced[2]["mae"]
        # Strictly require > 2% MAE improvement over best baseline
        if adv_mae < (best_mae * 0.98):
            selected_name = best_advanced[0]
            selected_cov = best_advanced[3]

    holdout_info["empirical_coverage"] = selected_cov
    holdout_info["holdout_eval_count"] = holdout_info["holdout_periods"]

    metric_items: list[BacktestMetricItem] = [
        BacktestMetricItem(
            model_name=name,
            mae=metrics["mae"],
            rmse=metrics["rmse"],
            wape=metrics["wape"],
            mape=metrics["mape"],
            mase=metrics["mase"],
            holdout_periods=holdout_info["holdout_periods"],
            is_selected=(name == selected_name),
        )
        for name, _, metrics, _ in evaluated_metrics
    ]

    return selected_name, metric_items, holdout_info
