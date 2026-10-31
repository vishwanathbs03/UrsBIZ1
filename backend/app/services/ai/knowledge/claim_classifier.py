"""SPRINT AI-16 — Verified External Knowledge + Freshness Layer.

Claim-kind classifier.

The classifier's only job is to label an atomic claim with one of
the six AI-16 :class:`ClaimKind` values. It is the safety gate
the audit trail walks: an ``INTERNAL_BUSINESS`` claim cannot
silently be downgraded to ``EXTERNAL_FACT``, and an
``EXTERNAL_FACT`` claim cannot be silently upgraded to
``INTERNAL_BUSINESS``.

Decision logic
--------------

The classifier is keyword-driven and deterministic. The legacy
7-bucket ``claim_type`` vocabulary is preserved on the wire
(``FACT``, ``CALCULATION``, ``INFERENCE``, ``RECOMMENDATION``,
``SCENARIO``, ``EXTERNAL_FACT``, ``UNKNOWN``) so the claim-parser
side does not change. The classifier maps legacy labels into
the new 6-way vocabulary as a safety net.

Mapping rules
-------------

  * Legacy ``FACT`` + has-business-context-token → ``INTERNAL_BUSINESS``
  * Legacy ``FACT`` + has-external-source → ``EXTERNAL_FACT``
  * Legacy ``FACT`` + has-finance-formula-token → ``CALCULATED``
  * Legacy ``FACT`` + bare → ``INTERNAL_BUSINESS`` (legacy default)
  * Legacy ``CALCULATION`` → ``CALCULATED``
  * Legacy ``INFERENCE`` → ``INTERNAL_BUSINESS`` (inferences are
    drawn from internal data; the engine labels them as such)
  * Legacy ``RECOMMENDATION`` → ``ASSUMPTION`` (advisory statements
    are not facts until they are acted on)
  * Legacy ``SCENARIO`` → ``SCENARIO``
  * Legacy ``EXTERNAL_FACT`` → ``EXTERNAL_FACT``
  * Legacy ``UNKNOWN`` → ``UNKNOWN``

When the kind cannot be inferred, the classifier returns
``UNKNOWN`` (authority 0) so the engine never silently labels
an unverified assertion.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.services.ai.knowledge.external_types import (
    ClaimKind,
)


# Token sets — keep them small and case-insensitive.
_BUSINESS_CONTEXT_TOKENS: tuple[str, ...] = (
    "your business", "your company", "your revenue", "your margin",
    "your working capital", "your team", "your product", "your factory",
    "your cash flow", "your current", "your employees", "your operation",
    "as per your profile", "in your case", "for your business",
    "your annual revenue", "your monthly",
)
_EXTERNAL_SOURCE_TOKENS: tuple[str, ...] = (
    "ministry", "rbi", "sebi", "fssai", "bis ", "echa", "dgft",
    "mudra", "kvic", "udyam", "ecb", "fema", "gst council",
    "world bank", "imf", "investopedia", "oecd",
    "european union", "us fda", "fda registration", "reach",
    "act ", "section ", "rule ", "notification ", "circular ",
    "as per the ", "as per regulation", "according to the act",
)
_CALCULATION_TOKENS: tuple[str, ...] = (
    "is calculated", "equals", "is computed", "by formula",
    "from inputs", "derived as", "therefore the value",
    "results in", "sums to", "subtotal",
)
_ASSUMPTION_TOKENS: tuple[str, ...] = (
    "we recommend", "you should", "we suggest", "we advise",
    "consider", "it may help", "ideally", "one option",
    "another option", "potentially", "perhaps",
)


@dataclass(frozen=True)
class ClassificationResult:
    """One classified claim.

    The classifier returns this small envelope rather than a raw
    :class:`ClaimKind` so the caller can ask "why?" (the
    ``reason`` field is one short sentence; it surfaces in
    debug logs and the audit envelope).
    """

    kind: ClaimKind
    reason: str


class ClaimKindClassifier:
    """Classify an atomic claim into a :class:`ClaimKind`.

    The classifier is pure: same input always produces the same
    :class:`ClassificationResult`. It is intentionally cheap —
    it does NOT consult the corpus, the context, or the LLM.

    The four classifier entry points
    --------------------------------

    1. :meth:`classify_legacy` — takes a legacy ``claim_type``
       string (``"FACT"`` / ``"CALCULATION"`` / etc.) and the
       claim text. Returns a :class:`ClassificationResult`.

    2. :meth:`classify_text` — takes the claim text only and
       infers the kind from the tokens. Used by external callers
       that have not run the legacy claim-parser.

    3. :meth:`enforce_business_isolation` — defensive guard:
       a claim with the ``INTERNAL_BUSINESS`` kind cannot carry
       an external source URL, and vice-versa. The classifier
       raises :class:`ClaimKindContaminationError` if violated.

    4. :meth:`validate_no_fabricated_source` — rejects fake
       URLs (``example.com`` / empty / unparseable) before they
       reach the wire.
    """

    def classify_legacy(
        self, *, claim_type: str, text: str
    ) -> ClassificationResult:
        """Map a legacy ``claim_type`` + claim text to a new kind."""
        text_low = (text or "").lower()
        ct = (claim_type or "").upper()

        if ct == "CALCULATION" or any(t in text_low for t in _CALCULATION_TOKENS):
            return ClassificationResult(
                kind=ClaimKind.CALCULATED,
                reason="Claim derives from a known formula.",
            )

        if ct == "SCENARIO":
            return ClassificationResult(
                kind=ClaimKind.SCENARIO,
                reason="Claim is a what-if estimate with declared assumptions.",
            )

        if ct == "RECOMMENDATION" or any(t in text_low for t in _ASSUMPTION_TOKENS):
            return ClassificationResult(
                kind=ClaimKind.ASSUMPTION,
                reason="Claim is advisory until acted upon.",
            )

        if ct == "INFERENCE":
            return ClassificationResult(
                kind=ClaimKind.INTERNAL_BUSINESS,
                reason="Inference drawn from internal data.",
            )

        if ct == "EXTERNAL_FACT" or any(t in text_low for t in _EXTERNAL_SOURCE_TOKENS):
            return ClassificationResult(
                kind=ClaimKind.EXTERNAL_FACT,
                reason="Claim cites an external authoritative source.",
            )

        if ct == "UNKNOWN":
            return ClassificationResult(
                kind=ClaimKind.UNKNOWN,
                reason="Claim was labelled UNKNOWN by the LLM.",
            )

        # Legacy "FACT" — disambiguate with text.
        if any(t in text_low for t in _EXTERNAL_SOURCE_TOKENS):
            return ClassificationResult(
                kind=ClaimKind.EXTERNAL_FACT,
                reason="FACT claim text references an external source.",
            )
        if any(t in text_low for t in _CALCULATION_TOKENS):
            return ClassificationResult(
                kind=ClaimKind.CALCULATED,
                reason="FACT claim text carries a calculation.",
            )
        if any(t in text_low for t in _BUSINESS_CONTEXT_TOKENS):
            return ClassificationResult(
                kind=ClaimKind.INTERNAL_BUSINESS,
                reason="FACT claim text references the user's business context.",
            )
        # Default — bare "FACT" → INTERNAL_BUSINESS to preserve
        # legacy default behaviour (LLM used FACT for "things we
        # believe about the user").
        return ClassificationResult(
            kind=ClaimKind.INTERNAL_BUSINESS,
            reason="Bare FACT claim defaults to internal business evidence.",
        )

    def classify_text(self, text: str) -> ClassificationResult:
        """Infer the kind from the claim text alone (no legacy label)."""
        text_low = (text or "").lower()
        if any(t in text_low for t in _ASSUMPTION_TOKENS):
            return ClassificationResult(
                kind=ClaimKind.ASSUMPTION,
                reason="Advisory phrasing detected.",
            )
        if any(t in text_low for t in _CALCULATION_TOKENS):
            return ClassificationResult(
                kind=ClaimKind.CALCULATED,
                reason="Calculation phrasing detected.",
            )
        if any(t in text_low for t in _EXTERNAL_SOURCE_TOKENS):
            return ClassificationResult(
                kind=ClaimKind.EXTERNAL_FACT,
                reason="External authority reference detected.",
            )
        if any(t in text_low for t in _BUSINESS_CONTEXT_TOKENS):
            return ClassificationResult(
                kind=ClaimKind.INTERNAL_BUSINESS,
                reason="Business context reference detected.",
            )
        return ClassificationResult(
            kind=ClaimKind.UNKNOWN,
            reason="No kind signal detected in claim text.",
        )

    def enforce_business_isolation(
        self, *, kind: ClaimKind, has_external_source: bool
    ) -> None:
        """Raise if business / external evidence is contaminated.

        The brief: "Do not allow external information to silently
        overwrite business data." This is the safety gate that
        enforces it.
        """
        if kind in (
            ClaimKind.INTERNAL_BUSINESS, ClaimKind.CALCULATED
        ) and has_external_source:
            raise ClaimKindContaminationError(
                f"INTERNAL/CALCULATED claim cannot carry an external source."
            )
        if kind == ClaimKind.EXTERNAL_FACT and not has_external_source:
            raise ClaimKindContaminationError(
                "EXTERNAL_FACT claim must carry a source."
            )

    def validate_no_fabricated_source(self, source_url: str) -> bool:
        """Reject obviously-fake URLs.

        The brief: "Do not fabricate dates, rules, benefits or links."
        This is the cheap pre-flight check. The caller should still
        confirm the URL resolves; this just blocks the obvious cases.
        """
        if not source_url or not source_url.strip():
            return False
        s = source_url.strip().lower()
        if s.startswith("http://example.com") or s.startswith("https://example.com"):
            return False
        if s in {"https://example.com", "http://example.com"}:
            return False
        if "placeholder" in s or "fake" in s or "todo" in s:
            return False
        return True


class ClaimKindContaminationError(ValueError):
    """Raised when business / external evidence streams cross."""
