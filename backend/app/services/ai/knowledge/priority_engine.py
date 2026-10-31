"""PriorityEngine — Sprint H8.2 Cross-module priority scoring."""

from __future__ import annotations

from app.services.ai.knowledge.knowledge_graph import (
    BusinessKnowledgeGraph,
    KnowledgeNode,
)


class PriorityEngine:
    """Calculates priority and urgency scores for graph nodes across all business modules."""

    def score_nodes(self, graph: BusinessKnowledgeGraph) -> list[KnowledgeNode]:
        """Compute and update priority_score for all nodes in the graph."""
        res: list[KnowledgeNode] = []

        for node in graph.nodes:
            base = node.priority_score
            # Boost score based on connected edges count
            neighbors = graph.get_neighbors(node.id)
            connectivity_boost = min(len(neighbors) * 5.0, 20.0)

            # Category-specific weighting
            category_boost = 0.0
            if node.category == "risk" and node.properties.get("priority") == "Critical":
                category_boost = 15.0
            elif node.category == "recommendation":
                roi = float(node.properties.get("estimated_roi", 0.0))
                score_gain = float(node.properties.get("estimated_score_gain", 0.0))
                category_boost = min((roi / 1000.0) + (score_gain * 2.0), 20.0)

            final_score = round(min(base + connectivity_boost + category_boost, 100.0), 2)
            # Create updated node with final_score
            updated_node = KnowledgeNode(
                id=node.id,
                category=node.category,
                label=node.label,
                properties=node.properties,
                evidence_id=node.evidence_id,
                priority_score=final_score,
            )
            graph._nodes[node.id] = updated_node
            res.append(updated_node)

        return sorted(res, key=lambda n: n.priority_score, reverse=True)
