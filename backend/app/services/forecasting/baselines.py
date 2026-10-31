"""Deterministic Baseline Forecasting Models (Phase 4).

Implements:
  1. Naive Forecast (last observed value)
  2. Simple Moving Average (configurable window, default 3)
  3. Weighted Moving Average (exponential decay / front-weighted recent window)
  4. Seasonal Naive (repeats previous seasonal cycle; strictly requires >= 2 full cycles)
"""

from __future__ import annotations

import numpy as np


def naive_forecast(y: np.ndarray, horizon: int) -> np.ndarray:
    """Predicts next `horizon` periods using the most recent observation."""
    if len(y) == 0:
        raise ValueError("Cannot compute naive forecast on empty historical series.")
    last_val = max(0.0, float(y[-1]))
    return np.full(horizon, last_val, dtype=np.float64)


def moving_average_forecast(y: np.ndarray, horizon: int, window: int = 3) -> np.ndarray:
    """Predicts next `horizon` periods using the unweighted average of the last `window` observations."""
    n = len(y)
    if n == 0:
        raise ValueError("Cannot compute moving average forecast on empty historical series.")
    effective_window = min(window, n)
    recent = y[-effective_window:]
    avg_val = max(0.0, float(np.mean(recent)))
    return np.full(horizon, round(avg_val, 4), dtype=np.float64)


def weighted_moving_average_forecast(
    y: np.ndarray, horizon: int, window: int = 3
) -> np.ndarray:
    """Predicts next `horizon` periods using front-weighted recent observations."""
    n = len(y)
    if n == 0:
        raise ValueError("Cannot compute weighted moving average on empty historical series.")
    
    k = min(window, n)
    recent = y[-k:]

    if k == 1:
        weights = np.array([1.0], dtype=np.float64)
    elif k == 2:
        weights = np.array([0.35, 0.65], dtype=np.float64)
    elif k == 3:
        weights = np.array([0.20, 0.30, 0.50], dtype=np.float64)
    else:
        # Linear ramp weights
        raw_w = np.arange(1, k + 1, dtype=np.float64)
        weights = raw_w / np.sum(raw_w)

    wma_val = max(0.0, float(np.sum(recent * weights)))
    return np.full(horizon, round(wma_val, 4), dtype=np.float64)


def seasonal_naive_forecast(
    y: np.ndarray, horizon: int, season_length: int = 4
) -> np.ndarray:
    """Predicts next `horizon` periods using the corresponding period from the prior seasonal cycle.
    
    Strictly requires at least 2 full seasonal cycles (len(y) >= 2 * season_length)
    to confirm seasonal recurrence. Raises ValueError if data is insufficient.
    """
    n = len(y)
    min_required = 2 * season_length
    if n < min_required:
        raise ValueError(
            f"Seasonal Naive requires at least {min_required} observations (2 full cycles of {season_length}), "
            f"but series only has {n} observations."
        )

    preds = []
    for step in range(horizon):
        # Look back to the corresponding point in the latest completed cycle
        offset = season_length - (step % season_length)
        source_idx = n - offset
        val = max(0.0, float(y[source_idx]))
        preds.append(val)

    return np.array(preds, dtype=np.float64)
