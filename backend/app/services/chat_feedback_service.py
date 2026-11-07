"""Service layer for AI answer feedback and quality evaluation (Phase 6.28)."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.chat import ChatMessage, ChatSession
from app.models.chat_feedback import ChatFeedback, FeedbackCategory
from app.schemas.chat_feedback import (
    ChatFeedbackAnalyticsResponse,
    ChatFeedbackCreateRequest,
    ChatFeedbackResponse,
    ChatFeedbackUpdateRequest,
    GroundingCorrelationMetrics,
)

logger = logging.getLogger("atlas.chat.feedback")


class ChatFeedbackService:
    """Coordinates structured user feedback on AI responses and quality metrics evaluation."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def submit_feedback(
        self,
        business_id: int,
        user_id: int,
        message_id: int,
        request: ChatFeedbackCreateRequest,
    ) -> ChatFeedbackResponse:
        """Submit or update feedback for an AI assistant message turn."""
        # 1. Validate message exists and belongs to a chat session of this business (Tenant Isolation)
        msg = (
            self.db.query(ChatMessage)
            .join(ChatSession, ChatMessage.session_id == ChatSession.id)
            .filter(
                ChatMessage.id == message_id,
                ChatSession.business_id == business_id,
            )
            .first()
        )
        if not msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Message {message_id} not found in active business conversations.",
            )

        # 2. Guard: Only assistant turns can receive feedback (users cannot rate their own prompts)
        if msg.role != "assistant":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Feedback can only be submitted on assistant responses, not user prompts.",
            )

        # 3. Upsert feedback record for (message_id, user_id)
        existing = (
            self.db.query(ChatFeedback)
            .filter(
                ChatFeedback.message_id == message_id,
                ChatFeedback.user_id == user_id,
            )
            .first()
        )

        if existing:
            existing.rating = request.rating
            existing.feedback_category = request.feedback_category.value
            existing.notes = request.notes
            self.db.commit()
            self.db.refresh(existing)
            logger.info("Updated feedback for message %d by user %d: rating=%d", message_id, user_id, request.rating)
            return self._to_response(existing)

        feedback = ChatFeedback(
            message_id=message_id,
            business_id=business_id,
            user_id=user_id,
            rating=request.rating,
            feedback_category=request.feedback_category.value,
            notes=request.notes,
        )
        self.db.add(feedback)
        self.db.commit()
        self.db.refresh(feedback)
        logger.info("Submitted feedback for message %d by user %d: rating=%d", message_id, user_id, request.rating)
        return self._to_response(feedback)

    def get_message_feedback(
        self,
        business_id: int,
        message_id: int,
        user_id: int | None = None,
    ) -> ChatFeedbackResponse | None:
        """Retrieve feedback for a specific message, isolated by business."""
        query = (
            self.db.query(ChatFeedback)
            .filter(
                ChatFeedback.message_id == message_id,
                ChatFeedback.business_id == business_id,
            )
        )
        if user_id is not None:
            query = query.filter(ChatFeedback.user_id == user_id)

        feedback = query.order_by(ChatFeedback.id.desc()).first()
        if not feedback:
            return None
        return self._to_response(feedback)

    def update_feedback(
        self,
        business_id: int,
        user_id: int,
        message_id: int,
        request: ChatFeedbackUpdateRequest,
    ) -> ChatFeedbackResponse:
        """Update existing feedback for an assistant turn."""
        feedback = (
            self.db.query(ChatFeedback)
            .filter(
                ChatFeedback.message_id == message_id,
                ChatFeedback.business_id == business_id,
                ChatFeedback.user_id == user_id,
            )
            .first()
        )
        if not feedback:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No feedback record found for message {message_id} by this user.",
            )

        if request.rating is not None:
            feedback.rating = request.rating
        if request.feedback_category is not None:
            feedback.feedback_category = request.feedback_category.value
        if request.notes is not None:
            feedback.notes = request.notes

        self.db.commit()
        self.db.refresh(feedback)
        return self._to_response(feedback)

    def delete_feedback(
        self,
        business_id: int,
        user_id: int,
        message_id: int,
        can_manage_all: bool = False,
    ) -> None:
        """Delete user feedback (supporting zero-retention compliance)."""
        query = (
            self.db.query(ChatFeedback)
            .filter(
                ChatFeedback.message_id == message_id,
                ChatFeedback.business_id == business_id,
            )
        )
        if not can_manage_all:
            query = query.filter(ChatFeedback.user_id == user_id)

        feedback = query.first()
        if not feedback:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No feedback found for message {message_id} to delete.",
            )

        self.db.delete(feedback)
        self.db.commit()
        logger.info("Deleted feedback for message %d by user %d", message_id, user_id)

    def get_quality_analytics(
        self,
        business_id: int,
        days: int = 30,
    ) -> ChatFeedbackAnalyticsResponse:
        """Aggregate quality evaluation metrics, helpfulness rates, and grounding correlations."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        records: list[tuple[ChatFeedback, ChatMessage]] = (
            self.db.query(ChatFeedback, ChatMessage)
            .join(ChatMessage, ChatFeedback.message_id == ChatMessage.id)
            .filter(
                ChatFeedback.business_id == business_id,
                ChatFeedback.created_at >= cutoff,
            )
            .all()
        )

        total_count = len(records)
        category_counts: dict[str, int] = {c.value: 0 for c in FeedbackCategory}

        if total_count == 0:
            return ChatFeedbackAnalyticsResponse(
                business_id=business_id,
                total_feedback_count=0,
                helpful_count=0,
                unhelpful_count=0,
                helpfulness_rate=0.0,
                average_rating=0.0,
                quality_score=100.0,  # Default clean baseline score when no negative signal
                category_distribution=category_counts,
                grounding_correlation=GroundingCorrelationMetrics(),
            )

        helpful_count = 0
        unhelpful_count = 0
        total_rating_sum = 0

        grounded_count = 0
        grounded_rating_sum = 0
        fallback_count = 0
        fallback_rating_sum = 0
        fallback_unhelpful_count = 0
        unclassified_count = 0

        for fb, msg in records:
            r = fb.rating
            total_rating_sum += r

            if r >= 4:
                helpful_count += 1
            elif r <= 2:
                unhelpful_count += 1

            cat = fb.feedback_category
            category_counts[cat] = category_counts.get(cat, 0) + 1

            # Grounding and fallback correlation based on system-persisted evidence
            gen_meta: dict[str, Any] = {}
            raw_meta = getattr(msg, "generation_meta_json", "") or ""
            if raw_meta:
                try:
                    parsed_meta = json.loads(raw_meta)
                    if isinstance(parsed_meta, dict):
                        gen_meta = parsed_meta
                except Exception:
                    gen_meta = {}

            sources_raw = getattr(msg, "sources_json", "[]") or "[]"
            has_sources = False
            try:
                parsed_sources = json.loads(sources_raw)
                has_sources = bool(parsed_sources and len(parsed_sources) > 0)
            except Exception:
                has_sources = False

            is_fallback = bool(
                getattr(msg, "fallback_used", False)
                or gen_meta.get("fallback_used") is True
                or gen_meta.get("provider") == "local-rule-engine"
            )

            is_grounded = (
                not is_fallback
                and (
                    bool(gen_meta.get("grounding_validated"))
                    or (isinstance(gen_meta.get("evidence_count"), (int, float)) and gen_meta["evidence_count"] > 0)
                    or (isinstance(gen_meta.get("server_grounding_score"), (int, float)) and gen_meta["server_grounding_score"] > 0)
                    or has_sources
                )
            )

            if is_fallback:
                fallback_count += 1
                fallback_rating_sum += r
                if r <= 2:
                    fallback_unhelpful_count += 1
            elif is_grounded:
                grounded_count += 1
                grounded_rating_sum += r
            else:
                # Missing or indeterminate provenance metadata: strictly excluded from comparison
                unclassified_count += 1

        avg_rating = round(total_rating_sum / total_count, 2)
        helpfulness_rate = round(helpful_count / total_count, 4)

        grounded_avg = round(grounded_rating_sum / max(grounded_count, 1), 2) if grounded_count > 0 else 0.0
        fallback_avg = round(fallback_rating_sum / max(fallback_count, 1), 2) if fallback_count > 0 else 0.0
        fallback_unhelpful_rate = (
            round(fallback_unhelpful_count / max(fallback_count, 1), 4) if fallback_count > 0 else 0.0
        )

        # Quality score: 70% helpfulness rate + 30% normalized average rating (1.0..5.0 -> 0..100)
        norm_rating_score = ((avg_rating - 1.0) / 4.0) * 100.0
        quality_score = round(max(0.0, min(100.0, (helpfulness_rate * 70.0) + (norm_rating_score * 0.30))), 1)

        return ChatFeedbackAnalyticsResponse(
            business_id=business_id,
            total_feedback_count=total_count,
            helpful_count=helpful_count,
            unhelpful_count=unhelpful_count,
            helpfulness_rate=helpfulness_rate,
            average_rating=avg_rating,
            quality_score=quality_score,
            category_distribution=category_counts,
            grounding_correlation=GroundingCorrelationMetrics(
                grounded_message_count=grounded_count,
                grounded_average_rating=grounded_avg,
                fallback_message_count=fallback_count,
                fallback_average_rating=fallback_avg,
                fallback_unhelpful_rate=fallback_unhelpful_rate,
                unclassified_message_count=unclassified_count,
            ),
        )

    def _to_response(self, feedback: ChatFeedback) -> ChatFeedbackResponse:
        return ChatFeedbackResponse(
            id=feedback.id,
            message_id=feedback.message_id,
            business_id=feedback.business_id,
            user_id=feedback.user_id,
            rating=feedback.rating,
            is_positive=feedback.rating >= 4,
            feedback_category=FeedbackCategory(feedback.feedback_category),
            notes=feedback.notes,
            created_at=feedback.created_at,
            updated_at=feedback.updated_at,
        )
