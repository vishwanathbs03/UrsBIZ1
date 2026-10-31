"""EvidenceRetriever — Sprint H8.11.

Given a :class:`ReasoningPlan` and the existing
:class:`EvidenceRegistry`, rank the registry's entries by
their relevance to the detected intent and the plan's
prioritised KG nodes. Return a new
:class:`RankedEvidence` dataclass the prompt builder
consumes.

Design rules
------------

  * **No mutation of the registry.** The
    :class:`EvidenceRegistry` is ``__slots__``-frozen and
    immutable. The retriever produces a NEW ordered tuple of
    :class:`EvidenceEntry` references and a metadata
    dictionary the prompt builder can render. The registry's
    ``by_id`` / ``by_kind`` indexes remain untouched.

  * **Intent-aware weight boosts.** A small per-intent
    table — :data:`_INTENT_WEIGHT_BOOSTS` — applies a
    multiplier per :class:`EvidenceKind`. A
    ``reach_revenue_target`` prompt gets a 1.5× boost on
    ``SCORE`` entries and a 1.4× boost on
    ``RECOMMENDATION`` entries. A ``government_schemes``
    prompt gets a 1.8× boost on ``SCHEME`` entries. The
    ``general`` intent uses 1.0× across the board.

  * **KG priority boost.** Entries whose ``id`` matches a
    KG node's ``evidence_id`` get an additive bonus
    proportional to the node's ``priority_score``. The
    boost is small (``0.2 × priority/100``) so it nudges
    but never dominates the intent boost.

  * **Stable ordering.** Entries are sorted by ``(score
    desc, insertion order asc)``. The retriever never
    shuffles equal-score entries randomly; two calls with
    the same inputs produce the same :class:`RankedEvidence`.

  * **Bounded output.** The retriever caps the result at
    ``top_n`` (default 25) — matching the registry's
    per-request evidence cap. The original count is
    preserved on ``RankedEvidence.total`` so the prompt
    builder can render a ``(N of M entries shown)`` footer.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.services.ai.providers.evidence_registry import (
    EvidenceEntry,
    EvidenceKind,
    EvidenceRegistry,
)


# Default cap on returned entries. Matches the cap the
# existing ``EvidenceRegistry`` builds into the prompt.
_DEFAULT_TOP_N = 25


# --------------------------------------------------------------------------- #
# Intent-aware weight boosts
# --------------------------------------------------------------------------- #
#
# Each value is a multiplier applied to an entry's base
# score (1.0). The retriever multiplies the base score by
# the boost for the entry's :class:`EvidenceKind` (default
# 1.0 when the kind is not in the table for the intent).
# Keys are the string values of :class:`QuestionIntent`.

_INTENT_WEIGHT_BOOSTS: dict[str, dict[EvidenceKind, float]] = {
    "reach_revenue_target": {
        EvidenceKind.SCORE: 1.5,
        EvidenceKind.RECOMMENDATION: 1.4,
        EvidenceKind.FORECAST: 1.3,
        EvidenceKind.RULE: 1.2,
    },
    "biggest_weakness": {
        EvidenceKind.RULE: 1.6,
        EvidenceKind.INSIGHT: 1.4,
        EvidenceKind.SCORE: 1.2,
    },
    "government_schemes": {
        EvidenceKind.SCHEME: 1.8,
    },
    "twelve_month_roadmap": {
        EvidenceKind.RECOMMENDATION: 1.4,
        EvidenceKind.INSIGHT: 1.2,
    },
    "export_expansion": {
        EvidenceKind.SCHEME: 1.3,
        EvidenceKind.RECOMMENDATION: 1.3,
    },
    # ``general`` intentionally omitted — the retriever
    # applies 1.0 across the board when the intent key is
    # missing from the table.
}


# --------------------------------------------------------------------------- #
# Result dataclass
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class RankedEvidence:
    """The retriever's output — a re-ordered view over a registry.

    Attributes
    ----------
    entries:
        The registry entries in relevance order. The
        underlying :class:`EvidenceEntry` objects are
        passed by reference (the registry is frozen).
    total:
        Total number of entries in the registry before
        truncation. The prompt builder renders a
        ``(N of M entries shown)`` footer using this.
    intent_boosts_applied:
        Snapshot of the intent-weight table the retriever
        used, with :class:`EvidenceKind` enum values
        converted to strings for JSON serialisation.
    truncated:
        True iff ``len(entries) < total``. The prompt
        builder adds the footer only when truncated.
    intent:
        The intent string the retriever used to look up
        the boost table. Echoed so the prompt builder can
        render it in the trace block without re-reading
        the plan.
    """

    entries: tuple[EvidenceEntry, ...]
    total: int
    intent_boosts_applied: dict[str, float] = field(default_factory=dict)
    truncated: bool = False
    intent: str = "general"


# --------------------------------------------------------------------------- #
# Retriever
# --------------------------------------------------------------------------- #


class EvidenceRetriever:
    """Rank a registry's entries by intent + KG relevance.

    Construction
    ------------

    ``top_n`` is the cap on returned entries. The default
    25 matches the per-request evidence cap the prompt
    builder already uses. Tests can override to verify
    truncation behaviour.
    """

    def __init__(self, *, top_n: int = _DEFAULT_TOP_N) -> None:
        self._top_n = max(1, int(top_n))

    # ---- public API -------------------------------------------------- #

    def rank(
        self,
        *,
        context: Any,
        registry: EvidenceRegistry,
        reasoning_plan: Any,
        top_n: int | None = None,
    ) -> RankedEvidence:
        """Return a :class:`RankedEvidence` ordered by relevance.

        Parameters
        ----------
        context:
            The :class:`AssistantContext` the registry was
            built from. Used to look up the KG node priority
            for entries whose ``id`` matches a node's
            ``evidence_id``.
        registry:
            The :class:`EvidenceRegistry` to rank. Not
            mutated.
        reasoning_plan:
            The :class:`ReasoningPlan` the engine emitted.
            The retriever reads ``plan.intent`` and
            ``plan.subgraph_node_ids``.
        top_n:
            Optional override for the entry cap. Defaults
            to the constructor's ``top_n``.
        """
        intent_value = getattr(reasoning_plan, "intent", "general") or "general"
        boost_table = _INTENT_WEIGHT_BOOSTS.get(intent_value, {})

        # Build the node-priority map once — we may look
        # up many nodes for many entries.
        node_priority = self._build_node_priority_map(
            context=context,
            subgraph_ids=tuple(getattr(reasoning_plan, "subgraph_node_ids", ()) or ()),
        )

        scored: list[tuple[float, int, EvidenceEntry]] = []
        for index, entry in enumerate(registry.all()):
            base = 1.0
            boost = boost_table.get(entry.kind, 1.0)
            score = base * float(boost)
            # KG boost: when the entry id matches a node
            # priority (by entry.id OR node.evidence_id),
            # add a small additive bonus. Capped at +0.2.
            priority = node_priority.get(entry.id, 0.0)
            if priority:
                score += min(0.2, 0.2 * (priority / 100.0))
            scored.append((score, index, entry))

        # Sort by (score desc, insertion order asc). Use
        # tuple comparison; we negate the score for desc.
        scored.sort(key=lambda t: (-t[0], t[1]))

        cap = max(1, int(top_n)) if top_n else self._top_n
        top = [t[2] for t in scored[:cap]]

        boosts_applied = {k.value: v for k, v in boost_table.items()}

        return RankedEvidence(
            entries=tuple(top),
            total=registry.count,
            intent_boosts_applied=boosts_applied,
            truncated=len(top) < registry.count,
            intent=intent_value,
        )

    # ---- internal helpers ------------------------------------------- #

    @staticmethod
    def _build_node_priority_map(
        *,
        context: Any,
        subgraph_ids: tuple[str, ...],
    ) -> dict[str, float]:
        """Return ``{entry_id: priority_score}`` for every relevant KG node.

        The retriever only looks up node ids the engine
        surfaced in the plan's sub-graph. Each node may
        contribute two keys to the map — its own ``id``
        and its ``evidence_id`` (when present) — so an
        entry whose ``id`` matches either is boosted.
        """
        if not subgraph_ids:
            return {}
        kg = getattr(context, "knowledge_graph", None)
        if kg is None or not hasattr(kg, "get_node"):
            return {}
        out: dict[str, float] = {}
        for nid in subgraph_ids:
            try:
                node = kg.get_node(nid)
            except Exception:
                continue
            if node is None:
                continue
            score = float(getattr(node, "priority_score", 0.0) or 0.0)
            if score <= 0:
                continue
            out[nid] = score
            evid = getattr(node, "evidence_id", None)
            if evid:
                # The node may boost an evidence entry
                # even when the entry id differs from the
                # node id; this is how the H8.2 KG
                # cross-references the registry.
                out[evid] = max(out.get(evid, 0.0), score)
        return out