"""ContextRanker — Sprint H8.2 Multi-module context ranking and selection."""

from __future__ import annotations

from typing import Iterable

from app.services.ai.knowledge.knowledge_graph import (
    BusinessKnowledgeGraph,
    KnowledgeNode,
)


class ContextRanker:
    """Ranks and selects nodes and triples from the BusinessKnowledgeGraph based on user intent."""

    def select_multi_module_context(
        self,
        graph: BusinessKnowledgeGraph,
        user_prompt: str,
        max_nodes: int = 25,
    ) -> list[KnowledgeNode]:
        """Select top multi-module nodes ensuring diversity across categories."""
        nodes = graph.nodes
        prompt_low = (user_prompt or "").lower()

        # Intent keyword boosting
        boosted_nodes: list[tuple[float, KnowledgeNode]] = []
        for n in nodes:
            score = n.priority_score
            label_low = n.label.lower()
            cat_low = n.category.lower()

            # Direct prompt match boost
            if any(term in prompt_low for term in (cat_low, label_low)):
                score += 15.0

            # Query intent heuristics
            if "grow" in prompt_low or "expand" in prompt_low:
                if n.category in ("recommendation", "scheme", "export", "goal"):
                    score += 10.0
            elif "risk" in prompt_low or "problem" in prompt_low or "cost" in prompt_low:
                if n.category in ("risk", "rule", "recommendation", "kpi"):
                    score += 10.0

            boosted_nodes.append((score, n))

        boosted_nodes.sort(key=lambda x: x[0], reverse=True)

        # Enforce diversity: cap nodes per category to guarantee multi-module representation
        category_counts: dict[str, int] = {}
        selected: list[KnowledgeNode] = []
        _MAX_PER_CAT = 4

        for _, node in boosted_nodes:
            cnt = category_counts.get(node.category, 0)
            if cnt < _MAX_PER_CAT or len(selected) < max_nodes // 2:
                category_counts[node.category] = cnt + 1
                selected.append(node)
            if len(selected) >= max_nodes:
                break

        return selected
