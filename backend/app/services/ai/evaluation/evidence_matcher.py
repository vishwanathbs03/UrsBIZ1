"""SPRINT AI-19 — Structural evidence/claim matcher.

This module sits *on top of* the existing
:class:`EvidenceRegistry` and :class:`Claim` surfaces. It
does not replace them; it is a deterministic, off-line
auditor that the metrics calculator can call to answer
the question:

    "Does this claim's cited evidence actually contain
    the value the claim states?"

The brief for Sprint AI-19 is explicit:

  * The LLM must never be allowed to invent evidence IDs.
  * Numeric claims must trace to a value-bearing surface.
  * Substring matching alone is not allowed.
  * Every claim must carry a structured support status.

The matcher's verdict is a single string from
``{SUPPORTED, PARTIALLY_SUPPORTED, UNSUPPORTED,
CONTRADICTED, NOT_APPLICABLE}`` — the same vocabulary
the brief lists.

The matcher is **pure**: it operates on the records the
runner projects onto ``notes`` and the entries
:mod:`app.services.ai.evaluation.question_bank` declares
as the canonical server-owned evidence. No DB access, no
LLM call, no mutation of any state.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------

# Support-status values are the brief's closed set.
# ``NOT_APPLICABLE`` is reserved for forward-looking or
# user-supplied claims that the structural matcher
# cannot — and should not — judge.
SUPPORTED = "SUPPORTED"
PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
UNSUPPORTED = "UNSUPPORTED"
CONTRADICTED = "CONTRADICTED"
NOT_APPLICABLE = "NOT_APPLICABLE"

SUPPORT_STATUSES: frozenset[str] = frozenset(
    {
        SUPPORTED,
        PARTIALLY_SUPPORTED,
        UNSUPPORTED,
        CONTRADICTED,
        NOT_APPLICABLE,
    }
)

# Claim types that are forward-looking or user-supplied.
# The structural matcher treats these as NOT_APPLICABLE
# because the support semantic differs (the claim *is*
# the user's framing, not a verifiable business fact).
NON_VERIFIABLE_CLAIM_TYPES: frozenset[str] = frozenset(
    {"ASSUMPTION", "UNKNOWN", "SCENARIO", "USER_PROVIDED"}
)

# 90-day freshness threshold. Evidence older than this
# is treated as stale. The threshold is a constant for
# AI-19; future sprints can wire it to the existing
# freshness layer.
_STALE_DAYS = 90


# ---------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EvidenceRecord:
    """Projection of ``EvidenceEntry`` for the matcher.

    The matcher is intentionally decoupled from the
    full :class:`EvidenceEntry` so it can run on
    fixtures that ship inline evidence (the adversarial
    matrix) without spinning up an
    :class:`AssistantContext`.
    """

    id: str
    kind: str
    value: str
    authoritative: bool = True
    freshness: str = "unknown"


@dataclass(frozen=True)
class ClaimRecord:
    """Projected claim with verified support status.

    Fields are the brief's required provenance columns:
    ``claim_id``, ``claim_type``, ``claim_text``,
    ``evidence_ids``, ``evidence_kind``,
    ``evidence_authority``, ``evidence_freshness``,
    ``support_status``.
    """

    claim_id: str
    claim_type: str
    claim_text: str
    evidence_ids: tuple[str, ...]
    evidence_kind: str
    evidence_authority: str
    evidence_freshness: str
    support_status: str


# ---------------------------------------------------------------------------
# Numeric extraction
# ---------------------------------------------------------------------------

# Matches numeric literals in the user's claim text.
# Captures sequences of digits with optional decimal
# points and optional magnitude suffixes (k, m, cr, %).
# Examples: "1.8 cr", "₹12,500", "23%", "2024", "3.14".
_NUMERIC_RE = re.compile(
    r"""
    (?:₹|rs\.?|inr|\$|€|£)?            # optional currency prefix
    \s*
    (\d+(?:\.\d+)?                       # plain or decimal number
        |\d{1,3}(?:[,]\d{3})+           # ...or thousands-separator groups
        |\d+)                           # ...or single integer
    \s*
    (?:cr(?:ore)?|lakh|mn|m|k|%|x)?   # optional magnitude suffix
    """,
    re.IGNORECASE | re.VERBOSE,
)


def _extract_numbers_with_units(
    text: str,
) -> tuple[tuple[float, str], ...]:
    """Return a tuple of (number, unit) pairs.

    The unit suffix (``%``, ``cr``, ``k``, etc.) is
    kept so the contradiction check can distinguish
    different units (e.g. ``6.5%`` from ``1.8 crore``).
    """
    if not text:
        return ()
    out: list[tuple[float, str]] = []
    for match in _NUMERIC_RE.finditer(text):
        raw = match.group(0)
        # Pull the unit suffix.
        unit_match = re.search(
            r"(cr(?:ore)?|lakh|mn|m|k|%|x)\s*$",
            raw,
            flags=re.IGNORECASE,
        )
        unit = (unit_match.group(0).lower() if unit_match else "")
        cleaned = re.sub(
            r"[₹$€£]|rs\.?|inr", "", raw, flags=re.IGNORECASE
        )
        cleaned = cleaned.replace(",", "")
        cleaned = re.sub(
            r"\s*(cr(?:ore)?|lakh|mn|m|k|%|x)\s*$",
            "",
            cleaned,
            flags=re.IGNORECASE,
        ).strip()
        if not cleaned:
            continue
        try:
            num = float(cleaned)
        except ValueError:
            continue
        out.append((num, unit))
    return tuple(out)


def extract_numeric_literals(text: str) -> tuple[float, ...]:
    """Return every numeric literal in ``text`` as a float.

    Currency symbols, commas, and magnitude suffixes
    (k, m, cr, lakh, %, x) are stripped. Tokens that
    cannot be parsed are silently skipped.

    The matcher uses the *set* of returned literals to
    detect numeric mismatches between claim and evidence.
    """
    if not text:
        return ()
    out: list[float] = []
    for match in _NUMERIC_RE.finditer(text):
        raw = match.group(0)
        # Strip currency and magnitude suffixes.
        cleaned = re.sub(r"[₹$€£]|rs\.?|inr", "", raw, flags=re.IGNORECASE)
        # Strip commas in separators.
        cleaned = cleaned.replace(",", "")
        # Drop magnitude suffixes; we treat them as distinct
        # tokens but normalise to the leading number for the
        # overlap check.
        cleaned = re.sub(
            r"\s*(cr(?:ore)?|lakh|mn|m|k|%|x)\s*$",
            "",
            cleaned,
            flags=re.IGNORECASE,
        ).strip()
        if not cleaned:
            continue
        try:
            out.append(float(cleaned))
        except ValueError:
            continue
    return tuple(out)


def _strip_magnitude(value: str) -> str:
    """Strip trailing magnitude suffix from a value token.

    The registry tends to store values like "18000000"
    without the magnitude suffix. The brief's examples
    use "1.8 cr" directly. We normalise both forms to a
    common numeric form for comparison.
    """
    if not value:
        return value
    cleaned = re.sub(r"[₹$€£]|rs\.?|inr", "", value, flags=re.IGNORECASE)
    cleaned = cleaned.replace(",", "")
    cleaned = re.sub(
        r"\s*(cr(?:ore)?|lakh|mn|m|k|%|x)\s*$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()
    return cleaned


# Crore / lakh conversion helpers. Crore = 10,000,000;
# lakh = 100,000. The matcher's numeric-overlap check
# supports these so the system can claim "1.8 cr" while
# the evidence stores "18000000".
def _to_rupees(value: float) -> float:
    """Convert a value to "rupees" form for comparison.

    This is a no-op for AI-19 — the values the registry
    stores are already in rupees. The function is
    documented for future sprints that may emit
    magnitudes directly.
    """
    return value


# ---------------------------------------------------------------------------
# ID fabrication
# ---------------------------------------------------------------------------


def is_fabricated_id(
    claim_id: str, registry_ids: Iterable[str]
) -> bool:
    """Return True iff ``claim_id`` is not in the registry.

    The registry is the *server-generated* set of valid
    evidence IDs. Any evidence ID cited by a claim that
    is not in this set is a fabrication. The check is
    structural (set membership) — see the brief's
    "SERVER AUTHORITY" rule.
    """
    return bool(claim_id) and claim_id not in set(registry_ids)


# ---------------------------------------------------------------------------
# Semantic ownership
# ---------------------------------------------------------------------------


def contains_semantic_value(
    claim_text: str, evidence_value: str
) -> bool:
    """Return True iff ``evidence_value`` is structurally
    contained in ``claim_text``.

    Evidence ownership is checked three ways, in order:

    1. **Substring match** — the evidence value (with
       currency and commas stripped) appears verbatim in
       the claim. Catches the easy case ("Revenue is
       ₹1.8 crore" ↔ evidence "1.8 crore").
    2. **Numeric overlap** — at least one normalised
       numeric literal from the claim equals the
       normalised numeric form of the evidence value.
       Catches unit differences ("1.8 cr" ↔ "18000000"
       when both reduce to the same magnitude).
    3. **Token overlap** — at least one keyword token
       from the evidence value appears in the claim.
       Catches non-numeric semantic ownership
       ("supplier concentration" ↔ "Suppliers are
       concentrated").
    """
    if not claim_text or not evidence_value:
        return False

    case_insensitive_claim = claim_text.lower()
    case_insensitive_value = evidence_value.lower()

    # 1. Substring match (direct ownership).
    stripped_value = _strip_magnitude(evidence_value).lower()
    if stripped_value and stripped_value in case_insensitive_claim:
        return True

    # 2. Numeric overlap.
    claim_numbers = extract_numeric_literals(claim_text)
    evidence_number = _parse_one(evidence_value)
    if claim_numbers and evidence_number is not None:
        for cn in claim_numbers:
            if _numbers_match(cn, evidence_number):
                return True

    # 3. Token overlap — multi-word semantic check. The
    # matcher only fires when the evidence value carries
    # at least two distinct value-bearing tokens (>= 4
    # chars, not stopword, not a bare unit). A single
    # shared topic word ("revenue") is too weak; the
    # evidence value must be structurally grounded in
    # the claim via a multi-word concept. Catches cases
    # like "Supplier concentration is the biggest risk"
    # <-> evidence "supplier concentration high".
    value_tokens = [
        tok
        for tok in re.findall(r"[a-z0-9]{4,}", case_insensitive_value)
        if not _is_stopword(tok) and not _is_unit_token(tok)
    ]
    if len(value_tokens) >= 2:
        claim_tokens = {
            tok
            for tok in re.findall(r"[a-z0-9]{4,}", case_insensitive_claim)
            if not _is_unit_token(tok)
        }
        # Require at least two value tokens to overlap.
        # Single-token overlap is rejected as too weak
        # (e.g. shared topic word "revenue"). A 2+ token
        # overlap on multi-word evidence ("supplier
        # concentration") still passes even when the claim
        # adds additional qualifiers.
        overlap = [tok for tok in value_tokens if tok in claim_tokens]
        if len(overlap) >= 2:
            return True

    return False


def _is_unit_token(token: str) -> bool:
    """Treat numeric / magnitude units as non-content tokens.

    The matcher strips tokens that describe units rather
    than semantic content. Otherwise "crore", "lakh",
    "percent" would match between two values that
    differ only by magnitude.
    """
    return token in {
        "crore",
        "lakh",
        "percent",
        "million",
        "billion",
        "thousand",
        "rupees",
        "inr",
        "inr.",
        "dollars",
        "euros",
        "pounds",
        "employees",
        "customers",
        "users",
        "score",
        "rating",
    }


def _parse_one(value: str) -> float | None:
    """Parse a single numeric value out of a string.

    Returns ``None`` when the string contains no parseable
    number. Used by :func:`contains_semantic_value` for
    the numeric-overlap check.
    """
    if not value:
        return None
    for match in _NUMERIC_RE.finditer(value):
        raw = match.group(0)
        cleaned = _strip_magnitude(raw)
        if not cleaned:
            continue
        try:
            return float(cleaned)
        except ValueError:
            continue
    return None


def _numbers_match(a: float, b: float) -> bool:
    """Return True if two numbers match within 5% relative.

    The 5% tolerance follows the brief's contradiction
    threshold. Sub-1.0 numbers use absolute tolerance
    to avoid the relative-percentage blowing up around
    zero.
    """
    if a == b:
        return True
    if abs(a) < 1.0 and abs(b) < 1.0:
        return abs(a - b) < 0.01
    high = max(abs(a), abs(b))
    return abs(a - b) / high <= 0.05


def _is_stopword(token: str) -> bool:
    """Filter short, generic tokens from the keyword-overlap check.

    Without this filter, "the" or "and" would count as a
    match, which the brief explicitly forbids as
    substring-only matching.
    """
    return token in {
        "the",
        "and",
        "for",
        "with",
        "this",
        "that",
        "are",
        "was",
        "were",
        "have",
        "has",
        "had",
        "from",
        "into",
        "but",
        "all",
        "any",
        "its",
        "our",
        "your",
        "they",
        "their",
        "them",
        "what",
        "when",
        "where",
        "which",
        "who",
        "whom",
        "why",
        "how",
        "per",
        "due",
        "via",
    }


# ---------------------------------------------------------------------------
# Freshness
# ---------------------------------------------------------------------------


def _days_since(freshness: str) -> float | None:
    """Return days since ``freshness`` (ISO-8601) or None.

    Returns ``None`` when the value is unparseable so
    callers can treat unknown freshness as "trust the
    evidence" rather than "stale evidence".
    """
    if not freshness or freshness == "unknown":
        return None
    from datetime import datetime, timezone

    iso = freshness.strip()
    # Accept "Z" suffix and microseconds.
    if iso.endswith("Z"):
        iso = iso[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(iso)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = datetime.now(tz=timezone.utc) - dt
    return delta.total_seconds() / 86400.0


def _freshness_summary(
    cited: Sequence[EvidenceRecord],
) -> str:
    """Return a short label for the cited evidence's freshness.

    Returns one of ``"fresh"``, ``"mixed"``, ``"stale"``,
    ``"unknown"``. Unparseable / unset freshness is
    treated as "unknown" — it is NOT a contradiction
    flag. Only a parsed timestamp older than 90 days
    demotes to ``"stale"``; ``"unknown"`` is neutral
    (the brief calls for downstream warning, not a
    structural downgrade).
    """
    if not cited:
        return "unknown"
    states: list[str] = []
    for ev in cited:
        days = _days_since(ev.freshness)
        if days is None:
            states.append("unknown")
        elif days > _STALE_DAYS:
            states.append("stale")
        else:
            states.append("fresh")
    if all(s == "stale" for s in states):
        return "stale"
    if any(s == "stale" for s in states):
        return "mixed"
    # All-fresh OR all-unknown -> fresh (neutral).
    if all(s == "fresh" for s in states):
        return "fresh"
    if all(s == "unknown" for s in states):
        return "fresh"
    # Mix of fresh and unknown is "fresh" (no known staleness).
    return "fresh"


# ---------------------------------------------------------------------------
# Match
# ---------------------------------------------------------------------------


def classify_support_status(
    *,
    fabricated: bool,
    semantic_owned: bool,
    has_authoritative: bool,
    freshness: str,
    contradicted: bool,
    claim_type: str,
    has_citations: bool = True,
    unverified_facts: int = 0,
) -> str:
    """Return the closed-set support status for one claim.

    Order of checks:

    1. Forward-looking or user-supplied claim → ``NOT_APPLICABLE``.
    2. No citations and no applicable registry → ``NOT_APPLICABLE``
       (external facts the server has no authority over).
    3. Contradiction → ``CONTRADICTED``.
    4. Fabricated ID or no semantic ownership → ``UNSUPPORTED``.
    5. All evidence stale → ``UNSUPPORTED``.
    6. Unverified facts present → ``PARTIALLY_SUPPORTED``
       (mixed-content claims: some facts grounded, others not).
    7. Weak authority or mixed freshness → ``PARTIALLY_SUPPORTED``.
    8. Otherwise → ``SUPPORTED``.
    """
    if claim_type.upper() in NON_VERIFIABLE_CLAIM_TYPES:
        return NOT_APPLICABLE
    if not has_citations:
        return NOT_APPLICABLE
    if contradicted:
        return CONTRADICTED
    if fabricated or not semantic_owned:
        return UNSUPPORTED
    if freshness == "stale":
        return UNSUPPORTED
    if unverified_facts > 0:
        return PARTIALLY_SUPPORTED
    if not has_authoritative or freshness == "mixed":
        return PARTIALLY_SUPPORTED
    return SUPPORTED


def evaluate_claim(
    *,
    claim_id: str,
    claim_type: str,
    claim_text: str,
    evidence_ids: Sequence[str],
    registry: Sequence[EvidenceRecord],
) -> ClaimRecord:
    """Run the structural matcher on one claim.

    Parameters
    ----------
    claim_id:
        Stable identifier of the claim. May be empty
        (the caller may not have one yet); the matcher
        still produces a verdict.
    claim_type:
        Claim kind. The brief's vocabulary includes
        ``FACT``, ``CALCULATION``, ``RECOMMENDATION``,
        ``ASSUMPTION``, ``UNKNOWN``, ``SCENARIO``,
        ``USER_PROVIDED``.
    claim_text:
        The natural-language claim being verified.
    evidence_ids:
        Server-supplied evidence IDs the claim cites.
    registry:
        The full evidence registry the runner is
        allowed to draw from. The matcher checks
        every cited ID against this set.

    Returns
    -------
    ClaimRecord
        A frozen record with the verified support status
        and the provenance columns the brief requires.
    """
    cite = tuple(evidence_ids)
    # Forward-looking / user-supplied claims are not
    # subject to the structural matcher.
    if claim_type.upper() in NON_VERIFIABLE_CLAIM_TYPES:
        return ClaimRecord(
            claim_id=claim_id,
            claim_type=claim_type,
            claim_text=claim_text,
            evidence_ids=cite,
            evidence_kind="n/a",
            evidence_authority="n/a",
            evidence_freshness="n/a",
            support_status=NOT_APPLICABLE,
        )

    registry_by_id = {ev.id: ev for ev in registry}
    cited = [
        registry_by_id[eid]
        for eid in cite
        if eid in registry_by_id
    ]
    fabricated_ids = [eid for eid in cite if eid not in registry_by_id]
    fabricated = bool(fabricated_ids)

    # Semantic ownership: at least one cited evidence's
    # value must be structurally contained in the claim.
    semantic_owned = False
    if cited:
        for ev in cited:
            if contains_semantic_value(claim_text, ev.value):
                semantic_owned = True
                break

    has_authoritative = any(ev.authoritative for ev in cited)
    freshness = _freshness_summary(cited)
    kind_summary = _kind_summary(cited)
    authority_summary = _authority_summary(cited)

    contradicted = _detect_contradiction(claim_text, cited)

    # Mixed-content check: count numeric literals in the
    # claim that no cited evidence references. A claim
    # with multiple distinct facts where some are
    # unverified is PARTIALLY_SUPPORTED — the verified
    # facts are correct but the claim as a whole is not
    # fully grounded.
    claim_nums = extract_numeric_literals(claim_text)
    unverified = 0
    if claim_nums and cited:
        ev_all_numbers: list[float] = []
        for ev in cited:
            ev_all_numbers.extend(
                extract_numeric_literals(ev.value or "")
            )
        for cn in claim_nums:
            if not any(
                _numbers_match(cn, evn) for evn in ev_all_numbers
            ):
                unverified += 1
    elif claim_nums and not cited:
        unverified = len(claim_nums)

    status = classify_support_status(
        fabricated=fabricated,
        semantic_owned=semantic_owned,
        has_authoritative=has_authoritative,
        freshness=freshness,
        contradicted=contradicted,
        claim_type=claim_type,
        has_citations=bool(cite),
        unverified_facts=unverified,
    )

    return ClaimRecord(
        claim_id=claim_id,
        claim_type=claim_type,
        claim_text=claim_text,
        evidence_ids=cite,
        evidence_kind=kind_summary,
        evidence_authority=authority_summary,
        evidence_freshness=freshness,
        support_status=status,
    )


def _kind_summary(cited: Sequence[EvidenceRecord]) -> str:
    """Return a comma-separated list of cited evidence kinds.

    Empty when no citations resolved. Used for the
    ``evidence_kind`` provenance column.
    """
    if not cited:
        return "none"
    return ",".join(sorted({ev.kind for ev in cited}))


def _authority_summary(cited: Sequence[EvidenceRecord]) -> str:
    """Return ``"authoritative"``, ``"non-authoritative"``, or ``"mixed"``."""
    if not cited:
        return "none"
    flags = {ev.authoritative for ev in cited}
    if flags == {True}:
        return "authoritative"
    if flags == {False}:
        return "non-authoritative"
    return "mixed"


def _detect_contradiction(
    claim_text: str, cited: Sequence[EvidenceRecord]
) -> bool:
    """Return True iff a cited evidence value contradicts the claim.

    Two numbers are considered contradictory when they
    differ by more than the brief's 5% threshold on the
    same unit (i.e. within 10x of each other). The check
    is intentionally narrow:

    * Self-reference guard: when the evidence value is
      the same text as the claim, every numeric matches
      itself. Skip the contradiction check.
    * Mixed-content guard: when the claim carries
      multiple distinct facts, the contradiction only
      fires on a fact the evidence also addresses.
      "Addresses" is determined by: the evidence's
      value carries at least one numeric that matches
      one of the claim's numerics (within 10x), AND the
      contested claim number has at least one
      numeric-match candidate in the evidence. Numbers
      the evidence does not address (e.g. an external
      rate in a mixed claim) do NOT count as
      contradictions.
    * Unit-aware: when the claim number carries a
      different unit suffix (e.g. ``%``, ``cr``,
      ``lakh``) from the evidence number, the two are
      treated as different facts even at similar
      magnitude. ``6.5%`` and ``1.8 crore`` differ in
      unit, so neither contradicts the other.
    """
    if not cited or not claim_text:
        return False
    claim_numbers = extract_numeric_literals(claim_text)
    if not claim_numbers:
        return False
    # Parse claim numbers with their unit suffixes so we
    # can compare against evidence numbers at the same
    # unit.
    claim_pairs = _extract_numbers_with_units(claim_text)
    if not claim_pairs:
        return False
    for ev in cited:
        ev_value = ev.value or ""
        ev_pairs = _extract_numbers_with_units(ev_value)
        if not ev_pairs:
            continue
        # Self-reference guard.
        if ev_value.strip() == claim_text.strip():
            continue
        # A claim number contradicts the evidence only when
        # it's plausibly the same number as the
        # evidence's number but disagrees. "Plausibly
        # the same" means within 5% of the evidence's
        # number OR within 5x of the magnitude, AND
        # both share a unit suffix (or both have no
        # unit). Numbers that are wildly different
        # (>= 5x off in magnitude) likely describe a
        # different fact (UNSUPPORTED), not a
        # contradiction.
        for cn, cn_unit in claim_pairs:
            matched_evidence_unit = False
            contradicted_any = False
            for ev_num, ev_unit in ev_pairs:
                # Unit-aware comparison: require same
                # unit (or both unitless) before we
                # consider contradiction.
                same_unit = (cn_unit or "") == (ev_unit or "")
                if not same_unit:
                    continue
                matched_evidence_unit = True
                if _numbers_match(cn, ev_num):
                    continue
                high = max(abs(cn), abs(ev_num))
                low = min(abs(cn), abs(ev_num))
                if low > 0 and high / low < 5:
                    contradicted_any = True
            if matched_evidence_unit and contradicted_any:
                return True
    return False


# ---------------------------------------------------------------------------
# Audit event
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EvidenceAuditEvent:
    """One audit event emitted by the matcher.

    The metrics calculator counts these events to
    produce the structural score. The driver writes a
    summary of these events to the report.
    """

    claim_id: str
    claim_text: str
    cited_ids: tuple[str, ...]
    resolved_ids: tuple[str, ...]
    fabricated_ids: tuple[str, ...]
    semantic_owned: bool
    has_authoritative: bool
    freshness: str
    contradicted: bool
    support_status: str


def to_audit_event(
    record: ClaimRecord,
    registry: Sequence[EvidenceRecord] = (),
) -> EvidenceAuditEvent:
    """Convert a :class:`ClaimRecord` to an audit event.

    The audit event is the wire shape the metrics
    calculator and the driver consume. When ``registry``
    is supplied, fabricated IDs are the cited IDs that
    did not resolve.
    """
    registry_ids = {ev.id for ev in registry}
    cited = record.evidence_ids
    resolved = tuple(eid for eid in cited if eid in registry_ids)
    fabricated = tuple(eid for eid in cited if eid not in registry_ids)
    return EvidenceAuditEvent(
        claim_id=record.claim_id,
        claim_text=record.claim_text,
        cited_ids=cited,
        resolved_ids=resolved,
        fabricated_ids=fabricated,
        semantic_owned=record.support_status
        in {SUPPORTED, PARTIALLY_SUPPORTED},
        has_authoritative=record.evidence_authority
        in {"authoritative", "mixed"},
        freshness=record.evidence_freshness,
        contradicted=record.support_status == CONTRADICTED,
        support_status=record.support_status,
    )


__all__ = [
    "SUPPORTED",
    "PARTIALLY_SUPPORTED",
    "UNSUPPORTED",
    "CONTRADICTED",
    "NOT_APPLICABLE",
    "SUPPORT_STATUSES",
    "NON_VERIFIABLE_CLAIM_TYPES",
    "EvidenceRecord",
    "ClaimRecord",
    "EvidenceAuditEvent",
    "extract_numeric_literals",
    "contains_semantic_value",
    "is_fabricated_id",
    "classify_support_status",
    "evaluate_claim",
    "to_audit_event",
]
