"""Business service — orchestration + business rules for the
Business Digital Twin.

The service is the only place that knows what "complete" means. The
repository owns SQL, the service owns decisions:

  * Many businesses per user (Sprint 23; the 1:1 cap is lifted)
  * Profile completeness rubric (deterministic, documented)
  * Replace-on-update semantics for nested collections
  * Mark-as-complete on the final PUT if completeness >= 100
  * Active-business promotion on every successful create

Endpoints stay thin: they convert HTTP into a service call, map
service exceptions to status codes, and serialize the result.
"""

from __future__ import annotations

from typing import Any

from app.models.business import Business
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.repositories.business_repository import (
    BusinessNotFound,
    BusinessRepository,
)
from app.schemas.business import (
    BusinessCreate,
    BusinessListItem,
    BusinessMeta,
    BusinessMinimalCreate,
    BusinessOut,
    BusinessUpdate,
    BusinessWithCompleteness,
    CompletenessMissingField,
    ProfileCompleteness,
)
from app.services.auth_service import AuthService


class BusinessLastError(Exception):
    """Raised when ``delete`` would leave the user with zero
    businesses. The endpoint maps this to HTTP 409."""


class BusinessService:
    """Stateless façade over :class:`BusinessRepository`."""

    def __init__(
        self,
        repo: BusinessRepository,
        auth_service: AuthService | None = None,
    ) -> None:
        """Sprint 23 - the service now optionally takes an
        ``AuthService`` so ``create`` / ``create_minimal`` can
        promote the new business to active. Endpoints that never
        create (the ``PUT`` / ``DELETE`` flows) keep the old
        single-argument call site by passing ``auth_service=None``."""
        self._repo = repo
        self._auth_service = auth_service

    # ---- Read ----------------------------------------------------------

    def get_for_owner(self, owner_id: int) -> BusinessWithCompleteness:
        """Back-compat: read the user's primary business.

        Preserved for the legacy callers (twin aggregator, finance
        aggregator, copilot context). Returns the user's *active*
        business if ``active_business_id`` is set, else falls back
        to the most-recently-created row, else ``BusinessNotFound``.
        Sprint 23's new endpoint calls the User-aware overload
        ``get_active_for_user`` below.
        """
        user_repo = UserRepository(self._repo._db)
        user = user_repo.get_by_id(owner_id)
        if user is None:
            raise BusinessNotFound(
                f"No business profile for owner_id={owner_id}."
            )
        return self.get_active_for_user(user)

    def get_active_for_user(self, user: User) -> BusinessWithCompleteness:
        """Sprint 23 - the active-business read path used by the
        ``GET /business`` endpoint.

        Resolution order:

        1. ``user.active_business_id`` if set and still owned.
        2. Otherwise, the user's most recently created business.
        3. Otherwise, ``BusinessNotFound`` (the user owns zero).
        """
        business = self._resolve_active(user)
        if business is None:
            raise BusinessNotFound("No business profile for this user yet.")
        return self._build(business)

    def exists(self, owner_id: int) -> bool:
        return self._repo.exists_for_owner(owner_id)

    def list_for_owner(self, user: User) -> list[BusinessListItem]:
        """Sprint 23 - every business the user owns, lightweight
        projection, oldest first (chronological "you added these
        in this order" reads better in the panel)."""
        rows = self._repo.list_for_owner(user.id)
        return [BusinessListItem.model_validate(r) for r in rows]

    def _resolve_active(self, user: User) -> Business | None:
        """Internal - return the user's active business row, or the
        most-recently-created fallback, or ``None``."""
        if user.active_business_id is not None:
            direct = self._repo.get_by_id_for_owner(
                business_id=user.active_business_id, owner_id=user.id
            )
            if direct is not None:
                return direct
        rows = self._repo.list_for_owner(user.id)
        return rows[-1] if rows else None

    # ---- Create --------------------------------------------------------

    def create(
        self, user: User, payload: BusinessCreate
    ) -> BusinessWithCompleteness:
        """Create a new business for the user; promote it to active.

        Sprint 23 - the 1:1 cap is lifted. A user may own many
        businesses. After a successful insert, the new row becomes
        the active one so the rest of the app picks it up
        immediately.
        """
        owner_id = user.id
        basic = payload.basic
        capacity = payload.capacity

        business = self._repo.create(
            owner_id=owner_id,
            legal_name=basic.legal_name,
            industry=basic.industry,
            established_year=basic.established_year,
            employee_count=basic.employee_count,
            annual_revenue=basic.annual_revenue,
            revenue_currency=basic.revenue_currency,
            trade_name=basic.trade_name,
            sub_industry=basic.sub_industry,
            business_type=basic.business_type,
            description=basic.description,
            country=basic.country,
            state_region=basic.state_region,
            city=basic.city,
            production_capacity=(capacity.production_capacity if capacity else None),
            production_capacity_unit=(capacity.production_capacity_unit if capacity else None),
            capacity_utilization_pct=(capacity.capacity_utilization_pct if capacity else None),
            monthly_production_units=(capacity.monthly_production_units if capacity else None),
        )

        # Nested collections — created in the same transaction so a
        # failed insert rolls everything back.
        if payload.products:
            self._repo.replace_products(business, [p.model_dump() for p in payload.products])
        if payload.certifications:
            self._repo.replace_certifications(
                business, [c.model_dump() for c in payload.certifications]
            )
        if payload.export_history:
            self._repo.replace_export_history(
                business, [e.model_dump() for e in payload.export_history]
            )
        if payload.goals:
            self._repo.replace_goals(business, [g.model_dump() for g in payload.goals])
        if payload.challenges:
            self._repo.replace_challenges(
                business, [c.model_dump() for c in payload.challenges]
            )
        if payload.digital_presence is not None:
            self._repo.upsert_digital_presence(
                business, payload.digital_presence.model_dump()
            )

        self._repo._db.commit()  # commit before refreshing nested rows

        # Sprint 23 - promote the newly created business to active so
        # the rest of the app picks it up immediately. The user's
        # current ``active_business_id`` may be pointing at a
        # different row (or be NULL); overwrite it.
        if self._auth_service is not None:
            self._auth_service.set_active_business(user, business.id)
        else:
            # No auth service wired - just set the column directly so
            # the create path still works in tests that don't go
            # through the FastAPI dependency graph.
            user.active_business_id = business.id
            self._repo._db.commit()
            self._repo._db.refresh(user)

        fresh = self._repo.get_by_id_for_owner(business.id, owner_id)
        assert fresh is not None  # we just created it

        # Same mark-complete logic as update(): the user lands on
        # the dashboard / re-fetches immediately, so the first
        # response must already reflect "complete" when applicable.
        completeness = self._compute_completeness(fresh)
        self._repo.mark_complete(fresh, completed=completeness.completed)
        self._repo._db.commit()
        return self._build(self._repo.get_by_id_for_owner(business.id, owner_id) or fresh)

    def create_minimal(
        self, user: User, payload: BusinessMinimalCreate
    ) -> BusinessWithCompleteness:
        """Sprint 23 - inline 'Add a business' form path.

        Build a ``BusinessCreate`` from the six required fields and
        delegate to ``create()``. The wizard on ``/business`` will
        fill in the remaining 7 sections after the row exists."""
        from app.schemas.business import BasicSection  # local to avoid cycles

        basic = BasicSection(
            legal_name=payload.legal_name,
            industry=payload.industry,
            established_year=payload.established_year,
            employee_count=payload.employee_count,
            annual_revenue=payload.annual_revenue,
            revenue_currency=payload.revenue_currency,
        )
        return self.create(user, BusinessCreate(basic=basic))

    # ---- Update --------------------------------------------------------

    def update(self, owner_id: int, payload: BusinessUpdate) -> BusinessWithCompleteness:
        # Sprint 23 - PUT /business updates the user's *active*
        # business. ``get_by_owner`` was the old 1:1 path and still
        # returns the user's single business when one exists, which
        # happens to be the right answer when there is only one row.
        # For multi-business users, callers should still hit the
        # active row (the canonical read path).
        business = self._repo.get_by_owner(owner_id)
        if business is None:
            raise BusinessNotFound(
                "No business profile to update. POST /business first."
            )

        if payload.basic is not None:
            b = payload.basic
            self._repo.update_basic(
                business,
                legal_name=b.legal_name,
                industry=b.industry,
                established_year=b.established_year,
                employee_count=b.employee_count,
                annual_revenue=b.annual_revenue,
                revenue_currency=b.revenue_currency,
                trade_name=b.trade_name,
                sub_industry=b.sub_industry,
                business_type=b.business_type,
                description=b.description,
                country=b.country,
                state_region=b.state_region,
                city=b.city,
            )

        if payload.capacity is not None:
            self._repo.update_capacity(
                business,
                production_capacity=payload.capacity.production_capacity,
                production_capacity_unit=payload.capacity.production_capacity_unit,
                capacity_utilization_pct=payload.capacity.capacity_utilization_pct,
                monthly_production_units=payload.capacity.monthly_production_units,
            )

        if payload.products is not None:
            self._repo.replace_products(
                business, [p.model_dump() for p in payload.products]
            )
        if payload.certifications is not None:
            self._repo.replace_certifications(
                business, [c.model_dump() for c in payload.certifications]
            )
        if payload.export_history is not None:
            self._repo.replace_export_history(
                business, [e.model_dump() for e in payload.export_history]
            )
        if payload.goals is not None:
            self._repo.replace_goals(
                business, [g.model_dump() for g in payload.goals]
            )
        if payload.challenges is not None:
            self._repo.replace_challenges(
                business, [c.model_dump() for c in payload.challenges]
            )
        if payload.digital_presence is not None:
            self._repo.upsert_digital_presence(
                business, payload.digital_presence.model_dump()
            )

        # H7.1 — flush pending mutations BEFORE the populate_existing
        # re-read below. The session runs with ``autoflush=False`` (see
        # ``app.utils.database.SessionLocal``) and ``get_by_owner`` uses
        # ``populate_existing=True``. Without an explicit flush the re-read
        # reloads the STALE committed row over the in-memory changes the
        # update_* / replace_* methods just staged, so a PUT returned 200
        # while silently discarding every field. Flushing makes the staged
        # changes the read-back's source of truth within the transaction.
        self._repo.flush()

        # If everything is filled in, flip is_completed. The service
        # owns this rule; the repository stays dumb.
        fresh = self._repo.get_by_owner(owner_id)
        assert fresh is not None
        completeness = self._compute_completeness(fresh)
        self._repo.mark_complete(fresh, completed=completeness.completed)
        self._repo._db.commit()
        return self._build(self._repo.get_by_owner(owner_id) or fresh)

    # ---- Delete --------------------------------------------------------

    def delete(self, user: User, business_id: int) -> Any:
        """Sprint 23 - delete a specific business owned by the user.

        Raises:

        * ``BusinessNotFound`` if the user does not own ``business_id``.
        * ``BusinessLastError`` if this is the user's only remaining
          business - we forbid deleting the last one so a user never
          ends up with zero context the rest of the app can render.

        Returns the standard ``DeleteResponse`` shape (``{"detail":
        ..., "id": <business_id>}``).
        """
        business = self._repo.get_by_id_for_owner(
            business_id=business_id, owner_id=user.id
        )
        if business is None:
            raise BusinessNotFound(
                f"No business with id={business_id} owned by this user."
            )

        remaining = self._repo.count_for_owner(user.id)
        if remaining <= 1:
            raise BusinessLastError(
                "Cannot delete your only remaining business."
            )

        self._repo.delete(business)
        # If the deleted row was the user's active one, point the
        # active id at another row (most recently created). If the
        # row was non-active, leave the active id untouched.
        if user.active_business_id == business_id:
            self._repo._db.flush()
            rows = self._repo.list_for_owner(user.id)
            # ``rows`` already excludes the deleted one because of
            # ``populate_existing`` semantics; pick the freshest.
            user.active_business_id = rows[-1].id if rows else None
        self._repo._db.commit()
        from app.schemas.business import DeleteResponse

        return DeleteResponse(
            detail="Business profile deleted.",
            id=business_id,
        )

    # ---- Internal ------------------------------------------------------

    def _build(self, business: Business) -> BusinessWithCompleteness:
        completeness = self._compute_completeness(business)
        return BusinessWithCompleteness(
            business=BusinessOut.model_validate(business),
            completeness=completeness,
            meta=BusinessMeta(
                profile_completion=completeness.score,
                profile_status=_status_from_score(completeness.score),
                last_updated=business.updated_at,
            ),
        )

    # ------------------------------------------------------------------- #
    # Completeness rubric
    # ------------------------------------------------------------------- #
    #
    # The rubric is explicit (not derived from a vague "is anything
    # empty" check) so the UI can show the user *which* fields are
    # missing, and the server stays the source of truth.
    #
    # Score = round(100 * completed_fields / total_fields). When all
    # fields are present the profile is marked complete.
    #
    # Sections map 1:1 to the wizard steps so the frontend can deep
    # link to the missing field.

    @staticmethod
    def _compute_completeness(business: Business) -> ProfileCompleteness:
        fields: list[tuple[str, str, str, Any]] = [
            # (section, key, label, value)
            ("basic", "legal_name", "Business name", business.legal_name),
            ("basic", "industry", "Industry", business.industry),
            ("basic", "established_year", "Established year", business.established_year),
            ("basic", "employee_count", "Employee count", business.employee_count),
            ("basic", "annual_revenue", "Annual revenue", business.annual_revenue),
            ("basic", "country", "Country", business.country),
            ("products", "products", "At least one product", business.products),
            ("capacity", "production_capacity", "Production capacity", business.production_capacity),
            ("digital_presence", "website_url", "Website", _attr(business.digital_presence, "website_url")),
            ("compliance", "certifications", "At least one certification", business.certifications),
            ("export_history", "export_history", "Export history", business.export_history),
            ("export_history", "iec_number", "IEC", _has_iec(business)),
            ("goals", "goals", "Business goals", business.goals),
            ("challenges", "challenges", "Business challenges", business.challenges),
        ]

        completed = 0
        missing: list[CompletenessMissingField] = []
        for section, key, label, value in fields:
            if _is_present(value):
                completed += 1
            else:
                missing.append(
                    CompletenessMissingField(section=section, field=key, label=label)
                )

        total = len(fields)
        score = round(100 * completed / total) if total else 0
        return ProfileCompleteness(
            score=score,
            completed=score >= 100,
            total_fields=total,
            completed_fields=completed,
            missing=missing,
        )


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _is_present(value: Any) -> bool:
    """Truthy + non-empty. Used for both scalar and collection fields."""
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ""
    if isinstance(value, (list, tuple, set)):
        return len(value) > 0
    if isinstance(value, (int, float)):
        return value > 0 or value == 0  # 0 is a valid revenue / employee count
    return bool(value)


def _attr(obj, name: str) -> Any:
    return getattr(obj, name, None) if obj is not None else None


def _has_iec(business: Business) -> Any:
    """IEC counts as present if any export row has an IEC number set."""
    for row in business.export_history:
        if row.iec_number and row.iec_number.strip():
            return row.iec_number
    return None


def _status_from_score(score: int) -> str:
    """Map a 0..100 completeness score to the three-step status the UI
    uses for chip / pill rendering.

      score == 0          -> "draft"        (no fields filled in)
      0  < score <  100   -> "in_progress"
      score == 100        -> "complete"
    """
    if score <= 0:
        return "draft"
    if score >= 100:
        return "complete"
    return "in_progress"
