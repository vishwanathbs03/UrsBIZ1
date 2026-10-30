"""EvidenceFusion — Sprint H8.2 Multi-module evidence fusion."""

from __future__ import annotations

from typing import Any

from app.services.ai.knowledge.knowledge_graph import (
    BusinessKnowledgeGraph,
    KnowledgeNode,
)


class EvidenceFusion:
    """Fuses multi-module graph facts into grounded evidence items."""

    def fuse_evidence_bundle(self, graph: BusinessKnowledgeGraph) -> list[dict[str, Any]]:
        """Extract multi-module evidence items from graph nodes."""
        evidence_items: list[dict[str, Any]] = []

        for node in graph.nodes:
            if node.evidence_id:
                evidence_items.append({
                    "id": node.evidence_id,
                    "kind": self._map_category_to_kind(node.category),
                    "label": node.label,
                    "category": node.category,
                    "properties": node.properties,
                })

        return evidence_items

    @staticmethod
    def _map_category_to_kind(category: str) -> str:
        mapping = {
            "profile": "score",
            "analytics": "score",
            "recommendation": "recommendation",
            "risk": "rule",
            "rule": "rule",
            "scheme": "scheme",
            "dna": "dna",
            "export": "score",
            "product": "score",
            "goal": "score",
        }
        return mapping.get(category, "score")
