"""BusinessKnowledgeGraph — Sprint H8.2 Multi-Module Knowledge Graph representation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable


@dataclass(frozen=True)
class KnowledgeNode:
    """A node in the Business Knowledge Graph representing a business entity or fact."""

    id: str
    category: str  # "profile", "analytics", "swot", "dna", "recommendation", "scheme", "ocr", "kpi", "risk", "opportunity", "goal", "challenge", "product", "certification", "digital_presence", "export"
    label: str
    properties: dict[str, Any] = field(default_factory=dict)
    evidence_id: str | None = None
    priority_score: float = 50.0


@dataclass(frozen=True)
class KnowledgeRelationship:
    """A directed edge in the Business Knowledge Graph between two nodes."""

    source_id: str
    target_id: str
    relation_type: str  # "mitigated_by", "improves_kpi", "supports_recommendation", "evidences_fact", "drives_goal", "linked_risk"
    weight: float = 1.0
    description: str = ""


class BusinessKnowledgeGraph:
    """Multi-module property graph unifying all 20+ MSME business dimensions."""

    def __init__(self) -> None:
        self._nodes: dict[str, KnowledgeNode] = {}
        self._relationships: list[KnowledgeRelationship] = []
        self._adj: dict[str, list[KnowledgeRelationship]] = {}

    def add_node(self, node: KnowledgeNode) -> None:
        """Add a node to the knowledge graph."""
        self._nodes[node.id] = node
        if node.id not in self._adj:
            self._adj[node.id] = []

    def add_relationship(self, rel: KnowledgeRelationship) -> None:
        """Add a directed relationship to the graph."""
        if rel.source_id in self._nodes and rel.target_id in self._nodes:
            self._relationships.append(rel)
            self._adj[rel.source_id].append(rel)

    def get_node(self, node_id: str) -> KnowledgeNode | None:
        return self._nodes.get(node_id)

    @property
    def nodes(self) -> tuple[KnowledgeNode, ...]:
        return tuple(self._nodes.values())

    @property
    def relationships(self) -> tuple[KnowledgeRelationship, ...]:
        return tuple(self._relationships)

    def get_neighbors(self, node_id: str) -> tuple[KnowledgeNode, ...]:
        """Return all target nodes directly connected from node_id."""
        if node_id not in self._adj:
            return ()
        target_ids = [rel.target_id for rel in self._adj[node_id]]
        return tuple(self._nodes[tid] for tid in target_ids if tid in self._nodes)

    def extract_subgraph(self, max_nodes: int = 30) -> list[KnowledgeNode]:
        """Return the top nodes ranked by priority_score."""
        sorted_nodes = sorted(
            self._nodes.values(),
            key=lambda n: n.priority_score,
            reverse=True,
        )
        return sorted_nodes[:max_nodes]

    def to_triples(self) -> list[str]:
        """Format relationships as readable (Subject -> Relation -> Object) triples."""
        triples: list[str] = []
        for rel in self._relationships:
            src = self._nodes.get(rel.source_id)
            tgt = self._nodes.get(rel.target_id)
            if src and tgt:
                rel_clean = rel.relation_type.replace("_", " ").upper()
                triples.append(
                    f"[{src.category.upper()}] {src.label} --{rel_clean}--> [{tgt.category.upper()}] {tgt.label}"
                )
        return triples

    @classmethod
    def from_context(cls, context: Any) -> BusinessKnowledgeGraph:
        """Ingest complete AssistantContext into a multi-module BusinessKnowledgeGraph."""
        graph = cls()

        # 1. Profile & Core Business Entity
        profile_id = "node_profile_main"
        legal_name = getattr(context, "legal_name", "SMB")
        industry = getattr(context, "industry", "MSME")
        revenue = getattr(context, "annual_revenue_inr", 0)
        graph.add_node(
            KnowledgeNode(
                id=profile_id,
                category="profile",
                label=f"{legal_name} ({industry})",
                properties={
                    "revenue_inr": revenue,
                    "target_revenue_inr": getattr(context, "target_revenue_inr", 0),
                    "location": getattr(context, "location", "India"),
                    "business_type": getattr(context, "business_type", "SMB"),
                },
                evidence_id="biz_profile_revenue",
                priority_score=95.0,
            )
        )

        # 2. Score & Analytics
        score_val = getattr(context, "overall_business_score", 0)
        band_val = getattr(context, "band", "Developing")
        score_id = "node_analytics_score"
        graph.add_node(
            KnowledgeNode(
                id=score_id,
                category="analytics",
                label=f"Business Health Score: {score_val}/100 ({band_val})",
                properties={"score": score_val, "band": band_val},
                evidence_id="biz_profile_score",
                priority_score=90.0,
            )
        )
        graph.add_relationship(
            KnowledgeRelationship(
                source_id=profile_id,
                target_id=score_id,
                relation_type="has_score",
                description="Business score rating",
            )
        )

        # 3. DNA Archetype
        dna = getattr(context, "dna", None)
        if dna and getattr(dna, "archetype_title", ""):
            dna_id = "node_dna_archetype"
            graph.add_node(
                KnowledgeNode(
                    id=dna_id,
                    category="dna",
                    label=f"Business DNA: {dna.archetype_title} ({dna.match_score}% match)",
                    properties={"archetype_key": dna.archetype_key, "match_score": dna.match_score},
                    evidence_id="biz_dna",
                    priority_score=85.0,
                )
            )
            graph.add_relationship(
                KnowledgeRelationship(
                    source_id=profile_id,
                    target_id=dna_id,
                    relation_type="characterized_by",
                )
            )

        # 4. Critical Rules & Risks
        for rule in getattr(context, "rules", ()):
            rid = f"node_rule_{rule.id}"
            graph.add_node(
                KnowledgeNode(
                    id=rid,
                    category="risk" if rule.priority == "Critical" else "rule",
                    label=f"Risk Rule: {rule.title}",
                    properties={"priority": rule.priority, "impact": rule.estimated_impact, "reason": rule.reason},
                    evidence_id=f"rule_{rule.id}",
                    priority_score=92.0 if rule.priority == "Critical" else 70.0,
                )
            )
            graph.add_relationship(
                KnowledgeRelationship(
                    source_id=profile_id,
                    target_id=rid,
                    relation_type="exposed_to_risk",
                )
            )

        # 5. Recommendations
        for rec in getattr(context, "recommendations", ()):
            rec_id = f"node_rec_{rec.id}"
            graph.add_node(
                KnowledgeNode(
                    id=rec_id,
                    category="recommendation",
                    label=f"Recommendation: {rec.title}",
                    properties={
                        "category": rec.category,
                        "priority": rec.priority,
                        "estimated_score_gain": rec.estimated_score_gain,
                        "estimated_roi": rec.estimated_roi,
                        "timeline": rec.estimated_timeline,
                    },
                    evidence_id=f"rec_{rec.id}",
                    priority_score=88.0 if rec.priority == "High" else 75.0,
                )
            )
            graph.add_relationship(
                KnowledgeRelationship(
                    source_id=profile_id,
                    target_id=rec_id,
                    relation_type="recommended_action",
                )
            )

        # 6. Schemes
        for scheme in getattr(context, "schemes", ()):
            s_id = getattr(scheme, "scheme_id", getattr(scheme, "id", "scheme"))
            sch_id = f"node_scheme_{s_id}"
            authority = getattr(scheme, "authority", getattr(scheme, "ministry", "Government"))
            graph.add_node(
                KnowledgeNode(
                    id=sch_id,
                    category="scheme",
                    label=f"Government Scheme: {scheme.title}",
                    properties={"authority": authority, "match_score": getattr(scheme, "profile_match_score", 80)},
                    evidence_id=f"scheme_{s_id}",
                    priority_score=80.0,
                )
            )
            graph.add_relationship(
                KnowledgeRelationship(
                    source_id=profile_id,
                    target_id=sch_id,
                    relation_type="eligible_scheme",
                )
            )

        # 7. Products, Services, Export History, Goals & Challenges
        for idx, prod in enumerate(getattr(context, "products", ())):
            pid = f"node_product_{idx}"
            graph.add_node(
                KnowledgeNode(
                    id=pid,
                    category="product",
                    label=f"Product: {prod}",
                    priority_score=60.0,
                )
            )
            graph.add_relationship(
                KnowledgeRelationship(source_id=profile_id, target_id=pid, relation_type="offers_product")
            )

        for idx, exp in enumerate(getattr(context, "export_history", ())):
            eid = f"node_export_{idx}"
            graph.add_node(
                KnowledgeNode(
                    id=eid,
                    category="export",
                    label=f"Export Country: {exp}",
                    priority_score=65.0,
                )
            )
            graph.add_relationship(
                KnowledgeRelationship(source_id=profile_id, target_id=eid, relation_type="exports_to")
            )

        for idx, goal in enumerate(getattr(context, "goals", ())):
            gid = f"node_goal_{idx}"
            graph.add_node(
                KnowledgeNode(
                    id=gid,
                    category="goal",
                    label=f"Business Goal: {goal}",
                    priority_score=82.0,
                )
            )
            graph.add_relationship(
                KnowledgeRelationship(source_id=profile_id, target_id=gid, relation_type="pursues_goal")
            )

        return graph
