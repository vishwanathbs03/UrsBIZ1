"""KnowledgeRetrievalService - Sprint 7 Part 4.

The orchestrator that the chat endpoint depends on. It
composes the four moving parts:

  KnowledgeRetriever  -> ScoredArticle list
  Ranker             -> RankedArticle top-k
  CitationBuilder    -> Citation records
  KnowledgeContextBuilder -> KnowledgeContext envelope

The service is **stateless**. Construct one per request
(cheap) or reuse one across requests.

The service does NOT own the JSON catalog:
``KnowledgeService`` does. The retriever pulls articles
through the existing service so every rank call goes
through the same code path the public ``/knowledge``
endpoint uses.
"""
from __future__ import annotations

from typing import Any

from app.services.knowledge.repository import JsonKnowledgeRepository
from app.services.knowledge.service import KnowledgeService
from app.services.knowledge_retrieval.base import KnowledgeContext
from app.services.knowledge_retrieval.citation_builder import CitationBuilder
from app.services.knowledge_retrieval.context_builder import (
    KnowledgeContextBuilder,
)
from app.services.knowledge_retrieval.ranker import Ranker
from app.services.knowledge_retrieval.retriever import KnowledgeRetriever


# Default top-k when the caller does not override.
DEFAULT_TOP_K = 3


class KnowledgeRetrievalService:
    """The public face of the knowledge retrieval layer."""

    def __init__(
        self,
        knowledge_service: KnowledgeService,
        *,
        top_k: int = DEFAULT_TOP_K,
    ) -> None:
        self._knowledge = knowledge_service
        self._top_k = max(0, int(top_k))
        self._retriever = KnowledgeRetriever(
            self._knowledge._repo.list_articles()  # type: ignore[attr-defined]
        )
        self._ranker = Ranker(top_k=self._top_k)
        self._context_builder = KnowledgeContextBuilder(
            knowledge_service=self._knowledge,
            citation_builder=CitationBuilder(),
        )

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def retrieve(
        self,
        *,
        query: str,
        owner_context: dict | None = None,
        top_k: int | None = None,
    ) -> KnowledgeContext:
        """Run the full retrieval pipeline for one query.

        ``owner_context`` is the optional per-business boost
        payload (see :meth:`KnowledgeRetriever.score`).
        Returns an empty :class:`KnowledgeContext` when the
        query has no overlapping tokens.
        """
        scored = self._retriever.score(
            query=query,
            owner_context=owner_context or {},
        )
        total_candidates = len(self._retriever._articles)  # type: ignore[attr-defined]
        k = top_k if top_k is not None else self._top_k
        ranker = self._ranker if top_k is None else Ranker(top_k=k)
        ranked = ranker.rank(scored)
        return self._context_builder.build(
            query=query,
            ranked=ranked,
            total_candidates=total_candidates,
        )

    # ------------------------------------------------------------------ #
    # Convenience constructors
    # ------------------------------------------------------------------ #

    @classmethod
    def from_repository(
        cls,
        repository: JsonKnowledgeRepository,
        *,
        top_k: int = DEFAULT_TOP_K,
    ) -> "KnowledgeRetrievalService":
        """Build a service from a JSON repository (used by
        the chat endpoint's dependency factory)."""
        return cls(KnowledgeService(repository), top_k=top_k)

    # ------------------------------------------------------------------ #
    # Helpers for the chat service
    # ------------------------------------------------------------------ #

    @staticmethod
    def owner_context_from_twin(
        business: dict | None,
        recommendations: list[dict] | None,
    ) -> dict[str, Any]:
        """Project the owner's Twin + Recommendations into the
        boost context the retriever consumes.

        The chat service builds this once per request and
        passes it into :meth:`retrieve`. A ``None`` business
        yields an empty dict (no boost).
        """
        low_score_keys: list[str] = []
        if isinstance(business, dict):
            summary = business.get("health_summary") or {}
            if isinstance(summary, dict):
                for item in summary.get("scores") or []:
                    if not isinstance(item, dict):
                        continue
                    if str(item.get("level", "")).lower() == "low":
                        key = item.get("key")
                        if isinstance(key, str) and key:
                            low_score_keys.append(key.lower())
        rec_categories: list[str] = []
        for rec in recommendations or []:
            if not isinstance(rec, dict):
                continue
            cat = rec.get("category")
            if isinstance(cat, str) and cat:
                rec_categories.append(cat.lower())
        return {
            "low_score_keys": tuple(sorted(set(low_score_keys))),
            "recommendation_categories": tuple(sorted(set(rec_categories))),
        }