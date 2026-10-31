"""Forecast Explanation Service with Gemini Grounding & Deterministic Fallback (Phase 4).

Explains verified numerical forecasts in plain business language without technical jargon.
Gemini may explain verified values but is strictly prevented from inventing forecasts.
If Gemini or network is unavailable, deterministic business rules provide instant, reliable fallbacks.
"""

from __future__ import annotations

import logging
import httpx

from app.config.settings import get_settings
from app.schemas.forecasting import ForecastExplainRequest, ForecastExplainResponse

logger = logging.getLogger(__name__)


def generate_deterministic_explanation(req: ForecastExplainRequest) -> str:
    """Generate deterministic, explainable forecast narrative directly from verified values."""
    trend_desc = {
        "Increasing": f"Demand for '{req.product_name}' is trending upward, with projected sales outpacing historical volume.",
        "Decreasing": f"Demand for '{req.product_name}' is projected to decline compared to historical baseline pace.",
        "Stable": f"Demand for '{req.product_name}' remains stable and consistent with recent sales rates.",
        "Insufficient History": f"Demand trajectory for '{req.product_name}' cannot be reliably classified due to limited history.",
    }.get(req.trend, f"Projected demand for '{req.product_name}'.")

    accuracy_part = (
        f" Selected {req.selected_model} as the optimal forecasting method based on chronological holdout backtesting (MAE: {req.best_mae})."
        if req.best_mae is not None
        else f" Projected using {req.selected_model} baseline."
    )

    reliability_part = f" Reliability is graded as '{req.reliability}'."
    if req.reliability == "High":
        reliability_part += " Strong historical data depth and low backtest error support this projection."
    elif req.reliability == "Medium":
        reliability_part += " Moderate historical data depth is available."
    elif req.reliability == "Low":
        reliability_part += " Higher variance or intermittent purchasing reduces projection certainty."

    summary = (
        f"{trend_desc} Expected sales volume is estimated at {req.forecast_units} units over the {req.forecast_horizon}."
        f"{accuracy_part}{reliability_part}"
    )

    if req.limitations:
        summary += f" Note: {req.limitations[0]}"

    return summary


def explain_forecast_narrative(req: ForecastExplainRequest) -> ForecastExplainResponse:
    """Generate forecast explanation using Gemini if configured, falling back to deterministic explanation."""
    settings = get_settings()
    deterministic_text = generate_deterministic_explanation(req)

    # If no AI API key is configured or provider is placeholder, return deterministic explanation directly
    if not settings.ai_api_key or settings.ai_provider == "placeholder":
        return ForecastExplainResponse(
            product_name=req.product_name,
            explanation=deterministic_text,
            is_ai_generated=False,
        )

    # Attempt bounded outbound call to Gemini
    try:
        system_prompt = (
            "You are an expert MSME business intelligence advisor for UrsBiz. "
            "Explain the following verified demand forecast to a small business owner in simple, clear business language. "
            "CRITICAL RULES:\n"
            "1. NEVER alter, round away, or invent any numbers or quantities. Use only the verified values supplied.\n"
            "2. Do not use complex statistical or ML jargon (e.g. do not say 'regularized loss' or 'stochastic gradient').\n"
            "3. Explicitly state the data limitations and remind the user that demand estimates do not represent production guarantees."
        )

        user_content = (
            f"Product Name: {req.product_name}\n"
            f"Historical Units Sold: {req.historical_units}\n"
            f"Forecasted Demand Units: {req.forecast_units}\n"
            f"Forecast Horizon: {req.forecast_horizon}\n"
            f"Selected Model: {req.selected_model}\n"
            f"Reliability: {req.reliability}\n"
            f"Trend: {req.trend}\n"
            f"Backtest MAE: {req.best_mae}\n"
            f"Limitations: {', '.join(req.limitations)}\n"
        )

        headers = {
            "Authorization": f"Bearer {settings.ai_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": settings.ai_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "max_tokens": 250,
            "temperature": 0.2,
        }

        url = f"{settings.ai_base_url.rstrip('/')}/chat/completions"
        with httpx.Client(timeout=8.0) as client:
            resp = client.post(url, headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"]["content"].strip()
                if content and len(content) > 20:
                    return ForecastExplainResponse(
                        product_name=req.product_name,
                        explanation=content,
                        is_ai_generated=True,
                    )
    except Exception as e:
        logger.warning(f"Gemini forecast explanation failed, using deterministic fallback: {e}")

    return ForecastExplainResponse(
        product_name=req.product_name,
        explanation=deterministic_text,
        is_ai_generated=False,
    )
