"""ChatSessionRepository — data-access layer for the chat persistence
endpoints (Sprint 7 & Phase 6.26 RBAC).

The repository owns every SQL statement that touches the
``chat_sessions`` / ``chat_messages`` tables.

In Phase 6.26, chat sessions can be business-associated and
chat messages record the auditable user_id of the collaborator.
"""
from __future__ import annotations

import json
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
        self, *, owner_id: int, title: str = "", business_id: int | None = None
    ) -> ChatSession:
        """Insert a new session row and return it."""
        session = ChatSession(
            owner_id=owner_id,
            business_id=business_id,
            title=(title or "").strip()[:120],
        )
        self._db.add(session)
        self._db.flush()
        self._db.commit()
        self._db.refresh(session)
        return session

    def list_sessions(self, *, owner_id: int, business_id: int | None = None) -> Sequence[ChatSession]:
        """Return sessions for owner and optional business scope, newest first."""
        stmt = select(ChatSession).where(ChatSession.owner_id == owner_id)
        if business_id is not None:
            stmt = stmt.where(ChatSession.business_id == business_id)
        stmt = stmt.order_by(ChatSession.updated_at.desc(), ChatSession.id.desc())
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
        user_id: int | None = None,
    ) -> ChatMessage:
        """Append a message to the session with auditable user_id tracking."""
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
            user_id=user_id,
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
