"""ChatSessionRepository — data-access layer for the chat persistence
endpoints (Sprint 7 Part 3).

The repository owns every SQL statement that touches the
``chat_sessions`` / ``chat_messages`` tables. The service layer
is the only consumer; endpoints never touch the session
directly.

Every read is **owner-scoped** at the SQL level — a request for
another user's conversation returns ``None``, which the service
translates into a 404. The repository never leaks a row across
owners.
"""
from __future__ import annotations

from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.chat import ChatMessage, ChatSession


class ChatSessionNotFound(Exception):
    """Raised when a session id does not exist for the owner."""


class ChatSessionRepository:
    """SQL access for chat_sessions + chat_messages."""

    def __init__(self, db: Session) -> None:
        self._db = db

    # ---- Sessions ----------------------------------------------------- #

    def create_session(
        self, *, owner_id: int, title: str = ""
    ) -> ChatSession:
        """Insert a new session row and return it.

        The repository commits the row before returning. This
        matches the existing ``BusinessRepository`` /
        ``BusinessService`` convention where every write
        service commits its own changes — the endpoint is
        not responsible for transaction management.
        """
        session = ChatSession(
            owner_id=owner_id,
            title=(title or "").strip()[:120],
        )
        self._db.add(session)
        self._db.flush()
        self._db.commit()
        # Refresh so the caller sees the server-defaulted
        # created_at / updated_at values.
        self._db.refresh(session)
        return session

    def list_sessions(self, *, owner_id: int) -> Sequence[ChatSession]:
        """Return the owner's sessions, newest first."""
        stmt = (
            select(ChatSession)
            .where(ChatSession.owner_id == owner_id)
            .order_by(ChatSession.updated_at.desc(), ChatSession.id.desc())
        )
        return tuple(self._db.scalars(stmt).all())

    def get_session(self, *, owner_id: int, session_id: int) -> ChatSession | None:
        """Return the owner's session, or None if not owned / not found."""
        stmt = select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.owner_id == owner_id,
        )
        return self._db.scalars(stmt).first()

    def delete_session(self, *, owner_id: int, session_id: int) -> bool:
        """Delete the owner's session. Returns True if a row was removed."""
        session = self.get_session(owner_id=owner_id, session_id=session_id)
        if session is None:
            return False
        self._db.delete(session)
        self._db.flush()
        self._db.commit()
        return True

    def touch_session(
        self,
        *,
        session: ChatSession,
        title: str | None = None,
        summary: str | None = None,
        last_model: str | None = None,
        fallback_used: bool | None = None,
        message_count: int | None = None,
    ) -> ChatSession:
        """Update mutable fields on the session row."""
        if title is not None:
            session.title = title[:120]
        if summary is not None:
            session.summary = summary[:500]
        if last_model is not None:
            session.last_model = last_model[:80]
        if fallback_used is not None:
            session.fallback_used = bool(fallback_used)
        if message_count is not None:
            session.message_count = int(message_count)
        # Force updated_at refresh even when the new values
        # are identical to the old ones — important so the
        # sidebar re-sorts after a user appends a message.
        from sqlalchemy import func as sqlfunc
        session.updated_at = sqlfunc.now()
        self._db.flush()
        self._db.commit()
        self._db.refresh(session)
        return session

    # ---- Messages ----------------------------------------------------- #

    def add_message(
        self,
        *,
        session: ChatSession,
        role: str,
        content: str,
        kind: str = "",
        sources: list[dict] | None = None,
        fallback_used: bool | None = None,
        generation_meta: dict | str | None = None,
    ) -> ChatMessage:
        """Append a message to the session and return it.

        H7.8A P2 — ``fallback_used`` is propagated to the per-message
        row when supplied, so the frontend ``MessageBubble`` can render
        the correct trust label ("Calculated by UrsBiz rule engine"
        vs "Generated explanation"). User messages always store
        ``fallback_used=False`` because the trust label only applies
        to assistant turns.

        H7.8C — ``generation_meta`` is the structured
        ``ChatGenerationMeta`` payload the provider layer stamps on
        every assistant turn. The repository serialises a dict
        via ``json.dumps(..., separators=(",", ":"))`` (compact
        form, no whitespace) and accepts a pre-serialised string
        for callers that already have one. User messages and any
        caller that does not need provenance pass ``None`` and the
        stored value defaults to ``""``.
        """
        import json
        if isinstance(generation_meta, dict):
            generation_meta_json = json.dumps(
                generation_meta, separators=(",", ":"), ensure_ascii=False
            )
        elif isinstance(generation_meta, str):
            generation_meta_json = generation_meta
        else:
            generation_meta_json = ""
        msg = ChatMessage(
            session_id=session.id,
            role=role,
            kind=kind or "",
            content=content,
            sources_json=json.dumps(sources or [], ensure_ascii=False),
            fallback_used=bool(fallback_used) if fallback_used is not None else False,
            generation_meta_json=generation_meta_json,
        )
        self._db.add(msg)
        self._db.flush()
        self._db.commit()
        self._db.refresh(msg)
        return msg

    def get_messages(self, *, session: ChatSession) -> Sequence[ChatMessage]:
        """Return the messages of a session, oldest first."""
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session.id)
            .order_by(ChatMessage.id.asc())
        )
        return tuple(self._db.scalars(stmt).all())

    # ---- Convenience -------------------------------------------------- #

    def count_messages(self, *, session: ChatSession) -> int:
        return len(self.get_messages(session=session))