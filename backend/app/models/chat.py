"""ORM models for the chat persistence layer (Sprint 7 & Phase 6.26).

Two tables back the assistant conversation memory:

  * :class:`ChatSession` — one row per conversation. Owner and business-scoped.
  * :class:`ChatMessage` — one row per turn. Append-only, tracking auditable user_id.

The cascade is set at the FK level: deleting a user drops
their sessions, and deleting a session drops its messages.
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.utils.database import Base


if TYPE_CHECKING:
    from app.models.business import Business
    from app.models.user import User
    from app.models.chat_feedback import ChatFeedback


class ChatSession(Base):
    """A conversation between a user and the AI Assistant."""

    __tablename__ = "chat_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Phase 6.26 — business association for multi-user MSME collaboration
    business_id: Mapped[int | None] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    title: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    summary: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_model: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    fallback_used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="ChatMessage.id",
    )

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<ChatSession id={self.id} owner={self.owner_id} business={self.business_id} title={self.title!r}>"


class ChatMessage(Base):
    """One turn in a :class:`ChatSession`. Append-only by convention."""

    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Phase 6.26 — auditable user tracking for collaboration turns
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Role: "user" or "assistant". Keep it a string column so
    # future roles (e.g. "system") do not require a migration.
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    # Kind: matches the QueryKind strings in
    # frontend/features/assistant/classify-query.ts. Empty
    # string when the message is not yet classified.
    kind: Mapped[str] = mapped_column(String(32), nullable=False, default="")

    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Per-message sources echoed for the UI. Empty list for
    # user messages. JSON-encoded so a future schema change can
    # add fields without a migration.
    sources_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    # H7.8A P2 — trust-label semantics.
    fallback_used: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    # H7.8C — per-message grounding provenance.
    generation_meta_json: Mapped[str] = mapped_column(
        Text, nullable=False, default=""
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    session: Mapped["ChatSession"] = relationship(back_populates="messages")
    feedback: Mapped[list["ChatFeedback"]] = relationship("ChatFeedback", back_populates="message", cascade="all, delete-orphan")

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<ChatMessage id={self.id} session={self.session_id} role={self.role}>"
