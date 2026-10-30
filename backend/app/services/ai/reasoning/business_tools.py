"""SPRINT AI-8 — Three additional ToolInterface wrappers.

AI-2 (SPRINT AI-2) shipped 16 real ``ToolInterface``
wrappers covering every existing AI engine. The AI-8 brief
calls for 12 whitelisted tools; 9 of them map cleanly onto
those 16 wrappers, but 3 (``get_roadmap``,
``compare_recommendations``, ``get_action_board``) need NEW
shims that the AI-2 commit didn't cover. This module
houses those three new wrappers.

Wrapper anatomy mirrors the AI-2 contract::

    class XTool:
        name = "x"
        def __init__(self, repo) -> None: ...
        def invoke(self, *, owner_id, call, context) -> ToolResult:
            ... translate exceptions → status="skipped"/"error"

Every wrapper takes a ``BusinessRepository`` (where the
underlying service expects one) OR the upstream singleton
directly. None of these wrappers hold onto a session;
they receive it through the constructor and resolve the
service on each call.
"""
from __future__ import annotations

import time
from typing import Any

from app.repositories.business_repository import (
    BusinessNotFound,
    BusinessRepository,
)
from app.services.ai.reasoning.engine_tools import (
    _error,
    _ok,
    _skipped,
    _to_dict,
)
from app.services.ai.reasoning.tool_selector import ToolResult


# --------------------------------------------------------------------------- #
# 1. RoadmapServiceTool
# --------------------------------------------------------------------------- #


class RoadmapServiceTool:
    """ToolInterface wrapper for :class:`RoadmapService`.

    AI-2 did not ship a roadmap wrapper (the AI-2 plan did
    not enumerate the roadmap service as a chat-tool — at
    the time it was only consumed by the dashboard). AI-8
    fills the gap so the LLM may request a quarterly
    roadmap under the ``get_roadmap`` whitelisted tool.

    The ``call.inputs`` may carry ``horizon_months`` (1..60)
    — passed through to the underlying engine where
    supported; ignored by the current implementation.
    """

    name = "roadmap"

    def __init__(self, repo: BusinessRepository) -> None:
        from app.services.roadmap.service import RoadmapService

        self._service = RoadmapService(repo)

    def invoke(self, *, owner_id: int, call: Any, context: Any) -> ToolResult:
        t0 = time.perf_counter()
        try:
            result = self._service.compute(owner_id)
            return _ok(self.name, result, t0)
        except BusinessNotFound:
            return _skipped(self.name, "business_not_found")
        except Exception as exc:
            return _error(self.name, exc, t0)


# --------------------------------------------------------------------------- #
# 2. CompareRecommendationsTool
# --------------------------------------------------------------------------- #


class CompareRecommendationsTool:
    """ToolInterface wrapper that compares recommendations side-by-side.

    Given a list of recommendation IDs (``call.inputs['recommendation_ids']``),
    the tool reads the user's full recommendation set and
    produces a side-by-side comparison row per ID. The
    comparison shape is::

        {
          "compared": [
            {"id": "rec_x", "title": ..., "priority": ...,
             "score_gain": ..., "timeline": ..., "category": ...},
            ...
          ],
          "missing": ["rec_y", ...]
        }

    The tool never invents a recommendation — ``missing``
    carries every ID the user supplied that the service
    did not surface (so the LLM can narrate "you asked about
    rec_y but I do not have it on file").
    """

    name = "compare_recommendations"

    def __init__(self, repo: BusinessRepository) -> None:
        from app.services.recommendation_service import (
            RecommendationService,
        )

        self._service = RecommendationService(repo)

    def invoke(self, *, owner_id: int, call: Any, context: Any) -> ToolResult:
        t0 = time.perf_counter()
        try:
            inputs = getattr(call, "inputs", {}) or {}
            requested = tuple(inputs.get("recommendation_ids") or ())
            payload = self._service.compute(owner_id)
            indexed = _index_recommendations(payload)
            compared, missing = _compare_recommended(requested, indexed)
            return _ok(
                self.name,
                {"compared": compared, "missing": list(missing)},
                t0,
            )
        except BusinessNotFound:
            return _skipped(self.name, "business_not_found")
        except Exception as exc:
            return _error(self.name, exc, t0)


def _index_recommendations(payload: Any) -> dict[str, dict[str, Any]]:
    """Turn a recommendation-engine payload into ``{id: row}``.

    Tolerant of Pydantic / dataclass / dict shapes — uses
    :func:`_to_dict` from :mod:`engine_tools` to normalise.
    """
    out: dict[str, dict[str, Any]] = {}
    items: list[Any] = []
    if isinstance(payload, dict):
        # The recommendation engine typically nests under a
        # ``recommendations`` key; some flavours store under
        # ``items``. We accept either.
        if isinstance(payload.get("recommendations"), list):
            items = list(payload["recommendations"])
        elif isinstance(payload.get("items"), list):
            items = list(payload["items"])
    elif isinstance(payload, list):
        items = list(payload)
    for idx, raw in enumerate(items):
        rec = _to_dict(raw)
        if not isinstance(rec, dict):
            continue
        rid = (
            rec.get("recommendation_id")
            or rec.get("id")
            or rec.get("rec_id")
            or f"rec_{idx:03d}"
        )
        out[str(rid)] = rec
    return out


def _compare_recommended(
    requested: tuple[str, ...],
    indexed: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], tuple[str, ...]]:
    """Return ``(compared_rows, missing_ids)``."""

    compared: list[dict[str, Any]] = []
    missing: list[str] = []
    for rid in requested:
        rid_str = str(rid)
        rec = indexed.get(rid_str)
        if rec is None:
            missing.append(rid_str)
            continue
        compared.append(
            {
                "id": rid_str,
                "title": rec.get("title") or rec.get("name") or "",
                "priority": rec.get("priority") or "",
                "estimated_score_gain": rec.get("estimated_score_gain"),
                "estimated_timeline": rec.get("estimated_timeline") or "",
                "category": rec.get("category") or "",
            }
        )
    return compared, tuple(missing)


# --------------------------------------------------------------------------- #
# 3. ActionBoardTool
# --------------------------------------------------------------------------- #


class ActionBoardTool:
    """ToolInterface wrapper for the action-board route payload.

    AI-2 did not include the action-board wrapper because
    the board was consumed only by the dashboard's static
    page. AI-8 makes it queryable through
    ``get_action_board`` so the LLM can narrate the user's
    outstanding action items alongside forecasts and
    recommendations.
    """

    name = "action_board"

    def __init__(self, repo: BusinessRepository) -> None:
        # ActionItemRepository takes a BusinessRepository
        # (it owns no DB session directly). The chat
        # endpoint constructs it the same way the existing
        # action-board endpoint does.
        from app.services.action_board_service import ActionBoardService

        # The action-board service expects an
        # ActionItemRepository, not a BusinessRepository.
        # The chat endpoint constructs one explicitly;
        # here we accept just enough to defer the wiring
        # to the endpoint (the service itself is stateless
        # w.r.t. DB sessions).
        self._service_factory = lambda b_repo: ActionBoardService(
            _make_action_item_repo(b_repo)
        )
        self._repo = repo

    def invoke(self, *, owner_id: int, call: Any, context: Any) -> ToolResult:
        t0 = time.perf_counter()
        try:
            service = self._service_factory(self._repo)
            board = service.get_board(owner_id)
            return _ok(self.name, board, t0)
        except BusinessNotFound:
            return _skipped(self.name, "business_not_found")
        except Exception as exc:
            return _error(self.name, exc, t0)


def _make_action_item_repo(business_repo: BusinessRepository) -> Any:
    """Build an ``ActionItemRepository`` for the action-board tool.

    Import is deferred so this module can be loaded without
    pulling the action-board package into the chat-endpoint
    cold path. The signature is whatever
    :class:`ActionBoardService` accepts — today that is an
    ``ActionItemRepository`` instance bound to the same
    ``Session`` that produced the ``BusinessRepository``.
    """
    try:
        # Real construction path. The chat endpoint passes
        # in a BusinessRepository bound to a SQLAlchemy
        # session; we resolve the same session and build an
        # ActionItemRepository against it.
        session = getattr(business_repo, "_session", None) or getattr(
            business_repo, "session", None
        )
        if session is not None:
            from app.repositories.action_item_repository import (
                ActionItemRepository,
            )

            return ActionItemRepository(session)
    except Exception:  # noqa: BLE001 — fallback below
        pass

    # Fallback: build against whatever session-like attr
    # the repo exposes. Tests can plug a mock here by
    # subclassing ``BusinessRepository``.
    try:
        from app.repositories.action_item_repository import (
            ActionItemRepository,
        )

        session = getattr(business_repo, "_session", None) or getattr(
            business_repo, "session", None
        )
        return ActionItemRepository(session) if session is not None else None
    except Exception:  # noqa: BLE001
        return None


# --------------------------------------------------------------------------- #
# All NEW wrappers
# --------------------------------------------------------------------------- #


ALL_BUSINESS_TOOL_CLASSES = (
    RoadmapServiceTool,
    CompareRecommendationsTool,
    ActionBoardTool,
)


__all__ = [
    "RoadmapServiceTool",
    "CompareRecommendationsTool",
    "ActionBoardTool",
    "ALL_BUSINESS_TOOL_CLASSES",
]
