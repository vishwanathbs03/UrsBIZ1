"""Repository for managing business personalization settings and owner preferences (Phase 5)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.business import Business
from app.models.business_challenge import BusinessChallenge
from app.models.business_goal import BusinessGoal
from app.models.personalization import BusinessPersonalizationSettings
from app.models.recommendation_feedback import RecommendationFeedback
from app.schemas.personalization import (
    BusinessConstraintType,
    BusinessGoalType,
    PersonalizationSettingsUpdate,
)

logger = logging.getLogger("atlas.repository.personalization")


class PersonalizationRepository:
    """Handles CRUD persistence for business personalization settings."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_settings(self, business_id: int) -> Optional[BusinessPersonalizationSettings]:
        """Fetch personalization settings if existing."""
        return (
            self.db.query(BusinessPersonalizationSettings)
            .filter(BusinessPersonalizationSettings.business_id == business_id)
            .first()
        )

    def get_or_create_settings(
        self, business_id: int, business: Optional[Business] = None
    ) -> BusinessPersonalizationSettings:
        """Fetch existing settings or initialize from verified business twin."""
        record = self.get_settings(business_id)
        if record:
            return record

        # Initialize from existing business twin context
        initial_goals: list[str] = []
        initial_constraints: list[str] = []
        source = "SYSTEM_INFERRED"

        if business is None:
            business = self.db.query(Business).filter(Business.id == business_id).first()

        if business:
            # Map existing BusinessGoal records if present
            if business.goals:
                for bg in business.goals:
                    title_l = bg.title.lower()
                    if "revenue" in title_l or "sales" in title_l or "grow" in title_l:
                        initial_goals.append(BusinessGoalType.INCREASE_REVENUE.value)
                    elif "profit" in title_l or "margin" in title_l:
                        initial_goals.append(BusinessGoalType.IMPROVE_PROFITABILITY.value)
                    elif "retain" in title_l or "customer" in title_l or "churn" in title_l:
                        initial_goals.append(BusinessGoalType.RETAIN_CUSTOMERS.value)
                    elif "cost" in title_l or "expense" in title_l:
                        initial_goals.append(BusinessGoalType.REDUCE_OPERATING_COSTS.value)
                    elif "product" in title_l or "launch" in title_l:
                        initial_goals.append(BusinessGoalType.LAUNCH_PRODUCTS.value)
                    elif "market" in title_l or "expand" in title_l or "export" in title_l:
                        initial_goals.append(BusinessGoalType.EXPAND_MARKETS.value)
                    elif "digital" in title_l or "web" in title_l or "online" in title_l:
                        initial_goals.append(BusinessGoalType.IMPROVE_DIGITAL_PRESENCE.value)
                    elif "efficient" in title_l or "operation" in title_l:
                        initial_goals.append(BusinessGoalType.IMPROVE_OPERATIONAL_EFFICIENCY.value)
                source = "ONBOARDING"

            # Map existing BusinessChallenge records
            if business.challenges:
                for bc in business.challenges:
                    title_c = (bc.title + " " + (bc.description or "")).lower()
                    if "cash" in title_c or "capital" in title_c or "budget" in title_c or "fund" in title_c:
                        initial_constraints.append(BusinessConstraintType.LIMITED_BUDGET.value)
                    if "staff" in title_c or "employee" in title_c or "workforce" in title_c or "manpower" in title_c:
                        initial_constraints.append(BusinessConstraintType.SMALL_WORKFORCE.value)
                    if "digital" in title_c or "tech" in title_c or "software" in title_c:
                        initial_constraints.append(BusinessConstraintType.LIMITED_DIGITAL_CAPABILITY.value)
                    if "time" in title_c or "delay" in title_c or "bandwidth" in title_c:
                        initial_constraints.append(BusinessConstraintType.TIME_CONSTRAINTS.value)

            # Auto-infer data/financial constraints if verified absent
            if not getattr(business, "annual_revenue", None) or business.annual_revenue <= 0:
                initial_constraints.append(BusinessConstraintType.MISSING_FINANCIAL_INFO.value)
            if not getattr(business, "sales_transactions", None) or len(business.sales_transactions) == 0:
                initial_constraints.append(BusinessConstraintType.LIMITED_HISTORICAL_DATA.value)

        # Deduplicate defaults
        goals_dedup = list(dict.fromkeys(initial_goals)) or [BusinessGoalType.INCREASE_REVENUE.value]
        constraints_dedup = list(dict.fromkeys(initial_constraints))

        record = BusinessPersonalizationSettings(
            business_id=business_id,
            goals=json.dumps(goals_dedup),
            constraints=json.dumps(constraints_dedup),
            focus_areas=json.dumps(["Sales & Growth", "Operational Stability"]),
            preferred_effort_level="Medium",
            preferred_investment_level="Low" if BusinessConstraintType.LIMITED_BUDGET.value in constraints_dedup else "Medium",
            source=source,
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def update_settings(
        self, business_id: int, payload: PersonalizationSettingsUpdate
    ) -> BusinessPersonalizationSettings:
        """Update owner-configured goals, constraints, and preferences."""
        record = self.get_or_create_settings(business_id)

        record.goals = json.dumps(payload.goals)
        record.constraints = json.dumps(payload.constraints)
        if payload.preferred_effort_level:
            record.preferred_effort_level = payload.preferred_effort_level
        if payload.preferred_investment_level:
            record.preferred_investment_level = payload.preferred_investment_level
        if payload.focus_areas is not None:
            record.focus_areas = json.dumps(payload.focus_areas)

        record.source = "OWNER_DECLARED"
        record.updated_at = datetime.now(timezone.utc)

        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def get_feedback_summary(self, business_id: int) -> dict[str, int]:
        """Aggregate counts of owner feedback types for learning."""
        rows = (
            self.db.query(
                RecommendationFeedback.feedback_type,
                func.count(RecommendationFeedback.id),
            )
            .filter(RecommendationFeedback.business_id == business_id)
            .group_by(RecommendationFeedback.feedback_type)
            .all()
        )
        return {r[0]: r[1] for r in rows}

    def get_recent_feedback(
        self, business_id: int, limit: int = 50
    ) -> list[RecommendationFeedback]:
        """Retrieve recent feedback rows for scoring adaptation."""
        return (
            self.db.query(RecommendationFeedback)
            .filter(RecommendationFeedback.business_id == business_id)
            .order_by(RecommendationFeedback.created_at.desc())
            .limit(limit)
            .all()
        )
