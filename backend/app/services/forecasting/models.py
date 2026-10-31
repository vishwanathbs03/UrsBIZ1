"""Statistical and Machine Learning Forecasting Models (Phase 4).

Implements:
  1. Holt's Linear Exponential Smoothing (level + damped trend)
  2. Autoregressive Lag-based Ridge Regression (AR-Ridge with lag-1, lag-2, rolling stats)

All models are built using pure numpy/pandas linear algebra without heavy external ML frameworks,
ensuring zero data leakage and deterministic backtesting.
"""

from __future__ import annotations

import numpy as np


def holt_linear_exponential_smoothing(
    y: np.ndarray,
    horizon: int,
    alpha: float = 0.3,
    beta: float = 0.1,
    phi: float = 0.9,
) -> np.ndarray:
    """Holt's Linear Exponential Smoothing with trend damping.
    
    Level: l_t = alpha * y_t + (1 - alpha) * (l_{t-1} + phi * b_{t-1})
    Trend: b_t = beta * (l_t - l_{t-1}) + (1 - beta) * phi * b_{t-1}
    Forecast: y_{t+h} = max(0, l_t + sum_{i=1}^h phi^i * b_t)
    
    Requires at least 5 historical observations.
    """
    n = len(y)
    if n < 5:
        raise ValueError(f"Holt's Linear Smoothing requires at least 5 observations, got {n}.")

    # Initialization
    l_t = float(y[0])
    b_t = float(y[1] - y[0])

    for t in range(1, n):
        y_val = float(y[t])
        prev_l = l_t
        prev_b = b_t

        l_t = alpha * y_val + (1.0 - alpha) * (prev_l + phi * prev_b)
        b_t = beta * (l_t - prev_l) + (1.0 - beta) * phi * prev_b

    # Generate multi-step forecasts with damped trend
    preds = []
    damped_sum = 0.0
    for h in range(1, horizon + 1):
        damped_sum += phi**h
        proj = l_t + damped_sum * b_t
        preds.append(max(0.0, round(proj, 4)))

    return np.array(preds, dtype=np.float64)


def autoregressive_ridge_forecast(
    y: np.ndarray,
    horizon: int,
    l2_reg: float = 1.0,
) -> np.ndarray:
    """Autoregressive Lag-based Ridge Regression (AR-ML).
    
    Constructs supervised lag features:
      - lag_1 (y_{t-1})
      - lag_2 (y_{t-2})
      - rolling_mean_3 (mean of last 3 periods)
      - rolling_std_3 (std of last 3 periods)
      - bias / intercept (1.0)
    
    Solves weights via closed-form regularized normal equations:
      w = (X^T X + lambda * I)^{-1} X^T y
    
    Forecasts iteratively using recursive multi-step rollout.
    Requires at least 8 historical observations to form meaningful feature rows.
    """
    n = len(y)
    min_required = 8
    if n < min_required:
        raise ValueError(
            f"Autoregressive Ridge Regression requires at least {min_required} observations, got {n}."
        )

    # Build feature matrix X and target vector targets
    # Feature window needs at least 3 lags
    X_list = []
    y_list = []

    for t in range(3, n):
        lag_1 = float(y[t - 1])
        lag_2 = float(y[t - 2])
        w3 = y[t - 3 : t]
        r_mean = float(np.mean(w3))
        r_std = float(np.std(w3))
        bias = 1.0

        X_list.append([bias, lag_1, lag_2, r_mean, r_std])
        y_list.append(float(y[t]))

    X = np.array(X_list, dtype=np.float64)
    target = np.array(y_list, dtype=np.float64)

    # Solve Ridge weights: (X^T X + alpha * I)^{-1} X^T target
    k_features = X.shape[1]
    # Do not penalize bias (index 0)
    reg_matrix = l2_reg * np.eye(k_features, dtype=np.float64)
    reg_matrix[0, 0] = 0.0

    xtx = X.T @ X + reg_matrix
    xty = X.T @ target

    try:
        weights = np.linalg.solve(xtx, xty)
    except np.linalg.LinAlgError:
        # Fallback to least squares if singular
        weights, _, _, _ = np.linalg.lstsq(xtx, xty, rcond=None)

    # Recursive multi-step rollout
    history_buf = list(y.astype(np.float64))
    preds = []

    for _ in range(horizon):
        lag_1 = history_buf[-1]
        lag_2 = history_buf[-2]
        w3 = history_buf[-3:]
        r_mean = float(np.mean(w3))
        r_std = float(np.std(w3))
        bias = 1.0

        features = np.array([bias, lag_1, lag_2, r_mean, r_std], dtype=np.float64)
        pred_val = float(features @ weights)
        pred_val = max(0.0, round(pred_val, 4))

        preds.append(pred_val)
        history_buf.append(pred_val)

    return np.array(preds, dtype=np.float64)
