"""Data Preparation & Regular Time Series Grid Pipeline (Phase 4 Hardening).

Transforms raw sales transactions into regular product-level demand series
with explicit separation of confirmed zero-demand vs. unconfirmed gaps,
safe product name normalization, and primary product_id key routing.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import re
from typing import Any, Sequence
import numpy as np
import pandas as pd

from app.models.sales import SalesTransaction
from app.schemas.forecasting import DataLimitationStatusEnum, ForecastIntervalEnum


def safe_normalize_product_name(name: str | None) -> str:
    """Safely normalize product names: collapse internal multiple whitespace, trim ends.
    
    Preserves case and variant specifiers (e.g. 'Bearing 6200' vs 'Bearing 6201')
    to prevent accidental merging of distinct product SKUs.
    """
    if not name:
        return ""
    # Collapse multiple whitespace to single space, trim edges
    cleaned = re.sub(r"\s+", " ", str(name).strip())
    return cleaned


@dataclass
class PreparedPeriod:
    """A regular calendar period observation with explicit coverage classification."""
    period_index: int
    period_label: str
    period_start: str  # YYYY-MM-DD
    period_end: str    # YYYY-MM-DD
    quantity: float
    has_data: bool
    coverage_status: str  # "active", "confirmed_zero", or "unconfirmed_gap"


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
    confirmed_zeros_count: int
    unconfirmed_gaps_count: int
    total_quantity: float
    sparsity_ratio: float
    status: DataLimitationStatusEnum
    limitation_notes: list[str]


def _extract_period_key(dt: datetime, interval: ForecastIntervalEnum) -> str:
    """Return grouping key for a given datetime and interval."""
    if interval == ForecastIntervalEnum.DAILY:
        return dt.strftime("%Y-%m-%d")
    elif interval == ForecastIntervalEnum.MONTHLY:
        return dt.strftime("%Y-%m")
    else:
        # Weekly: anchor to Monday
        monday = dt.date() - timedelta(days=dt.weekday())
        return monday.strftime("%Y-%m-%d")


def prepare_product_demand_series(
    transactions: Sequence[SalesTransaction | dict[str, Any]],
    product_name: str,
    product_id: str | None = None,
    interval: ForecastIntervalEnum = ForecastIntervalEnum.WEEKLY,
    business_active_periods: set[str] | None = None,
) -> PreparedProductSeries:
    """Filter non-duplicate transactions for a product and resample into a regular calendar grid.
    
    Hardened for Data Integrity:
    1. Uses product_id as primary grouping key when available.
    2. Uses safe normalization when grouping by product_name, preventing merging of distinct variants.
    3. Differentiates between 'confirmed_zero' (business sold other SKUs) and 'unconfirmed_gap'
       (no sales recorded anywhere in business) rather than assuming all missing points are verified zeroes.
    """
    notes: list[str] = []
    clean_target_name = safe_normalize_product_name(product_name)
    target_id_str = str(product_id).strip() if product_id is not None and str(product_id).strip() else None

    # Determine business-wide active periods if not provided
    inferred_business_active_periods: set[str] = set()
    if business_active_periods is None:
        for t in transactions:
            t_is_dup = getattr(t, "is_duplicate", False) if hasattr(t, "is_duplicate") else t.get("is_duplicate", False)
            if t_is_dup:
                continue
            t_date = getattr(t, "transaction_date", None) if hasattr(t, "transaction_date") else t.get("transaction_date")
            if t_date:
                dt = t_date if isinstance(t_date, datetime) else pd.to_datetime(t_date).to_pydatetime()
                inferred_business_active_periods.add(_extract_period_key(dt, interval))
        active_periods_lookup = inferred_business_active_periods
    else:
        active_periods_lookup = business_active_periods

    # 1. Filter matching transactions
    matching_rows: list[dict[str, Any]] = []
    resolved_product_id: str | None = target_id_str

    for t in transactions:
        t_is_dup = getattr(t, "is_duplicate", False) if hasattr(t, "is_duplicate") else t.get("is_duplicate", False)
        if t_is_dup:
            continue

        curr_p_id = getattr(t, "product_id", None) if hasattr(t, "product_id") else t.get("product_id")
        curr_p_id_str = str(curr_p_id).strip() if curr_p_id is not None and str(curr_p_id).strip() else None

        t_p_name = getattr(t, "product_name", "") if hasattr(t, "product_name") else t.get("product_name", "")
        clean_row_p_name = safe_normalize_product_name(t_p_name)

        # Match logic:
        # If target_id_str is specified, must match product_id strictly
        if target_id_str:
            if curr_p_id_str != target_id_str:
                continue
        else:
            # Match by normalized product name (case-insensitive)
            if clean_row_p_name.lower() != clean_target_name.lower():
                continue

        if curr_p_id_str and not resolved_product_id:
            resolved_product_id = curr_p_id_str

        t_date = getattr(t, "transaction_date", None) if hasattr(t, "transaction_date") else t.get("transaction_date")
        t_qty = getattr(t, "quantity", 0.0) if hasattr(t, "quantity") else t.get("quantity", 0.0)

        if t_date is not None and t_qty is not None and float(t_qty) > 0:
            if isinstance(t_date, str):
                dt = pd.to_datetime(t_date).to_pydatetime()
            else:
                dt = t_date
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            matching_rows.append({"date": dt, "quantity": float(t_qty)})

    if not matching_rows:
        return PreparedProductSeries(
            product_name=clean_target_name,
            product_id=resolved_product_id,
            interval=interval,
            periods=[],
            quantities=np.array([], dtype=np.float64),
            total_periods=0,
            active_periods=0,
            confirmed_zeros_count=0,
            unconfirmed_gaps_count=0,
            total_quantity=0.0,
            sparsity_ratio=1.0,
            status=DataLimitationStatusEnum.NO_SALES_HISTORY,
            limitation_notes=["No valid, non-duplicate sales transactions recorded for this product SKU."],
        )

    df = pd.DataFrame(matching_rows)
    df = df.sort_values("date")

    min_date = df["date"].min()
    max_date = df["date"].max()

    # 2. Resample onto regular grid with coverage classification
    periods_list: list[PreparedPeriod] = []

    if interval == ForecastIntervalEnum.DAILY:
        df["period_key"] = df["date"].dt.strftime("%Y-%m-%d")
        daily_grouped = df.groupby("period_key")["quantity"].sum().to_dict()

        curr = min_date.date()
        end_d = max_date.date()
        idx = 0
        while curr <= end_d:
            key = curr.strftime("%Y-%m-%d")
            qty = daily_grouped.get(key, 0.0)
            has_data = key in daily_grouped
            
            if has_data:
                cov_status = "active"
            elif key in active_periods_lookup:
                cov_status = "confirmed_zero"
            else:
                cov_status = "unconfirmed_gap"

            periods_list.append(
                PreparedPeriod(
                    period_index=idx,
                    period_label=key,
                    period_start=key,
                    period_end=key,
                    quantity=round(float(qty), 4),
                    has_data=has_data,
                    coverage_status=cov_status,
                )
            )
            curr += timedelta(days=1)
            idx += 1

    elif interval == ForecastIntervalEnum.MONTHLY:
        df["period_key"] = df["date"].dt.strftime("%Y-%m")
        monthly_grouped = df.groupby("period_key")["quantity"].sum().to_dict()

        start_year, start_month = min_date.year, min_date.month
        end_year, end_month = max_date.year, max_date.month

        curr_y, curr_m = start_year, start_month
        idx = 0
        while (curr_y < end_year) or (curr_y == end_year and curr_m <= end_month):
            key = f"{curr_y:04d}-{curr_m:02d}"
            qty = monthly_grouped.get(key, 0.0)
            has_data = key in monthly_grouped

            if has_data:
                cov_status = "active"
            elif key in active_periods_lookup:
                cov_status = "confirmed_zero"
            else:
                cov_status = "unconfirmed_gap"

            start_str = f"{key}-01"
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
                    coverage_status=cov_status,
                )
            )

            if curr_m == 12:
                curr_y += 1
                curr_m = 1
            else:
                curr_m += 1
            idx += 1

    else:
        # WEEKLY (default standard for demand planning)
        def to_monday(dt: datetime) -> datetime:
            return dt - timedelta(days=dt.weekday())

        start_mon = to_monday(min_date).date()
        end_mon = to_monday(max_date).date()

        df["week_start"] = df["date"].apply(lambda d: to_monday(d).strftime("%Y-%m-%d"))
        weekly_grouped = df.groupby("week_start")["quantity"].sum().to_dict()

        curr_mon = start_mon
        idx = 0
        while curr_mon <= end_mon:
            w_start_str = curr_mon.strftime("%Y-%m-%d")
            w_end_str = (curr_mon + timedelta(days=6)).strftime("%Y-%m-%d")
            iso_year, iso_week, _ = curr_mon.isocalendar()
            label = f"{iso_year}-W{iso_week:02d}"

            qty = weekly_grouped.get(w_start_str, 0.0)
            has_data = w_start_str in weekly_grouped

            if has_data:
                cov_status = "active"
            elif w_start_str in active_periods_lookup:
                cov_status = "confirmed_zero"
            else:
                cov_status = "unconfirmed_gap"

            periods_list.append(
                PreparedPeriod(
                    period_index=idx,
                    period_label=label,
                    period_start=w_start_str,
                    period_end=w_end_str,
                    quantity=round(float(qty), 4),
                    has_data=has_data,
                    coverage_status=cov_status,
                )
            )
            curr_mon += timedelta(days=7)
            idx += 1

    total_periods = len(periods_list)
    active_periods = sum(1 for p in periods_list if p.has_data and p.quantity > 0)
    confirmed_zeros = sum(1 for p in periods_list if p.coverage_status == "confirmed_zero")
    unconfirmed_gaps = sum(1 for p in periods_list if p.coverage_status == "unconfirmed_gap")
    
    total_zero_or_gap = total_periods - active_periods
    sparsity = (total_zero_or_gap / total_periods) if total_periods > 0 else 1.0
    total_qty = sum(p.quantity for p in periods_list)
    quantities = np.array([p.quantity for p in periods_list], dtype=np.float64)

    # 3. Document Coverage Assumptions and Data Quality Limitations
    notes.append(
        f"Timeline coverage assumption: {total_periods} contiguous {interval.value} periods between "
        f"{periods_list[0].period_start} and {periods_list[-1].period_end}."
    )
    if unconfirmed_gaps > 0:
        notes.append(
            f"Coverage notice: {unconfirmed_gaps} period(s) had no recorded transactions across any business product. "
            "These intervals are tracked as potential recording gaps rather than confirmed zero sales."
        )
    if confirmed_zeros > 0:
        notes.append(
            f"Verified inactivity: {confirmed_zeros} period(s) had confirmed zero sales while other business products were actively sold."
        )

    # 4. Assess Data Feasibility
    if total_periods < 4 or active_periods < 2:
        status = DataLimitationStatusEnum.INSUFFICIENT_HISTORY
        notes.append(
            f"Product has only {total_periods} historical {interval.value} periods ({active_periods} with sales). "
            "At least 4 regular periods are required to compute reliable demand forecasts."
        )
    elif sparsity > 0.70:
        status = DataLimitationStatusEnum.INTERMITTENT_DEMAND
        notes.append(
            f"Demand is highly intermittent ({round(sparsity * 100, 1)}% zero/gap periods). "
            "Using expected demand rate (occurrence rate * positive average quantity) to prevent forecast inflation."
        )
    else:
        status = DataLimitationStatusEnum.FORECAST_AVAILABLE

    return PreparedProductSeries(
        product_name=clean_target_name,
        product_id=resolved_product_id,
        interval=interval,
        periods=periods_list,
        quantities=quantities,
        total_periods=total_periods,
        active_periods=active_periods,
        confirmed_zeros_count=confirmed_zeros,
        unconfirmed_gaps_count=unconfirmed_gaps,
        total_quantity=round(total_qty, 2),
        sparsity_ratio=round(sparsity, 3),
        status=status,
        limitation_notes=notes,
    )
