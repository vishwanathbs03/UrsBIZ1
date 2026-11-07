"""Pydantic schemas for AI answer feedback and quality evaluation (Phase 6.28)."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.chat_feedback import FeedbackCategory


class ChatFeedbackCreateRequest(BaseModel):
    """Payload for submitting feedback on an AI assistant turn."""

    rating: int = Field(
        ...,
        ge=1,
        le=5,
        description="Rating from 1 (Very Unhelpful / Poor) to 5 (Very Helpful / Excellent).",
    )
    feedback_category: FeedbackCategory = Field(
        ...,
        description="Categorical failure mode or commendation from Phase 6.28 taxonomy.",
    )
    notes: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Optional qualitative details or factual corrections.",
    )


class ChatFeedbackUpdateRequest(BaseModel):
    """Payload for updating existing feedback on an AI assistant turn."""

    rating: Optional[int] = Field(
        default=None,
        ge=1,
        le=5,
        description="Updated rating from 1 to 5.",
    )
    feedback_category: Optional[FeedbackCategory] = Field(
        default=None,
        description="Updated category classification.",
    )
    notes: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Updated qualitative notes.",
    )


class ChatFeedbackResponse(BaseModel):
    """Representation of user feedback record on a chat message."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    message_id: int
    business_id: int
    user_id: Optional[int] = None
    rating: int
    is_positive: bool = Field(
        ...,
        description="True if rating >= 4, indicating general helpfulness.",
    )
    feedback_category: FeedbackCategory
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class GroundingCorrelationMetrics(BaseModel):
    """Correlation between answer grounding metadata and user feedback."""

    grounded_message_count: int = Field(
        default=0,
        description="Number of feedback records for messages with verified source citations.",
    )
    grounded_average_rating: float = Field(
        default=0.0,
        description="Average rating (1.0 to 5.0) for grounded answers with cited sources.",
    )
    fallback_message_count: int = Field(
        default=0,
        description="Number of feedback records for messages that triggered rule-engine fallbacks.",
    )
    fallback_average_rating: float = Field(
        default=0.0,
        description="Average rating (1.0 to 5.0) for fallback answers.",
    )
    fallback_unhelpful_rate: float = Field(
        default=0.0,
        description="Percentage of fallback messages rated unhelpful (rating < 3).",
    )
    unclassified_message_count: int = Field(
        default=0,
        description="Number of messages with missing or indeterminate grounding metadata excluded from comparison.",
    )


class ChatFeedbackAnalyticsResponse(BaseModel):
    """Aggregate quality evaluation summary for a business's AI assistant turns."""

    business_id: int
    total_feedback_count: int
    helpful_count: int
    unhelpful_count: int
    helpfulness_rate: float = Field(
        ...,
        description="Ratio of helpful feedback (rating >= 4) to total feedback (0.0 to 1.0).",
    )
    average_rating: float = Field(
        ...,
        description="Mean satisfaction rating on 1.0 to 5.0 scale.",
    )
    quality_score: float = Field(
        ...,
        description="Normalized 0 to 100 quality confidence score based on helpfulness and grounding veracity.",
    )
    category_distribution: dict[str, int] = Field(
        default_factory=dict,
        description="Counts of feedback occurrences across each FeedbackCategory.",
    )
    grounding_correlation: GroundingCorrelationMetrics
