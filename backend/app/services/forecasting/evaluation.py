"""Chronological Backtesting & Forecast Evaluation Engine (Phase 4).

Enforces strict chronological train/test splitting with zero data leakage.
Computes MAE, RMSE, WAPE, guarded MAPE, and MASE, and performs evidence-based
model selection comparing advanced ML/statistical models against deterministic baselines.
"""

from __future__ import annotations

import math
from typing import Callable
import numpy as np

from app.schemas.forecasting import BacktestMetricItem
from app.services.forecasting.baselines import (
    moving_average_forecast,
    naive_forecast,
    seasonal_naive_forecast,
    weighted_moving_average_forecast,
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


def backtest_and_select_model(
    y: np.ndarray,
    horizon: int = 4,
    season_length: int = 4,
) -> tuple[str, list[BacktestMetricItem], dict[str, Any]]:
    """Perform chronological train/test split, evaluate all eligible models, and select best method.
    
    Returns:
      (selected_model_name, list_of_backtest_metrics, holdout_info)
    """
    n = len(y)
    if n < 4:
        # Not enough observations for holdout splitting; return default Moving Average baseline
        return (
            "Moving Average (3-Period)",
            [],
            {"train_periods": n, "holdout_periods": 0, "split_possible": False},
        )

    # Chronological holdout test size: 20-25% of data, between 1 and 4 periods
    holdout_size = max(1, min(4, int(math.ceil(n * 0.25))))
    train_size = n - holdout_size

    y_train = y[:train_size]
    y_test = y[train_size:]

    candidates: list[tuple[str, bool, Callable[[np.ndarray, int], np.ndarray]]] = [
        # (Model Name, Is Baseline, Function)
        ("Naive (Latest Demand)", True, lambda hist, h: naive_forecast(hist, h)),
        ("Moving Average (3-Period)", True, lambda hist, h: moving_average_forecast(hist, h, window=3)),
        ("Weighted Moving Average", True, lambda hist, h: weighted_moving_average_forecast(hist, h, window=3)),
    ]

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

    evaluated_metrics: list[tuple[str, bool, dict[str, float | None]]] = []

    for name, is_baseline, func in candidates:
        try:
            preds = func(y_train, holdout_size)
            metrics = compute_metrics(y_test, preds, y_train)
            evaluated_metrics.append((name, is_baseline, metrics))
        except Exception:
            continue

    if not evaluated_metrics:
        return (
            "Moving Average (3-Period)",
            [],
            {"train_periods": train_size, "holdout_periods": holdout_size, "split_possible": True},
        )

    # Find best baseline model (lowest MAE)
    baseline_evals = [m for m in evaluated_metrics if m[1]]
    advanced_evals = [m for m in evaluated_metrics if not m[1]]

    best_baseline = min(baseline_evals, key=lambda x: x[2]["mae"])
    selected_name = best_baseline[0]
    best_mae = best_baseline[2]["mae"]

    # If an advanced model outperforms the best baseline by at least 2% MAE improvement, select it
    if advanced_evals:
        best_advanced = min(advanced_evals, key=lambda x: x[2]["mae"])
        adv_mae = best_advanced[2]["mae"]
        if best_mae > 0 and adv_mae < best_mae * 0.98:
            selected_name = best_advanced[0]

    metric_items = [
        BacktestMetricItem(
            model_name=m_name,
            mae=m_data["mae"],
            rmse=m_data["rmse"],
            wape=m_data["wape"],
            mape=m_data["mape"],
            mase=m_data["mase"],
            holdout_periods=holdout_size,
            is_selected=(m_name == selected_name),
        )
        for m_name, _, m_data in evaluated_metrics
    ]

    holdout_info = {
        "train_periods": train_size,
        "holdout_periods": holdout_size,
        "split_possible": True,
        "test_actuals": [round(float(v), 2) for v in y_test],
    }

    return selected_name, metric_items, holdout_info
