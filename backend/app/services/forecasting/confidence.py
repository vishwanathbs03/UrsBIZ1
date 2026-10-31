"""Uncertainty Intervals & Forecast Reliability Scoring (Phase 4 Hardening).

Defensible Prediction Range Estimation & Holdout Diagnostic Evaluation.
Avoids unverified claims of exact 80% coverage on small MSME samples;
reports actual empirical coverage with exact sample counts (e.g. '3/3 points (100.0%)').
"""

from __future__ import annotations

import math
import numpy as np

from app.schemas.forecasting import ForecastReliabilityEnum


def evaluate_holdout_interval_coverage(
    y_test: np.ndarray,
    lowers: np.ndarray,
    uppers: np.ndarray,
) -> tuple[float | None, int, int]:
    """Evaluate actual empirical coverage of prediction intervals against holdout actuals.
    
    Returns:
        (coverage_fraction, covered_count, total_count)
    """
    if len(y_test) == 0 or len(lowers) == 0 or len(uppers) == 0:
        return None, 0, 0
    n = min(len(y_test), len(lowers), len(uppers))
    if n == 0:
        return None, 0, 0
    
    actuals = y_test[:n]
    low = lowers[:n]
    up = uppers[:n]
    
    covered = (actuals >= low) & (actuals <= up)
    cov_count = int(np.sum(covered))
    return float(np.mean(covered)), cov_count, n


def calculate_prediction_intervals(
    y_history: np.ndarray,
    forecast_preds: np.ndarray,
    backtest_mae: float | None = None,
    holdout_empirical_coverage: float | None = None,
    holdout_eval_count: int = 0,
    holdout_covered_count: int = 0,
) -> tuple[np.ndarray, np.ndarray, str, float | None, str | None, str]:
    """Calculate empirical prediction range scaling with forecast horizon step.
    
    Returns:
      (lowers, uppers, range_type, empirical_coverage_pct, empirical_coverage_summary, calibration_note)
    
    Guarantees:
      1. Lower bound is non-negative: lower >= 0.0.
      2. Always labels bounds as 'Estimated Prediction Range' (never claims 3 observations are 'validated').
      3. If holdout empirical observations exist, reports exact diagnostic sample count (e.g. '100.0% (3/3 points)').
      4. Transparently documents that small sample counts are empirical checks, not large-sample calibrations.
    """
    h = len(forecast_preds)
    range_type = "Estimated Prediction Range"

    if h == 0:
        return (
            np.array([], dtype=np.float64),
            np.array([], dtype=np.float64),
            range_type,
            None,
            None,
            "No forecast periods to evaluate.",
        )

    n = len(y_history)
    if n > 1:
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

    low_arr = np.array(lowers, dtype=np.float64)
    up_arr = np.array(uppers, dtype=np.float64)

    # Assess holdout empirical coverage with transparent sample count
    if holdout_empirical_coverage is not None and holdout_eval_count > 0:
        cov_pct = round(holdout_empirical_coverage * 100.0, 1)
        cov_summary = f"{cov_pct}% ({holdout_covered_count}/{holdout_eval_count} holdout points)"
        note = (
            f"Prediction range represents an empirical estimate based on historical variance. "
            f"Observed holdout coverage: {cov_summary}. "
            f"Note: Small sample count (n={holdout_eval_count}) serves as an empirical diagnostic rather than formal statistical calibration."
        )
    else:
        cov_pct = None
        cov_summary = None
        note = (
            "Prediction range represents an empirical estimate based on historical variance. "
            f"Because historical sample size is limited ({n} periods), formal 80% coverage calibration is not claimed."
        )

    return low_arr, up_arr, range_type, cov_pct, cov_summary, note


def evaluate_forecast_reliability(
    total_periods: int,
    sparsity_ratio: float,
    best_wape: float | None,
    best_mae: float | None,
    mean_demand: float,
    unconfirmed_gaps: int = 0,
) -> ForecastReliabilityEnum:
    """Classify forecast reliability based on historical data depth and holdout accuracy."""
    if total_periods < 4:
        return ForecastReliabilityEnum.INSUFFICIENT_HISTORY

    # Normalized error ratio
    error_ratio = best_wape if best_wape is not None else ((best_mae / mean_demand) if mean_demand > 0 else 1.0)

    # If dataset has unconfirmed gaps > 20% of timeline, downgrade reliability
    if unconfirmed_gaps > 0 and (unconfirmed_gaps / total_periods) > 0.20:
        return ForecastReliabilityEnum.LOW

    if total_periods >= 12 and sparsity_ratio <= 0.30 and error_ratio <= 0.25:
        return ForecastReliabilityEnum.HIGH
    elif total_periods >= 6 and sparsity_ratio <= 0.50 and error_ratio <= 0.50:
        return ForecastReliabilityEnum.MEDIUM
    else:
        return ForecastReliabilityEnum.LOW
