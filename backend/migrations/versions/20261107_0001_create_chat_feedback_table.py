"""create chat_feedback table (Phase 6.28)

Revision ID: 20261107_0001
Revises: 20261106_0001
Create Date: 2026-11-07 20:00:00

Creates:
  - chat_feedback: structured user ratings, categories, and notes for AI assistant messages.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20261107_0001"
down_revision: Union[str, None] = "20261106_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "chat_feedback",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "message_id",
            sa.Integer(),
            sa.ForeignKey("chat_messages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "business_id",
            sa.Integer(),
            sa.ForeignKey("businesses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("feedback_category", sa.String(50), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("message_id", "user_id", name="uq_chat_feedback_message_user"),
    )
    op.create_index("ix_chat_feedback_message_id", "chat_feedback", ["message_id"])
    op.create_index("ix_chat_feedback_business_id", "chat_feedback", ["business_id"])
    op.create_index("ix_chat_feedback_user_id", "chat_feedback", ["user_id"])
    op.create_index("ix_chat_feedback_feedback_category", "chat_feedback", ["feedback_category"])
    op.create_index("ix_chat_feedback_created_at", "chat_feedback", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_chat_feedback_created_at", table_name="chat_feedback")
    op.drop_index("ix_chat_feedback_feedback_category", table_name="chat_feedback")
    op.drop_index("ix_chat_feedback_user_id", table_name="chat_feedback")
    op.drop_index("ix_chat_feedback_business_id", table_name="chat_feedback")
    op.drop_index("ix_chat_feedback_message_id", table_name="chat_feedback")
    op.drop_table("chat_feedback")
