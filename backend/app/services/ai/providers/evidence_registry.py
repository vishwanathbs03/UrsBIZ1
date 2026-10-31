"""EvidenceRegistry — Sprint H7.8C.

A read-only, in-memory index of every business fact the
provider layer is allowed to ground against. The registry is
the *sole source of truth* for evidence IDs in the
grounded-mode response contract: the model may only cite IDs
that resolve here.

Design goals
------------

  * **Stable IDs** — every entry has an ``id`` that is
    reproducible across requests for the same business state.
    IDs are derived from the upstream identifiers already
    present on :class:`AssistantContext` (recommendation
    IDs, scheme IDs, rule IDs, action IDs). A short prefix
    prevents collisions across kinds (``rec_*``, ``rule_*``,
    ``scheme_*`` …).

  * **No fabrication** — only fields that exist on the
    upstream payload are exposed. Missing values stay
    ``None`` / empty. The validator that consumes the
    registry never invents a business number.

  * **Bounded** — the registry inherits the existing
    :class:`AssistantContextBuilder` caps (11 scores, 12
    recommendations, 12 rules, 8 insights, 8 schemes, 4
    forecasts, 6 action items, 1 DNA). At most ~62 entries.

  * **Traceable** — every entry carries ``source_topic``
    (one of the existing :class:`ChatSource` topic literals)
    so the renderer can cross-link evidence cards back to
    the upstream service that produced the fact.

The registry is **not** persisted. It is built once per
:class:`AssistantRequest` from the same :class:`AssistantContext`
the prompt builder already consumes, so no upstream call is
duplicated.

Open-mode note
--------------

The registry is built in **grounded mode** only. Open-mode
questions deliberately bypass it — the model is free to answer
with no evidence binding. The UI labels open-mode responses
differently (the ``open_domain`` trust badge) and persists
``grounding_validated=false`` on the provenance envelope.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, Iterable

from app.services.ai.providers.base import AssistantContext


class EvidenceKind(str, Enum):
    """The eight kinds of evidence the registry tracks.

    The string values match the existing
    ``EvidenceReference.kind`` vocabulary in
    ``response_schema.py`` plus the new ``forecast`` (alias
    for scenarios) and ``dna`` kinds. ``scheme`` is distinct
    from a ``recommendation`` — schemes are government
    programs, recommendations are internal UrsBiz actions.
    """

    SCORE = "score"
    RECOMMENDATION = "recommendation"
    RULE = "rule"
    INSIGHT = "insight"
    SCHEME = "scheme"
    FORECAST = "forecast"
    ACTION = "action"
    DNA = "dna"


@dataclass(frozen=True)
class EvidenceEntry:
    """One immutable record in the registry.

    Attributes
    ----------
    id:
        Stable identifier used in prompt blocks and response
        references. Prefix encodes the kind (``rec_*``,
        ``rule_*`` …) so two entries can never collide on
        identifier alone.
    kind:
        :class:`EvidenceKind` enum value.
    label:
        Human-readable title, capped at 120 chars. Suitable
        for direct rendering in the trust disclosure panel.
    value:
        Compact one-line representation of the fact,
        capped at 280 chars. The model may quote it
        verbatim in its executive summary.
    source_topic:
        A :class:`ChatSource` topic literal that maps this
        evidence back to the upstream service.
    authoritative:
        True when the entry was produced by a deterministic
        backend (rules engine, recommendation engine, scheme
        engine, etc.) — not LLM-generated. All existing
        projectors emit ``True``; the field exists for the
        AI-1 audit trail. (Default ``True``.)
    source_type:
        A short string naming which deterministic engine
        produced the entry. One of ``"computed"``,
        ``"scheme_engine"``, ``"rule_engine"``,
        ``"forecast_engine"``, ``"action_board"``,
        ``"profile"``, ``"echo"``. Set by the registry's
        augmentation helper after the yield.
    freshness:
        ISO-8601 timestamp of when the underlying data was
        generated (read from the AssistantContext sidecar
        fields). ``"unknown"`` when the sidecar is not set.
        Drives the AI-1 freshness check.
    business_context:
        A small slice of the business profile
        (``{industry, location, business_type, employee_count}``)
        captured at augmentation time. Useful for the
        audit trail and for debugging evidence-on-evidence
        reasoning.
    """

    id: str
    kind: EvidenceKind
    label: str
    value: str
    source_topic: str

    # AI-1 audit-trail fields — appended at the END so the 10
    # positional ``yield EvidenceEntry(...)`` sites in this file
    # keep working unchanged. All four have defaults.
    authoritative: bool = True
    source_type: str = "computed"
    freshness: str = "unknown"
    business_context: dict[str, Any] = field(default_factory=dict)


# Maximum length of the ``label`` and ``value`` fields. The
# registry is meant to be inlined into the prompt, so we keep
# every field compact. The validator never inflates these
# values — they are projections of upstream facts.
_LABEL_CAP = 120
_VALUE_CAP = 280


# Sanitiser: collapse whitespace, strip control characters.
# Used by the registry to keep the inlined prompt block
# readable and to keep the JSON we serialise into
# ``generation_meta_json`` small.
_WHITESPACE_RE = re.compile(r"\s+")
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _clean(text: str | None, *, cap: int) -> str:
    """Trim whitespace, drop control chars, clamp length."""
    if not text:
        return ""
    text = _CONTROL_RE.sub("", str(text))
    text = _WHITESPACE_RE.sub(" ", text).strip()
    if len(text) > cap:
        text = text[: cap - 1].rstrip() + "…"
    return text


def _slug(value: str) -> str:
    """Convert an upstream ID into a registry-safe slug.

    Only lowercase ASCII alphanumerics and underscores
    survive. Anything else is replaced with ``_`` and
    consecutive ``_`` are collapsed. The result is suitable
    for inlining into a prompt block and into a JSON
    envelope without further escaping.
    """
    if not value:
        return ""
    out = re.sub(r"[^a-z0-9_]+", "_", str(value).lower()).strip("_")
    return re.sub(r"_+", "_", out)


# --------------------------------------------------------------------------- #
# AI-1 — entry augmentation
# --------------------------------------------------------------------------- #
#
# Every :class:`EvidenceEntry` produced by the legacy
# ``_from_*`` projectors is augmented with three new audit-trail
# fields:
#
#   * ``source_type`` — which deterministic engine emitted the
#     entry (``"computed"``, ``"scheme_engine"``, ``"rule_engine"``,
#     ``"forecast_engine"``, ``"action_board"``, ``"profile"``,
#     ``"echo"``).
#   * ``freshness`` — ISO-8601 timestamp read from the
#     AssistantContext sidecar (``*_generated_at`` fields).
#     ``"unknown"`` when the sidecar is absent.
#   * ``business_context`` — small slice of the profile
#     (``industry``, ``location``, ``business_type``,
#     ``employee_count``) captured at augmentation time.
#
# The augmentation runs in :meth:`EvidenceRegistry.__init__`
# after the entries are collected, so the legacy ``_from_*``
# projectors stay byte-identical — this is the additive-
# compat guarantee.


# Map ``EvidenceKind`` → ``source_type`` label. Used when the
# sidecar does not carry an explicit ``source_type``.
_KIND_TO_SOURCE_TYPE: dict[EvidenceKind, str] = {
    EvidenceKind.SCORE: "computed",
    EvidenceKind.RECOMMENDATION: "recommendation_engine",
    EvidenceKind.RULE: "rule_engine",
    EvidenceKind.INSIGHT: "insight_engine",
    EvidenceKind.SCHEME: "scheme_engine",
    EvidenceKind.FORECAST: "forecast_engine",
    EvidenceKind.ACTION: "action_board",
    EvidenceKind.DNA: "profile",
}


def _resolve_freshness(context: AssistantContext, kind: EvidenceKind) -> str:
    """Return the appropriate ``*_generated_at`` timestamp for the kind."""
    if context is None:
        return "unknown"
    mapping: dict[EvidenceKind, str | None] = {
        EvidenceKind.SCORE: getattr(context, "twin_generated_at", None),
        EvidenceKind.RECOMMENDATION: getattr(
            context, "recommendations_generated_at", None
        ),
        EvidenceKind.RULE: getattr(context, "rules_generated_at", None),
        EvidenceKind.INSIGHT: getattr(context, "insights_generated_at", None),
        EvidenceKind.SCHEME: getattr(context, "schemes_generated_at", None),
        EvidenceKind.FORECAST: getattr(context, "forecasts_generated_at", None),
        EvidenceKind.ACTION: getattr(
            context, "action_items_generated_at", None
        ),
        EvidenceKind.DNA: getattr(context, "twin_generated_at", None),
    }
    ts = mapping.get(kind)
    return ts if isinstance(ts, str) and ts else "unknown"


def _business_context_slice(context: AssistantContext | None) -> dict[str, Any]:
    """Return the small profile slice every audit entry carries."""
    if context is None:
        return {}
    return {
        "industry": getattr(context, "industry", "unknown") or "unknown",
        "location": getattr(context, "location", "unknown") or "unknown",
        "business_type": getattr(context, "business_type", "unknown") or "unknown",
        "employee_count": getattr(context, "employee_count", "unknown") or "unknown",
    }


def _augment_entry(
    entry: EvidenceEntry, context: AssistantContext | None
) -> EvidenceEntry:
    """Return an augmented copy of ``entry`` with the AI-1 audit fields.

    Frozen dataclass → use ``dataclasses.replace``.
    """
    source_type = _KIND_TO_SOURCE_TYPE.get(entry.kind, "computed")
    freshness = _resolve_freshness(context, entry.kind)
    biz_ctx = _business_context_slice(context)
    return replace(
        entry,
        source_type=source_type,
        freshness=freshness,
        business_context=biz_ctx,
    )


class EvidenceRegistry:
    """The immutable per-request evidence index.

    Build it once from the assembled :class:`AssistantContext`,
    query it during prompt construction and grounding
    validation. The registry is intentionally cheap to
    construct (a single pass over the context dataclass) so
    the per-request cost is negligible.
    """

    __slots__ = ("_by_id", "_entries", "_by_kind")

    def __init__(self, context: AssistantContext | None) -> None:
        self._by_id: dict[str, EvidenceEntry] = {}
        self._entries: tuple[EvidenceEntry, ...]
        self._by_kind: dict[EvidenceKind, list[EvidenceEntry]] = {
            kind: [] for kind in EvidenceKind
        }
        if context is None:
            self._entries = ()
            return
        entries: list[EvidenceEntry] = []
        entries.extend(self._from_overall_score(context))
        entries.extend(self._from_user_prompt_echoes(context))
        entries.extend(self._from_scores(context))
        entries.extend(self._from_recommendations(context))
        entries.extend(self._from_rules(context))
        entries.extend(self._from_insights(context))
        entries.extend(self._from_schemes(context))
        entries.extend(self._from_forecasts(context))
        entries.extend(self._from_action_items(context))
        entries.extend(self._from_dna(context))
        # AI-1 — augment every entry with the source_type,
        # freshness, and business_context fields. The
        # positional yield sites above stay byte-identical;
        # the helper runs after the entries have been
        # collected. ``EvidenceEntry`` is frozen so we
        # ``replace()`` each one.
        entries = [_augment_entry(e, context) for e in entries]
        # Deduplicate by id — a malformed context with two
        # recommendations sharing an id would otherwise leak
        # the wrong fact when the model references the dup.
        seen: set[str] = set()
        deduped: list[EvidenceEntry] = []
        for entry in entries:
            if not entry.id or entry.id in seen:
                continue
            seen.add(entry.id)
            deduped.append(entry)
            self._by_id[entry.id] = entry
            self._by_kind[entry.kind].append(entry)
        self._entries = tuple(deduped)

    # ---- query API ---------------------------------------------------- #

    def all(self) -> tuple[EvidenceEntry, ...]:
        """Return every entry, in insertion order."""
        return self._entries

    def by_id(self, evidence_id: str) -> EvidenceEntry | None:
        """Return the entry with ``evidence_id`` or ``None``."""
        if not evidence_id:
            return None
        return self._by_id.get(evidence_id)

    def by_kind(self, kind: EvidenceKind) -> tuple[EvidenceEntry, ...]:
        """Return every entry of the given kind."""
        return tuple(self._by_kind.get(kind, ()))

    def has_id(self, evidence_id: str) -> bool:
        """Return True iff ``evidence_id`` resolves in this registry."""
        return bool(evidence_id) and evidence_id in self._by_id

    @property
    def count(self) -> int:
        """Total number of entries in the registry."""
        return len(self._entries)

    def ids(self) -> tuple[str, ...]:
        """All stable IDs, in insertion order."""
        return tuple(e.id for e in self._entries)

    # ---- prompt block ------------------------------------------------- #

    def to_prompt_block(self) -> str:
        """Render the registry as a system-prompt block.

        The block is what the model sees — a numbered list of
        evidence entries with ``[id] kind — label`` headers
        and a compact ``value`` line. The block is empty when
        the context had no upstream data; the model is told
        that explicitly in the system prompt.
        """
        if not self._entries:
            return (
                "=== EVIDENCE REGISTRY (server-resolved, stable IDs) ===\n"
                "(no business evidence is available for this request — answer accordingly)\n"
                "=== END EVIDENCE REGISTRY ==="
            )
        lines = [
            "=== EVIDENCE REGISTRY (server-resolved, stable IDs) ===",
            "Cite evidence by its bracketed ID. Do not invent IDs that are not present here.",
        ]
        for idx, entry in enumerate(self._entries, start=1):
            header = f"[{idx}] {entry.id} — {entry.kind.value} — {entry.label}"
            lines.append(header)
            if entry.value:
                lines.append(f"    value: {entry.value}")
        lines.append("=== END EVIDENCE REGISTRY ===")
        return "\n".join(lines)

    # ---- internal projectors ----------------------------------------- #

    @staticmethod
    def _from_overall_score(
        context: AssistantContext,
    ) -> Iterable[EvidenceEntry]:
        """Emit a single ``score_overall`` registry entry so the
        grounding validator's ``no_invented_numbers`` rule has a
        numeric anchor for the headline business score that the
        model inevitably quotes.

        The entry is synthetic — it carries no upstream fact the
        context didn't already expose; it just normalises the
        headline score into the same evidence contract that the
        per-pillar scores use. Without it, the validator flags
        ``82`` (or whatever the headline score is) as an
        unsupported numeric literal whenever the model mentions
        the headline score in its answer.
        """
        score = getattr(context, "overall_business_score", 0) or 0
        if not score:
            return
        band = getattr(context, "band", "") or ""
        level = band.title() if band else ""
        value = f"{score}/100" + (f" ({level})" if level else "")
        yield EvidenceEntry(
            id="score_overall",
            kind=EvidenceKind.SCORE,
            label=_clean("Overall business score", cap=_LABEL_CAP),
            value=_clean(value, cap=_VALUE_CAP),
            source_topic="Twin",
        )

    @staticmethod
    def _from_user_prompt_echoes(
        context: AssistantContext,
    ) -> Iterable[EvidenceEntry]:
        """Emit registry entries that anchor the numeric literals
        the user is allowed to mention: revenue figures the model
        echoes back from the user's own prompt.

        H7.8C — Gemini's prose output quotes the user's prompt
        numbers (e.g. ``₹1.8 Cr to ₹3 Cr``) verbatim. Those are
        NOT invented — they're the user's own stated targets. The
        ``no_invented_numbers`` rule has no way to know that
        without a registry entry. We synthesise one from
        ``business_id`` / annual-revenue shape (when present in
        the context) so the validator passes.

        For now we emit a single ``biz_profile_revenue`` entry
        whose value contains the headline numeric. The context
        builder does not currently project annual_revenue (it
        lives in the businesses table, not the twin), so we read
        it via the context's optional ``annual_revenue_inr``
        attribute if a future commit wires it; absent that, this
        is a no-op and the prose-recovery path continues to use
        approximation qualifiers.
        """
        # Best-effort: read optional attribute (set by future
        # context-builder revisions that expose annual_revenue).
        revenue_inr = getattr(context, "annual_revenue_inr", 0) or 0
        if not revenue_inr:
            return
        # Convert to Cr for the prompt (1 Cr = 10,000,000 INR).
        # H7.8C — round to 2 dp but DROP trailing zeros so the
        # registry value matches what the user typed (e.g.
        # "₹1.8 Cr" not "₹1.80 Cr"). The grounding validator's
        # ``no_invented_numbers`` rule does literal-string
        # matching; ``1.80`` would not match the user's
        # quoted ``1.8`` and would falsely flag the user's own
        # prompt number as invented.
        cr_value = round(revenue_inr / 10_000_000, 2)
        cr_str = f"{cr_value:.2f}".rstrip("0").rstrip(".")
        yield EvidenceEntry(
            id="biz_profile_revenue",
            kind=EvidenceKind.SCORE,
            label=_clean("Annual revenue baseline", cap=_LABEL_CAP),
            value=_clean(
                f"₹{cr_str} Cr (INR {revenue_inr:,})", cap=_VALUE_CAP,
            ),
            source_topic="Profile",
        )

    @staticmethod
    def _from_scores(context: AssistantContext) -> Iterable[EvidenceEntry]:
        for s in context.scores:
            sid = f"score_{_slug(s.key)}" if s.key else ""
            if not sid:
                continue
            value = f"{s.score}/100 ({s.level})"
            yield EvidenceEntry(
                id=sid,
                kind=EvidenceKind.SCORE,
                label=_clean(s.title or s.key, cap=_LABEL_CAP),
                value=_clean(value, cap=_VALUE_CAP),
                source_topic="Twin",
            )

    @staticmethod
    def _from_recommendations(context: AssistantContext) -> Iterable[EvidenceEntry]:
        for r in context.recommendations:
            rid = f"rec_{_slug(r.id)}" if r.id else ""
            if not rid:
                continue
            value_bits: list[str] = []
            if r.priority:
                value_bits.append(f"priority={r.priority}")
            if r.estimated_score_gain:
                value_bits.append(f"score_gain=+{r.estimated_score_gain}")
            if r.estimated_timeline:
                value_bits.append(f"timeline={r.estimated_timeline}")
            if r.category:
                value_bits.append(f"category={r.category}")
            value = ", ".join(value_bits)
            yield EvidenceEntry(
                id=rid,
                kind=EvidenceKind.RECOMMENDATION,
                label=_clean(r.title or r.id, cap=_LABEL_CAP),
                value=_clean(value, cap=_VALUE_CAP),
                source_topic="Recommendations",
            )

    @staticmethod
    def _from_rules(context: AssistantContext) -> Iterable[EvidenceEntry]:
        for r in context.rules:
            rid = f"rule_{_slug(r.id)}" if r.id else ""
            if not rid:
                continue
            value_bits: list[str] = []
            if r.priority:
                value_bits.append(f"priority={r.priority}")
            if r.estimated_impact:
                value_bits.append(f"impact={r.estimated_impact}")
            if r.category:
                value_bits.append(f"category={r.category}")
            if r.reason:
                value_bits.append(f"reason={r.reason}")
            value = ", ".join(value_bits)
            yield EvidenceEntry(
                id=rid,
                kind=EvidenceKind.RULE,
                label=_clean(r.title or r.id, cap=_LABEL_CAP),
                value=_clean(value, cap=_VALUE_CAP),
                source_topic="Rules",
            )

    @staticmethod
    def _from_insights(context: AssistantContext) -> Iterable[EvidenceEntry]:
        for ins in context.insights:
            iid = f"insight_{_slug(ins.id)}" if ins.id else ""
            if not iid:
                continue
            value = (
                f"confidence={ins.confidence}, priority={ins.priority}"
                if ins.confidence or ins.priority
                else ""
            )
            yield EvidenceEntry(
                id=iid,
                kind=EvidenceKind.INSIGHT,
                label=_clean(ins.title or ins.id, cap=_LABEL_CAP),
                value=_clean(value, cap=_VALUE_CAP),
                source_topic="Insights",
            )

    @staticmethod
    def _from_schemes(context: AssistantContext) -> Iterable[EvidenceEntry]:
        for s in context.schemes:
            slug = _slug(s.scheme_id)
            if not slug:
                continue
            sid = f"scheme_{slug}"
            value_bits: list[str] = []
            if s.authority:
                value_bits.append(f"authority={s.authority}")
            if s.profile_match_score:
                value_bits.append(f"profile_match={s.profile_match_score}/100")
            if s.last_verified_date:
                value_bits.append(f"verified={s.last_verified_date}")
            value = ", ".join(value_bits)
            yield EvidenceEntry(
                id=sid,
                kind=EvidenceKind.SCHEME,
                label=_clean(s.title or s.scheme_id, cap=_LABEL_CAP),
                value=_clean(value, cap=_VALUE_CAP),
                source_topic="GovernmentScheme",
            )

    @staticmethod
    def _from_forecasts(context: AssistantContext) -> Iterable[EvidenceEntry]:
        for f in context.forecasts:
            sid = f"forecast_{_slug(f.scenario_id)}" if f.scenario_id else ""
            if not sid:
                continue
            value_bits: list[str] = []
            if f.horizon_label:
                value_bits.append(f"horizon={f.horizon_label}")
            if f.revenue_delta:
                value_bits.append(f"revenue_delta={f.revenue_delta}")
            if f.score_delta:
                value_bits.append(f"score_delta={f.score_delta:+d}")
            if f.confidence:
                value_bits.append(f"confidence={f.confidence}")
            if f.assumption_summary:
                value_bits.append(f"assumption={f.assumption_summary}")
            value = ", ".join(value_bits)
            yield EvidenceEntry(
                id=sid,
                kind=EvidenceKind.FORECAST,
                label=_clean(f.horizon_label or f.scenario_id, cap=_LABEL_CAP),
                value=_clean(value, cap=_VALUE_CAP),
                source_topic="Insights",
            )

    @staticmethod
    def _from_action_items(context: AssistantContext) -> Iterable[EvidenceEntry]:
        for a in context.action_items:
            aid = f"action_{_slug(a.action_id)}" if a.action_id else ""
            if not aid:
                continue
            value_bits: list[str] = []
            if a.status:
                value_bits.append(f"status={a.status}")
            if a.priority:
                value_bits.append(f"priority={a.priority}")
            if a.due_in_days:
                value_bits.append(f"due_in_days={a.due_in_days}")
            value = ", ".join(value_bits)
            yield EvidenceEntry(
                id=aid,
                kind=EvidenceKind.ACTION,
                label=_clean(a.title or a.action_id, cap=_LABEL_CAP),
                value=_clean(value, cap=_VALUE_CAP),
                source_topic="Insights",
            )

    @staticmethod
    def _from_dna(context: AssistantContext) -> Iterable[EvidenceEntry]:
        dna = context.dna
        if not dna or not dna.archetype_key:
            return ()
        key = _slug(dna.archetype_key) or "dna"
        value = (
            f"match={dna.match_score}%" if dna.match_score else ""
        )
        yield EvidenceEntry(
            id=f"dna_{key}",
            kind=EvidenceKind.DNA,
            label=_clean(dna.archetype_title or dna.archetype_key, cap=_LABEL_CAP),
            value=_clean(value, cap=_VALUE_CAP),
            source_topic="Business DNA",
        )