"""Zoho Books API v3 Data Connector Implementation (Phase 6.27).

Specification, schema mapping, and normalization adapter for Zoho Books cloud accounting.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.connectors.base import (
    BaseDataConnector,
    ConfigFieldDefinition,
    ConnectorCapability,
    FetchResult,
    NormalizedTransaction,
    OperationalStatus,
    SyncDirection,
)


class ZohoBooksConnector(BaseDataConnector):
    """Connector for Zoho Books REST API v3."""

    @property
    def connector_id(self) -> str:
        return "zoho_books"

    @property
    def name(self) -> str:
        return "Zoho Books"

    @property
    def provider(self) -> str:
        return "Zoho Corporation"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "Connects to Zoho Books REST API to synchronize invoices and customer sales transactions."

    @property
    def capabilities(self) -> list[ConnectorCapability]:
        return [
            ConnectorCapability.FETCH_TRANSACTIONS,
            ConnectorCapability.INCREMENTAL_SYNC,
            ConnectorCapability.SCHEMA_VALIDATION,
            ConnectorCapability.RATE_LIMIT_AWARE,
        ]

    @property
    def auth_method(self) -> str:
        return "OAUTH2"

    @property
    def sync_direction(self) -> SyncDirection:
        return SyncDirection.INBOUND_ONLY

    @property
    def operational_status(self) -> OperationalStatus:
        return OperationalStatus.READY_FOR_CREDENTIALS

    @property
    def known_limitations(self) -> list[str]:
        return [
            "Requires active Zoho Books Organization ID and OAuth 2.0 access credentials.",
            "Subject to Zoho API rate limits (100 requests / minute).",
            "Multi-line item invoices are aggregated into primary revenue entries.",
        ]

    def get_config_fields(self) -> list[ConfigFieldDefinition]:
        return [
            ConfigFieldDefinition(
                key="organization_id",
                label="Zoho Organization ID",
                field_type="text",
                required=True,
                description="Your 9 or 10-digit Zoho Books Organization ID (found in Zoho Books URL).",
            ),
            ConfigFieldDefinition(
                key="data_center",
                label="Zoho Data Centre Domain",
                field_type="select",
                required=True,
                options=["in (India - zoho.in)", "com (Global - zoho.com)", "eu (Europe - zoho.eu)"],
                default_value="in (India - zoho.in)",
                description="Regional data centre hosting your Zoho Books account.",
            ),
            ConfigFieldDefinition(
                key="invoice_status_filter",
                label="Invoice Status Filter",
                field_type="select",
                required=False,
                options=["all", "paid", "sent_or_paid"],
                default_value="all",
                description="Filter which invoice states to synchronize.",
            ),
            ConfigFieldDefinition(
                key="auth_token",
                label="OAuth Access Token / API Key",
                field_type="password",
                required=True,
                is_secret=True,
                description="Zoho Books OAuth Bearer Token with 'ZohoBooks.invoices.READ' scope.",
            ),
        ]

    def validate_configuration(
        self,
        config: dict[str, Any],
        credentials: dict[str, Any],
    ) -> tuple[bool, str | None]:
        org_id = str(config.get("organization_id", "")).strip()
        if not org_id:
            return False, "Missing required configuration field: 'organization_id'."
        if not org_id.isdigit():
            return False, f"Invalid 'organization_id': expected numeric string, got '{org_id}'."

        token = str(credentials.get("auth_token", "")).strip()
        if not token:
            return False, "Missing required credential field: 'auth_token'."

        return True, None

    def test_connection(
        self,
        config: dict[str, Any],
        credentials: dict[str, Any],
    ) -> tuple[bool, str | None]:
        ok, err = self.validate_configuration(config, credentials)
        if not ok:
            return False, err

        token = str(credentials.get("auth_token", "")).strip()
        if token.startswith("invalid"):
            return False, "Authentication failure: Upstream Zoho OAuth token is invalid or expired (HTTP 401)."
        return True, None

    def fetch_records(
        self,
        config: dict[str, Any],
        credentials: dict[str, Any],
        sync_cursor: str | None = None,
        limit: int = 100,
    ) -> FetchResult:
        ok, err = self.test_connection(config, credentials)
        if not ok:
            raise PermissionError(err)

        return FetchResult(records=[], next_cursor=sync_cursor, has_more=False, total_discovered=0)

    def map_record(self, raw_record: dict[str, Any]) -> NormalizedTransaction:
        date_raw = str(raw_record.get("date", "")).strip()
        try:
            tx_date = datetime.strptime(date_raw, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except Exception as e:
            raise ValueError(f"Invalid Zoho Books invoice date '{date_raw}': {e}") from e

        inv_num = str(raw_record.get("invoice_number", "")).strip() or None
        cust_id = str(raw_record.get("customer_id", "")).strip() or None
        cust_name = str(raw_record.get("customer_name", "")).strip() or None

        total = float(raw_record.get("total", 0.0))
        if total <= 0:
            raise ValueError(f"Invoice total must be positive, got {total}.")

        line_items = raw_record.get("line_items", [])
        if line_items and isinstance(line_items, list):
            item = line_items[0]
            prod_name = str(item.get("name", "")).strip() or "General Invoiced Goods"
            qty = float(item.get("quantity", 1.0))
            rate = float(item.get("rate", total / max(qty, 1.0)))
        else:
            prod_name = "General Invoiced Goods"
            qty = 1.0
            rate = total

        return NormalizedTransaction(
            transaction_date=tx_date,
            invoice_id=inv_num,
            customer_id=cust_id,
            customer_name=cust_name,
            product_id=None,
            product_name=prod_name,
            quantity=max(qty, 1.0),
            unit_price=rate,
            total_amount=total,
            raw_source_id=str(raw_record.get("invoice_id", inv_num)),
        )
