"""Connector Registry (Phase 6.27).

Maintains available connector adapters and capability specifications.
"""

from __future__ import annotations

from typing import Dict, List

from app.services.connectors.base import BaseDataConnector
from app.services.connectors.implementations.csv_feed import CsvFeedConnector
from app.services.connectors.implementations.tally import TallyConnector
from app.services.connectors.implementations.test_harness import TestHarnessConnector
from app.services.connectors.implementations.zoho_books import ZohoBooksConnector


class ConnectorRegistry:
    """Registry managing available data source connectors for UrsBiz."""

    _connectors: Dict[str, BaseDataConnector] = {}

    @classmethod
    def register(cls, connector: BaseDataConnector) -> None:
        """Register a connector adapter in the central catalogue."""
        cls._connectors[connector.connector_id] = connector

    @classmethod
    def get(cls, connector_id: str) -> BaseDataConnector:
        """Retrieve a registered connector by its unique identifier."""
        if not cls._connectors:
            cls._initialize_defaults()

        if connector_id not in cls._connectors:
            raise KeyError(
                f"Connector '{connector_id}' is not registered or supported. "
                f"Available connectors: {list(cls._connectors.keys())}."
            )
        return cls._connectors[connector_id]

    @classmethod
    def list(cls) -> List[BaseDataConnector]:
        """List all available registered connectors in catalogue display order."""
        if not cls._connectors:
            cls._initialize_defaults()
        return list(cls._connectors.values())

    @classmethod
    def _initialize_defaults(cls) -> None:
        """Register the built-in connectors."""
        cls._connectors.clear()
        cls.register(TestHarnessConnector())
        cls.register(TallyConnector())
        cls.register(ZohoBooksConnector())
        cls.register(CsvFeedConnector())
