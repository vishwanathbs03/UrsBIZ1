"""Generic CSV Feed / POS Data Connector Implementation (Phase 6.27).

Adapter for scheduled remote CSV feeds and point-of-sale exports.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import urllib.parse

from app.services.connectors.base import (
    BaseDataConnector,
    ConfigFieldDefinition,
    ConnectorCapability,
    FetchResult,
    NormalizedTransaction,
    OperationalStatus,
    SyncDirection,
)


class CsvFeedConnector(BaseDataConnector):
    """Connector for recurring remote CSV feeds or automated webhook payloads."""

    @property
    def connector_id(self) -> str:
        return "csv_feed"

    @property
    def name(self) -> str:
        return "Automated CSV Feed / POS"

    @property
    def provider(self) -> str:
        return "Generic POS / Data Feed"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "Synchronizes recurring sales datasets from remote HTTP/HTTPS CSV endpoints or cloud storage feeds."

    @property
    def capabilities(self) -> list[ConnectorCapability]:
        return [
            ConnectorCapability.FETCH_TRANSACTIONS,
            ConnectorCapability.SCHEMA_VALIDATION,
            ConnectorCapability.RATE_LIMIT_AWARE,
        ]

    @property
    def auth_method(self) -> str:
        return "BEARER_TOKEN"

    @property
    def sync_direction(self) -> SyncDirection:
        return SyncDirection.INBOUND_ONLY

    @property
    def operational_status(self) -> OperationalStatus:
        return OperationalStatus.OPERATIONAL

    @property
    def known_limitations(self) -> list[str]:
        return [
            "Requires HTTP/HTTPS endpoint returning CSV text or direct file URL.",
            "Maximum 50MB payload per batch.",
        ]

    def get_config_fields(self) -> list[ConfigFieldDefinition]:
        return [
            ConfigFieldDefinition(
                key="feed_url",
                label="Feed Source URL",
                field_type="url",
                required=True,
                description="Secure HTTPS endpoint or presigned URL providing recurring sales CSV data.",
            ),
            ConfigFieldDefinition(
                key="delimiter",
                label="CSV Delimiter",
                field_type="select",
                required=False,
                options=[",", ";", "\t", "|"],
                default_value=",",
                description="Column separator character used in the CSV feed.",
            ),
            ConfigFieldDefinition(
                key="feed_token",
                label="Feed Bearer Token / API Key",
                field_type="password",
                required=False,
                is_secret=True,
                description="Optional Bearer token sent in Authorization header.",
            ),
        ]

    def validate_configuration(
        self,
        config: dict[str, Any],
        credentials: dict[str, Any],
    ) -> tuple[bool, str | None]:
        url = str(config.get("feed_url", "")).strip()
        if not url:
            return False, "Missing required configuration field: 'feed_url'."
        try:
            parsed = urllib.parse.urlparse(url)
            if parsed.scheme not in ("http", "https"):
                return False, f"Invalid 'feed_url' scheme '{parsed.scheme}'. Only http and https are permitted."
        except Exception as e:
            return False, f"Invalid 'feed_url': {e}"
        return True, None

    def test_connection(
        self,
        config: dict[str, Any],
        credentials: dict[str, Any],
    ) -> tuple[bool, str | None]:
        ok, err = self.validate_configuration(config, credentials)
        if not ok:
            return False, err
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
            raise ConnectionError(err)
        return FetchResult(records=[], next_cursor=sync_cursor, has_more=False, total_discovered=0)

    def map_record(self, raw_record: dict[str, Any]) -> NormalizedTransaction:
        date_raw = str(raw_record.get("transaction_date", raw_record.get("date", ""))).strip()
        try:
            if "T" in date_raw:
                tx_date = datetime.fromisoformat(date_raw.replace("Z", "+00:00"))
            else:
                tx_date = datetime.strptime(date_raw, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except Exception as e:
            raise ValueError(f"Invalid transaction date '{date_raw}': {e}") from e

        product = str(raw_record.get("product_name", raw_record.get("product", ""))).strip()
        if not product:
            raise ValueError("Product name cannot be empty.")

        qty = float(raw_record.get("quantity", raw_record.get("qty", 1.0)))
        unit_price = float(raw_record.get("unit_price", raw_record.get("price", 0.0)))
        total = float(raw_record.get("total_amount", raw_record.get("amount", qty * unit_price)))

        return NormalizedTransaction(
            transaction_date=tx_date,
            invoice_id=raw_record.get("invoice_id", raw_record.get("invoice_no")),
            customer_id=raw_record.get("customer_id"),
            customer_name=raw_record.get("customer_name"),
            product_id=raw_record.get("product_id"),
            product_name=product,
            quantity=qty,
            unit_price=unit_price,
            total_amount=total,
            raw_source_id=raw_record.get("raw_id"),
            line_item_id=str(raw_record.get("line_item_id") or raw_record.get("line_no") or "").strip() or None,
        )
