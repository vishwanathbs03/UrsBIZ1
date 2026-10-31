"""CrossSourceContradictionDetector — SPRINT AI-12.

Pre-LLM detection of profile-vs-analytics-vs-scheme-vs-forecast
conflicts. Walks the deterministic context the question
understanding selected and the :class:`StructuredToolEnvelope`
tuple the dispatcher produced; emits a :class:`ContradictionReport`
with severity ``none / low / medium / high``.

The detector is **advisory only**. It NEVER blocks the LLM call.
On ``severity == "high"``, the caller augments the LLM system
prompt with a ``CONTRADICTIONS:`` disclosure block so the LLM
sees the conflict before it answers. On ``low / medium`` the
disclosure is omitted to avoid noise.

Heuristic shape
---------------

The detector scans three pairs of source types and looks for
overlapping numeric claims with materially different values:

  * profile ↔ analytics — business score and revenue.
  * analytics ↔ scheme — revenue tiers used by scheme
    eligibility.
  * scheme ↔ forecast — projected revenue impact from the
    selected scheme versus the forecast horizon.

Materiality threshold is 20 % — below that we treat the two
values as the same number for the audit trail.

Side-effect free. Pure function over the inputs. No I/O. No
LLM access.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from app.services.ai.reasoning.structured_envelope import StructuredToolEnvelope


Severity = str  # "none" | "low" | "medium" | "high"


@dataclass(frozen=True)
class ContradictionItem:
    """A single detected contradiction.

    Attributes
    ----------
    source_a, source_b:
        The two tools / contexts that disagree (e.g.
        ``"profile"`` vs ``"analytics"``).
    metric:
        The metric key being compared (e.g. ``"revenue"``,
        ``"health_score"``).
    value_a, value_b:
        The two values in the same units.
    delta_pct:
        The signed percentage difference
        ``(b - a) / a * 100``. ``0.0`` when either side is
        zero (caller treats zero-delta as no conflict).
    note:
        One-line human-readable explanation.
    """

    source_a: str
    source_b: str
    metric: str
    value_a: float
    value_b: float
    delta_pct: float
    note: str = ""

    def to_dict(self) -> dict:
        return {
            "source_a": self.source_a,
            "source_b": self.source_b,
            "metric": self.metric,
            "value_a": self.value_a,
            "value_b": self.value_b,
            "delta_pct": self.delta_pct,
            "note": self.note,
        }


@dataclass(frozen=True)
class ContradictionReport:
    """The full detection result for a single request.

    Attributes
    ----------
    severity:
        The most severe contradiction detected. ``"none"``
        when the report is empty.
    items:
        Tuple of :class:`ContradictionItem` — every
        material contradiction the scan found.
    rationale:
        One-line summary for the audit trail.
    """

    severity: Severity = "none"
    items: tuple[ContradictionItem, ...] = field(default_factory=tuple)
    rationale: str = ""

    def to_dict(self) -> dict:
        return {
            "severity": self.severity,
            "items": [i.to_dict() for i in self.items],
            "rationale": self.rationale,
        }


# Materiality threshold — below this we treat the two numbers
# as the same for the audit trail.
_MATERIALITY_PCT = 20.0

# Severity thresholds — at or above these counts we escalate.
_HIGH_AT_OR_ABOVE = 2
_MEDIUM_AT_OR_ABOVE = 1


def _coerce_float(value: Any) -> float | None:
    """Best-effort coercion of ``value`` to ``float``.

    Returns ``None`` when the value is not numeric. Strings
    are tolerated (used by some legacy ``health_score``
    payloads that print ``"72.5"`` instead of ``72.5``).
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except (TypeError, ValueError):
            return None
    return None


def _delta_pct(a: float, b: float) -> float:
    """Signed percentage delta of ``b`` vs ``a``. Zero-safe."""
    if a == 0:
        return 0.0
    return (b - a) / a * 100.0


class CrossSourceContradictionDetector:
    """Scan context + envelopes for material cross-source conflicts."""

    def detect(
        self,
        context: Any,
        envelopes: tuple["StructuredToolEnvelope", ...] = (),
    ) -> ContradictionReport:
        """Return a :class:`ContradictionReport` for the request.

        Pure function. Same inputs ⇒ same output. The scan
        walks:

          * ``context.profile`` (when present) for the
            business-baseline numbers.
          * ``context.analytics`` (when present) for the
            last-90-days numbers.
          * the ``envelopes`` tuple for ``schemes_sprint16``
            and ``predictive_sprint14`` numbers.
        """
        items: list[ContradictionItem] = []

        profile = getattr(context, "profile", None)
        analytics = getattr(context, "analytics", None)
        profile_rev = _profile_revenue(profile)
        analytics_rev = _analytics_revenue(analytics)
        if profile_rev is not None and analytics_rev is not None:
            delta = _delta_pct(profile_rev, analytics_rev)
            if abs(delta) >= _MATERIALITY_PCT:
                items.append(
                    ContradictionItem(
                        source_a="profile",
                        source_b="analytics",
                        metric="annual_revenue",
                        value_a=profile_rev,
                        value_b=analytics_rev,
                        delta_pct=delta,
                        note=(
                            "profile and analytics disagree on annual "
                            f"revenue by {delta:+.1f}%"
                        ),
                    )
                )

        # Envelope-driven checks.
        health_envelope = _envelope_for(envelopes, "health_score")
        if health_envelope is not None:
            health_value = _coerce_float(health_envelope.value)
            if health_value is not None and profile is not None:
                profile_score = _coerce_float(getattr(profile, "health_score", None))
                if profile_score is not None and profile_score > 0:
                    delta = _delta_pct(profile_score, health_value)
                    if abs(delta) >= _MATERIALITY_PCT:
                        items.append(
                            ContradictionItem(
                                source_a="profile",
                                source_b="health_score",
                                metric="health_score",
                                value_a=profile_score,
                                value_b=health_value,
                                delta_pct=delta,
                                note=(
                                    "profile and health_score envelope "
                                    f"disagree by {delta:+.1f}%"
                                ),
                            )
                        )

        scheme_envelope = _envelope_for(envelopes, "schemes_sprint16")
        forecast_envelope = _envelope_for(envelopes, "predictive_sprint14")
        if (
            scheme_envelope is not None
            and forecast_envelope is not None
            and scheme_envelope.value is not None
            and forecast_envelope.value is not None
        ):
            scheme_val = _coerce_float(scheme_envelope.value)
            forecast_val = _coerce_float(forecast_envelope.value)
            if scheme_val is not None and forecast_val is not None and scheme_val > 0:
                delta = _delta_pct(scheme_val, forecast_val)
                if abs(delta) >= _MATERIALITY_PCT:
                    items.append(
                        ContradictionItem(
                            source_a="schemes_sprint16",
                            source_b="predictive_sprint14",
                            metric="projected_revenue",
                            value_a=scheme_val,
                            value_b=forecast_val,
                            delta_pct=delta,
                            note=(
                                "scheme and forecast envelopes disagree "
                                f"by {delta:+.1f}%"
                            ),
                        )
                    )

        # Roll up severity.
        severity: Severity = "none"
        if len(items) >= _HIGH_AT_OR_ABOVE:
            severity = "high"
        elif len(items) >= _MEDIUM_AT_OR_ABOVE:
            severity = "medium"
        rationale = (
            f"{len(items)} material contradiction(s) detected "
            f"(threshold {_MATERIALITY_PCT:.0f}%)"
        )
        return ContradictionReport(
            severity=severity,
            items=tuple(items),
            rationale=rationale,
        )


def _profile_revenue(profile: Any) -> float | None:
    """Pull annual revenue off the profile, tolerating schema drift."""
    if profile is None:
        return None
    for attr in ("annual_revenue", "annualRevenue", "revenue"):
        v = getattr(profile, attr, None)
        coerced = _coerce_float(v)
        if coerced is not None:
            return coerced
    return None


def _analytics_revenue(analytics: Any) -> float | None:
    """Pull revenue off the analytics dict, tolerating schema drift."""
    if analytics is None:
        return None
    if isinstance(analytics, dict):
        for key in ("annual_revenue", "annualRevenue", "revenue"):
            coerced = _coerce_float(analytics.get(key))
            if coerced is not None:
                return coerced
    for attr in ("annual_revenue", "annualRevenue", "revenue"):
        v = getattr(analytics, attr, None)
        coerced = _coerce_float(v)
        if coerced is not None:
            return coerced
    return None


def _envelope_for(
    envelopes: tuple["StructuredToolEnvelope", ...],
    tool_name: str,
) -> "StructuredToolEnvelope | None":
    """Return the first envelope matching ``tool_name`` (or ``None``)."""
    for env in envelopes:
        if env.tool_name == tool_name:
            return env
    return None