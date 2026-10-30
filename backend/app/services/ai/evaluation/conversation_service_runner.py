"""SPRINT AI-18 — Universal AI Evaluation + Freeze Gate.

ConversationServiceRunner — drives the production
:class:`ConversationService.append_message` path end-to-end.

The existing :class:`EvaluationRunner` (in ``runner.py``) drives
:func:`AssistantProviderService.generate` directly with a stub
context builder, bypassing the chat façade. The brief's PART 8
requires the runner to drive the *production* chat path —
meaning every prompt must go through:

  ConversationService.append_message
  → session lookup
  → user message persistence
  → rolling-history compose
  → AssistantContextBuilder.build
  → proactive missing-data detect
  → AssistantProviderService.generate
  → assistant message persistence
  → session touch (title / summary / last_model / fallback_used)

This module re-uses the existing
:class:`AssistantContextBuilder` (it accepts an injected
``AssistantContext`` and short-circuits the upstream repositories)
and wires a :class:`ConversationService` on top of it. The
``ChatSessionRepository`` is substituted with an in-memory fake
so the runner never touches the real database.

The runner returns an :class:`EvaluationResult` shaped exactly
like the one :class:`EvaluationRunner` returns, so the existing
:class:`MetricsCalculator` consumes the results without any
change.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

from app.services.ai.evaluation.runner import (
    EvaluationResult,
    EvaluationRunner,
)
from app.services.ai.evaluation.data_quality_profiles import (
    DataQualityProfile,
    all_profiles,
)
from app.services.ai.providers.base import (
    AssistantContext,
    DeterministicFallbackProvider,
)
from app.services.ai.providers.context_builder import (
    AssistantContextBuilder,
)
from app.services.ai.providers.service import AssistantProviderService
from app.services.chat.conversation_service import (
    ConversationService,
)


# --------------------------------------------------------------------------- #
# In-memory ChatSessionRepository — no DB writes
# --------------------------------------------------------------------------- #


class _SessionRow:
    """Lightweight stand-in for the SQLAlchemy row returned by
    ``ChatSessionRepository.create_session`` / ``get_session``.

    The production façade in ``conversation_service.py`` mixes
    attribute access (``session.title``, ``session.messages``)
    and dict-style projection (via ``_session_summary`` and
    ``_message_payload``). The shim therefore exposes BOTH
    surfaces: each instance is a ``SimpleNamespace`` that has
    the SQL row fields, AND it can be re-shaped to a dict on
    demand by ``__iter__`` / ``to_dict``.
    """

    __slots__ = (
        "id",
        "owner_id",
        "title",
        "summary",
        "last_model",
        "fallback_used",
        "message_count",
        "messages",
        "created_at",
        "updated_at",
    )

    def __init__(
        self,
        *,
        id: int,
        owner_id: int,
        title: str = "",
        summary: str = "",
        last_model: str = "",
        fallback_used: bool = False,
        message_count: int = 0,
        messages: list | None = None,
        created_at: Any = None,
        updated_at: Any = None,
    ) -> None:
        self.id = id
        self.owner_id = owner_id
        self.title = title
        self.summary = summary
        self.last_model = last_model
        self.fallback_used = fallback_used
        self.message_count = message_count
        self.messages: list = list(messages) if messages is not None else []
        # Production rows carry created_at / updated_at
        # timestamps; the chat façade projects them via
        # ``_iso(msg.created_at)``. We default to a fixed
        # sentinel so equality comparisons stay deterministic.
        self.created_at = created_at
        self.updated_at = updated_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "owner_id": self.owner_id,
            "title": self.title,
            "summary": self.summary,
            "last_model": self.last_model,
            "fallback_used": self.fallback_used,
            "message_count": self.message_count,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "messages": [self._msg_to_dict(m) for m in self.messages],
        }

    @staticmethod
    def _msg_to_dict(msg: Any) -> dict[str, Any]:
        if isinstance(msg, _MessageRow):
            return msg.to_dict()
        if isinstance(msg, dict):
            return dict(msg)
        return {"id": getattr(msg, "id", 0), "content": str(msg)}

    def __getitem__(self, key: str) -> Any:
        # Defensive: some legacy projectors index sessions like
        # ``session["id"]`` even though the production row uses
        # attribute access. Honor that contract.
        return getattr(self, key)


class _MessageRow:
    """Lightweight stand-in for the SQLAlchemy
    ``ChatSessionRepository.add_message`` row.

    Production rows expose ``id``, ``session_id``, ``role``,
    ``kind``, ``content``, ``sources_json``, ``fallback_used``,
    ``generation_meta_json``, and ``created_at`` as
    attributes (used by ``_message_payload``). The shim
    mirrors that.
    """

    __slots__ = (
        "id",
        "session_id",
        "role",
        "kind",
        "content",
        "sources_json",
        "fallback_used",
        "generation_meta_json",
        "created_at",
    )

    def __init__(
        self,
        *,
        id: int,
        session_id: int,
        role: str,
        content: str,
        kind: str = "",
        sources_json: str = "[]",
        fallback_used: bool = False,
        generation_meta_json: str = "",
        created_at: Any = None,
    ) -> None:
        self.id = id
        self.session_id = session_id
        self.role = role
        self.kind = kind
        self.content = content
        self.sources_json = sources_json
        self.fallback_used = fallback_used
        self.generation_meta_json = generation_meta_json
        self.created_at = created_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "role": self.role,
            "kind": self.kind,
            "content": self.content,
            "sources_json": self.sources_json,
            "fallback_used": self.fallback_used,
            "generation_meta_json": self.generation_meta_json,
            "created_at": self.created_at,
        }

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)


class _InMemoryChatSession:
    """A minimal chat-session shim compatible with
    :class:`ChatSessionRepository`'s public surface used by
    :class:`ConversationService.append_message`.

    Production rows expose attribute access
    (``session.id``, ``msg.role``, ...) — the shim returns
    ``_SessionRow`` / ``_MessageRow`` instances that mirror the
    production attribute surface so the chat façade can run
    end-to-end without a SQLAlchemy session.
    """

    def __init__(self) -> None:
        self._sessions: dict[tuple[int, int], _SessionRow] = {}
        self._next_session_id = 1
        self._next_message_id = 1
        self.append_message_calls: int = 0

    # ---- Sessions ---------------------------------------------------- #

    def create_session(
        self, *, owner_id: int, title: str = ""
    ) -> _SessionRow:
        sid = self._next_session_id
        self._next_session_id += 1
        session = _SessionRow(
            id=sid,
            owner_id=owner_id,
            title=title,
        )
        self._sessions[(owner_id, sid)] = session
        return session

    def get_session(
        self, *, owner_id: int, session_id: int
    ) -> _SessionRow | None:
        return self._sessions.get((owner_id, session_id))

    def list_sessions(
        self, *, owner_id: int
    ) -> list[_SessionRow]:
        return [
            s for (o, _), s in self._sessions.items()
            if o == owner_id
        ]

    def delete_session(
        self, *, owner_id: int, session_id: int
    ) -> bool:
        return (
            self._sessions.pop((owner_id, session_id), None) is not None
        )

    def touch_session(
        self,
        *,
        session: _SessionRow,
        title: str | None = None,
        **kwargs: Any,
    ) -> _SessionRow:
        if title is not None:
            session.title = str(title)[:120]
        for k, v in kwargs.items():
            if v is not None and hasattr(session, k):
                setattr(session, k, v)
        return session

    # ---- Messages ---------------------------------------------------- #

    def add_message(
        self,
        *,
        session: _SessionRow,
        role: str,
        content: str,
        kind: str = "",
        sources: list[dict] | None = None,
        fallback_used: bool | None = None,
        generation_meta: dict | str | None = None,
    ) -> _MessageRow:
        import json as _json

        if isinstance(generation_meta, dict):
            gen_json = _json.dumps(
                generation_meta,
                separators=(",", ":"),
                ensure_ascii=False,
            )
        elif isinstance(generation_meta, str):
            gen_json = generation_meta
        else:
            gen_json = ""
        mid = self._next_message_id
        self._next_message_id += 1
        msg = _MessageRow(
            id=mid,
            session_id=session.id,
            role=role,
            content=content,
            kind=kind or "",
            sources_json=_json.dumps(
                sources or [], ensure_ascii=False
            ),
            fallback_used=bool(fallback_used)
            if fallback_used is not None
            else False,
            generation_meta_json=gen_json,
        )
        session.messages.append(msg)
        session.message_count = len(session.messages)
        if role == "user":
            self.append_message_calls += 1
        return msg

    def get_messages(
        self, *, session: _SessionRow
    ) -> list[_MessageRow]:
        return list(session.messages)

    def count_messages(self, *, session: _SessionRow) -> int:
        return len(session.messages)


# --------------------------------------------------------------------------- #
# Stub AssistantContextBuilder — returns the runner's fixture context
# --------------------------------------------------------------------------- #


class _StubAssistantContextBuilder:
    """Drop-in :class:`AssistantContextBuilder` that returns the
    fixture context the runner was constructed with.

    The :class:`AssistantProviderService` only calls
    ``build(owner_id=...)`` on the builder, so this stub is
    sufficient. The real builder reads from five upstream
    services and is exercised by the existing AI-13 e2e suite;
    for the freeze gate we want the chat façade running, not
    the upstream repositories.
    """

    def __init__(self, context: AssistantContext) -> None:
        self._ctx = context

    def build(self, *, owner_id: int = 0, user_prompt: str = "") -> AssistantContext:
        return self._ctx


# --------------------------------------------------------------------------- #
# ConversationServiceRunner
# --------------------------------------------------------------------------- #


@dataclass
class _RunnerConfig:
    """Bundle the runner's wiring so callers can inspect it."""

    owner_id: int
    session_id: int
    profile_id: str
    assistant_service_id: str
    repo_calls: int = 0


def _count_evidence(
    references: tuple[Any, ...] | list[Any],
    envelopes: tuple[Any, ...] | list[Any],
) -> int:
    """Count evidence across both wire-envelope surfaces.

    Sprint AI-19 — the deterministic fallback path emits
    its authoritative figures through
    ``structured_tool_envelopes`` (carrying ``tool_name`` /
    ``input_evidence_ids``) rather than the
    ``evidence_references`` tuple. The previous projection
    only counted ``evidence_references``, which yielded a
    misleading 0.0 evidence-correctness metric for the
    deterministic path. This helper mirrors the count
    logic the existing :class:`EvaluationRunner` uses.
    """
    total = 0
    total += len(references or ())
    for env in envelopes or ():
        if isinstance(env, dict):
            if env.get("tool_name") or env.get("input_evidence_ids"):
                total += 1
    return total


@dataclass
class ConversationServiceRunner:
    """Drive prompts through the production
    :class:`ConversationService.append_message` path.

    The runner is a sibling of :class:`EvaluationRunner`; it
    shares the same :class:`EvaluationResult` shape so the
    metrics calculator consumes both runners' output
    interchangeably.

    Construction
    ------------
    Pass a fixture :class:`AssistantContext` (typically built
    from a :class:`DataQualityProfile`). The runner wires:

      * an in-memory :class:`_InMemoryChatSession`
      * a stub :class:`_StubAssistantContextBuilder` that
        returns the fixture context
      * a real :class:`AssistantProviderService`
      * a real :class:`ConversationService` on top

    Calling ``run_prompt(prompt)`` invokes
    ``ConversationService.append_message(...)`` end-to-end. The
    returned :class:`EvaluationResult` carries
    ``production_path=True`` whenever the chat façade was
    actually invoked (which is always, when the call
    succeeds).
    """

    context: AssistantContext
    profile_id: str = "profile_complete_001"
    owner_id: int = 1
    mode: str = "grounded"
    # The runner's wired services are exposed for tests that
    # want to assert "real" production-path behaviour (e.g.
    # the chat repo's ``append_message_calls`` counter).
    repo: _InMemoryChatSession = field(default_factory=_InMemoryChatSession)
    assistant_service: AssistantProviderService | None = None
    conversation_service: ConversationService | None = None
    session_id: int = 0
    config: _RunnerConfig | None = None

    def __post_init__(self) -> None:
        # 1. Build the assistant service with the fixture context.
        builder = _StubAssistantContextBuilder(self.context)
        self.assistant_service = AssistantProviderService(
            context_builder=builder,  # type: ignore[arg-type]
        )
        # 2. Wire the conversation service on top.
        self.conversation_service = ConversationService(
            self.repo,  # type: ignore[arg-type]
            assistant_service=self.assistant_service,
        )
        # 3. Pre-create one session so every prompt has a
        #    session_id to thread into append_message.
        session = self.repo.create_session(
            owner_id=self.owner_id, title="AI-18 freeze gate"
        )
        self.session_id = int(session.id)
        self.config = _RunnerConfig(
            owner_id=self.owner_id,
            session_id=self.session_id,
            profile_id=self.profile_id,
            assistant_service_id=id(self.assistant_service),
        )

    # ---- single-prompt entry point -------------------------------- #

    def run_prompt(
        self,
        prompt: str,
        *,
        case_id: str = "",
    ) -> EvaluationResult:
        """Drive one prompt through ``append_message``.

        Returns an :class:`EvaluationResult` with
        ``production_path=True`` when the chat façade ran. The
        runner NEVER swallows :class:`ChatSessionNotFound` /
        unexpected exceptions — failures surface as
        ``success=False, error=...``.
        """
        start = time.perf_counter()
        try:
            result = self.conversation_service.append_message(  # type: ignore[union-attr]
                owner_id=self.owner_id,
                session_id=self.session_id,
                content=prompt,
                mode=self.mode,
            )
        except Exception as exc:  # pragma: no cover — defensive
            elapsed_ms = max(1, int((time.perf_counter() - start) * 1000))
            return EvaluationResult(
                case_id=case_id or prompt[:40],
                prompt=prompt,
                production_path=False,
                latency_ms=elapsed_ms,
                success=False,
                error=f"{type(exc).__name__}: {exc}",
            )
        elapsed_ms = max(1, int((time.perf_counter() - start) * 1000))
        assistant_msg = result.assistant_message or {}
        # ``assistant_message`` is the wire dict produced by
        # ``_message_payload``; the GenerationMeta lives under
        # the ``generation`` key.
        if isinstance(assistant_msg, dict):
            body = str(assistant_msg.get("content", "") or "")
            generation = assistant_msg.get("generation") or {}
        else:
            body = str(getattr(assistant_msg, "content", "") or "")
            generation = getattr(assistant_msg, "generation", None) or {}
        # The wire envelope already carries the per-sprint
        # fields; we project them onto notes for the metrics
        # calculator.
        notes: dict[str, Any] = {
            "answer_mode": str(
                generation.get("answer_mode", "") or ""
            ),
            "business_dependency": str(
                generation.get("business_dependency", "none") or "none"
            ),
            "capability": list(generation.get("capability") or []),
            # Sprint AI-21 — legacy intent compatibility metric.
            # The legacy ``QuestionIntent`` enum must always be
            # reachable through the QU; the metric reports the
            # non-empty fraction. The wire envelope carries
            # ``relevant_existing_intents`` as a list of
            # ``.value`` strings.
            "relevant_existing_intents": list(
                generation.get("relevant_existing_intents") or []
            ),
            # SPRINT AI-19 — evidence correctness closure.
            # The deterministic fallback path carries its
            # authoritative figures via
            # ``structured_tool_envelopes`` rather than
            # ``evidence_references``; both surfaces count.
            # The presence-only ``evidence_correctness``
            # metric (field #2 in AI-18) reads this value.
            "evidence_count": _count_evidence(
                generation.get("evidence_references") or (),
                generation.get("structured_tool_envelopes") or (),
            ),
            # The structural evidence-correctness metric
            # (field #19 in AI-19) needs the raw envelopes
            # so the matcher can walk tool claims + values.
            "structured_tool_envelopes": list(
                generation.get("structured_tool_envelopes") or ()
            ),
            "evidence_references": list(
                generation.get("evidence_references") or ()
            ),
            "fallback_used": bool(generation.get("fallback_used", False)),
            "server_confidence": generation.get("server_confidence"),
            "needs_warning": bool(
                generation.get("needs_warning", False)
            ),
            "fabricated_source_count": int(
                generation.get("fabricated_source_count", 0) or 0
            ),
            "unsupported_claim_count": int(
                generation.get("unsupported_claim_count", 0) or 0
            ),
            # SPRINT AI-20 — tool minimality. The two
            # new metrics read the per-tool execution
            # trace the dispatcher stamped onto
            # GenerationMeta. Each entry carries
            # ``tool_name``, ``selected``, ``executed``,
            # ``success``, ``used_in_final_answer``, etc.
            "tool_execution_traces": list(
                generation.get("tool_execution_traces") or ()
            ),
            # Required-tools list from the question
            # understanding — drives the post-plan
            # intersection in ``ToolSelector``. Surfaced
            # on notes so the metrics layer + report
            # driver can compare actual vs required.
            "required_tools": list(
                generation.get("required_tools") or ()
            ),
        }
        return EvaluationResult(
            case_id=case_id or prompt[:40],
            prompt=prompt,
            body=body,
            generation=_fake_generation(generation),
            production_path=True,
            latency_ms=elapsed_ms,
            success=bool(body.strip()),
            notes=notes,
        )

    # ---- batch entry points --------------------------------------- #

    def run_question_bank(self, questions: tuple[Any, ...]) -> tuple[EvaluationResult, ...]:
        return tuple(
            self.run_prompt(q.prompt, case_id=f"qbank:{q.category}:{i}")
            for i, q in enumerate(questions)
        )


# --------------------------------------------------------------------------- #
# Internal — build a duck-typed GenerationMeta from the wire dict
# --------------------------------------------------------------------------- #


def _fake_generation(wire: dict[str, Any]) -> SimpleNamespace:
    """Return a SimpleNamespace that looks enough like
    :class:`GenerationMeta` for the metrics calculator's
    ``getattr``-based reads. The runner NEVER mutates the wire
    envelope; it just exposes the values the calculator keys
    off.
    """
    return SimpleNamespace(
        answer_mode=wire.get("answer_mode", ""),
        capability=tuple(wire.get("capability") or ()),
        business_dependency=wire.get("business_dependency", "none"),
        evidence_references=tuple(wire.get("evidence_references") or ()),
        structured_tool_envelopes=tuple(
            wire.get("structured_tool_envelopes") or ()
        ),
        deterministic_services_used=tuple(
            wire.get("deterministic_services_used") or ()
        ),
        server_confidence=wire.get("server_confidence"),
        unsupported_claim_count=int(
            wire.get("unsupported_claim_count", 0) or 0
        ),
        fabricated_source_count=int(
            wire.get("fabricated_source_count", 0) or 0
        ),
        needs_warning=bool(wire.get("needs_warning", False)),
        fallback_used=bool(wire.get("fallback_used", False)),
        confidence_penalty=int(wire.get("confidence_penalty", 0) or 0),
        partial_failure_disclosure=wire.get("partial_failure_disclosure"),
        numeric_conflicts_count=int(
            wire.get("numeric_conflicts_count", 0) or 0
        ),
        provider_used=wire.get("provider", ""),
        server_grounding_score=int(
            wire.get("server_grounding_score", 0) or 0
        ),
        model=wire.get("model", ""),
        runtime_provider=wire.get("runtime_provider", ""),
        mode=wire.get("mode", ""),
    )


# --------------------------------------------------------------------------- #
# Convenience factory
# --------------------------------------------------------------------------- #


def runner_for_profile(
    profile_id: str = "profile_complete_001",
    *,
    owner_id: int = 1,
    mode: str = "grounded",
) -> ConversationServiceRunner:
    """Build a :class:`ConversationServiceRunner` from a profile id."""
    profile: DataQualityProfile | None = next(
        (p for p in all_profiles() if p.profile_id == profile_id),
        None,
    )
    if profile is None:
        raise ValueError(f"unknown profile_id {profile_id!r}")
    return ConversationServiceRunner(
        context=profile.build(),
        profile_id=profile_id,
        owner_id=owner_id,
        mode=mode,
    )


__all__ = [
    "ConversationServiceRunner",
    "runner_for_profile",
]