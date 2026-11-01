"""create recommendation_outcomes and business_monitoring tables (Phase 5 Final Verification)

Revision ID: 20261101_0005
Revises: 20261101_0004
Create Date: 2026-11-01 06:00:01

Creates tables for:
  - recommendation_outcomes (Closed-loop learning and before/after measurement)
  - business_signal_events (Proactive business change detection and risk/opportunity signals)
  - business_monitoring_preferences (Owner monitoring configuration)
  - recommendation_refresh_records (Audit trail of recommendation re-evaluations)
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20261101_0005"
down_revision: Union[str, None] = "20261101_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. recommendation_outcomes
    op.create_table(
        "recommendation_outcomes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("business_id", sa.Integer(), nullable=False),
        sa.Column("recommendation_id", sa.String(length=100), nullable=False),
        sa.Column("is_started", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_completed", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_abandoned", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actual_effort", sa.String(length=50), nullable=True),
        sa.Column("owner_rating", sa.Integer(), nullable=True),
        sa.Column("qualitative_feedback", sa.Text(), nullable=True),
        sa.Column("perceived_utility", sa.String(length=50), nullable=True),
        sa.Column("non_completion_reason", sa.String(length=100), nullable=True),
        sa.Column("still_relevant", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("measured_outcome_summary", sa.Text(), nullable=True),
        sa.Column("baseline_metrics", sa.JSON(), nullable=True),
        sa.Column("post_metrics", sa.JSON(), nullable=True),
        sa.Column("observed_changes", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["business_id"],
            ["businesses.id"],
            name="fk_recommendation_outcomes_business_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_recommendation_outcomes"),
        sa.UniqueConstraint("business_id", "recommendation_id", name="uq_business_recommendation_outcome"),
    )
    op.create_index("ix_recommendation_outcomes_business_id", "recommendation_outcomes", ["business_id"])
    op.create_index("ix_recommendation_outcomes_recommendation_id", "recommendation_outcomes", ["recommendation_id"])

    # 2. business_signal_events
    op.create_table(
        "business_signal_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("business_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("relevant_entity", sa.String(length=128), nullable=True),
        sa.Column(
            "detected_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("data_period", sa.String(length=64), nullable=False),
        sa.Column("event_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("is_suppressed", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("suppression_reason", sa.String(length=128), nullable=True),
        sa.Column("escalation_level", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("linked_recommendation_id", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="NEW"),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("what_changed", sa.Text(), nullable=False),
        sa.Column("why_it_matters", sa.Text(), nullable=False),
        sa.Column("suggested_action", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.85"),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["business_id"],
            ["businesses.id"],
            name="fk_business_signal_events_business_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_business_signal_events"),
        sa.UniqueConstraint("event_id", name="uq_business_signal_events_event_id"),
    )
    op.create_index("ix_business_signal_events_business_id", "business_signal_events", ["business_id"])
    op.create_index("ix_business_signal_events_event_id", "business_signal_events", ["event_id"])
    op.create_index("ix_business_signal_events_event_type", "business_signal_events", ["event_type"])
    op.create_index("ix_business_signal_events_fingerprint", "business_signal_events", ["fingerprint"])
    op.create_index("ix_business_signal_events_detected_at", "business_signal_events", ["detected_at"])

    # 3. business_monitoring_preferences
    op.create_table(
        "business_monitoring_preferences",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("business_id", sa.Integer(), nullable=False),
        sa.Column("monitored_metrics", sa.JSON(), nullable=False),
        sa.Column("areas_of_interest", sa.JSON(), nullable=False),
        sa.Column("alert_frequency", sa.String(length=32), nullable=False, server_default="REALTIME"),
        sa.Column("preferred_notification_types", sa.JSON(), nullable=False),
        sa.Column("min_severity", sa.String(length=32), nullable=False, server_default="LOW"),
        sa.Column("cooldown_days", sa.Integer(), nullable=False, server_default="7"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["business_id"],
            ["businesses.id"],
            name="fk_business_monitoring_preferences_business_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_business_monitoring_preferences"),
        sa.UniqueConstraint("business_id", name="uq_business_monitoring_preferences_business_id"),
    )
    op.create_index("ix_business_monitoring_preferences_business_id", "business_monitoring_preferences", ["business_id"])

    # 4. recommendation_refresh_records
    op.create_table(
        "recommendation_refresh_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("business_id", sa.Integer(), nullable=False),
        sa.Column("recommendation_id", sa.String(length=64), nullable=False),
        sa.Column("refresh_reason", sa.String(length=64), nullable=False),
        sa.Column("old_priority_score", sa.Integer(), nullable=False),
        sa.Column("new_priority_score", sa.Integer(), nullable=False),
        sa.Column("old_status", sa.String(length=32), nullable=False),
        sa.Column("new_status", sa.String(length=32), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column(
            "refreshed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["business_id"],
            ["businesses.id"],
            name="fk_recommendation_refresh_records_business_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_recommendation_refresh_records"),
    )
    op.create_index("ix_recommendation_refresh_records_business_id", "recommendation_refresh_records", ["business_id"])
    op.create_index("ix_recommendation_refresh_records_recommendation_id", "recommendation_refresh_records", ["recommendation_id"])
    op.create_index("ix_recommendation_refresh_records_refreshed_at", "recommendation_refresh_records", ["refreshed_at"])


def downgrade() -> None:
    op.drop_table("recommendation_refresh_records")
    op.drop_table("business_monitoring_preferences")
    op.drop_table("business_signal_events")
    op.drop_table("recommendation_outcomes")
