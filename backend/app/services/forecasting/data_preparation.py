"""Data Preparation & Regular Time Series Grid Pipeline (Phase 4).

Transforms raw, normalized sales transactions into regular product-level demand series
with explicit zero-demand handling and data limitation detection.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Sequence
import numpy as np
import pandas as pd

from app.models.sales import SalesTransaction
from app.schemas.forecasting import DataLimitationStatusEnum, ForecastIntervalEnum


@dataclass
class PreparedPeriod:
    """A regular calendar period observation."""
    period_index: int
    period_label: str
    period_start: str  # YYYY-MM-DD
    period_end: str    # YYYY-MM-DD
    quantity: float
    has_data: bool


@dataclass
class PreparedProductSeries:
    """Structured demand series for a single product."""
    product_name: str
    product_id: str | None
    interval: ForecastIntervalEnum
    periods: list[PreparedPeriod]
    quantities: np.ndarray  # 1D array of float64 quantities
    total_periods: int
    active_periods: int
    total_quantity: float
    sparsity_ratio: float
    status: DataLimitationStatusEnum
    limitation_notes: list[str]


def prepare_product_demand_series(
    transactions: Sequence[SalesTransaction | dict[str, Any]],
    product_name: str,
    interval: ForecastIntervalEnum = ForecastIntervalEnum.WEEKLY,
) -> PreparedProductSeries:
    """Filter non-duplicate transactions for a product and resample into a regular calendar grid.
    
    Ensures that periods without sales are explicitly recognized as zero-demand observations
    without silently dropping them or corrupting chronological sequence.
    """
    notes: list[str] = []

    # 1. Filter transactions for the requested product (case-insensitive) and non-duplicate
    matching_rows: list[dict[str, Any]] = []
    p_name_lower = product_name.strip().lower()
    p_id: str | None = None

    for t in transactions:
        t_is_dup = getattr(t, "is_duplicate", False) if hasattr(t, "is_duplicate") else t.get("is_duplicate", False)
        if t_is_dup:
            continue

        t_p_name = getattr(t, "product_name", "") if hasattr(t, "product_name") else t.get("product_name", "")
        if (t_p_name or "").strip().lower() != p_name_lower:
            continue

        t_date = getattr(t, "transaction_date", None) if hasattr(t, "transaction_date") else t.get("transaction_date")
        t_qty = getattr(t, "quantity", 0.0) if hasattr(t, "quantity") else t.get("quantity", 0.0)
        curr_p_id = getattr(t, "product_id", None) if hasattr(t, "product_id") else t.get("product_id")
        if curr_p_id and not p_id:
            p_id = str(curr_p_id)

        if t_date is not None and t_qty is not None and float(t_qty) > 0:
            # Ensure datetime is timezone-aware UTC
            if isinstance(t_date, str):
                dt = pd.to_datetime(t_date).to_pydatetime()
            else:
                dt = t_date
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            matching_rows.append({"date": dt, "quantity": float(t_qty)})

    if not matching_rows:
        return PreparedProductSeries(
            product_name=product_name,
            product_id=p_id,
            interval=interval,
            periods=[],
            quantities=np.array([], dtype=np.float64),
            total_periods=0,
            active_periods=0,
            total_quantity=0.0,
            sparsity_ratio=1.0,
            status=DataLimitationStatusEnum.NO_SALES_HISTORY,
            limitation_notes=["No valid, non-duplicate sales transactions recorded for this product."],
        )

    df = pd.DataFrame(matching_rows)
    df = df.sort_values("date")

    min_date = df["date"].min()
    max_date = df["date"].max()

    # 2. Resample onto regular grid
    periods_list: list[PreparedPeriod] = []

    if interval == ForecastIntervalEnum.DAILY:
        # Group by calendar day
        df["period_key"] = df["date"].dt.strftime("%Y-%m-%d")
        daily_grouped = df.groupby("period_key")["quantity"].sum().to_dict()

        curr = min_date.date()
        end_d = max_date.date()
        idx = 0
        while curr <= end_d:
            key = curr.strftime("%Y-%m-%d")
            qty = daily_grouped.get(key, 0.0)
            has_data = key in daily_grouped
            periods_list.append(
                PreparedPeriod(
                    period_index=idx,
                    period_label=key,
                    period_start=key,
                    period_end=key,
                    quantity=round(float(qty), 4),
                    has_data=has_data,
                )
            )
            curr += timedelta(days=1)
            idx += 1

    elif interval == ForecastIntervalEnum.MONTHLY:
        # Group by calendar month YYYY-MM
        df["period_key"] = df["date"].dt.strftime("%Y-%m")
        monthly_grouped = df.groupby("period_key")["quantity"].sum().to_dict()

        # Build contiguous list of months
        start_year, start_month = min_date.year, min_date.month
        end_year, end_month = max_date.year, max_date.month

        curr_y, curr_m = start_year, start_month
        idx = 0
        while (curr_y < end_year) or (curr_y == end_year and curr_m <= end_month):
            key = f"{curr_y:04d}-{curr_m:02d}"
            qty = monthly_grouped.get(key, 0.0)
            has_data = key in monthly_grouped
            
            # Start and end date for the month
            start_str = f"{key}-01"
            # Calculate next month minus one day
            next_m = curr_m + 1 if curr_m < 12 else 1
            next_y = curr_y if curr_m < 12 else curr_y + 1
            last_day = (datetime(next_y, next_m, 1) - timedelta(days=1)).day
            end_str = f"{key}-{last_day:02d}"

            periods_list.append(
                PreparedPeriod(
                    period_index=idx,
                    period_label=key,
                    period_start=start_str,
                    period_end=end_str,
                    quantity=round(float(qty), 4),
                    has_data=has_data,
                )
            )

            if curr_m == 12:
                curr_y += 1
                curr_m = 1
            else:
                curr_m += 1
            idx += 1

    else:
        # WEEKLY (default standard for inventory demand planning)
        # Anchor each week to Monday
        def to_monday(dt: datetime) -> datetime:
            return dt - timedelta(days=dt.weekday())

        start_mon = to_monday(min_date).date()
        end_mon = to_monday(max_date).date()

        # Map each transaction date to its Monday week key
        df["week_start"] = df["date"].apply(lambda d: to_monday(d).strftime("%Y-%m-%d"))
        weekly_grouped = df.groupby("week_start")["quantity"].sum().to_dict()

        curr_mon = start_mon
        idx = 0
        while curr_mon <= end_mon:
            w_start_str = curr_mon.strftime("%Y-%m-%d")
            w_end_str = (curr_mon + timedelta(days=6)).strftime("%Y-%m-%d")
            # ISO year and week number
            iso_year, iso_week, _ = curr_mon.isocalendar()
            label = f"{iso_year}-W{iso_week:02d}"

            qty = weekly_grouped.get(w_start_str, 0.0)
            has_data = w_start_str in weekly_grouped

            periods_list.append(
                PreparedPeriod(
                    period_index=idx,
                    period_label=label,
                    period_start=w_start_str,
                    period_end=w_end_str,
                    quantity=round(float(qty), 4),
                    has_data=has_data,
                )
            )
            curr_mon += timedelta(days=7)
            idx += 1

    total_periods = len(periods_list)
    active_periods = sum(1 for p in periods_list if p.quantity > 0)
    zero_periods = total_periods - active_periods
    sparsity = (zero_periods / total_periods) if total_periods > 0 else 1.0
    total_qty = sum(p.quantity for p in periods_list)
    quantities = np.array([p.quantity for p in periods_list], dtype=np.float64)

    # 3. Assess data limitations
    if total_periods < 4 or active_periods < 2:
        status = DataLimitationStatusEnum.INSUFFICIENT_HISTORY
        notes.append(
            f"Product has only {total_periods} historical {interval.value} periods ({active_periods} with sales). "
            "At least 4 regular periods are required to compute reliable demand forecasts."
        )
    elif sparsity > 0.70:
        status = DataLimitationStatusEnum.INTERMITTENT_DEMAND
        notes.append(
            f"Demand is highly intermittent ({round(sparsity * 100, 1)}% zero-sales periods). "
            "Forecast uncertainty is elevated due to irregular purchase intervals."
        )
    else:
        status = DataLimitationStatusEnum.FORECAST_AVAILABLE

    return PreparedProductSeries(
        product_name=product_name,
        product_id=p_id,
        interval=interval,
        periods=periods_list,
        quantities=quantities,
        total_periods=total_periods,
        active_periods=active_periods,
        total_quantity=round(total_qty, 2),
        sparsity_ratio=round(sparsity, 3),
        status=status,
        limitation_notes=notes,
    )
