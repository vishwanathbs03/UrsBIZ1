"""RelationshipEngine — Sprint H8.2 Cross-module edge inferencing."""

from __future__ import annotations

from app.services.ai.knowledge.knowledge_graph import (
    BusinessKnowledgeGraph,
    KnowledgeRelationship,
)


class RelationshipEngine:
    """Discovers and establishes cross-module relationships across MSME business entities."""

    def infer_and_link_relationships(self, graph: BusinessKnowledgeGraph) -> int:
        """Infer cross-module edges and add them to the BusinessKnowledgeGraph.

        Returns the total number of new relationships established.
        """
        nodes = graph.nodes
        new_rels: list[KnowledgeRelationship] = []

        risks = [n for n in nodes if n.category in ("risk", "rule")]
        recs = [n for n in nodes if n.category == "recommendation"]
        schemes = [n for n in nodes if n.category == "scheme"]
        goals = [n for n in nodes if n.category == "goal"]
        analytics = [n for n in nodes if n.category == "analytics"]
        products = [n for n in nodes if n.category == "product"]
        exports = [n for n in nodes if n.category == "export"]

        # 1. Link Risks -> Recommendations (mitigated_by)
        for risk in risks:
            r_text = (risk.label + " " + str(risk.properties.get("reason", ""))).lower()
            for rec in recs:
                rec_text = (rec.label + " " + str(rec.properties.get("category", ""))).lower()
                # Category or keyword matching
                if ("supplier" in r_text and "supplier" in rec_text) or \
                   ("credit" in r_text and ("cash" in rec_text or "finance" in rec_text)) or \
                   ("quality" in r_text and ("iso" in rec_text or "audit" in rec_text)) or \
                   (risk.properties.get("priority") == "Critical"):
                    new_rels.append(
                        KnowledgeRelationship(
                            source_id=risk.id,
                            target_id=rec.id,
                            relation_type="mitigated_by",
                            weight=1.5,
                            description=f"Action '{rec.label}' mitigates risk '{risk.label}'",
                        )
                    )

        # 2. Link Recommendations -> Analytics (improves_health_score)
        for rec in recs:
            for score in analytics:
                gain = rec.properties.get("estimated_score_gain", 0)
                if gain > 0:
                    new_rels.append(
                        KnowledgeRelationship(
                            source_id=rec.id,
                            target_id=score.id,
                            relation_type="improves_health_score",
                            weight=1.2,
                            description=f"Action '{rec.label}' improves score by +{gain}",
                        )
                    )

        # 3. Link Schemes -> Recommendations / Goals (funds_action / supports_goal)
        for sch in schemes:
            sch_title = sch.label.lower()
            for rec in recs:
                rec_title = rec.label.lower()
                if ("export" in sch_title and "export" in rec_title) or \
                   ("tech" in sch_title and "digital" in rec_title) or \
                   ("credit" in sch_title and ("loan" in rec_title or "finance" in rec_title)):
                    new_rels.append(
                        KnowledgeRelationship(
                            source_id=sch.id,
                            target_id=rec.id,
                            relation_type="funds_action",
                            weight=1.4,
                            description=f"Scheme '{sch.label}' provides financial assistance for '{rec.label}'",
                        )
                    )

            for goal in goals:
                g_title = goal.label.lower()
                if ("growth" in g_title or "expand" in g_title or "export" in g_title):
                    new_rels.append(
                        KnowledgeRelationship(
                            source_id=sch.id,
                            target_id=goal.id,
                            relation_type="supports_goal",
                            weight=1.3,
                        )
                    )

        # 4. Link Goals -> Recommendations (driven_by_action)
        for goal in goals:
            for rec in recs:
                new_rels.append(
                    KnowledgeRelationship(
                        source_id=goal.id,
                        target_id=rec.id,
                        relation_type="driven_by_action",
                        weight=1.1,
                    )
                )

        # Add inferred relationships into the graph
        for rel in new_rels:
            graph.add_relationship(rel)

        return len(new_rels)
