"""Data quality validation and revenue calculation engine for sales uploads (Phase 3)."""

from __future__ import annotations

from datetime import datetime, timezone
import math
from typing import Any
import pandas as pd

from app.schemas.sales import ColumnMapping, DataQualitySummary, QualityIssue


def _parse_date(raw_val: Any) -> tuple[datetime | None, str | None]:
    """Parse various date formats into a timezone-aware UTC datetime."""
    if raw_val is None or (isinstance(raw_val, float) and math.isnan(raw_val)):
        return None, "Date is missing or null."

    val_str = str(raw_val).strip()
    if not val_str or val_str.lower() in ["nan", "none", "null", "nat"]:
        return None, "Date is empty."

    # Try pandas to_datetime which handles ISO, timestamps, DD/MM/YYYY, MM/DD/YYYY
    try:
        dt = pd.to_datetime(val_str, errors="raise")
        if pd.isna(dt):
            return None, f"Invalid date value '{val_str}'"
        # Convert to python datetime
        pydt: datetime = dt.to_pydatetime()
        if pydt.tzinfo is None:
            pydt = pydt.replace(tzinfo=timezone.utc)
        return pydt, None
    except Exception as e:
        return None, f"Could not parse date '{val_str}': {e}"


def _parse_float(raw_val: Any) -> float | None:
    """Clean and parse a numeric float value, handling currency symbols and commas."""
    if raw_val is None or (isinstance(raw_val, float) and math.isnan(raw_val)):
        return None
    val_str = str(raw_val).strip()
    if not val_str or val_str.lower() in ["nan", "none", "null"]:
        return None
    # Strip common currency signs and commas: ₹, $, €, £, commas
    cleaned = (
        val_str.replace("₹", "")
        .replace("$", "")
        .replace("€", "")
        .replace("£", "")
        .replace(",", "")
        .strip()
    )
    try:
        num = float(cleaned)
        if math.isnan(num) or math.isinf(num):
            return None
        return num
    except ValueError:
        return None


def validate_and_process_sales_data(
    df: pd.DataFrame,
    mapping: ColumnMapping,
    existing_fingerprints: set[tuple] | None = None,
) -> tuple[list[dict[str, Any]], DataQualitySummary]:
    """Validate DataFrame row by row against mapping and generate quality audit summary."""
    total_rows = len(df)
    valid_rows: list[dict[str, Any]] = []
    issues: list[QualityIssue] = []

    missing_dates_count = 0
    missing_id_count = 0
    invalid_quantities_count = 0
    invalid_prices_count = 0
    duplicate_count = 0
    calculated_revenues_count = 0
    invalid_rows_count = 0
    flagged_rows_count = 0

    seen_fingerprints: set[tuple] = (
        set(existing_fingerprints) if existing_fingerprints else set()
    )

    for idx, row in df.iterrows():
        row_num = int(idx) + 1  # 1-based row index for user friendliness
        row_has_error = False

        # 1. Date Validation
        raw_date = row.get(mapping.transaction_date)
        txn_date, date_err = _parse_date(raw_date)
        if date_err or txn_date is None:
            missing_dates_count += 1
            issues.append(
                QualityIssue(
                    row_index=row_num,
                    issue_type="missing_or_invalid_date",
                    severity="error",
                    message=date_err or "Invalid transaction date",
                    field="transaction_date",
                    value=str(raw_date),
                )
            )
            row_has_error = True

        # 2. Product Name Validation
        raw_product = row.get(mapping.product_name)
        product_name = str(raw_product).strip() if raw_product is not None else ""
        if not product_name or product_name.lower() in ["nan", "none", "null"]:
            missing_id_count += 1
            issues.append(
                QualityIssue(
                    row_index=row_num,
                    issue_type="missing_product_name",
                    severity="error",
                    message="Product name is required and cannot be empty.",
                    field="product_name",
                    value=str(raw_product),
                )
            )
            row_has_error = True

        # 3. Quantity Validation
        raw_qty = row.get(mapping.quantity)
        qty = _parse_float(raw_qty)
        if qty is None or qty <= 0:
            invalid_quantities_count += 1
            issues.append(
                QualityIssue(
                    row_index=row_num,
                    issue_type="invalid_quantity",
                    severity="error",
                    message="Quantity must be a positive number greater than 0.",
                    field="quantity",
                    value=str(raw_qty),
                )
            )
            row_has_error = True

        # 4. Unit Price Validation
        raw_price = row.get(mapping.unit_price)
        unit_price = _parse_float(raw_price)
        if unit_price is None or unit_price <= 0:
            invalid_prices_count += 1
            issues.append(
                QualityIssue(
                    row_index=row_num,
                    issue_type="invalid_unit_price",
                    severity="error",
                    message="Unit price must be a positive number greater than 0.",
                    field="unit_price",
                    value=str(raw_price),
                )
            )
            row_has_error = True

        # 5. Customer & Optional Fields
        customer_name = (
            str(row.get(mapping.customer_name)).strip()
            if mapping.customer_name and row.get(mapping.customer_name) is not None
            else None
        )
        if customer_name and customer_name.lower() in ["nan", "none", "null", ""]:
            customer_name = None

        customer_id = (
            str(row.get(mapping.customer_id)).strip()
            if mapping.customer_id and row.get(mapping.customer_id) is not None
            else None
        )
        if customer_id and customer_id.lower() in ["nan", "none", "null", ""]:
            customer_id = None

        product_id = (
            str(row.get(mapping.product_id)).strip()
            if mapping.product_id and row.get(mapping.product_id) is not None
            else None
        )
        if product_id and product_id.lower() in ["nan", "none", "null", ""]:
            product_id = None

        invoice_id = (
            str(row.get(mapping.invoice_id)).strip()
            if mapping.invoice_id and row.get(mapping.invoice_id) is not None
            else None
        )
        if invoice_id and invoice_id.lower() in ["nan", "none", "null", ""]:
            invoice_id = None

        # 6. Revenue Calculation & Consistency
        total_amount: float | None = None
        is_revenue_missing = False

        if mapping.total_amount:
            raw_total = row.get(mapping.total_amount)
            if (
                raw_total is None
                or (isinstance(raw_total, float) and math.isnan(raw_total))
                or str(raw_total).strip() == ""
                or str(raw_total).strip().lower() in ["nan", "none", "null", "nat"]
            ):
                is_revenue_missing = True
            else:
                total_amount = _parse_float(raw_total)
                if total_amount is None:
                    # Non-empty string could not be parsed as a float
                    issues.append(
                        QualityIssue(
                            row_index=row_num,
                            issue_type="invalid_total_amount",
                            severity="error",
                            message=f"Total amount '{raw_total}' could not be parsed as a valid numeric amount.",
                            field="total_amount",
                            value=str(raw_total),
                        )
                    )
                    row_has_error = True
        else:
            is_revenue_missing = True

        if not row_has_error and qty is not None and unit_price is not None:
            expected_total = round(qty * unit_price, 2)

            if is_revenue_missing:
                # Deterministically calculate missing revenue
                total_amount = expected_total
                calculated_revenues_count += 1
                flagged_rows_count += 1
                issues.append(
                    QualityIssue(
                        row_index=row_num,
                        issue_type="calculated_revenue",
                        severity="warning",
                        message=f"Revenue was missing in source row; calculated deterministically as {qty} × {unit_price} = {total_amount}",
                        field="total_amount",
                        value=total_amount,
                    )
                )
            else:
                assert total_amount is not None
                if total_amount <= 0:
                    # Explicit zero or negative revenue provided -> reject as unsupported return / credit note
                    row_has_error = True
                    issues.append(
                        QualityIssue(
                            row_index=row_num,
                            issue_type="unsupported_zero_or_negative_revenue",
                            severity="error",
                            message=(
                                f"Explicit zero or negative revenue ({total_amount}) is not supported. "
                                "Returns, refunds, credit notes, and zero-value adjustments are currently out of scope."
                            ),
                            field="total_amount",
                            value=total_amount,
                        )
                    )
                else:
                    # Positive revenue provided: check for severe discrepancy (> 10%)
                    diff = abs(total_amount - expected_total)
                    if expected_total > 0 and (diff / expected_total) > 0.10:
                        flagged_rows_count += 1
                        issues.append(
                            QualityIssue(
                                row_index=row_num,
                                issue_type="inconsistent_revenue",
                                severity="warning",
                                message=(
                                    f"Provided revenue ({total_amount}) differs from qty × unit_price ({expected_total}). "
                                    "Recorded provided revenue."
                                ),
                                field="total_amount",
                                value=total_amount,
                            )
                        )

        # 7. Duplicate Check
        is_duplicate = False
        if not row_has_error and txn_date is not None and total_amount is not None and qty is not None:
            date_str = txn_date.strftime("%Y-%m-%d")
            p_name = product_name.strip().lower()
            q_val = round(qty, 4)
            tot_val = round(total_amount, 2)

            if invoice_id:
                fingerprint = ("inv", invoice_id.strip().lower(), p_name, q_val, tot_val)
            else:
                c_name = (customer_name or customer_id or "").strip().lower()
                fingerprint = ("date", date_str, c_name, p_name, q_val, tot_val)

            if fingerprint in seen_fingerprints:
                duplicate_count += 1
                flagged_rows_count += 1
                is_duplicate = True
                issues.append(
                    QualityIssue(
                        row_index=row_num,
                        issue_type="duplicate_transaction",
                        severity="warning",
                        message=(
                            "Duplicate transaction detected (matches previous date/invoice, product, quantity & total). "
                            "Row accepted for audit trail but excluded from default analytics to prevent metric inflation."
                        ),
                        field="invoice_id" if invoice_id else "transaction_date",
                        value=invoice_id or date_str,
                    )
                )
            else:
                seen_fingerprints.add(fingerprint)

        # Final acceptance or rejection
        if row_has_error:
            invalid_rows_count += 1
        else:
            assert txn_date is not None
            assert qty is not None
            assert unit_price is not None
            assert total_amount is not None

            valid_rows.append(
                {
                    "transaction_date": txn_date,
                    "invoice_id": invoice_id,
                    "customer_id": customer_id,
                    "customer_name": customer_name,
                    "product_id": product_id,
                    "product_name": product_name,
                    "quantity": qty,
                    "unit_price": unit_price,
                    "total_amount": total_amount,
                    "is_duplicate": is_duplicate,
                }
            )

    valid_count = len(valid_rows)
    quality_score = (
        round((valid_count / total_rows) * 100, 1) if total_rows > 0 else 0.0
    )

    summary = DataQualitySummary(
        total_rows_received=total_rows,
        valid_rows=valid_count,
        invalid_rows=invalid_rows_count,
        flagged_rows=flagged_rows_count,
        missing_dates=missing_dates_count,
        missing_customer_or_product=missing_id_count,
        invalid_quantities=invalid_quantities_count,
        invalid_or_missing_prices=invalid_prices_count,
        duplicate_transactions=duplicate_count,
        calculated_revenues=calculated_revenues_count,
        quality_score=quality_score,
        issues=issues[:100],  # Keep first 100 issues for audit responsiveness
    )

    return valid_rows, summary
