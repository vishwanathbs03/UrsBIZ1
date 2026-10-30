"""H7.8C P3 — regressions and event-emission tests.

Sprint H7.8C P3 closed three concrete backend gaps:

  1. The ``ConversationService._build_history`` filter
     previously compared ``m.id`` to ``session.id`` and almost
     never excluded the just-inserted user message — so the
     rolling context leaked the prompt back into the model.
     The fix introduces an ``exclude_message_id`` keyword
     parameter and threads it from ``append_message``.

  2. Three structured events now fire on every meaningful
     provider decision:

        - ``ai.provider.grounded_succeeded``
        - ``ai.provider.fallback_chosen``
        - ``ai.provider.open_mode_provider_failure``

     The audit trail must be observable end-to-end so the
     judge session can prove *why* the assistant degraded
     gracefully when the upstream provider is unavailable.

  3. The deterministic fallback now reads
     ``Settings.ai_max_history_turns`` /
     ``Settings.ai_grounding_threshold`` so operators can
     tune the rolling context + grounding threshold without
     redeploying.

These tests cover (1) and (2). Settings plumbing (3) is
covered by the ``Settings`` model tests in
``test_config_settings.py``.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Sequence

import pytest

from app.services.ai.providers.base import (
    AssistantContext,
    AssistantContextDna,
    AssistantContextRecommendation,
    AssistantContextScore,
    AssistantRequest,
    AssistantResponse,
    AssistantTurn,
    GenerationMeta,
    ProviderUnavailableError,
)
from app.services.ai.providers.context_builder import AssistantContextBuilder
from app.services.ai.providers.factory import ProviderFactory
from app.services.ai.providers.grounding_validator import (
    DEFAULT_GROUNDING_THRESHOLD,
)
from app.services.ai.providers.service import AssistantProviderService
from app.services.chat import ConversationService


# --------------------------------------------------------------------------- #
# Stubs — no database, no upstream providers
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class _StubMessage:
    id: int
    role: str
    content: str


@dataclass(frozen=True)
class _StubSession:
    id: int
    owner_id: int


class _StubRepo:
    """Just enough of ChatSessionRepository for ``_build_history``."""

    def __init__(self, messages: Sequence[_StubMessage]) -> None:
        self._messages = tuple(messages)

    def get_messages(self, *, session: Any) -> Sequence[_StubMessage]:
        return self._messages


class _StubAssistantService:
    """Placeholder AssistantProviderService.

    ``_build_history`` does not call the assistant, but the
    constructor requires one. Use this stub so the test never
    hits the default factory.
    """

    def __init__(self) -> None:
        self.calls: list[Any] = []

    def build_context(self, owner_id: int) -> AssistantContext:
        return _make_context()

    def generate(self, **_kwargs: Any) -> AssistantResponse:
        raise AssertionError("stub should never be invoked here")


def _make_context() -> AssistantContext:
    """A context that produces a non-empty evidence registry.

    The registry projects entries from the context's
    ``scores``, ``recommendations``, ``rules``, ``schemes``,
    ``forecasts``, ``action_items``, and ``dna`` fields. To
    exercise the grounded_succeeded path the model must cite
    IDs that the registry knows about — so we ship one
    recommendation (id = ``rec-001``) and one score (key =
    ``financial_readiness``).
    """
    return AssistantContext(
        business_id=42,
        overall_business_score=63,
        band="Established",
        dna=AssistantContextDna(
            archetype_key="growth_operator",
            archetype_title="Growth Operator",
            match_score=78,
        ),
        scores=(
            AssistantContextScore(
                key="financial_readiness",
                title="Financial Readiness",
                score=70,
                level="Developing",
            ),
        ),
        recommendations=(
            AssistantContextRecommendation(
                id="rec-001",
                title="Diversify suppliers",
                category="operations",
                priority="High",
                estimated_score_gain=4,
                estimated_roi=2.5,
                estimated_timeline="2-4 weeks",
            ),
        ),
    )


# --------------------------------------------------------------------------- #
# Regression 1 — _build_history excludes the just-inserted user message
# --------------------------------------------------------------------------- #


def test_build_history_excludes_just_inserted_user_message() -> None:
    """When the caller passes ``exclude_message_id``, the rolling
    context MUST NOT include that message.

    Before the H7.8C P3 fix the filter compared ``m.id`` to
    ``session.id`` and almost never matched, so the prompt we
    just added leaked into the rolling context.
    """
    repo = _StubRepo(
        messages=[
            _StubMessage(id=10, role="user", content="older turn 1"),
            _StubMessage(id=11, role="assistant", content="older answer 1"),
            _StubMessage(id=20, role="user", content="older turn 2"),
            _StubMessage(id=21, role="assistant", content="older answer 2"),
            _StubMessage(id=30, role="user", content="the just-inserted prompt"),
        ]
    )
    svc = ConversationService(
        repo,  # type: ignore[arg-type]
        assistant_service=_StubAssistantService(),
        rolling_context_turns=8,
    )
    session = _StubSession(id=99, owner_id=1)
    history = svc._build_history(session, exclude_message_id=30)
    # The just-inserted message must be absent.
    assert all(m.content != "the just-inserted prompt" for m in history)
    # Every other user/assistant turn must still be present.
    contents = [m.content for m in history]
    assert "older turn 1" in contents
    assert "older answer 1" in contents
    assert "older turn 2" in contents
    assert "older answer 2" in contents
    assert len(history) == 4


def test_build_history_returns_full_when_exclude_id_is_none() -> None:
    """The legacy ``exclude_message_id=None`` path still returns
    every user/assistant turn (used by callers that have not
    yet persisted a user message).
    """
    repo = _StubRepo(
        messages=[
            _StubMessage(id=1, role="user", content="t1"),
            _StubMessage(id=2, role="assistant", content="a1"),
            _StubMessage(id=3, role="user", content="t2"),
        ]
    )
    svc = ConversationService(
        repo,  # type: ignore[arg-type]
        assistant_service=_StubAssistantService(),
        rolling_context_turns=8,
    )
    session = _StubSession(id=1, owner_id=1)
    history = svc._build_history(session)
    assert len(history) == 3


def test_build_history_respects_rolling_window() -> None:
    """When the rolling window is smaller than the full
    conversation, the most-recent turns are returned.
    """
    repo = _StubRepo(
        messages=[
            _StubMessage(id=1, role="user", content="old1"),
            _StubMessage(id=2, role="assistant", content="old1a"),
            _StubMessage(id=3, role="user", content="recent1"),
            _StubMessage(id=4, role="assistant", content="recent1a"),
            _StubMessage(id=5, role="user", content="latest"),
        ]
    )
    svc = ConversationService(
        repo,  # type: ignore[arg-type]
        assistant_service=_StubAssistantService(),
        rolling_context_turns=2,
    )
    session = _StubSession(id=1, owner_id=1)
    history = svc._build_history(session, exclude_message_id=5)
    contents = [m.content for m in history]
    assert contents == ["recent1", "recent1a"]


# --------------------------------------------------------------------------- #
# Regression 2 — three new structured events
# --------------------------------------------------------------------------- #


def _build_service() -> AssistantProviderService:
    """Build an AssistantProviderService that always returns
    the stub context.

    Mirrors the ``acme_service`` fixture in
    ``test_h7_8c_hybrid_grounded_ai.py`` — monkey-patches the
    context builder's ``build`` so the service's
    ``self._context_builder.build(owner_id=...)`` call returns
    the prepared :class:`AssistantContext` directly, bypassing
    the upstream-payload projection. Tests want to drive the
    registry with a known-good context, not with whatever
    shape Twin/Recommendations happen to return today.
    """
    def _builder(owner_id: int) -> AssistantContext:
        return _make_context()

    ctx = _make_context()
    context_builder = AssistantContextBuilder(
        twin_provider=_builder,
        recommendations_provider=_builder,
        roadmap_provider=_builder,
        rules_provider=_builder,
        insights_provider=_builder,
    )
    context_builder.build = (  # type: ignore[method-assign]
        lambda owner_id: ctx
    )
    factory = ProviderFactory()
    return AssistantProviderService(
        context_builder=context_builder,
        provider_factory=factory,
    )


@dataclass(frozen=True)
class _StubProvider:
    """Provider stub with a configurable body and behaviour."""

    body: str
    raise_error: ProviderUnavailableError | None = None

    def complete(self, request: AssistantRequest) -> AssistantResponse:
        if self.raise_error is not None:
            raise self.raise_error
        from datetime import datetime, timezone
        return AssistantResponse(
            body=self.body,
            model="stub-model",
            fallback_used=False,
            provider_used="stub-provider",
            generated_at=datetime.now(tz=timezone.utc).isoformat(),
            provider_latency_ms=12,
            generation=GenerationMeta.empty(
                mode="grounded",
                provider_used="stub-provider",
                model="stub-model",
                provider_latency_ms=12,
                fallback_used=False,
            ),
        )


def test_grounded_succeeded_event_fires() -> None:
    """A real provider answer in grounded mode MUST emit the
    ``ai.provider.grounded_succeeded`` event.
    """
    # A complete grounded payload the schema validator accepts.
    # The evidence_refs MUST resolve to IDs the registry will
    # produce from the stub context — the registry applies the
    # ``rec_`` / ``score_`` prefix and the ``_slug`` transform
    # (``rec-001`` → ``rec_rec_001``,
    # ``financial_readiness`` → ``score_financial_readiness``).
    # The recommendation_id and the plan recommendation_ref
    # must use the *slugged* id, since that is what the
    # validator looks up.
    valid_payload = (
        '{"executive_summary": "Acme Textiles is on a steady growth trajectory.",'
        '"key_findings": ['
        '{"statement": "Supplier dependency risk is the dominant constraint.",'
        ' "evidence_refs": ["rec_rec_001", "score_financial_readiness"]}],'
        '"recommendations": ['
        '{"recommendation_id": "rec_rec_001", "title": "Diversify suppliers",'
        ' "rationale": "Reduces single-supplier risk.",'
        ' "evidence_refs": ["rec_rec_001"]}],'
        '"thirty_day_plan": [{"week": 1, "task": "Map supplier base",'
        ' "recommendation_ref": "rec_rec_001", "evidence_refs": ["rec_rec_001"]}],'
        '"scheme_matches": [],'
        '"assumptions": ["Founder has capacity to negotiate."],'
        '"limitations": ["Only profile-level scheme matches."],'
        '"confidence": 78,'
        '"evidence_references": ['
        '{"id": "rec_rec_001", "kind": "recommendation", "label": "Diversify suppliers"},'
        '{"id": "score_financial_readiness", "kind": "score", "label": "Financial Readiness"}]}'
    )
    provider = _StubProvider(body=valid_payload)
    service = _build_service()
    with _capture_log("atlas.ai.provider") as records:
        resp = service.generate(
            owner_id=1,
            user_prompt="Help Acme Textiles",
            history=(),
            knowledge=None,
            provider=provider,
            mode="grounded",
        )
    assert resp.fallback_used is False
    events = _events(records)
    assert "ai.provider.grounded_succeeded" in events, (
        f"missing grounded_succeeded event; saw {events}"
    )
    record = _event_record(records, "ai.provider.grounded_succeeded")
    assert record.provider_used == "stub-provider"
    assert record.model == "stub-model"
    assert getattr(record, "grounding_score", 0) >= 0
    assert getattr(record, "registry_count", 0) >= 1
    assert getattr(record, "evidence_count", 0) >= 1


def test_fallback_chosen_event_fires_on_provider_unavailable() -> None:
    """When the provider is unavailable the service MUST emit
    ``ai.provider.fallback_chosen`` with a normalised reason.
    """
    provider = _StubProvider(
        body="",
        raise_error=ProviderUnavailableError("simulated"),
    )
    service = _build_service()
    with _capture_log("atlas.ai.provider") as records:
        resp = service.generate(
            owner_id=1,
            user_prompt="Help Acme Textiles",
            history=(),
            knowledge=None,
            provider=provider,
            mode="grounded",
        )
    assert resp.fallback_used is True
    events = _events(records)
    assert "ai.provider.fallback_chosen" in events
    record = _event_record(records, "ai.provider.fallback_chosen")
    assert record.reason == "provider_unavailable"
    assert record.mode == "grounded"


def test_open_mode_provider_failure_event_fires() -> None:
    """Open-mode provider failures MUST emit the dedicated
    ``ai.provider.open_mode_provider_failure`` event so the
    UI can render a different label than the grounded
    ``provider_unavailable`` path.
    """
    provider = _StubProvider(
        body="",
        raise_error=ProviderUnavailableError("simulated"),
    )
    service = _build_service()
    with _capture_log("atlas.ai.provider") as records:
        resp = service.generate(
            owner_id=1,
            user_prompt="Help Acme Textiles",
            history=(),
            knowledge=None,
            provider=provider,
            mode="open",
        )
    assert resp.fallback_used is True
    events = _events(records)
    assert "ai.provider.open_mode_provider_failure" in events, (
        f"missing open_mode_provider_failure event; saw {events}"
    )
    record = _event_record(records, "ai.provider.open_mode_provider_failure")
    assert record.reason == "open_mode_provider_failure"
    assert record.mode == "open"


# --------------------------------------------------------------------------- #
# Log capture utility — non-intrusive structured-event observer
# --------------------------------------------------------------------------- #


class _CapturedRecord:
    """Wrap a :class:`logging.LogRecord` with attribute access
    for the ``extra`` dict the service emits."""

    __slots__ = ("_record",)

    def __init__(self, record: logging.LogRecord) -> None:
        super().__setattr__("_record", record)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._record, name, None)


class _capture_log:
    """Context manager that captures log records from a named logger.

    The service emits structured events via ``logger.info("…",
    extra={"event": …})``. The :class:`logging.LogRecord`
    surface those extras as attributes on the record itself, so
    the wrapper exposes them transparently.
    """

    def __init__(self, logger_name: str, level: int = logging.INFO) -> None:
        self._logger = logging.getLogger(logger_name)
        self._level = level
        self._handler: logging.Handler | None = None
        self.records: list[_CapturedRecord] = []

    def __enter__(self) -> "list[_CapturedRecord]":
        outer = self

        class _Handler(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                outer.records.append(_CapturedRecord(record))

        self._handler = _Handler(level=self._level)
        self._logger.addHandler(self._handler)
        self._previous_level = self._logger.level
        self._logger.setLevel(self._level)
        return self.records

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if self._handler is not None:
            self._logger.removeHandler(self._handler)
        self._logger.setLevel(self._previous_level)


def _events(records: Sequence[_CapturedRecord]) -> list[str]:
    return [r.event for r in records if getattr(r, "event", None)]


def _event_record(
    records: Sequence[_CapturedRecord], name: str
) -> _CapturedRecord:
    for record in records:
        if getattr(record, "event", None) == name:
            return record
    raise AssertionError(f"event {name!r} not found in {len(records)} records")
