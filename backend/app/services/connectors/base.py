"""Base Data Connector Contract and Abstractions (Phase 6.27).

Defines:
  - BaseDataConnector: Abstract contract implemented by every external data integration.
  - NormalizedTransaction: Canonical schema mapping target for UrsBiz SalesTransaction.
  - FetchResult: Paginated discovery and record extraction envelope.
  - ConfigFieldDefinition: Field metadata and validation rules for connector setup.
  - ConnectorCapability & SyncDirection: Enumerations of connector competencies.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class SyncDirection(str, Enum):
    """Supported direction for data flow."""
    INBOUND_ONLY = "INBOUND_ONLY"
    OUTBOUND_ONLY = "OUTBOUND_ONLY"
    BIDIRECTIONAL = "BIDIRECTIONAL"


class ConnectorCapability(str, Enum):
    """Capabilities supported by a data connector."""
    FETCH_TRANSACTIONS = "FETCH_TRANSACTIONS"
    INCREMENTAL_SYNC = "INCREMENTAL_SYNC"
    SCHEMA_VALIDATION = "SCHEMA_VALIDATION"
    HISTORICAL_BACKFILL = "HISTORICAL_BACKFILL"
    RATE_LIMIT_AWARE = "RATE_LIMIT_AWARE"
    WEBHOOK_TRIGGERED = "WEBHOOK_TRIGGERED"


class OperationalStatus(str, Enum):
    """Realistic operational readiness status of a connector."""
    OPERATIONAL = "OPERATIONAL"
    BETA = "BETA"
    READY_FOR_CREDENTIALS = "READY_FOR_CREDENTIALS"
    COMING_SOON = "COMING_SOON"


@dataclass
class ConfigFieldDefinition:
    """Schema descriptor for a configuration or credential field required by the connector."""
    key: str
    label: str
    field_type: str  # "text", "password", "number", "select", "url"
    required: bool = True
    description: str = ""
    default_value: Any = None
    options: list[str] | None = None
    is_secret: bool = False  # If True, routed through encrypted credential vault


@dataclass
class NormalizedTransaction:
    """Standardized transactional entity ready for validation and insertion into SalesTransaction."""
    transaction_date: datetime
    invoice_id: str | None
    customer_id: str | None
    customer_name: str | None
    product_id: str | None
    product_name: str
    quantity: float
    unit_price: float
    total_amount: float
    raw_source_id: str | None = None


@dataclass
class FetchResult:
    """Standardized batch payload returned by connector fetch operations."""
    records: list[dict[str, Any]] = field(default_factory=list)
    next_cursor: str | None = None
    has_more: bool = False
    total_discovered: int = 0


class BaseDataConnector(ABC):
    """Abstract Base Class defining the contract for all UrsBiz data source connectors."""

    @property
    @abstractmethod
    def connector_id(self) -> str:
        """Unique machine identifier for this connector (e.g. 'tally_prime', 'zoho_books')."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable display name (e.g. 'Tally Prime ERP')."""
        pass

    @property
    @abstractmethod
    def provider(self) -> str:
        """Vendor or provider organization (e.g. 'Tally Solutions', 'Zoho Corp')."""
        pass

    @property
    @abstractmethod
    def version(self) -> str:
        """Connector adapter semantic version (e.g. '1.0.0')."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Overview of what this connector connects and its purpose."""
        pass

    @property
    @abstractmethod
    def capabilities(self) -> list[ConnectorCapability]:
        """List of supported functional capabilities."""
        pass

    @property
    @abstractmethod
    def auth_method(self) -> str:
        """Authentication mechanism (e.g. 'API_KEY', 'OAUTH2', 'BASIC_AUTH', 'NONE')."""
        pass

    @property
    @abstractmethod
    def sync_direction(self) -> SyncDirection:
        """Directionality of data synchronization."""
        pass

    @property
    @abstractmethod
    def operational_status(self) -> OperationalStatus:
        """Current operational status: OPERATIONAL, BETA, READY_FOR_CREDENTIALS, COMING_SOON."""
        pass

    @property
    @abstractmethod
    def known_limitations(self) -> list[str]:
        """Explicit list of technical boundaries and known constraints."""
        pass

    @abstractmethod
    def get_config_fields(self) -> list[ConfigFieldDefinition]:
        """Return the list of non-secret configuration and secret credential fields."""
        pass

    @abstractmethod
    def validate_configuration(
        self,
        config: dict[str, Any],
        credentials: dict[str, Any],
    ) -> tuple[bool, str | None]:
        """Validate configuration values and credentials syntactically before saving."""
        pass

    @abstractmethod
    def test_connection(
        self,
        config: dict[str, Any],
        credentials: dict[str, Any],
    ) -> tuple[bool, str | None]:
        """Execute a live ping or authentication check against the upstream provider.

        Returns:
            (success: bool, error_message: str | None)
        """
        pass

    @abstractmethod
    def fetch_records(
        self,
        config: dict[str, Any],
        credentials: dict[str, Any],
        sync_cursor: str | None = None,
        limit: int = 100,
    ) -> FetchResult:
        """Fetch a paginated batch of raw records from the data source."""
        pass

    @abstractmethod
    def map_record(self, raw_record: dict[str, Any]) -> NormalizedTransaction:
        """Normalize an upstream provider record into a canonical NormalizedTransaction."""
        pass
