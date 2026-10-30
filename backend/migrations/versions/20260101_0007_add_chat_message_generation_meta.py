"""add chat_messages.generation_meta_json (per-message grounding provenance)

Revision ID: 20260101_0007
Revises: 20260101_0006
Create Date: 2026-08-05 00:00:00

H7.8C — evidence-grounded AI assistant.

H7.8A Part 2 added ``chat_messages.fallback_used`` (a boolean
trust-label flag) so the frontend could distinguish "Generated
explanation" from "Calculated by UrsBiz rule engine". That
toggle is necessary but not sufficient for the H7.8C judge
demo, because the boolean cannot answer any of the questions
a judge will ask:

  * Which provider actually answered?
  * Was the model output grounded against business evidence,
    or was it a free-form LLM reply?
  * How many evidence references were cited?
  * What was the model, the latency, the schema/grounding
    validation status, the fallback reason (when applicable)?

This migration adds a single JSON-encoded text column
(`generation_meta_json`) that the append endpoint writes
to on every assistant turn. The JSON shape is a stable
``ChatGenerationMeta`` object (see
``backend/app/schemas/chat.py``). User messages store ``""``
(no provenance needed for the user-typed half of the
conversation).

The change is purely additive:

  * New column ``chat_messages.generation_meta_json`` (TEXT,
    NOT NULL, server_default "").
  * No table rewrite, no index changes, no data migration.
  * Existing rows are valid without backfill because the
    default is the empty string and the getter treats "" as
    "no provenance".

Why a JSON column, not many separate columns?
-------------------------------------------

A JSON column keeps the migration atomic and the schema
decoupled from the AI provider's internal vocabulary. Future
fields (e.g. ``prompt_token_count``, ``context_completeness``,
``reasoning_chain_echo``) can be added without further migrations.
The validator at the schema layer (``ChatGenerationMeta``,
``extra="forbid"``) gives us the type safety we would have
gotten from real columns.

Downgrade is symmetric: drop the column. SQLite accepts
``ALTER TABLE DROP COLUMN`` since 3.35. The end-to-end
behaviour reverts to the H7.8A P2 (boolean-only) state.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260101_0007"
down_revision: Union[str, None] = "20260101_0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "chat_messages",
        sa.Column(
            "generation_meta_json",
            sa.Text(),
            nullable=False,
            server_default=sa.text("''"),
        ),
    )


def downgrade() -> None:
    op.drop_column("chat_messages", "generation_meta_json")
