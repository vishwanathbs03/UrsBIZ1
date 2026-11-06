"""Test Harness Connector Implementation (Phase 6.27).

A deterministic, fully operational connector adapter designed for automated testing,
integration verification, local development, and end-to-end sync validation.
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


class TestHarnessConnector(BaseDataConnector):
    """Test harness connector with controlled fault injection and realistic transaction generation."""

    @property
    def connector_id(self) -> str:
        return "test_harness"

    @property
    def name(self) -> str:
        return "UrsBiz Test Harness Simulator"

    @property
    def provider(self) -> str:
        return "UrsBiz Engineering"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "Operational test adapter providing deterministic MSME sales ledgers and fault simulation."

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
        return "API_KEY"

    @property
    def sync_direction(self) -> SyncDirection:
        return SyncDirection.INBOUND_ONLY

    @property
    def operational_status(self) -> OperationalStatus:
        return OperationalStatus.OPERATIONAL

    @property
    def known_limitations(self) -> list[str]:
        return [
            "Local test harness for verification; does not connect to external third-party servers.",
            "Simulated data only.",
        ]

    def get_config_fields(self) -> list[ConfigFieldDefinition]:
        return [
            ConfigFieldDefinition(
                key="store_identifier",
                label="Store Identifier",
                field_type="text",
                required=True,
                default_value="STORE-BLR-01",
                description="Unique identifier for the simulated store location.",
            ),
            ConfigFieldDefinition(
                key="batch_size",
                label="Batch Size",
                field_type="number",
                required=False,
                default_value=5,
                description="Number of records to fetch per pagination batch.",
            ),
            ConfigFieldDefinition(
                key="simulate_rate_limit",
                label="Simulate Rate Limit",
                field_type="select",
                required=False,
                options=["false", "true"],
                default_value="false",
                description="Simulate HTTP 429 Too Many Requests error on sync.",
            ),
            ConfigFieldDefinition(
                key="simulate_timeout",
                label="Simulate Timeout",
                field_type="select",
                required=False,
                options=["false", "true"],
                default_value="false",
                description="Simulate upstream server timeout error on sync.",
            ),
            ConfigFieldDefinition(
                key="simulate_bad_data",
                label="Simulate Bad Data",
                field_type="select",
                required=False,
                options=["false", "true"],
                default_value="false",
                description="Simulate invalid data schema to test validation error handling.",
            ),
            ConfigFieldDefinition(
                key="api_key",
                label="Simulator API Key",
                field_type="password",
                required=True,
                is_secret=True,
                description="Authentication API key. Use 'valid-test-key' for success, 'invalid_key' or 'expired_key' for failure testing.",
            ),
        ]

    def validate_configuration(
        self,
        config: dict[str, Any],
        credentials: dict[str, Any],
    ) -> tuple[bool, str | None]:
        if not config.get("store_identifier"):
            return False, "Missing required configuration field: 'store_identifier'."
        if not credentials.get("api_key"):
            return False, "Missing required credential field: 'api_key'."
        return True, None

    def test_connection(
        self,
        config: dict[str, Any],
        credentials: dict[str, Any],
    ) -> tuple[bool, str | None]:
        api_key = str(credentials.get("api_key", "")).strip()
        if not api_key:
            return False, "Authentication failure: Missing API key."
        if api_key == "invalid_key":
            return False, "Authentication failure: Invalid or revoked API key."
        if api_key == "expired_key":
            return False, "Authentication failure: Upstream credential expired. Re-authentication required."
        return True, None

    def fetch_records(
        self,
        config: dict[str, Any],
        credentials: dict[str, Any],
        sync_cursor: str | None = None,
        limit: int = 100,
    ) -> FetchResult:
        # Check auth first
        ok, err = self.test_connection(config, credentials)
        if not ok:
            raise PermissionError(err)

        # Fault injection simulation
        if str(config.get("simulate_rate_limit")).lower() == "true":
            raise RuntimeError("Rate limited: Upstream provider quota exceeded (HTTP 429). Retry after 60s.")
        if str(config.get("simulate_timeout")).lower() == "true":
            raise TimeoutError("Provider unavailable: Connection timed out while contacting upstream endpoint.")

        cursor_int = int(sync_cursor) if sync_cursor and sync_cursor.isdigit() else 0
        batch_size = int(config.get("batch_size") or 5)
        limit = min(limit, batch_size)

        max_records = 15  # Total finite simulated records
        if cursor_int >= max_records:
            return FetchResult(records=[], next_cursor=str(cursor_int), has_more=False, total_discovered=max_records)

        end_idx = min(cursor_int + limit, max_records)
        raw_records: list[dict[str, Any]] = []

        is_bad_data = str(config.get("simulate_bad_data")).lower() == "true"

        for i in range(cursor_int, end_idx):
            inv_num = i + 1
            if is_bad_data and i == cursor_int:
                # Produce bad row missing required date and negative total
                raw_records.append({
                    "raw_id": f"th-raw-{inv_num}",
                    "invoice_no": f"INV-TH-{inv_num:04d}",
                    "tx_date": "INVALID_DATE",
                    "product": "",
                    "qty": -5,
                    "unit_price": -100.0,
                    "amount": -500.0,
                })
            else:
                raw_records.append({
                    "raw_id": f"th-raw-{inv_num}",
                    "invoice_no": f"INV-TH-{inv_num:04d}",
                    "tx_date": f"2026-11-0{min(inv_num, 9)}T10:00:00Z" if inv_num < 10 else f"2026-11-{inv_num}T10:00:00Z",
                    "customer_id": f"CUST-TH-{(inv_num % 3) + 1}",
                    "customer_name": f"Retail Customer {(inv_num % 3) + 1}",
                    "product_id": f"PROD-TH-{(inv_num % 4) + 1}",
                    "product": f"Karnataka Spices Pack {(inv_num % 4) + 1}",
                    "qty": float(2 + (inv_num % 5)),
                    "unit_price": 250.0,
                    "amount": float((2 + (inv_num % 5)) * 250.0),
                })

        next_c = str(end_idx)
        has_more = end_idx < max_records

        return FetchResult(
            records=raw_records,
            next_cursor=next_c,
            has_more=has_more,
            total_discovered=max_records,
        )

    def map_record(self, raw_record: dict[str, Any]) -> NormalizedTransaction:
        date_str = str(raw_record.get("tx_date", ""))
        try:
            # Parse ISO date string
            if "T" in date_str:
                tx_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            else:
                tx_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except Exception as e:
            raise ValueError(f"Invalid transaction date '{date_str}': {e}") from e

        product_name = str(raw_record.get("product", "")).strip()
        if not product_name:
            raise ValueError("Product name cannot be empty.")

        qty = float(raw_record.get("qty", 0.0))
        if qty <= 0:
            raise ValueError(f"Quantity must be strictly positive, got {qty}.")

        unit_price = float(raw_record.get("unit_price", 0.0))
        if unit_price <= 0:
            raise ValueError(f"Unit price must be strictly positive, got {unit_price}.")

        total_amount = float(raw_record.get("amount", qty * unit_price))
        if total_amount <= 0:
            raise ValueError(f"Total amount must be strictly positive, got {total_amount}.")

        return NormalizedTransaction(
            transaction_date=tx_date,
            invoice_id=raw_record.get("invoice_no"),
            customer_id=raw_record.get("customer_id"),
            customer_name=raw_record.get("customer_name"),
            product_id=raw_record.get("product_id"),
            product_name=product_name,
            quantity=qty,
            unit_price=unit_price,
            total_amount=total_amount,
            raw_source_id=raw_record.get("raw_id"),
        )
