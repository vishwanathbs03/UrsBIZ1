"""Uncertainty Intervals & Forecast Reliability Scoring (Phase 4).

Computes empirical residual-based prediction intervals (80% bounds scaling with horizon)
and scores forecast reliability without arbitrary probability claims.
"""

from __future__ import annotations

import math
import numpy as np

from app.schemas.forecasting import ForecastReliabilityEnum


def calculate_prediction_intervals(
    y_history: np.ndarray,
    forecast_preds: np.ndarray,
    backtest_mae: float | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Calculate 80% empirical prediction intervals scaling with forecast horizon step.
    
    Uses standard error of historical differences and backtest MAE to define an empirical
    residual scale:
      Margin_h = 1.28 * s_e * sqrt(h)
    
    Guarantees that lower bound is never negative: lower >= 0.0.
    """
    h = len(forecast_preds)
    if h == 0:
        return np.array([]), np.array([])

    n = len(y_history)
    if n > 1:
        # Standard deviation of period-to-period changes
        diffs = np.diff(y_history)
        s_e = float(np.std(diffs))
        if s_e < 1e-4 and backtest_mae is not None and backtest_mae > 0:
            s_e = backtest_mae * 1.25
        elif s_e < 1e-4:
            s_e = max(0.5, float(np.mean(y_history)) * 0.15)
    else:
        s_e = max(1.0, float(forecast_preds[0]) * 0.20)

    lowers = []
    uppers = []

    for step in range(1, h + 1):
        margin = 1.28 * s_e * math.sqrt(step)
        pred_val = float(forecast_preds[step - 1])
        low = max(0.0, round(pred_val - margin, 2))
        high = max(low, round(pred_val + margin, 2))
        lowers.append(low)
        uppers.append(high)

    return np.array(lowers, dtype=np.float64), np.array(uppers, dtype=np.float64)


def evaluate_forecast_reliability(
    total_periods: int,
    sparsity_ratio: float,
    best_wape: float | None,
    best_mae: float | None,
    mean_demand: float,
) -> ForecastReliabilityEnum:
    """Classify forecast reliability based on historical data depth and holdout accuracy."""
    if total_periods < 4:
        return ForecastReliabilityEnum.INSUFFICIENT_HISTORY

    # Normalized error ratio
    error_ratio = best_wape if best_wape is not None else ((best_mae / mean_demand) if mean_demand > 0 else 1.0)

    if total_periods >= 12 and sparsity_ratio <= 0.30 and error_ratio <= 0.25:
        return ForecastReliabilityEnum.HIGH
    elif total_periods >= 6 and sparsity_ratio <= 0.50 and error_ratio <= 0.50:
        return ForecastReliabilityEnum.MEDIUM
    else:
        return ForecastReliabilityEnum.LOW
