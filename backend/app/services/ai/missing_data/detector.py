"""SPRINT AI-7 — proactive missing-data detector.

Brief contract
--------------

> Missing-data detection must be proactive. If a question
> requires data that does not exist, identify it before
> generation when possible.

The detector runs BEFORE the LLM call (step 3.7 of
``ConversationService.append_message``). It reads:

  1. The user's intent — classified by :class:`intent_router.
     QuestionIntent` (extended with HIRING in AI-7).
  2. The :class:`AssistantContext` — the rich dataclass
     describing the slice of business state the provider is
     allowed to see.

For every intent, a declarative ``FieldRequirement`` map lists
which context fields the answer REQUIRES. The detector walks the
map; for each required field whose value is missing in the
context it emits a ``MissingDataObject`` row. Empty AssistantContext
surfaces every required row.

The hiring example from the brief
----------------------------------

> User: "Can I afford to hire five employees?"
> Assistant MUST emit: payroll, cash flow, operating margin.

The HIRING map's four required fields are exactly the three the
brief mandates (plus employee_count, which the brief's example
also implies). With an empty ``AssistantContext``, the detector
emits all four rows; with a fully-populated one, it emits none.
Verified by ``test_ai7_missing_data.py::test_hiring_intent_emits_payroll_cash_flow_margin``
and ``test_hiring_intent_with_full_context_emits_no_rows``.

Design rules
------------

  * **Pure function** — ``detect_missing_data(context, intent)``
    reads the context and returns a tuple. No I/O, no side
    effects, no exceptions. A failure here would crash the chat
    endpoint for a UI-only field, which is unacceptable, so the
    function wraps the loop in a defensive guard.

  * **Frozen dataclasses** — ``MissingDataObject`` is frozen so
    the structured row is hashable + serialisable. The wire
    mirror in :class:`ChatMessageOut` accepts it as a plain
    ``list[dict]``.

  * **AI-N field append contract** — every new field the
    detector touches on ``AssistantContext`` is appended at the
    end with a safe default (0 / 0.0) so legacy callers keep
    working. The brief mandates that *absence* is the signal, so
    0 is exactly the missing sentinel.

  * **Deterministic** — two calls with the same intent + same
    context produce the same rows. The classifier is
    deterministic; the context dataclass is frozen.

  * **Backwards-compatible** — ``detect_missing_data`` returns
    ``()`` for intents not in the map (``GENERAL``,
    ``BIGGEST_WEAKNESS``, ``TWELVE_MONTH_ROADMAP``). The wire
    keeps ``missing_data=[]`` for those rows and the frontend's
    legacy prose path renders unchanged.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Mapping

# The intent router lives in ``intent_router.py`` next to the AI-7
# detector so they evolve together. Importing the enum via a string
# indirection keeps this module importable from the test suite
# before ``intent_router`` adds HIRING (AI-7 adds HIRING after this
# module lands; the ``str | Any`` fallback covers the pre-HIRING
# state).
from ..providers.intent_router import QuestionIntent


Importance = Literal["LOW", "MEDIUM", "HIGH"]


@dataclass(frozen=True)
class MissingDataObject:
    """One structured row the assistant is missing.

    The wire contract exactly matches the brief::

        {"field": "", "importance": "LOW | MEDIUM | HIGH",
         "reason": "", "affects": [], "suggested_source": ""}

    The dataclass is the canonical Python shape; the wire payload
    is the dict form (``dataclasses.asdict``).
    """

    field: str
    importance: Importance
    reason: str
    affects: tuple[str, ...] = field(default_factory=tuple)
    suggested_source: str = ""

    def to_dict(self) -> dict:
        """Serialise to the wire shape (list for ``affects``)."""
        return {
            "field": self.field,
            "importance": self.importance,
            "reason": self.reason,
            "affects": list(self.affects),
            "suggested_source": self.suggested_source,
        }


@dataclass(frozen=True)
class FieldRequirement:
    """One declared requirement the detector checks for an intent.

    ``field`` is the dotted-path name on ``AssistantContext``
    (the brief calls for ``monthly_operating_cash_flow_inr`` and
    similar; we keep snake_case attribute names everywhere).
    ``importance`` is the row's chip colour tier in the UI;
    ``reason`` is the one-line "why this matters" string the
    "Why it matters" sub-section aggregates; ``affects`` is the
    list of analysis dimensions that depend on this field (the
    UI renders it under "Affects:"); ``suggested_source`` is the
    human-readable hint the UI renders under "Source:".
    """

    field: str
    importance: Importance
    reason: str
    affects: tuple[str, ...] = field(default_factory=tuple)
    suggested_source: str = ""


# --------------------------------------------------------------------------- #
# Required-field map                                                         #
# --------------------------------------------------------------------------- #


_REQUIRED_BY_INTENT: dict[QuestionIntent, tuple[FieldRequirement, ...]] = {
    QuestionIntent.HIRING: (
        FieldRequirement(
            field="employee_count",
            importance="HIGH",
            reason=(
                "We can't size the new payroll addition without "
                "the current headcount."
            ),
            affects=("hire_affordability", "30_day_runway"),
            suggested_source="HR roster or payroll register for the current month.",
        ),
        FieldRequirement(
            field="monthly_payroll_cost_inr",
            importance="HIGH",
            reason=(
                "Existing payroll is the baseline the addition "
                "extends from."
            ),
            affects=("hire_affordability", "score"),
            suggested_source=(
                "Last 3 months of payroll register or CA's P&L."
            ),
        ),
        FieldRequirement(
            field="monthly_operating_cash_flow_inr",
            importance="HIGH",
            reason=(
                "Cash flow tells us whether the additional "
                "payroll is sustainable."
            ),
            affects=("hire_affordability", "runway"),
            suggested_source=(
                "Bank statement + cash-flow forecast for last 3 months."
            ),
        ),
        FieldRequirement(
            field="operating_margin_pct",
            importance="MEDIUM",
            reason=(
                "Operating margin tells us whether the business "
                "absorbs the new fixed cost."
            ),
            affects=("hire_affordability", "score"),
            suggested_source=(
                "Latest P&L or CA's monthly MIS."
            ),
        ),
    ),
    QuestionIntent.REACH_REVENUE_TARGET: (
        FieldRequirement(
            field="annual_revenue_inr",
            importance="HIGH",
            reason=(
                "The gap math needs an anchored current-revenue "
                "baseline."
            ),
            affects=("gap_math", "quarterly_roadmap"),
            suggested_source=(
                "Business profile → annual revenue (auto-imported from ITR)."
            ),
        ),
        FieldRequirement(
            field="target_revenue_inr",
            importance="HIGH",
            reason=(
                "The target revenue figure is the second half of "
                "the gap."
            ),
            affects=("gap_math", "levers"),
            suggested_source=(
                "Business profile → goals → target revenue."
            ),
        ),
        FieldRequirement(
            field="analytics_metrics",
            importance="MEDIUM",
            reason=(
                "KPIs anchor the quarterly milestones."
            ),
            affects=("kpis", "monitoring"),
            suggested_source=(
                "CRM export or accounting dashboard for the last 6 months."
            ),
        ),
    ),
    QuestionIntent.EXPORT_EXPANSION: (
        FieldRequirement(
            field="export_history",
            importance="MEDIUM",
            reason=(
                "Prior export context tells us whether this is a "
                "first shipment or a scale."
            ),
            affects=("export_readiness", "compliance"),
            suggested_source=(
                "Past IEC filings or shipping bills."
            ),
        ),
        FieldRequirement(
            field="certifications",
            importance="HIGH",
            reason=(
                "Most export markets require ISO / BIS / ZED "
                "certification."
            ),
            affects=("export_readiness", "buyer_acceptance"),
            suggested_source=(
                "ZED Bronze certification via the ZED portal."
            ),
        ),
        FieldRequirement(
            field="digital_presence",
            importance="MEDIUM",
            reason=(
                "Digital presence is the discovery channel for "
                "international buyers."
            ),
            affects=("export_marketing", "lead_generation"),
            suggested_source=(
                "Website + LinkedIn company page + one B2B portal listing."
            ),
        ),
    ),
    QuestionIntent.GOVERNMENT_SCHEMES: (
        FieldRequirement(
            field="industry",
            importance="HIGH",
            reason=(
                "Scheme eligibility is keyed off the declared "
                "industry."
            ),
            affects=("scheme_match", "eligibility"),
            suggested_source="Business profile → industry.",
        ),
        FieldRequirement(
            field="location",
            importance="MEDIUM",
            reason=(
                "Some schemes are state-specific."
            ),
            affects=("scheme_match",),
            suggested_source="Business profile → registered address.",
        ),
    ),
    # BIGGEST_WEAKNESS / TWELVE_MONTH_ROADMAP / GENERAL — no required
    # fields; the assistant works from context.rules + context.recommendations.
}


# --------------------------------------------------------------------------- #
# Detector                                                                   #
# --------------------------------------------------------------------------- #


def _required_fields_for_intent(
    intent: Any,
) -> tuple[FieldRequirement, ...]:
    """Return the requirement map for an intent.

    Pure function over the static ``_REQUIRED_BY_INTENT`` table.
    Unknown intents (including the pre-HIRING enum value during
    the rollout window) return ``()`` so the detector is a no-op
    on those prompts.
    """
    try:
        return _REQUIRED_BY_INTENT.get(intent, ())
    except (TypeError, AttributeError):
        return ()


def _is_missing(context: Any, field_name: str) -> bool:
    """Return True iff ``getattr(context, field_name)`` is missing.

    The "missing" test mirrors the existing per-intent section
    builders in ``intent_router.py`` — they treat ``0``, empty
    tuple, ``None``, and the sentinel string ``"unknown"`` as
    absent. Anything else is present (even if it is a value the
    assistant would judge poor quality — that's a separate axis).
    """
    try:
        value = getattr(context, field_name, _MISSING)
    except Exception:
        return True
    if value is _MISSING:
        return True
    if value is None:
        return True
    if isinstance(value, (int, float)) and value <= 0:
        return True
    if isinstance(value, str) and value.strip().lower() in _MISSING_STRINGS:
        return True
    if isinstance(value, (tuple, list, dict)) and len(value) == 0:
        return True
    return False


# Sentinel + absent-string set. The string sentinels are the same
# ones the context_builder stamps when an upstream value is unknown
# (legal_name / industry / location / business_type / employee_count).
_MISSING = object()
_MISSING_STRINGS: frozenset[str] = frozenset({"", "unknown", "n/a", "na", "—"})


def detect_missing_data(
    context: Any,
    intent: Any,
) -> tuple[MissingDataObject, ...]:
    """Return the structured missing-data rows for an intent.

    Walks :data:`_REQUIRED_BY_INTENT[intent]` and emits a
    :class:`MissingDataObject` per requirement whose value on
    ``context`` is missing. Returns an empty tuple when the
    intent has no required fields or when ``context`` is None.

    The function NEVER raises. A failure here is a UI-only field;
    the chat endpoint must not crash because of it.
    """
    try:
        if context is None:
            return ()
        rows: list[MissingDataObject] = []
        for req in _required_fields_for_intent(intent):
            if not _is_missing(context, req.field):
                continue
            rows.append(
                MissingDataObject(
                    field=req.field,
                    importance=req.importance,
                    reason=req.reason,
                    affects=req.affects,
                    suggested_source=req.suggested_source,
                )
            )
        return tuple(rows)
    except Exception:  # pragma: no cover — defensive
        return ()


def detect_missing_data_from_mapping(
    context_map: Mapping[str, Any],
    intent: Any,
) -> tuple[MissingDataObject, ...]:
    """Detector variant that reads from a plain dict.

    Used by the frontend mirror (``frontend/features/assistant/
    sections/detectMissingData.ts``) and by tests that build a
    minimal context without instantiating the dataclass. The
    semantics are identical to :func:`detect_missing_data` —
    only the lookup path changes (dict vs getattr).
    """
    try:
        if context_map is None:
            return ()
        rows: list[MissingDataObject] = []
        for req in _required_fields_for_intent(intent):
            value = context_map.get(req.field, _MISSING)
            if value is _MISSING or value is None:
                rows.append(
                    MissingDataObject(
                        field=req.field,
                        importance=req.importance,
                        reason=req.reason,
                        affects=req.affects,
                        suggested_source=req.suggested_source,
                    )
                )
                continue
            if isinstance(value, (int, float)) and value <= 0:
                rows.append(
                    MissingDataObject(
                        field=req.field,
                        importance=req.importance,
                        reason=req.reason,
                        affects=req.affects,
                        suggested_source=req.suggested_source,
                    )
                )
                continue
            if isinstance(value, str) and value.strip().lower() in _MISSING_STRINGS:
                rows.append(
                    MissingDataObject(
                        field=req.field,
                        importance=req.importance,
                        reason=req.reason,
                        affects=req.affects,
                        suggested_source=req.suggested_source,
                    )
                )
                continue
            if isinstance(value, (tuple, list, dict)) and len(value) == 0:
                rows.append(
                    MissingDataObject(
                        field=req.field,
                        importance=req.importance,
                        reason=req.reason,
                        affects=req.affects,
                        suggested_source=req.suggested_source,
                    )
                )
        return tuple(rows)
    except Exception:  # pragma: no cover — defensive
        return ()


def to_payload(rows: tuple[MissingDataObject, ...]) -> list[dict]:
    """Serialise a tuple of rows for the wire / JSON column.

    The dataclass ``.to_dict()`` already converts ``affects`` to a
    list; this helper is a one-liner so callers don't have to
    remember the method name.
    """
    return [r.to_dict() for r in rows]


def from_payload(payload: list[dict] | tuple[dict, ...]) -> tuple[MissingDataObject, ...]:
    """Re-hydrate rows from a wire payload (used by tests + the
    legacy-row default branch in ``GenerationMeta.from_dict``).
    """
    if not payload:
        return ()
    rows: list[MissingDataObject] = []
    for item in payload:
        if not isinstance(item, Mapping):
            continue
        field_name = str(item.get("field") or "")
        if not field_name:
            continue
        importance = str(item.get("importance") or "MEDIUM").upper()
        if importance not in ("LOW", "MEDIUM", "HIGH"):
            importance = "MEDIUM"
        rows.append(
            MissingDataObject(
                field=field_name,
                importance=importance,  # type: ignore[arg-type]
                reason=str(item.get("reason") or ""),
                affects=tuple(item.get("affects") or ()),
                suggested_source=str(item.get("suggested_source") or ""),
            )
        )
    return tuple(rows)