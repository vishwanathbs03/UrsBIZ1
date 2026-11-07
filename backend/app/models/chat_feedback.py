"""ORM model for AI answer feedback and quality evaluation (Phase 6.28)."""
from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.utils.database import Base

if TYPE_CHECKING:
    from app.models.business import Business
    from app.models.chat import ChatMessage
    from app.models.user import User


class FeedbackCategory(str, enum.Enum):
    """Categorical classification of user feedback for AI responses."""
    HELPFUL = "Helpful"
    INCORRECT_INFORMATION = "Incorrect Information"
    MISSING_EVIDENCE = "Missing Evidence"
    OUTDATED_DATA = "Outdated Data"
    DIFFICULT_TO_UNDERSTAND = "Difficult to Understand"


class ChatFeedback(Base):
    """Structured user feedback on an assistant turn in a chat session."""

    __tablename__ = "chat_feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    message_id: Mapped[int] = mapped_column(
        ForeignKey("chat_messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    business_id: Mapped[int] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Rating: 1 (Very Unhelpful / Thumbs Down) to 5 (Very Helpful / Thumbs Up)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)

    # Category classification from frozen Phase 6 specification
    feedback_category: Mapped[str] = mapped_column(String(50), nullable=False)

    # Optional qualitative feedback / corrective notes
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    message: Mapped["ChatMessage"] = relationship(back_populates="feedback")
    business: Mapped["Business"] = relationship(back_populates="chat_feedbacks")
    user: Mapped["User"] = relationship()

    __table_args__ = (
        UniqueConstraint("message_id", "user_id", name="uq_chat_feedback_message_user"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ChatFeedback id={self.id} message_id={self.message_id} rating={self.rating} category={self.feedback_category!r}>"
