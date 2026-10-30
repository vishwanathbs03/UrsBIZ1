"""Pydantic v2 schemas for the AI Business Copilot
endpoint.

The Copilot is a *read-only* orchestrator. The
endpoint is a thin wrapper around
:class:`~app.services.copilot.CopilotService`.
Every model uses ``extra="forbid"`` so an
unhandled code path fails loudly at the API
boundary, not silently in the UI.

Request
-------

``POST /api/v1/business/copilot/chat`` accepts a
JSON body with a single ``message`` field:

  {
    "message": "How can I improve my export readiness?"
  }

Response
--------

  * ``generated_at``         — ISO-8601 UTC.
  * ``conversation_id``      — deterministic id
    derived from the owner + message. Two calls
    with the same message from the same user
    return the same conversation_id; the
    Copilot does NOT store any history.
  * ``message_id``           — deterministic
    per-message id.
  * ``intent``               — one of the 14
    spec'd categories (see
    :data:`app.services.copilot.base.INTENTS`).
  * ``confidence``           — 0..100, the
    intent detector's confidence.
  * ``response``             — 2-4 sentence
    consultant's answer (deterministic
    template response).
  * ``citations``            — every source the
    response leaned on.
  * ``follow_up_questions``  — 3 deterministic
    follow-ups.
  * ``context_summary``      — small metadata
    block (services used, counts).
  * ``inputs``               — sidecar of
    upstream ``*_generated_at`` timestamps.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# --------------------------------------------------------------------------- #
# Intent literal — mirrors the spec's 14
# categories.
# --------------------------------------------------------------------------- #


IntentCategoryLiteral = Literal[
    "GENERAL_BUSINESS",
    "BUSINESS_SCORE",
    "EXPORT",
    "DIGITAL",
    "COMPLIANCE",
    "DNA",
    "ROADMAP",
    "RECOMMENDATIONS",
    "RULES",
    "SCENARIO",
    "OCR",
    "FINANCE",
    "GREETING",
    "UNKNOWN",
]


CitationKindLiteral = Literal[
    "recommendation",
    "rule",
    "article",
    "roadmap",
    "score",
    "dna",
    "intelligence",
]


# --------------------------------------------------------------------------- #
# Request
# --------------------------------------------------------------------------- #


class CopilotRequest(BaseModel):
    """The shape of the request body for
    ``POST /api/v1/business/copilot/chat``.

    A single ``message`` field. The spec
    example is "How can I improve my export
    readiness?"; the field accepts any
    non-empty string up to 4000 characters.
    """

    model_config = ConfigDict(extra="forbid")

    message: str = Field(
        min_length=1,
        max_length=4000,
        description=(
            "Free-text question the user is asking the "
            "UrsBiz Advisor. 1-4000 characters."
        ),
    )


# --------------------------------------------------------------------------- #
# Citations
# --------------------------------------------------------------------------- #


class CitationOut(BaseModel):
    """A single source the Copilot leaned on.

    ``kind`` is one of the seven citation
    kinds the spec lists. ``id`` is the
    stable id within that kind
    (``rule.export.no_iec`` for a rule,
    ``R-001`` for a recommendation,
    ``KB-001`` for an article, etc.).
    ``label`` is the human-readable title
    so the UI can render a one-line chip
    without a follow-up fetch. ``reference``
    is a one-sentence reason the citation
    was included.
    """

    model_config = ConfigDict(extra="forbid")

    kind: CitationKindLiteral
    id: str
    label: str
    reference: str = ""


# --------------------------------------------------------------------------- #
# Follow-up questions
# --------------------------------------------------------------------------- #


class FollowUpQuestionOut(BaseModel):
    """A single follow-up question.

    ``anchor`` is the id of the citation the
    question is anchored to (empty when the
    question is generic). ``intent`` is the
    intent the question would trigger if the
    user clicks through.
    """

    model_config = ConfigDict(extra="forbid")

    question: str
    intent: IntentCategoryLiteral
    anchor: str = ""


# --------------------------------------------------------------------------- #
# Context summary
# --------------------------------------------------------------------------- #


class ContextSummaryOut(BaseModel):
    """The small context metadata block.

    ``services_used`` is the list of service
    names the context builder actually called
    (e.g. ``["scores", "rules", "knowledge"]``).
    The four ``*_used`` integer fields are the
    counts the response leaned on. ``score_keys_used``
    is the list of score keys the context
    pulled.
    """

    model_config = ConfigDict(extra="forbid")

    services_used: list[str] = Field(default_factory=list)
    recommendations_used: int = Field(default=0, ge=0)
    rules_used: int = Field(default=0, ge=0)
    roadmap_items_used: int = Field(default=0, ge=0)
    knowledge_used: int = Field(default=0, ge=0)
    score_keys_used: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Inputs sidecar
# --------------------------------------------------------------------------- #


class CopilotInputsOut(BaseModel):
    """Echoes every upstream service's
    ``generated_at`` timestamp so the UI can
    show "Copilot answer is current as of X
    (scores Y, rules Z, ...)".

    The model name is the provider's
    ``name`` attribute. Unused services
    carry ``None``.
    """

    model_config = ConfigDict(extra="forbid")

    model: str

    business_generated_at: str | None = None
    scores_generated_at: str | None = None
    rules_generated_at: str | None = None
    recommendations_generated_at: str | None = None
    roadmap_generated_at: str | None = None
    dna_generated_at: str | None = None
    knowledge_generated_at: str | None = None
    finance_generated_at: str | None = None
    twin_generated_at: str | None = None


# --------------------------------------------------------------------------- #
# Response envelope
# --------------------------------------------------------------------------- #


class CopilotResponse(BaseModel):
    """Returned by ``POST /api/v1/business/copilot/chat``."""

    model_config = ConfigDict(extra="forbid")

    generated_at: str
    conversation_id: str
    message_id: str
    intent: IntentCategoryLiteral
    confidence: int = Field(ge=0, le=100)
    response: str
    citations: list[CitationOut] = Field(default_factory=list)
    follow_up_questions: list[FollowUpQuestionOut] = Field(
        default_factory=list
    )
    context_summary: ContextSummaryOut = Field(
        default_factory=ContextSummaryOut
    )
    inputs: CopilotInputsOut
