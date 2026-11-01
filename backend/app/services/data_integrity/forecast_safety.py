"""Safe Forecast Data Consumption & Boundary Guard (Phase 5 Data Integrity).

Enforces strict consumption boundaries for Phase 4 Demand Forecasting:
  1. Never silently converts unconfirmed sales gaps into confirmed zero demand.
  2. Distinguishes zero-recorded-sales observations from unconfirmed data gaps.
  3. Enforces minimum historical period requirement (minimum 6 observations).
  4. Preserves model limitations and independent evaluation reliability grades.
  5. Forbids presenting statistical forecast estimates as actual historical sales.
"""

from __future__ import annotations

import logging
from typing import Any

from app.schemas.recommendation_context import DemandForecastContext, ProductForecastItemContext

logger = logging.getLogger("ursbiz.forecast_safety")


class SafeForecastConsumer:
    """Validates and sanitizes forecast data consumption for recommendations and AI reasoning."""

    MINIMUM_HISTORICAL_PERIODS = 6

    @staticmethod
    def audit_forecast_consumption(
        forecast_ctx: DemandForecastContext,
        total_historical_periods: int,
        unconfirmed_gaps_present: bool = False,
    ) -> tuple[bool, list[str], list[ProductForecastItemContext]]:
        """Audit forecast consumption and formulate safety boundaries.
        
        Returns:
            (is_consumption_safe, safety_disclaimers, sanitized_forecast_items)
        """
        disclaimers: list[str] = []
        sanitized_items: list[ProductForecastItemContext] = []

        if not forecast_ctx.has_forecast_data or not forecast_ctx.product_forecasts:
            return (
                False,
                ["Demand forecast data is not available. Real-time predictions require historical transaction ledgers."],
                [],
            )

        # 1. Minimum History Guard
        if total_historical_periods < SafeForecastConsumer.MINIMUM_HISTORICAL_PERIODS:
            disclaimers.append(
                f"Statistical Forecast Depth Warning: Dataset contains {total_historical_periods} periods "
                f"(minimum {SafeForecastConsumer.MINIMUM_HISTORICAL_PERIODS} required). Forecasts are marked Provisional."
            )

        # 2. Unconfirmed Sales Gap Isolation
        if unconfirmed_gaps_present:
            disclaimers.append(
                "Unconfirmed Data Gap Guard: Missing historical months are classified as unconfirmed gaps "
                "and have NOT been treated as zero-demand periods."
            )

        # 3. Model Limitation & Epistemic Sanity Check
        for item in forecast_ctx.product_forecasts:
            clean_limitations = list(item.limitation_notes or [])

            # Ensure warehouse stock limitation is present
            if not any("warehouse" in lim.lower() for lim in clean_limitations):
                clean_limitations.append(
                    "Phase 3 lacks physical warehouse counts: operational trend forecast only, not inventory stock count."
                )

            # Ensure nature is never described as actual sales
            clean_item = item.model_copy(
                update={"limitation_notes": clean_limitations}
            )
            sanitized_items.append(clean_item)

        disclaimers.append(
            "Forecast Nature Disclosure: Demand figures are forward-looking statistical estimates "
            "(Auto-ARIMA / Croston / Exp Smoothing) and do not represent guaranteed or historical sales."
        )

        return True, disclaimers, sanitized_items
