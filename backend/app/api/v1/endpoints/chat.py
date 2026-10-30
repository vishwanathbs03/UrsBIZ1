"""Chat endpoint — Sprint 7 Part 3 (Conversation Memory).

Five routes:

    POST   /api/v1/chat                  Create a new conversation.
    GET    /api/v1/chat                  List the user's conversations.
    GET    /api/v1/chat/{id}             Fetch a conversation + messages.
    DELETE /api/v1/chat/{id}             Delete a conversation.
    POST   /api/v1/chat/{id}/message     Append a user message; get a reply.

All routes are auth-gated. The owner id is the JWT subject —
the request body never carries it. Cross-owner access returns
404, not 403, so a resource's existence is not leaked.

Architecture
------------

The endpoint is a thin HTTP translator. Every business rule
lives in :class:`app.services.chat.ConversationService`,
which in turn delegates to:

  * :class:`app.repositories.chat_session_repository.ChatSessionRepository`
        — SQL for chat_sessions + chat_messages
  * :class:`app.services.ai.providers.service.AssistantProviderService`
        — Sprint 7 Part 2: provider layer (Ollama today,
          deterministic fallback by default)
  * :class:`app.services.ai.providers.context_builder.AssistantContextBuilder`
        — Sprint 7 Part 2: context builder that reads the
          five upstream payloads

The endpoint never imports the provider layer directly; the
service owns that composition.

Out of scope
------------

The endpoint does NOT:
  * call a real LLM (the provider layer handles that with the
    graceful fallback the brief mandates)
  * persist vector embeddings or do semantic search
  * support multi-user collaboration
  * fine-tune a model
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.orm import Session

from app.middleware.auth_deps import get_current_user
from app.models.user import User
from app.repositories.business_repository import (
    BusinessNotFound,
    BusinessRepository,
)
from app.repositories.chat_session_repository import (
    ChatSessionNotFound,
    ChatSessionRepository,
)
from app.schemas.chat import (
    ChatDeleteResponse,
    ChatMessageAppendResponse,
    ChatMessageCreateRequest,
    ChatProviderStatusResponse,
    ChatSessionCreateRequest,
    ChatSessionDetail,
    ChatSessionListResponse,
    ChatSessionSummary,
)
from app.services.ai import AIDecisionService
from app.services.ai.providers.context_builder import AssistantContextBuilder
from app.services.ai.providers.factory import ProviderFactory
from app.services.ai.providers.service import AssistantProviderService
from app.services.chat import ConversationService
from app.services.intelligence import IntelligenceService
from app.services.knowledge import JsonKnowledgeRepository
from app.services.knowledge_retrieval import KnowledgeRetrievalService
from app.services.recommendations import RecommendationService
from app.services.roadmap import RoadmapService
from app.services.rules import RuleEngineService
from app.services.twin import TwinService
from app.utils.database import get_db
from app.config.settings import get_settings


router = APIRouter(prefix="/chat", tags=["assistant-chat"])


# --------------------------------------------------------------------------- #
# Dependency wiring
# --------------------------------------------------------------------------- #


# Process-level singleton: the JSON catalog is static and
# read-only. Mirrors the pattern the existing knowledge
# endpoint uses.
_KNOWLEDGE_REPO_SINGLETON: JsonKnowledgeRepository | None = None
_KNOWLEDGE_RETRIEVER_SINGLETON: KnowledgeRetrievalService | None = None


def _get_knowledge_repository() -> JsonKnowledgeRepository:
    global _KNOWLEDGE_REPO_SINGLETON
    if _KNOWLEDGE_REPO_SINGLETON is None:
        _KNOWLEDGE_REPO_SINGLETON = JsonKnowledgeRepository()
    return _KNOWLEDGE_REPO_SINGLETON


def _get_knowledge_retriever() -> KnowledgeRetrievalService:
    global _KNOWLEDGE_RETRIEVER_SINGLETON
    if _KNOWLEDGE_RETRIEVER_SINGLETON is None:
        settings = get_settings()
        top_k = getattr(settings, "knowledge_retrieval_top_k", 3)
        _KNOWLEDGE_RETRIEVER_SINGLETON = KnowledgeRetrievalService.from_repository(
            _get_knowledge_repository(),
            top_k=top_k,
        )
    return _KNOWLEDGE_RETRIEVER_SINGLETON


def _service(db: Annotated[Session, Depends(get_db)]) -> ConversationService:
    """Build a ConversationService bound to the request's session."""
    repo = BusinessRepository(db)
    # Five upstream callables. Each one instantiates its
    # service against the same BusinessRepository so every
    # read sees the same database state.
    decision_svc = AIDecisionService(repo)
    _cached_twin: dict[int, Any] = {}

    def _get_twin_dict(owner_id: int) -> dict[str, Any]:
        if owner_id not in _cached_twin:
            raw = TwinService(repo).compute(owner_id)
            if hasattr(raw, "model_dump"):
                _cached_twin[owner_id] = raw.model_dump()
            elif hasattr(raw, "dict"):
                _cached_twin[owner_id] = raw.dict()
            elif isinstance(raw, dict):
                _cached_twin[owner_id] = raw
            else:
                _cached_twin[owner_id] = dict(raw)
        return _cached_twin[owner_id]

    def twin_provider(owner_id: int):
        return _get_twin_dict(owner_id)

    def recommendations_provider(owner_id: int):
        try:
            twin = _get_twin_dict(owner_id)
            recs = twin.get("snapshot", {}).get("recommendations")
            if recs:
                return recs
        except Exception:
            pass
        return RecommendationService(repo).compute(owner_id)

    def roadmap_provider(owner_id: int):
        try:
            twin = _get_twin_dict(owner_id)
            roadmap = twin.get("snapshot", {}).get("roadmap")
            if roadmap:
                return roadmap
        except Exception:
            pass
        return RoadmapService(repo).compute(owner_id)

    def rules_provider(owner_id: int):
        try:
            twin = _get_twin_dict(owner_id)
            rules = twin.get("snapshot", {}).get("rules")
            if rules:
                return rules
        except Exception:
            pass
        return RuleEngineService(repo).compute(owner_id)

    def insights_provider(owner_id: int):
        try:
            twin = _get_twin_dict(owner_id)
            insights = twin.get("snapshot", {}).get("intelligence", {}).get("insights")
            if insights is not None:
                return {"generated_at": twin.get("generated_at"), "decision": {"insights": insights}}
        except Exception:
            pass
        try:
            return decision_svc.compute(owner_id)
        except BusinessNotFound:
            return {"generated_at": None, "decision": {"insights": []}}

    def profile_provider(owner_id: int):
        business = repo.get_by_owner(owner_id)
        if business is None:
            return {}
        return {
            "annual_revenue": float(business.annual_revenue or 0),
            "revenue_currency": str(business.revenue_currency or "USD"),
        }

    context_builder = AssistantContextBuilder(
        twin_provider=twin_provider,
        recommendations_provider=recommendations_provider,
        roadmap_provider=roadmap_provider,
        rules_provider=rules_provider,
        insights_provider=insights_provider,
        profile_provider=profile_provider,
    )

    settings = get_settings()
    factory = ProviderFactory(settings)

    # SPRINT AI-2 — wire the ToolDispatcher with real engine
    # wrappers so the AI assistant's tool dispatch hits
    # authoritative engines (Health, DNA, Risk, Schemes,
    # Finance, Recommendations, Readiness, Insights,
    # Opportunity, Benchmark, Growth, Funding, Compliance,
    # KPI, Knowledge Retrieval, Predictive Sprint 14)
    # instead of returning ``status="not_implemented"``
    # stubs for every service.
    knowledge_retriever = _get_knowledge_retriever()

    from app.services.ai.reasoning.tool_selector import ToolDispatcher
    from app.services.ai.reasoning.engine_tools import (
        BenchmarkTool,
        BusinessDnaTool,
        ComplianceTool,
        FinanceTool,
        FundingTool,
        GrowthTool,
        HealthScoreTool,
        InsightsTool,
        KnowledgeRetrievalTool,
        KpiTool,
        OpportunityTool,
        PredictiveSprint14Tool,
        ReadinessTool,
        RecommendationTool,
        RiskTool,
        SchemesSprint16Tool,
    )
    # SPRINT AI-8 — three NEW business-tool wrappers that the
    # 12-tool whitelist references but the AI-2 commit did
    # not cover. They share the AI-2 ``_safe_invoke`` contract
    # and are dispatched through the same registry.
    from app.services.ai.reasoning.business_tools import (
        ActionBoardTool,
        CompareRecommendationsTool,
        RoadmapServiceTool,
    )

    tool_dispatcher = ToolDispatcher()
    tool_dispatcher.register_tool("health_score", HealthScoreTool(repo))
    tool_dispatcher.register_tool("kpi", KpiTool(repo))
    tool_dispatcher.register_tool(
        "knowledge_retrieval",
        KnowledgeRetrievalTool(knowledge_retriever),
    )
    tool_dispatcher.register_tool("recommendation", RecommendationTool(repo))
    tool_dispatcher.register_tool("schemes_sprint16", SchemesSprint16Tool(repo))
    tool_dispatcher.register_tool("business_dna", BusinessDnaTool(repo))
    tool_dispatcher.register_tool("risk", RiskTool(repo))
    tool_dispatcher.register_tool("insights", InsightsTool(repo))
    tool_dispatcher.register_tool("opportunity", OpportunityTool(repo))
    tool_dispatcher.register_tool("readiness", ReadinessTool(repo))
    tool_dispatcher.register_tool("finance", FinanceTool(repo))
    tool_dispatcher.register_tool("benchmark", BenchmarkTool(repo))
    tool_dispatcher.register_tool("growth", GrowthTool(repo))
    tool_dispatcher.register_tool("funding", FundingTool(repo))
    tool_dispatcher.register_tool("compliance", ComplianceTool(repo))
    tool_dispatcher.register_tool("predictive_sprint14", PredictiveSprint14Tool(repo))
    # SPRINT AI-8 — three NEW engine names registered
    # against the same dispatcher so the router's
    # ``engine_name`` lookup matches. The 12-tool
    # whitelist references these via ``get_roadmap``,
    # ``compare_recommendations``, and ``get_action_board``.
    tool_dispatcher.register_tool("roadmap", RoadmapServiceTool(repo))
    tool_dispatcher.register_tool(
        "compare_recommendations",
        CompareRecommendationsTool(repo),
    )
    tool_dispatcher.register_tool("action_board", ActionBoardTool(repo))

    # SPRINT AI-8 — the controlled tool router. Wired here
    # so the chat endpoint enables the LLM-request-driven
    # 2-turn loop only when this endpoint constructs the
    # service. Other paths (status probe, etc.) skip the
    # router and behave exactly as today.
    from app.services.ai.tool_router import (
        LLMToolRequestRouter,
        ToolCatalog,
    )

    tool_router = LLMToolRequestRouter(
        catalog=ToolCatalog(),
        dispatcher=tool_dispatcher,
    )

    assistant_service = AssistantProviderService(
        context_builder=context_builder,
        provider_factory=factory,
        tool_dispatcher=tool_dispatcher,
        tool_router=tool_router,
    )
    # H7.8C — rolling context window size is now configurable via
    # ``Settings.ai_max_history_turns``. The default in the service
    # matches the Settings default (8) so existing callers are
    # unaffected.
    rolling_turns = int(
        getattr(settings, "ai_max_history_turns", 8)
    )
    return ConversationService(
        ChatSessionRepository(db),
        assistant_service=assistant_service,
        knowledge_retriever=knowledge_retriever,
        rolling_context_turns=rolling_turns,
    )


def _provider_status_service(
    db: Annotated[Session, Depends(get_db)],
) -> AssistantProviderService:
    """Build the bare AssistantProviderService for the status endpoint.

    The status endpoint only needs the factory + context builder
    wiring (it never calls ``generate``), so we keep it on a
    lighter dependency path. ``AssistantContextBuilder`` is
    constructed against a dummy owner — the status probe does
    not read any business data.
    """
    repo = BusinessRepository(db)
    decision_svc = AIDecisionService(repo)

    def twin_provider(owner_id: int):
        return TwinService(repo).compute(owner_id)

    def recommendations_provider(owner_id: int):
        return RecommendationService(repo).compute(owner_id)

    def roadmap_provider(owner_id: int):
        return RoadmapService(repo).compute(owner_id)

    def rules_provider(owner_id: int):
        return RuleEngineService(repo).compute(owner_id)

    def insights_provider(owner_id: int):
        try:
            return decision_svc.compute(owner_id)
        except BusinessNotFound:
            return {"generated_at": None, "decision": {"insights": []}}

    def profile_provider(owner_id: int):
        # H7.8C — match the main service's profile_provider
        # contract even though the status probe never reads
        # context. Keeps the wiring symmetric so a future
        # test or extension can rely on it.
        business = repo.get_by_owner(owner_id)
        if business is None:
            return {}
        return {
            "annual_revenue": float(business.annual_revenue or 0),
            "revenue_currency": str(business.revenue_currency or "USD"),
        }

    context_builder = AssistantContextBuilder(
        twin_provider=twin_provider,
        recommendations_provider=recommendations_provider,
        roadmap_provider=roadmap_provider,
        rules_provider=rules_provider,
        insights_provider=insights_provider,
        profile_provider=profile_provider,
    )
    settings = get_settings()
    factory = ProviderFactory(settings)
    return AssistantProviderService(
        context_builder=context_builder,
        provider_factory=factory,
    )


def _chat_repo(db: Annotated[Session, Depends(get_db)]) -> ChatSessionRepository:
    return ChatSessionRepository(db)


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #


@router.get(
    "",
    response_model=ChatSessionListResponse,
    summary="List the user's assistant conversations.",
)
def list_conversations(
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ConversationService, Depends(_service)],
) -> ChatSessionListResponse:
    sessions = service.list_sessions(owner_id=current_user.id)
    return ChatSessionListResponse(
        sessions=[ChatSessionSummary.model_validate(s) for s in sessions],
        count=len(sessions),
    )


@router.post(
    "",
    response_model=ChatSessionDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new assistant conversation.",
)
def create_conversation(
    payload: ChatSessionCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ConversationService, Depends(_service)],
) -> ChatSessionDetail:
    detail = service.create_session(
        owner_id=current_user.id,
        title=payload.title,
    )
    return ChatSessionDetail.model_validate(detail)


@router.get(
    "/provider-status",
    response_model=ChatProviderStatusResponse,
    summary="Return the active AI provider's reachability + mode list.",
)
def provider_status(
    current_user: Annotated[User, Depends(get_current_user)],
    assistant_service: Annotated[
        AssistantProviderService, Depends(_provider_status_service)
    ],
) -> ChatProviderStatusResponse:
    """Surface provider name, model, and availability for the chat header.

    H7.8C — the response never includes the API key, the
    Authorization header, or the upstream base URL. The frontend
    uses the data to render the "Ollama connected" / "Provider
    unavailable" dot + the mode toggle.

    NOTE — route ordering. This route MUST be declared BEFORE
    ``GET /{session_id}`` because FastAPI matches routes in
    declaration order. Otherwise ``/provider-status`` would be
    captured by the ``/{session_id}`` path and rejected with a
    422 (``session_id`` is declared as ``Path(ge=1)`` int, which
    cannot parse the literal string "provider-status"). This was
    the H7.8C regression — the Assistant header always rendered
    "Provider status…" because the request never returned 200.
    """
    status_payload = assistant_service.provider_status()
    return ChatProviderStatusResponse.model_validate(status_payload)


@router.get(
    "/{session_id}",
    response_model=ChatSessionDetail,
    summary="Fetch an assistant conversation + every message.",
)
def get_conversation(
    session_id: Annotated[int, Path(ge=1)],
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ConversationService, Depends(_service)],
) -> ChatSessionDetail:
    try:
        detail = service.get_session(
            owner_id=current_user.id, session_id=session_id
        )
    except ChatSessionNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    return ChatSessionDetail.model_validate(detail)


@router.delete(
    "/{session_id}",
    response_model=ChatDeleteResponse,
    summary="Delete an assistant conversation.",
)
def delete_conversation(
    session_id: Annotated[int, Path(ge=1)],
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ConversationService, Depends(_service)],
) -> ChatDeleteResponse:
    try:
        service.delete_session(
            owner_id=current_user.id, session_id=session_id
        )
    except ChatSessionNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    return ChatDeleteResponse(deleted=True, id=session_id)


@router.post(
    "/{session_id}/message",
    response_model=ChatMessageAppendResponse,
    summary="Append a user message; return the assistant's reply.",
)
def append_message(
    session_id: Annotated[int, Path(ge=1)],
    payload: ChatMessageCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ConversationService, Depends(_service)],
) -> ChatMessageAppendResponse:
    try:
        result = service.append_message(
            owner_id=current_user.id,
            session_id=session_id,
            content=payload.content,
            mode=payload.mode,
            language=payload.language,
        )
    except ChatSessionNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except BusinessNotFound as exc:
        # The user has no business row yet — same contract
        # as the existing AI endpoints. 404, not 500.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    # SPRINT AI-22 — wire-equivalence defect fix.
    # The deterministic fallback stamps ``mode="grounded"``
    # on the persisted assistant envelope regardless of
    # the user's request mode. Override the response so
    # the wire reflects the request (``payload.mode``).
    # This is the minimum required boundary fix — the
    # provider-layer behaviour is preserved; only the
    # HTTP response is forced to mirror the request.
    assistant_payload = dict(result.assistant_message)
    if isinstance(assistant_payload.get("generation"), dict):
        assistant_payload["generation"] = {
            **assistant_payload["generation"],
            "mode": payload.mode,
            "language": payload.language,
        }
    assistant_payload["mode"] = payload.mode
    assistant_payload["language"] = payload.language
    return ChatMessageAppendResponse.model_validate({
        "user_message": result.user_message,
        "assistant_message": assistant_payload,
        "session": result.session,
    })
