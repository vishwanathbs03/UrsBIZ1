"""Business Goal & Progress Tracker Service (Prompt 6.24).

Implements:
  - Deterministic progress evaluation against authoritative business metrics.
  - Distinguishes automated metrics, manual declarations, and estimates.
  - Honest missing data and stale data handling (never fabricates progress).
  - Period boundary detection (future start dates, expired targets).
  - Valid status transition state machine.
  - Append-only audit history & progress snapshots (resilient to goal archival).
  - Non-mutating AI explanation with deterministic fallback.
  - Multi-tenant isolation for all operations.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
import json
from typing import Any

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.config.logging import get_logger
from app.config.settings import get_settings
from app.models.business import Business
from app.models.business_goal import BusinessGoal, BusinessGoalAudit
from app.models.decision_workbench import BusinessDecision
from app.models.recommendation_lifecycle import RecommendationLifecycleState
from app.models.sales import SalesTransaction, SalesUpload
from app.schemas.business_goal import (
    BusinessGoalAuditOut,
    BusinessGoalCreate,
    BusinessGoalListResponse,
    BusinessGoalManualProgressUpdate,
    BusinessGoalOut,
    BusinessGoalStatusUpdate,
    BusinessGoalUpdate,
    GoalAIExplanationResponse,
    GoalDataAvailability,
    GoalMeasurementMethod,
    GoalMetricKey,
    GoalStatus,
    RelatedItemOut,
)

logger = get_logger(__name__)


# Valid state transitions for goal lifecycle
VALID_TRANSITIONS: dict[str, set[str]] = {
    GoalStatus.ACTIVE.value: {
        GoalStatus.PAUSED.value,
        GoalStatus.COMPLETED.value,
        GoalStatus.INCOMPLETE.value,
        GoalStatus.EXPIRED.value,
        GoalStatus.ARCHIVED.value,
    },
    GoalStatus.PAUSED.value: {
        GoalStatus.ACTIVE.value,
        GoalStatus.ARCHIVED.value,
    },
    GoalStatus.COMPLETED.value: {
        GoalStatus.ACTIVE.value,
        GoalStatus.ARCHIVED.value,
    },
    GoalStatus.INCOMPLETE.value: {
        GoalStatus.ACTIVE.value,
        GoalStatus.ARCHIVED.value,
    },
    GoalStatus.EXPIRED.value: {
        GoalStatus.ACTIVE.value,
        GoalStatus.ARCHIVED.value,
    },
    GoalStatus.ARCHIVED.value: set(),  # Terminal state
}


class BusinessGoalService:
    """Authoritative service for business goals and progress tracking."""

    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()

    # -------------------------------------------------------------------------
    # CRUD & Lifecycle Operations
    # -------------------------------------------------------------------------

    def create_goal(
        self,
        business_id: int,
        user_id: int | None,
        payload: BusinessGoalCreate,
    ) -> BusinessGoalOut:
        """Create a new measurable business goal and record audit trail."""
        biz = self.db.query(Business).filter(Business.id == business_id).first()
        if not biz:
            raise ValueError(f"Business {business_id} does not exist.")

        # Default start date to today if omitted
        start_date = payload.start_date or date.today()

        goal = BusinessGoal(
            business_id=business_id,
            title=payload.title.strip(),
            description=payload.description.strip() if payload.description else None,
            timeframe=payload.timeframe,
            priority=payload.priority.lower(),
            metric_key=payload.metric_key,
            measurement_method=payload.measurement_method.value,
            baseline_value=payload.baseline_value,
            target_value=payload.target_value,
            unit=payload.unit,
            start_date=start_date,
            target_date=payload.target_date,
            status=GoalStatus.ACTIVE.value,
            data_availability=GoalDataAvailability.AVAILABLE.value,
            created_by_user_id=user_id,
            is_archived=False,
        )
        self.db.add(goal)
        self.db.flush()

        # Append-only creation audit entry
        audit = BusinessGoalAudit(
            goal_id=goal.id,
            business_id=business_id,
            changed_by_user_id=user_id,
            action="CREATED",
            old_status=None,
            new_status=GoalStatus.ACTIVE.value,
            target_value=goal.target_value,
            notes=f"Goal created with target {goal.target_value} {goal.unit}.",
        )
        self.db.add(audit)
        self.db.commit()
        self.db.refresh(goal)

        # Run immediate evaluation
        return self._populate_and_evaluate_goal(goal, user_id=user_id)

    def list_goals(
        self,
        business_id: int,
        include_archived: bool = False,
        status: str | None = None,
    ) -> BusinessGoalListResponse:
        """List all goals for the business with refreshed progress evaluations."""
        query = self.db.query(BusinessGoal).filter(BusinessGoal.business_id == business_id)
        if not include_archived:
            query = query.filter(BusinessGoal.is_archived.is_(False))
        if status:
            query = query.filter(BusinessGoal.status == status.upper())

        goals = query.order_by(BusinessGoal.created_at.desc()).all()

        items: list[BusinessGoalOut] = []
        active_count = 0
        completed_count = 0
        at_risk_count = 0
        stale_or_missing_count = 0

        for g in goals:
            out = self._populate_and_evaluate_goal(g, persist=False)
            items.append(out)

            if out.status == GoalStatus.ACTIVE:
                active_count += 1
                if (
                    out.days_remaining is not None
                    and out.days_remaining <= 7
                    and (out.progress_pct is None or out.progress_pct < 80.0)
                ):
                    at_risk_count += 1
            elif out.status == GoalStatus.COMPLETED:
                completed_count += 1

            if out.data_availability in (
                GoalDataAvailability.MISSING_DATA,
                GoalDataAvailability.STALE_DATA,
            ):
                stale_or_missing_count += 1

        return BusinessGoalListResponse(
            items=items,
            total=len(items),
            active_count=active_count,
            completed_count=completed_count,
            at_risk_count=at_risk_count,
            stale_or_missing_data_count=stale_or_missing_count,
        )

    def get_goal(
        self,
        goal_id: int,
        business_id: int,
        re_evaluate: bool = True,
    ) -> BusinessGoalOut:
        """Retrieve single goal with strict tenant isolation and fresh progress."""
        goal = (
            self.db.query(BusinessGoal)
            .filter(
                BusinessGoal.id == goal_id,
                BusinessGoal.business_id == business_id,
            )
            .first()
        )
        if not goal or goal.is_archived:
            raise ValueError(f"Goal {goal_id} not found for business {business_id}.")

        return self._populate_and_evaluate_goal(goal, persist=re_evaluate)

    def update_goal(
        self,
        goal_id: int,
        business_id: int,
        user_id: int | None,
        payload: BusinessGoalUpdate,
    ) -> BusinessGoalOut:
        """Update goal parameters and record audit entry."""
        goal = (
            self.db.query(BusinessGoal)
            .filter(
                BusinessGoal.id == goal_id,
                BusinessGoal.business_id == business_id,
            )
            .first()
        )
        if not goal or goal.is_archived:
            raise ValueError(f"Goal {goal_id} not found for business {business_id}.")

        changes = []
        if payload.title is not None and payload.title.strip() != goal.title:
            changes.append(f"Title updated to '{payload.title.strip()}'")
            goal.title = payload.title.strip()
        if payload.description is not None:
            goal.description = payload.description.strip()
        if payload.target_value is not None and payload.target_value != goal.target_value:
            changes.append(f"Target changed from {goal.target_value} to {payload.target_value}")
            goal.target_value = payload.target_value
        if payload.target_date is not None and payload.target_date != goal.target_date:
            changes.append(f"Deadline changed to {payload.target_date}")
            goal.target_date = payload.target_date
        if payload.priority is not None:
            goal.priority = payload.priority.lower()
        if payload.status_notes is not None:
            goal.status_notes = payload.status_notes

        audit = BusinessGoalAudit(
            goal_id=goal.id,
            business_id=business_id,
            changed_by_user_id=user_id,
            action="UPDATED",
            old_status=goal.status,
            new_status=goal.status,
            target_value=goal.target_value,
            notes="; ".join(changes) if changes else "Goal details updated.",
        )
        self.db.add(audit)
        self.db.commit()
        self.db.refresh(goal)

        return self._populate_and_evaluate_goal(goal, user_id=user_id)

    def update_status(
        self,
        goal_id: int,
        business_id: int,
        user_id: int | None,
        payload: BusinessGoalStatusUpdate,
    ) -> BusinessGoalOut:
        """Enforce state machine transitions for business goals."""
        goal = (
            self.db.query(BusinessGoal)
            .filter(
                BusinessGoal.id == goal_id,
                BusinessGoal.business_id == business_id,
            )
            .first()
        )
        if not goal or goal.is_archived:
            raise ValueError(f"Goal {goal_id} not found for business {business_id}.")

        current_status = goal.status
        next_status = payload.status.value

        allowed = VALID_TRANSITIONS.get(current_status, set())
        if next_status not in allowed:
            raise ValueError(
                f"Invalid status transition from {current_status} to {next_status}. "
                f"Allowed transitions: {sorted(allowed)}"
            )

        goal.status = next_status
        if payload.notes:
            goal.status_notes = payload.notes

        audit = BusinessGoalAudit(
            goal_id=goal.id,
            business_id=business_id,
            changed_by_user_id=user_id,
            action="STATUS_CHANGED",
            old_status=current_status,
            new_status=next_status,
            measured_value=goal.current_value,
            progress_pct=goal.progress_pct,
            notes=payload.notes or f"Status changed from {current_status} to {next_status}.",
        )
        self.db.add(audit)
        self.db.commit()
        self.db.refresh(goal)

        return self._populate_and_evaluate_goal(goal, persist=False)

    def record_manual_progress(
        self,
        goal_id: int,
        business_id: int,
        user_id: int | None,
        payload: BusinessGoalManualProgressUpdate,
    ) -> BusinessGoalOut:
        """Record owner-declared manual progress update."""
        goal = (
            self.db.query(BusinessGoal)
            .filter(
                BusinessGoal.id == goal_id,
                BusinessGoal.business_id == business_id,
            )
            .first()
        )
        if not goal or goal.is_archived:
            raise ValueError(f"Goal {goal_id} not found for business {business_id}.")

        goal.current_value = payload.current_value
        goal.last_evaluated_at = datetime.now(timezone.utc)
        goal.data_availability = GoalDataAvailability.AVAILABLE.value

        # Calculate progress
        pct, gap, achieved = self._compute_progress_math(
            metric_key=goal.metric_key,
            baseline=goal.baseline_value,
            target=goal.target_value,
            current=goal.current_value,
        )
        goal.progress_pct = pct

        if achieved and goal.status == GoalStatus.ACTIVE.value:
            goal.status = GoalStatus.COMPLETED.value
            goal.status_notes = "Goal achieved via manual progress declaration."

        audit = BusinessGoalAudit(
            goal_id=goal.id,
            business_id=business_id,
            changed_by_user_id=user_id,
            action="MANUAL_PROGRESS_LOGGED",
            old_status=goal.status,
            new_status=goal.status,
            measured_value=goal.current_value,
            target_value=goal.target_value,
            progress_pct=goal.progress_pct,
            notes=payload.notes or f"Manual value updated to {goal.current_value} {goal.unit}.",
        )
        self.db.add(audit)
        self.db.commit()
        self.db.refresh(goal)

        return self._populate_and_evaluate_goal(goal, persist=False)

    def archive_goal(
        self,
        goal_id: int,
        business_id: int,
        user_id: int | None,
        reason: str | None = None,
    ) -> BusinessGoalOut:
        """Soft-delete a goal while strictly preserving its audit history."""
        goal = (
            self.db.query(BusinessGoal)
            .filter(
                BusinessGoal.id == goal_id,
                BusinessGoal.business_id == business_id,
            )
            .first()
        )
        if not goal:
            raise ValueError(f"Goal {goal_id} not found for business {business_id}.")

        old_status = goal.status
        goal.is_archived = True
        goal.archived_at = datetime.now(timezone.utc)
        goal.archived_by_user_id = user_id
        goal.status = GoalStatus.ARCHIVED.value
        goal.status_notes = reason or "Goal archived by owner."

        audit = BusinessGoalAudit(
            goal_id=goal.id,
            business_id=business_id,
            changed_by_user_id=user_id,
            action="ARCHIVED",
            old_status=old_status,
            new_status=GoalStatus.ARCHIVED.value,
            measured_value=goal.current_value,
            progress_pct=goal.progress_pct,
            notes=reason or "Goal archived. Audit snapshots preserved.",
        )
        self.db.add(audit)
        self.db.commit()
        self.db.refresh(goal)

        return self._populate_and_evaluate_goal(goal, persist=False)

    def get_goal_history(
        self,
        goal_id: int,
        business_id: int,
    ) -> list[BusinessGoalAuditOut]:
        """Fetch chronological audit snapshots for a goal."""
        audits = (
            self.db.query(BusinessGoalAudit)
            .filter(
                BusinessGoalAudit.goal_id == goal_id,
                BusinessGoalAudit.business_id == business_id,
            )
            .order_by(desc(BusinessGoalAudit.created_at))
            .all()
        )
        return [BusinessGoalAuditOut.model_validate(a) for a in audits]

    # -------------------------------------------------------------------------
    # Deterministic Progress Calculation & Evaluation Engine
    # -------------------------------------------------------------------------

    def _compute_progress_math(
        self,
        metric_key: str | None,
        baseline: float | None,
        target: float,
        current: float | None,
    ) -> tuple[float | None, float | None, bool]:
        """Pure deterministic formula calculation for progress percentage and remaining gap.

        Returns: (progress_pct, remaining_gap, is_achieved)
        """
        if current is None:
            return None, None, False

        # Reduction / Ceiling metric (e.g. customer_concentration, days_sales_outstanding)
        is_reduction = metric_key in ("customer_concentration", "days_sales_outstanding")

        if is_reduction:
            # Baseline is starting high value (e.g. 50%), Target is lower (e.g. 25%)
            if current <= target:
                return 100.0, 0.0, True
            if baseline is not None and baseline > target:
                if current >= baseline:
                    return 0.0, round(current - target, 2), False
                progress = round(((baseline - current) / (baseline - target)) * 100.0, 1)
                return max(0.0, min(100.0, progress)), round(current - target, 2), False
            # Fallback if no baseline: distance from 100%
            gap = max(0.0, current - target)
            progress = max(0.0, round(100.0 - ((current - target) / (target if target > 0 else 1.0) * 100.0), 1))
            return progress, round(gap, 2), current <= target

        # Standard increasing metric (Revenue, Repeat Orders, AOV, Count)
        if target <= 0.0:
            return 100.0 if current >= 0.0 else 0.0, 0.0, current >= 0.0

        if baseline is not None and target > baseline:
            if current <= baseline:
                return 0.0, round(target - current, 2), False
            progress = round(((current - baseline) / (target - baseline)) * 100.0, 1)
            gap = max(0.0, round(target - current, 2))
            return max(0.0, progress), gap, current >= target

        # Simple current / target
        progress = round((current / target) * 100.0, 1)
        gap = max(0.0, round(target - current, 2))
        return max(0.0, progress), gap, current >= target

    def _evaluate_metric(
        self,
        goal: BusinessGoal,
    ) -> tuple[float | None, float | None, float | None, GoalDataAvailability, str | None, str, bool]:
        """Evaluate goal progress against ingested transactional data or declared updates.

        Returns:
          (current_val, progress_pct, remaining_gap, availability, freshness_warning, evidence_source, is_achieved)
        """
        today = date.today()

        # Period boundary checks
        if goal.start_date and goal.start_date > today:
            return (
                goal.baseline_value or 0.0,
                0.0,
                goal.target_value - (goal.baseline_value or 0.0),
                GoalDataAvailability.PENDING_PERIOD,
                f"Measurement observation window begins on {goal.start_date}.",
                "Observation period has not started yet.",
                False,
            )

        # Manual progress reporting path
        if (
            goal.measurement_method == GoalMeasurementMethod.MANUAL_REPORTED.value
            or goal.metric_key == GoalMetricKey.MANUAL.value
        ):
            if goal.current_value is None:
                return (
                    None,
                    None,
                    goal.target_value,
                    GoalDataAvailability.MISSING_DATA,
                    "No manual progress updates recorded yet.",
                    "Owner Manual Declaration (Awaiting first update)",
                    False,
                )
            pct, gap, achieved = self._compute_progress_math(
                metric_key=goal.metric_key,
                baseline=goal.baseline_value,
                target=goal.target_value,
                current=goal.current_value,
            )
            return (
                goal.current_value,
                pct,
                gap,
                GoalDataAvailability.AVAILABLE,
                None,
                "Owner Manual Declaration",
                achieved,
            )

        # Automated Transactional Metric Path
        metric_key = (goal.metric_key or "").lower()

        # Determine evaluation window
        window_start = goal.start_date or (today - timedelta(days=30))
        window_end = min(goal.target_date or today, today)
        start_dt = datetime.combine(window_start, datetime.min.time())
        end_dt = datetime.combine(window_end, datetime.max.time())

        # 1. Monthly Revenue / Revenue
        if metric_key in ("monthly_revenue", "revenue", "revenue_30d"):
            txns = (
                self.db.query(SalesTransaction)
                .filter(
                    SalesTransaction.business_id == goal.business_id,
                    SalesTransaction.is_duplicate.is_(False),
                    SalesTransaction.transaction_date >= start_dt,
                    SalesTransaction.transaction_date <= end_dt,
                )
                .all()
            )
            if not txns:
                # Check if business has any transactions at all
                any_txns = (
                    self.db.query(SalesTransaction.id)
                    .filter(
                        SalesTransaction.business_id == goal.business_id,
                        SalesTransaction.is_duplicate.is_(False),
                    )
                    .first()
                )
                if not any_txns:
                    return (
                        None,
                        None,
                        goal.target_value,
                        GoalDataAvailability.MISSING_DATA,
                        "No sales records uploaded. Ingest sales data to track revenue progress.",
                        "Authoritative Ingested Sales Transactions (0 records)",
                        False,
                    )
                # Has data elsewhere, but none in measurement window
                return (
                    0.0,
                    0.0,
                    goal.target_value,
                    GoalDataAvailability.AVAILABLE,
                    f"No sales transactions recorded between {window_start} and {window_end}.",
                    f"Authoritative Ingested Sales Transactions ({window_start} to {window_end})",
                    False,
                )

            total_rev = round(sum(t.total_amount for t in txns), 2)
            max_txn_date = max(t.transaction_date for t in txns)
            freshness_warning = None
            availability = GoalDataAvailability.AVAILABLE

            # Stale check: if latest record is > 30 days old
            now_dt = datetime.now(timezone.utc).replace(tzinfo=None) if max_txn_date.tzinfo is None else datetime.now(timezone.utc)
            if (now_dt - max_txn_date).days > 30:
                availability = GoalDataAvailability.STALE_DATA
                freshness_warning = (
                    f"Latest transaction is from {max_txn_date.strftime('%Y-%m-%d')} (>30 days old). "
                    "Upload fresh sales data for accurate progress."
                )

            pct, gap, achieved = self._compute_progress_math(
                metric_key=metric_key,
                baseline=goal.baseline_value,
                target=goal.target_value,
                current=total_rev,
            )
            return (
                total_rev,
                pct,
                gap,
                availability,
                freshness_warning,
                f"Authoritative Ingested Sales Transactions ({len(txns)} verified rows)",
                achieved,
            )

        # 2. Customer Concentration
        elif metric_key == "customer_concentration":
            txns = (
                self.db.query(SalesTransaction)
                .filter(
                    SalesTransaction.business_id == goal.business_id,
                    SalesTransaction.is_duplicate.is_(False),
                )
                .all()
            )
            if not txns:
                return (
                    None,
                    None,
                    None,
                    GoalDataAvailability.MISSING_DATA,
                    "No sales transactions uploaded to compute customer concentration.",
                    "Authoritative Sales Transactions (Missing)",
                    False,
                )

            by_cust = defaultdict(float)
            total_rev = 0.0
            for t in txns:
                key = t.customer_name or t.customer_id or "Anonymous"
                by_cust[key] += t.total_amount
                total_rev += t.total_amount

            if total_rev <= 0.0 or len(by_cust) < 2:
                conc = 100.0
            else:
                top_cust_rev = max(by_cust.values())
                conc = round((top_cust_rev / total_rev) * 100.0, 1)

            pct, gap, achieved = self._compute_progress_math(
                metric_key=metric_key,
                baseline=goal.baseline_value,
                target=goal.target_value,
                current=conc,
            )
            return (
                conc,
                pct,
                gap,
                GoalDataAvailability.AVAILABLE,
                None,
                f"Customer Ledger ({len(by_cust)} active accounts, top account share)",
                achieved,
            )

        # 3. Repeat Customer Rate
        elif metric_key == "repeat_customer_rate":
            txns = (
                self.db.query(SalesTransaction)
                .filter(
                    SalesTransaction.business_id == goal.business_id,
                    SalesTransaction.is_duplicate.is_(False),
                )
                .all()
            )
            if not txns:
                return (
                    None,
                    None,
                    None,
                    GoalDataAvailability.MISSING_DATA,
                    "No sales transactions uploaded to compute repeat purchase rate.",
                    "Authoritative Sales Transactions (Missing)",
                    False,
                )

            by_cust = defaultdict(int)
            for t in txns:
                key = t.customer_name or t.customer_id or "Anonymous"
                by_cust[key] += 1

            total_custs = len(by_cust)
            if total_custs == 0:
                rate = 0.0
            else:
                repeats = sum(1 for cnt in by_cust.values() if cnt >= 2)
                rate = round((repeats / total_custs) * 100.0, 1)

            pct, gap, achieved = self._compute_progress_math(
                metric_key=metric_key,
                baseline=goal.baseline_value,
                target=goal.target_value,
                current=rate,
            )
            return (
                rate,
                pct,
                gap,
                GoalDataAvailability.AVAILABLE,
                None,
                f"Customer Purchase Frequency ({repeats}/{total_custs} accounts with >=2 orders)",
                achieved,
            )

        # 4. Average Order Value
        elif metric_key == "average_order_value":
            txns = (
                self.db.query(SalesTransaction)
                .filter(
                    SalesTransaction.business_id == goal.business_id,
                    SalesTransaction.is_duplicate.is_(False),
                )
                .all()
            )
            if not txns:
                return (
                    None,
                    None,
                    None,
                    GoalDataAvailability.MISSING_DATA,
                    "No sales transactions uploaded to compute average order value.",
                    "Authoritative Sales Transactions (Missing)",
                    False,
                )

            total_rev = sum(t.total_amount for t in txns)
            aov = round(total_rev / len(txns), 2)
            pct, gap, achieved = self._compute_progress_math(
                metric_key=metric_key,
                baseline=goal.baseline_value,
                target=goal.target_value,
                current=aov,
            )
            return (
                aov,
                pct,
                gap,
                GoalDataAvailability.AVAILABLE,
                None,
                f"Sales Invoices ({len(txns)} transactions, ₹{round(total_rev, 2)} total)",
                achieved,
            )

        # 5. New Customers Count
        elif metric_key == "new_customers_count":
            txns = (
                self.db.query(SalesTransaction)
                .filter(
                    SalesTransaction.business_id == goal.business_id,
                    SalesTransaction.is_duplicate.is_(False),
                )
                .order_by(SalesTransaction.transaction_date.asc())
                .all()
            )
            if not txns:
                return (
                    None,
                    None,
                    None,
                    GoalDataAvailability.MISSING_DATA,
                    "No transactions uploaded to compute customer acquisition.",
                    "Customer Ledger (Missing)",
                    False,
                )

            # Find first order date for each customer
            first_seen: dict[str, date] = {}
            for t in txns:
                key = t.customer_name or t.customer_id or "Anonymous"
                d = t.transaction_date.date() if isinstance(t.transaction_date, datetime) else t.transaction_date
                if key not in first_seen or d < first_seen[key]:
                    first_seen[key] = d

            # Count those first seen inside the window
            acquired = sum(1 for d in first_seen.values() if window_start <= d <= window_end)
            pct, gap, achieved = self._compute_progress_math(
                metric_key=metric_key,
                baseline=goal.baseline_value,
                target=goal.target_value,
                current=float(acquired),
            )
            return (
                float(acquired),
                pct,
                gap,
                GoalDataAvailability.AVAILABLE,
                None,
                f"Customer Ledger ({acquired} new customer accounts acquired in window)",
                achieved,
            )

        # 6. Sales Upload Frequency
        elif metric_key == "sales_upload_frequency":
            uploads = (
                self.db.query(SalesUpload)
                .filter(
                    SalesUpload.business_id == goal.business_id,
                    SalesUpload.created_at >= start_dt,
                    SalesUpload.created_at <= end_dt,
                )
                .all()
            )
            cnt = float(len(uploads))
            pct, gap, achieved = self._compute_progress_math(
                metric_key=metric_key,
                baseline=goal.baseline_value,
                target=goal.target_value,
                current=cnt,
            )
            return (
                cnt,
                pct,
                gap,
                GoalDataAvailability.AVAILABLE,
                None,
                f"Data Ingestion Log ({len(uploads)} uploads recorded in period)",
                achieved,
            )

        # 7. Digital Twin Health Score
        elif metric_key == "digital_twin_health_score":
            biz = self.db.query(Business).filter(Business.id == goal.business_id).first()
            if not biz:
                return (
                    None,
                    None,
                    None,
                    GoalDataAvailability.MISSING_DATA,
                    "Business profile not found.",
                    "Digital Twin Health Engine",
                    False,
                )
            try:
                from app.services.health_score_service import HealthScoreService

                score_result = HealthScoreService.compute(biz)
                score = float(score_result.score)
                pct, gap, achieved = self._compute_progress_math(
                    metric_key=metric_key,
                    baseline=goal.baseline_value,
                    target=goal.target_value,
                    current=score,
                )
                return (
                    score,
                    pct,
                    gap,
                    GoalDataAvailability.AVAILABLE,
                    None,
                    f"Digital Twin Health Score Engine (Grade: {score_result.grade})",
                    achieved,
                )
            except Exception as exc:
                return (
                    None,
                    None,
                    None,
                    GoalDataAvailability.MISSING_DATA,
                    f"Failed to calculate health score: {exc}",
                    "Digital Twin Health Score Engine",
                    False,
                )

        # Fallback for unrecognized or custom metrics
        current = goal.current_value
        if current is None:
            return (
                None,
                None,
                goal.target_value,
                GoalDataAvailability.MISSING_DATA,
                "Awaiting progress entry or automated metric synchronization.",
                "Custom Metric Tracker",
                False,
            )

        pct, gap, achieved = self._compute_progress_math(
            metric_key=metric_key,
            baseline=goal.baseline_value,
            target=goal.target_value,
            current=current,
        )
        return (
            current,
            pct,
            gap,
            GoalDataAvailability.AVAILABLE,
            None,
            "Custom Progress Tracker",
            achieved,
        )

    def _populate_and_evaluate_goal(
        self,
        goal: BusinessGoal,
        user_id: int | None = None,
        persist: bool = True,
    ) -> BusinessGoalOut:
        """Evaluate deterministic progress and return full populated DTO."""
        today = date.today()
        (
            current_val,
            pct,
            gap,
            avail,
            freshness_warn,
            evidence_src,
            is_achieved,
        ) = self._evaluate_metric(goal)

        # Compute days remaining
        days_rem = None
        if goal.target_date:
            days_rem = (goal.target_date - today).days

        # Period boundary status adjustment:
        # If target date passed and not yet completed:
        # Note: Do not mutate completed or paused goals
        new_status = goal.status
        status_note = goal.status_notes
        if goal.status == GoalStatus.ACTIVE.value:
            if is_achieved:
                new_status = GoalStatus.COMPLETED.value
                status_note = "Goal reached target successfully."
            elif goal.target_date and goal.target_date < today:
                new_status = GoalStatus.EXPIRED.value
                status_note = f"Target deadline {goal.target_date} passed with {pct or 0}% progress."

        # Persist evaluated values if changed and persist requested
        if persist:
            has_changes = (
                goal.current_value != current_val
                or goal.progress_pct != pct
                or goal.data_availability != avail.value
                or goal.status != new_status
            )
            goal.current_value = current_val
            goal.progress_pct = pct
            goal.data_availability = avail.value
            goal.last_evaluated_at = datetime.now(timezone.utc)

            if goal.status != new_status:
                old_status = goal.status
                goal.status = new_status
                goal.status_notes = status_note
                # Log audit snapshot
                audit = BusinessGoalAudit(
                    goal_id=goal.id,
                    business_id=goal.business_id,
                    changed_by_user_id=user_id,
                    action="STATUS_CHANGED",
                    old_status=old_status,
                    new_status=new_status,
                    measured_value=current_val,
                    target_value=goal.target_value,
                    progress_pct=pct,
                    notes=status_note,
                )
                self.db.add(audit)
            elif has_changes:
                # Log progress snapshot
                audit = BusinessGoalAudit(
                    goal_id=goal.id,
                    business_id=goal.business_id,
                    changed_by_user_id=user_id,
                    action="PROGRESS_EVALUATED",
                    old_status=goal.status,
                    new_status=goal.status,
                    measured_value=current_val,
                    target_value=goal.target_value,
                    progress_pct=pct,
                    notes=f"Evaluated progress: {pct}% ({evidence_src})",
                )
                self.db.add(audit)

            self.db.commit()
            self.db.refresh(goal)

        # Related recommendations & decisions
        recs = self._get_related_recommendations(goal.business_id, goal.metric_key)
        decs = self._get_related_decisions(goal.business_id, goal.metric_key)

        # Format audit trail
        audits_out = [
            BusinessGoalAuditOut.model_validate(a) for a in (goal.audits or [])
        ]

        return BusinessGoalOut(
            id=goal.id,
            business_id=goal.business_id,
            title=goal.title,
            description=goal.description,
            timeframe=goal.timeframe,
            priority=goal.priority,
            start_date=goal.start_date,
            target_date=goal.target_date,
            metric_key=goal.metric_key,
            measurement_method=GoalMeasurementMethod(goal.measurement_method),
            baseline_value=goal.baseline_value,
            target_value=goal.target_value,
            current_value=current_val,
            progress_pct=pct,
            remaining_gap=gap,
            unit=goal.unit,
            status=GoalStatus(new_status),
            status_notes=status_note,
            data_availability=avail,
            data_freshness_warning=freshness_warn,
            evidence_source=evidence_src,
            is_achieved=is_achieved,
            days_remaining=days_rem,
            last_evaluated_at=goal.last_evaluated_at,
            created_at=goal.created_at,
            updated_at=goal.updated_at,
            related_recommendations=recs,
            related_decisions=decs,
            audits=audits_out,
        )

    def _get_related_recommendations(
        self,
        business_id: int,
        metric_key: str | None,
    ) -> list[RelatedItemOut]:
        """Fetch related active recommendations from Action Board."""
        recs = (
            self.db.query(RecommendationLifecycleState)
            .filter(
                RecommendationLifecycleState.business_id == business_id,
                RecommendationLifecycleState.status.in_(["New", "Accepted", "In Progress"]),
            )
            .limit(5)
            .all()
        )
        return [
            RelatedItemOut(
                id=r.recommendation_id,
                type="recommendation",
                title=f"Recommendation {r.recommendation_id.replace('_', ' ').title()}",
                status=r.status,
            )
            for r in recs
        ]

    def _get_related_decisions(
        self,
        business_id: int,
        metric_key: str | None,
    ) -> list[RelatedItemOut]:
        """Fetch related strategic decisions from Decision Workbench."""
        decs = (
            self.db.query(BusinessDecision)
            .filter(
                BusinessDecision.business_id == business_id,
                BusinessDecision.is_deleted.is_(False),
            )
            .order_by(BusinessDecision.created_at.desc())
            .limit(5)
            .all()
        )
        return [
            RelatedItemOut(
                id=d.id,
                type="decision",
                title=d.title,
                status=d.status,
            )
            for d in decs
        ]

    # -------------------------------------------------------------------------
    # Non-Mutating AI Explanation & Guidance
    # -------------------------------------------------------------------------

    def explain_goal(
        self,
        goal_id: int,
        business_id: int,
    ) -> GoalAIExplanationResponse:
        """Generate non-mutating AI trajectory analysis and tactical suggestions."""
        goal_out = self.get_goal(goal_id=goal_id, business_id=business_id, re_evaluate=True)

        # Trajectory assessment
        trajectory = "ON_TRACK"
        if goal_out.data_availability == GoalDataAvailability.MISSING_DATA:
            trajectory = "NEEDS_DATA"
        elif goal_out.is_achieved or goal_out.status == GoalStatus.COMPLETED:
            trajectory = "ACHIEVED"
        elif goal_out.days_remaining is not None and goal_out.days_remaining <= 0:
            trajectory = "BEHIND"
        elif (
            goal_out.progress_pct is not None
            and goal_out.progress_pct < 50.0
            and goal_out.days_remaining is not None
            and goal_out.days_remaining < 15
        ):
            trajectory = "AT_RISK"
        elif goal_out.progress_pct is not None and goal_out.progress_pct >= 80.0:
            trajectory = "ON_TRACK"

        # Deterministic Grounded Fallback
        feasibility = (
            f"Target of {goal_out.target_value} {goal_out.unit} has {goal_out.progress_pct or 0}% measured progress "
            f"with {goal_out.days_remaining or 'unspecified'} days remaining."
        )
        actions = []
        if goal_out.data_availability == GoalDataAvailability.MISSING_DATA:
            analysis = (
                f"Progress for goal '{goal_out.title}' cannot be reliably computed because required source data is missing. "
                "Deterministic verification prevents guessing or manufacturing artificial progress."
            )
            actions = [
                "Upload recent sales CSV transactions to calibrate measurement.",
                "Verify date formatting and column mappings in the Sales Intelligence portal.",
            ]
        elif trajectory == "ACHIEVED":
            analysis = (
                f"Goal '{goal_out.title}' has achieved {goal_out.progress_pct}% of target ({goal_out.current_value} {goal_out.unit}). "
                "Authoritative evidence confirms target conditions have been satisfied."
            )
            actions = [
                "Lock in operational gains by updating standard operating procedures.",
                "Define a new milestone in Business Goals to maintain momentum.",
            ]
        elif trajectory == "AT_RISK" or trajectory == "BEHIND":
            analysis = (
                f"Goal '{goal_out.title}' is currently tracking behind required velocity. "
                f"Current verified value is {goal_out.current_value} {goal_out.unit} with a remaining gap of {goal_out.remaining_gap} {goal_out.unit}."
            )
            actions = [
                "Review high-impact recommendations in the Action Board for quick volume wins.",
                "Simulate a pricing or discount scenario in What-If Simulator to evaluate demand elasticity.",
                "Focus sales outreach on existing repeat buyers to shorten collection cycles.",
            ]
        else:
            analysis = (
                f"Goal '{goal_out.title}' is on a viable trajectory. Current progress is {goal_out.progress_pct}% "
                f"against target {goal_out.target_value} {goal_out.unit}."
            )
            actions = [
                "Continue executing current sales cadence.",
                "Review weekly sales velocity in Sales Intelligence to detect early friction.",
            ]

        # LLM enhancement attempt (strictly non-mutating)
        ai_key = getattr(self.settings, "ai_api_key", "")
        if ai_key:
            try:
                from google import genai
                from google.genai import types

                client = genai.Client(api_key=ai_key)
                prompt = (
                    "You are UrsBiz AI Goal Advisor. Explain the business owner's goal trajectory and recommend tactical next steps.\n"
                    "RULES:\n"
                    "1. Strictly use the provided verified goal numbers. DO NOT fabricate or alter targets, progress, or gaps.\n"
                    "2. If data is MISSING_DATA, state that data must be uploaded and do not guess progress.\n"
                    "3. Return strict JSON with keys: analysis (string), suggested_actions (list of strings).\n\n"
                    f"GOAL EVIDENCE:\n"
                    f"- Title: {goal_out.title}\n"
                    f"- Target: {goal_out.target_value} {goal_out.unit}\n"
                    f"- Baseline: {goal_out.baseline_value} {goal_out.unit}\n"
                    f"- Current Measured: {goal_out.current_value} {goal_out.unit}\n"
                    f"- Progress: {goal_out.progress_pct}%\n"
                    f"- Remaining Gap: {goal_out.remaining_gap} {goal_out.unit}\n"
                    f"- Days Remaining: {goal_out.days_remaining}\n"
                    f"- Data Availability: {goal_out.data_availability.value}\n"
                    f"- Trajectory: {trajectory}\n"
                )
                resp = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.2,
                    ),
                )
                if resp.text:
                    parsed = json.loads(resp.text)
                    if "analysis" in parsed and isinstance(parsed["analysis"], str):
                        analysis = parsed["analysis"]
                    if "suggested_actions" in parsed and isinstance(parsed["suggested_actions"], list):
                        actions = [str(a) for a in parsed["suggested_actions"][:4]]
            except Exception as exc:
                logger.warning("Gemini AI explanation failed, used deterministic fallback: %s", exc)

        return GoalAIExplanationResponse(
            goal_id=goal_out.id,
            goal_title=goal_out.title,
            trajectory=trajectory,
            feasibility_assessment=feasibility,
            analysis=analysis,
            suggested_actions=actions,
            evidence_summary=goal_out.evidence_source,
        )
