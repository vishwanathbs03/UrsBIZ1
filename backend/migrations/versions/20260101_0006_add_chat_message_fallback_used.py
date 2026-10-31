"""add chat_messages.fallback_used (per-message trust flag)

Revision ID: 20260101_0006
Revises: 20260101_0005
Create Date: 2026-08-05 00:00:00

H7.8A Part 2 — trust-label semantics.

The chat_sessions table already carries a session-level
``fallback_used`` flag, but the frontend ``MessageBubble``
needs to decide the per-message trust label ("Calculated by
UrsBiz rule engine" vs "Generated explanation") for every
assistant bubble it renders.

This migration adds the same boolean to ``chat_messages`` so
the append endpoint can persist it on each assistant turn, and
the GET response can echo it back to the UI. The default is
``False`` so existing rows are valid without backfill.

The change is purely additive:

  * New column ``chat_messages.fallback_used`` (BOOLEAN,
    NOT NULL, server_default false).
  * No table rewrite, no index changes, no data migration.

Downgrade is symmetric: drop the column. SQLite accepts
``ALTER TABLE DROP COLUMN`` since 3.35.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260101_0006"
down_revision: Union[str, None] = "20260101_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "chat_messages",
        sa.Column(
            "fallback_used",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("chat_messages", "fallback_used")
