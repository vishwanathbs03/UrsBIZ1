"""Chronological Backtesting & Forecast Evaluation Engine (Phase 4 Final Hardening).

Enforces strict chronological train/test splitting with zero future data leakage.
Implements a defensible two-stage evaluation architecture:
  Stage 1: Internal Model Selection Tournament
    - Chronological rolling-origin backtesting (walk-forward CV) across expanding folds.
    - Strict > 2% MAE baseline superiority hurdle (advanced models win only if they beat the baseline).
    - Preference for simpler baselines with zero/constrained parameter capacity in ties or marginal differences.
    - All tournament metrics are explicitly tagged as model-selection diagnostics (metric_role='model_selection').

  Stage 2: Independent Final Test Holdout (when data is statistically sufficient)
    - When historical length N >= 8 + H_test (minimum 8 periods for selection + H_test for holdout):
      * The final H_test periods are completely held out as an unseen test segment (y_test = y[-H_test:]).
      * Candidate models are trained, evaluated, and selected strictly on y_selection = y[:-H_test].
      * Not a single observation from y_test is seen, used, or leaked during model selection.
      * The selected winning model and reference baseline are evaluated once on y_test.
      * Independent out-of-sample metrics (MAE, RMSE, WAPE, MAPE, MASE) are reported in independent_test_metrics.
      * Evaluation stage is set to 'independent_test_evaluated'.
    - When historical length N < 8 + H_test (short series):
      * An independent test is not fabricated.
      * Metrics are not silently reused or mislabeled as independent generalization.
      * The tournament is executed on available history to select the best model.
      * Evaluation stage is set to 'insufficient_independent_evaluation_data'.
      * Limitations transparently explain that metrics reflect internal tournament selection diagnostics.
"""

from __future__ import annotations

import math
from typing import Any, Callable
import numpy as np

from app.schemas.forecasting import BacktestMetricItem, IndependentEvaluationItem
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
) -> dict[str, Any]:
    """Calculate MAE, RMSE, WAPE, guarded MAPE, and MASE with sample size and zero-demand metadata."""
    errors = y_true - y_pred
    abs_errors = np.abs(errors)

    mae = float(np.mean(abs_errors))
    rmse = float(np.sqrt(np.mean(errors**2)))

    # Sample counts
    n_pts = len(y_true)
    non_zero_mask = y_true > 0
    n_nonzero = int(np.sum(non_zero_mask))
    n_zero = n_pts - n_nonzero

    # WAPE = sum(|actual - pred|) / sum(actual)
    sum_actual = float(np.sum(y_true))
    wape = round(float(np.sum(abs_errors) / sum_actual), 4) if sum_actual > 0 else None

    # Guarded MAPE: evaluate only on non-zero actuals to prevent divide-by-zero or infinity
    if n_nonzero > 0:
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

    # Interpretive notes for metric reliability and zero-demand caveats
    metric_notes: list[str] = []
    if sum_actual == 0:
        metric_notes.append("WAPE is undefined because total actual demand in this evaluation segment is zero.")
    if n_zero > 0:
        metric_notes.append(
            f"MAPE is evaluated on {n_nonzero}/{n_pts} positive period(s); "
            f"it does not penalize over-forecasting on the {n_zero} zero-sales period(s)."
        )
    if mase is not None:
        metric_notes.append(f"MASE is scaled by in-sample 1-step naive difference on training history (N={len(y_train)}).")
    metric_notes.append(f"Sample size: evaluated on {n_pts} period(s) (empirical check, not asymptotic validation).")

    return {
        "mae": round(mae, 4),
        "rmse": round(rmse, 4),
        "wape": wape,
        "mape": mape,
        "mase": mase,
        "test_periods": n_pts,
        "non_zero_periods": n_nonzero,
        "zero_periods": n_zero,
        "metric_notes": metric_notes,
    }


def fit_and_project(model_name: str, y: np.ndarray, horizon: int) -> np.ndarray:
    """Project future periods using the specified model on historical data."""
    if "Intermittent" in model_name:
        return intermittent_expected_demand_forecast(y, horizon)
    elif "Naive" in model_name and "Seasonal" not in model_name:
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
        return moving_average_forecast(y, horizon, window=3)


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


def run_model_selection_tournament(
    y: np.ndarray,
    horizon: int = 4,
    season_length: int = 4,
    is_intermittent: bool = False,
) -> tuple[str, str, list[BacktestMetricItem], dict[str, Any]]:
    """Execute model selection tournament on given historical series y.
    
    Evaluates candidates across chronological expanding walk-forward splits (N >= 8)
    or fixed holdout (4 <= N < 8). Advanced models win only if they beat the baseline
    by > 2% MAE.
    
    Returns:
        (selected_model_name, best_baseline_name, tournament_metric_items, tournament_info)
    """
    n = len(y)
    if n < 4:
        default_model = "Intermittent Rate (Expected Demand)" if is_intermittent else "Moving Average (3-Period)"
        return (
            default_model,
            default_model,
            [],
            {
                "train_periods": n,
                "holdout_periods": 0,
                "holdout_eval_count": 0,
                "holdout_covered_count": 0,
                "split_possible": False,
                "evaluation_method": "none",
                "selection_mae": None,
                "selection_wape": None,
                "reason": "Insufficient history (< 4 periods) for holdout backtesting.",
            },
        )

    # Path A: Rolling-Origin Backtesting (for series with >= 8 periods)
    if n >= 8:
        num_splits = min(4, n - 5)
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

        expected_eval_points = 0
        for split_idx in range(num_splits):
            origin_t = initial_train_size + split_idx
            y_train_curr = y[:origin_t]

            eval_h = min(horizon, n - origin_t)
            if eval_h < 1:
                break
            expected_eval_points += eval_h
            y_actual_trajectory = y[origin_t : origin_t + eval_h]

            for name, is_baseline, func in candidates:
                try:
                    preds_h = np.maximum(0.0, np.array(func(y_train_curr, eval_h), dtype=float))
                    errs = y_actual_trajectory - preds_h
                    abs_errs = np.abs(errs)

                    lows, ups, _, _, _, _ = calculate_prediction_intervals(
                        y_train_curr, preds_h
                    )
                    covered = (y_actual_trajectory >= lows) & (y_actual_trajectory <= ups)

                    model_results[name]["abs_errors"].extend(abs_errs.tolist())
                    model_results[name]["sq_errors"].extend((errs**2).tolist())
                    model_results[name]["actuals"].extend(y_actual_trajectory.tolist())
                    model_results[name]["preds"].extend(preds_h.tolist())
                    model_results[name]["interval_covered"].extend(covered.tolist())
                except Exception:
                    continue

        evaluated_metrics: list[tuple[str, bool, dict[str, float | None], float | None, int, int]] = []
        for name, data in model_results.items():
            if len(data["abs_errors"]) == expected_eval_points:
                mae = float(np.mean(data["abs_errors"]))
                rmse = float(np.sqrt(np.mean(data["sq_errors"])))
                sum_act = float(np.sum(data["actuals"]))
                wape = round(float(np.sum(data["abs_errors"]) / sum_act), 4) if sum_act > 0 else None

                acts = np.array(data["actuals"])
                preds = np.array(data["preds"])
                nz = acts > 0
                mape = round(float(np.mean(np.abs(acts[nz] - preds[nz]) / acts[nz]) * 100.0), 2) if np.any(nz) else None

                naive_in_sample = np.mean(np.abs(np.diff(y[:initial_train_size])))
                mase = round(float(mae / naive_in_sample), 4) if naive_in_sample > 1e-6 else None

                cov_count = sum(1 for c in data["interval_covered"] if c)
                total_count = len(data["interval_covered"])
                emp_coverage = float(cov_count / total_count) if total_count > 0 else None

                metrics_dict = {
                    "mae": round(mae, 4),
                    "rmse": round(rmse, 4),
                    "wape": wape,
                    "mape": mape,
                    "mase": mase,
                }
                evaluated_metrics.append((name, data["is_baseline"], metrics_dict, emp_coverage, cov_count, total_count))

        tourn_info = {
            "evaluation_method": "rolling_origin",
            "rolling_splits_count": num_splits,
            "train_periods": initial_train_size,
            "holdout_periods": expected_eval_points,
            "holdout_eval_count": expected_eval_points,
            "split_possible": True,
        }

    # Path B: Fixed Holdout Backtesting (for shorter series: 4 to 7 periods)
    else:
        holdout_size = max(1, min(2, int(math.ceil(n * 0.25))))
        train_size = n - holdout_size
        y_train = y[:train_size]
        eval_h = min(horizon, holdout_size)
        y_test = y[train_size : train_size + eval_h]

        candidates = _get_candidate_models(
            train_size, season_length=season_length, is_intermittent=is_intermittent
        )

        evaluated_metrics = []
        for name, is_baseline, func in candidates:
            try:
                preds = np.maximum(0.0, np.array(func(y_train, eval_h), dtype=float))
                metrics = compute_metrics(y_test, preds, y_train)

                lows, ups, _, _, _, _ = calculate_prediction_intervals(y_train, preds)
                emp_cov, cov_count, total_count = evaluate_holdout_interval_coverage(y_test, lows, ups)

                evaluated_metrics.append((name, is_baseline, metrics, emp_cov, cov_count, total_count))
            except Exception:
                continue

        tourn_info = {
            "evaluation_method": "fixed_holdout",
            "train_periods": train_size,
            "holdout_periods": eval_h,
            "holdout_eval_count": len(y_test),
            "split_possible": True,
            "reason": (
                f"Historical series has {n} periods; insufficient depth for rolling-origin splits "
                "(minimum 8 periods required)."
            ),
        }

    if not evaluated_metrics:
        fallback_model = "Intermittent Rate (Expected Demand)" if is_intermittent else "Moving Average (3-Period)"
        tourn_info["holdout_eval_count"] = 0
        tourn_info["holdout_covered_count"] = 0
        tourn_info["empirical_coverage"] = None
        tourn_info["selection_mae"] = None
        tourn_info["selection_wape"] = None
        return fallback_model, fallback_model, [], tourn_info

    # Identify standard general-purpose reference baselines (used for fair baseline comparison)
    standard_baseline_names = {
        "Naive (Latest Demand)",
        "Moving Average (3-Period)",
        "Weighted Moving Average",
    }
    standard_evals = [m for m in evaluated_metrics if m[0] in standard_baseline_names]
    best_standard = min(standard_evals, key=lambda x: x[2]["mae"]) if standard_evals else min(evaluated_metrics, key=lambda x: x[2]["mae"])
    best_standard_name = best_standard[0]

    # Baseline pool for standard time series (excluding intermittent rate so intermittent rate has a separate reference baseline)
    baseline_evals = [m for m in evaluated_metrics if m[1] and m[0] != "Intermittent Rate (Expected Demand)"]
    if not baseline_evals:
        baseline_evals = [best_standard]

    best_baseline = min(baseline_evals, key=lambda x: x[2]["mae"])
    best_baseline_name = best_baseline[0]
    selected_name = best_baseline_name
    best_mae = best_baseline[2]["mae"]
    best_wape = best_baseline[2]["wape"]
    selected_cov = best_baseline[3]
    selected_cov_count = best_baseline[4]
    selected_total_count = best_baseline[5]

    # Evaluate Intermittent Demand model if present (selected if it beats the standard baseline)
    intermittent_evals = [m for m in evaluated_metrics if m[0] == "Intermittent Rate (Expected Demand)"]
    if intermittent_evals:
        interm = intermittent_evals[0]
        interm_mae = interm[2]["mae"]
        if interm_mae < best_mae:
            selected_name = interm[0]
            best_mae = interm_mae
            best_wape = interm[2]["wape"]
            selected_cov = interm[3]
            selected_cov_count = interm[4]
            selected_total_count = interm[5]

    # Evaluate Advanced ML / Smoothing models (must beat baseline hurdle by > 2% MAE)
    advanced_evals = [m for m in evaluated_metrics if not m[1]]
    if advanced_evals:
        best_advanced = min(advanced_evals, key=lambda x: x[2]["mae"])
        adv_mae = best_advanced[2]["mae"]
        if adv_mae < (best_mae * 0.98):
            selected_name = best_advanced[0]
            best_mae = adv_mae
            best_wape = best_advanced[2]["wape"]
            selected_cov = best_advanced[3]
            selected_cov_count = best_advanced[4]
            selected_total_count = best_advanced[5]

    tourn_info["empirical_coverage"] = selected_cov
    tourn_info["holdout_covered_count"] = selected_cov_count
    tourn_info["holdout_eval_count"] = selected_total_count
    tourn_info["selection_mae"] = best_mae
    tourn_info["selection_wape"] = best_wape

    metric_items: list[BacktestMetricItem] = [
        BacktestMetricItem(
            model_name=name,
            mae=metrics["mae"],
            rmse=metrics["rmse"],
            wape=metrics["wape"],
            mape=metrics["mape"],
            mase=metrics["mase"],
            holdout_periods=total_cnt,
            is_selected=(name == selected_name),
            metric_role="model_selection",
        )
        for name, _, metrics, _, _, total_cnt in evaluated_metrics
    ]

    return selected_name, best_baseline_name, metric_items, tourn_info


def backtest_and_select_model(
    y: np.ndarray,
    horizon: int = 4,
    season_length: int = 4,
    is_intermittent: bool = False,
) -> tuple[str, list[BacktestMetricItem], dict[str, Any]]:
    """Execute defensible two-stage model selection and independent final evaluation.
    
    Architecture:
      Stage 1: Internal Model Selection Tournament
        - If N >= 8 + H_test: Candidate models are evaluated and selected strictly
          on y_selection = y[:-H_test]. y_test is completely held out with ZERO data leakage.
        - If N < 8 + H_test: Tournament evaluates candidates on full y as model-selection diagnostics.
      Stage 2: Independent Final Evaluation
        - If N >= 8 + H_test: The selected model and reference baseline are evaluated once on y_test.
          Results reported in holdout_info['independent_test_metrics'].
        - If N < 8 + H_test: Returns evaluation_stage='insufficient_independent_evaluation_data'.
    
    Returns:
      (selected_model_name, list_of_tournament_metrics, holdout_info)
    """
    n = len(y)
    if n < 4:
        fallback_model = "Intermittent Rate (Expected Demand)" if is_intermittent else "Moving Average (3-Period)"
        return (
            fallback_model,
            [],
            {
                "train_periods": n,
                "holdout_periods": 0,
                "holdout_eval_count": 0,
                "holdout_covered_count": 0,
                "split_possible": False,
                "evaluation_method": "none",
                "evaluation_stage": "insufficient_data",
                "is_independent_evaluation": False,
                "independent_test_metrics": None,
                "independent_mae": None,
                "independent_wape": None,
                "selection_mae": None,
                "selection_wape": None,
                "reason": "Insufficient history (< 4 periods) for holdout backtesting.",
            },
        )

    # Required independent holdout test horizon (matches forecast horizon, capped at 4)
    h_test = min(horizon, 4)
    min_periods_for_independent_test = 8 + h_test

    # -------------------------------------------------------------------------
    # Case 1: Series has sufficient history for separate final holdout test
    # (N >= 8 + H_test: e.g. >= 12 periods for H=4, >= 10 periods for H=2)
    # -------------------------------------------------------------------------
    if n >= min_periods_for_independent_test:
        y_selection = y[:-h_test]
        y_test = y[-h_test:]

        # Preprocessing & intermittency flag fitted STRICTLY on y_selection (zero leakage)
        is_intermittent_sel = bool(np.mean(y_selection <= 0.0) > 0.70) if len(y_selection) > 0 else is_intermittent

        # Stage 1: Run tournament STRICTLY on y_selection (zero knowledge of y_test)
        selected_model, best_baseline, tournament_metrics, tourn_info = run_model_selection_tournament(
            y_selection,
            horizon=h_test,
            season_length=season_length,
            is_intermittent=is_intermittent_sel,
        )

        # Stage 2: Independent Final Evaluation on y_test (trained on y_selection)
        # Guarantee a standard reference benchmark for side-by-side comparison on y_test
        ref_baseline = best_baseline
        if ref_baseline == selected_model:
            alt_candidates = ["Moving Average (3-Period)", "Naive (Latest Demand)", "Weighted Moving Average"]
            for alt in alt_candidates:
                if alt != selected_model:
                    ref_baseline = alt
                    break

        pred_selected = np.maximum(0.0, fit_and_project(selected_model, y_selection, h_test))
        pred_baseline = np.maximum(0.0, fit_and_project(ref_baseline, y_selection, h_test))

        metrics_selected = compute_metrics(y_test, pred_selected, y_selection)
        metrics_baseline = compute_metrics(y_test, pred_baseline, y_selection)

        # Prediction interval coverage on unseen test segment
        lows_indep, ups_indep, _, _, _, _ = calculate_prediction_intervals(y_selection, pred_selected)
        covered_indep = (y_test >= lows_indep) & (y_test <= ups_indep)
        cov_count_indep = int(np.sum(covered_indep))
        emp_cov_indep = float(cov_count_indep / len(y_test))

        indep_items = [
            IndependentEvaluationItem(
                model_name=selected_model,
                mae=metrics_selected["mae"],
                rmse=metrics_selected["rmse"],
                wape=metrics_selected["wape"],
                mape=metrics_selected["mape"],
                mase=metrics_selected["mase"],
                test_periods=len(y_test),
                non_zero_periods=metrics_selected.get("non_zero_periods", len(y_test)),
                zero_periods=metrics_selected.get("zero_periods", 0),
                is_baseline=(selected_model == ref_baseline),
                is_selected=True,
                metric_notes=metrics_selected.get("metric_notes", []),
            )
        ]
        if selected_model != ref_baseline:
            indep_items.append(
                IndependentEvaluationItem(
                    model_name=ref_baseline,
                    mae=metrics_baseline["mae"],
                    rmse=metrics_baseline["rmse"],
                    wape=metrics_baseline["wape"],
                    mape=metrics_baseline["mape"],
                    mase=metrics_baseline["mase"],
                    test_periods=len(y_test),
                    non_zero_periods=metrics_baseline.get("non_zero_periods", len(y_test)),
                    zero_periods=metrics_baseline.get("zero_periods", 0),
                    is_baseline=True,
                    is_selected=False,
                    metric_notes=metrics_baseline.get("metric_notes", []),
                )
            )

        holdout_info = {
            "evaluation_stage": "independent_test_evaluated",
            "is_independent_evaluation": True,
            "evaluation_method": tourn_info.get("evaluation_method", "rolling_origin"),
            "rolling_splits_count": tourn_info.get("rolling_splits_count", 0),
            "train_periods": len(y_selection),
            "selection_periods": len(y_selection),
            "final_test_size": len(y_test),
            "holdout_periods": len(y_test),
            "holdout_eval_count": len(y_test),
            "holdout_covered_count": cov_count_indep,
            "empirical_coverage": emp_cov_indep,
            "split_possible": True,
            "independent_test_metrics": indep_items,
            "independent_mae": metrics_selected["mae"],
            "independent_wape": metrics_selected["wape"],
            "selection_mae": tourn_info.get("selection_mae"),
            "selection_wape": tourn_info.get("selection_wape"),
            "best_baseline": ref_baseline,
            "required_periods": min_periods_for_independent_test,
        }

        return selected_model, tournament_metrics, holdout_info

    # -------------------------------------------------------------------------
    # Case 2: Series is too short for separate final test holdout (4 <= N < 8 + H_test)
    # (Do not fabricate an independent evaluation; report tournament diagnostics)
    # -------------------------------------------------------------------------
    else:
        is_intermittent_full = bool(np.mean(y <= 0.0) > 0.70) if len(y) > 0 else is_intermittent
        selected_model, best_baseline, tournament_metrics, tourn_info = run_model_selection_tournament(
            y,
            horizon=horizon,
            season_length=season_length,
            is_intermittent=is_intermittent_full,
        )

        holdout_info = dict(tourn_info)
        holdout_info["evaluation_stage"] = "insufficient_independent_evaluation_data"
        holdout_info["is_independent_evaluation"] = False
        holdout_info["independent_test_metrics"] = None
        holdout_info["independent_mae"] = None
        holdout_info["independent_wape"] = None
        holdout_info["selection_mae"] = tourn_info.get("selection_mae")
        holdout_info["selection_wape"] = tourn_info.get("selection_wape")
        holdout_info["best_baseline"] = best_baseline
        holdout_info["required_periods"] = min_periods_for_independent_test
        holdout_info["reason"] = (
            f"Historical series has {n} periods; insufficient history for a separate independent test segment "
            f"(requires at least {min_periods_for_independent_test} periods: 8 for rolling-origin model selection + "
            f"{h_test} for separate final holdout). Reported metrics represent internal model-selection "
            "tournament diagnostics only."
        )

        return selected_model, tournament_metrics, holdout_info
