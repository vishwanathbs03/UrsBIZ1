"""Column alias detection and matching engine for sales uploads (Phase 3)."""

from __future__ import annotations

import re
from typing import Optional


# Known column aliases across Indian and global MSME invoice/accounting exports
FIELD_ALIASES: dict[str, list[str]] = {
    "transaction_date": [
        "date",
        "transaction_date",
        "order_date",
        "sale_date",
        "invoice_date",
        "txn_date",
        "bill_date",
        "booking_date",
        "time",
        "timestamp",
    ],
    "product_name": [
        "product",
        "product_name",
        "item",
        "item_name",
        "description",
        "product_description",
        "item_description",
        "sku_name",
        "service_name",
        "particulars",
        "goods_description",
    ],
    "quantity": [
        "quantity",
        "qty",
        "units",
        "volume",
        "count",
        "items_sold",
        "pcs",
        "pieces",
        "nos",
        "number_of_items",
        "weight",
    ],
    "unit_price": [
        "unit_price",
        "price",
        "rate",
        "item_price",
        "cost_per_unit",
        "price_per_unit",
        "mrp",
        "selling_price",
        "unit_cost",
    ],
    "total_amount": [
        "total",
        "total_amount",
        "amount",
        "revenue",
        "gross_revenue",
        "sales_amount",
        "line_total",
        "total_sales",
        "net_amount",
        "invoice_amount",
        "grand_total",
        "value",
    ],
    "customer_name": [
        "customer",
        "customer_name",
        "client",
        "client_name",
        "buyer",
        "buyer_name",
        "party",
        "party_name",
        "account_name",
        "customer_trade_name",
    ],
    "customer_id": [
        "customer_id",
        "cust_id",
        "client_id",
        "buyer_id",
        "account_id",
        "customer_code",
        "party_code",
    ],
    "product_id": [
        "product_id",
        "prod_id",
        "sku",
        "sku_id",
        "item_id",
        "item_code",
        "barcode",
        "hsn_code",
        "hs_code",
    ],
    "invoice_id": [
        "invoice",
        "invoice_id",
        "invoice_no",
        "invoice_number",
        "bill_no",
        "bill_number",
        "order_id",
        "order_no",
        "order_number",
        "txn_id",
        "voucher_no",
    ],
}


def _normalize_string(val: str) -> str:
    """Normalize string by removing non-alphanumeric chars and lowercasing."""
    return re.sub(r"[^a-z0-9]", "", val.lower())


def detect_columns(headers: list[str]) -> tuple[dict[str, Optional[str]], dict[str, float]]:
    """Inspect list of headers and suggest mapping for each conceptual field with confidence."""
    suggested_mapping: dict[str, Optional[str]] = {field: None for field in FIELD_ALIASES}
    confidence_scores: dict[str, float] = {field: 0.0 for field in FIELD_ALIASES}

    normalized_headers = {header: _normalize_string(header) for header in headers}

    # For each conceptual field, find best matching header
    for field, aliases in FIELD_ALIASES.items():
        best_header: Optional[str] = None
        best_score: float = 0.0

        for header, norm_h in normalized_headers.items():
            for alias in aliases:
                norm_alias = _normalize_string(alias)
                # Exact match
                if norm_h == norm_alias:
                    score = 1.0
                # Full word boundary or prefix match
                elif norm_h.startswith(norm_alias) or norm_alias in norm_h:
                    score = 0.8
                else:
                    score = 0.0

                if score > best_score:
                    best_score = score
                    best_header = header

        if best_header and best_score >= 0.8:
            # Check if this header was already assigned to another field with a higher score
            suggested_mapping[field] = best_header
            confidence_scores[field] = best_score

    return suggested_mapping, confidence_scores
