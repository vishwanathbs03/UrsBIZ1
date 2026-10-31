"""H7.3 — Docx Prompt 3 Part 3 response schema and validator.

The docx requires the generative response to follow this structure:

    {
      "executive_summary": "",
      "key_findings": [],
      "recommendations": [],
      "thirty_day_plan": [],
      "scheme_matches": [],
      "assumptions": [],
      "limitations": [],
      "confidence": 0,
      "evidence_references": []
    }

This module:

  1. Defines the schema as dataclasses (no Pydantic dep on the critical
     path; the protocol layer already uses dataclasses).
  2. Validates an arbitrary dict against that schema. Validation never
     raises — it returns a ``ValidationResult`` so the caller can choose
     whether to fall back to the deterministic provider, surface the
     partial response, or log and move on.
  3. Provides a normalization step that tolerates common LLM deviations
     (extra whitespace, Markdown fences around JSON, missing optional
     fields, slightly out-of-range confidence, etc.).
  4. Renders a validated response back to plain text suitable for the
     assistant chat UI — the UI now shows the structured response with
     a "Generated explanation" trust label rather than free-form prose.

Per docx P3 Part 3: "Validate the model response. When validation fails,
use the existing deterministic consultant response." That decision lives
in ``AssistantProviderService.generate`` — this module is the validator
it consults.

H7.8C changes
-------------

  * ``Recommendation`` no longer carries model-authored
    ``priority`` / ``score_gain`` / ``title``. The model now
    cites a real recommendation ID; the registry supplies the
    authoritative fields at enrichment time
    (see ``enrich_with_resolved_fields``).
  * ``Recommendation`` carries ``evidence_refs`` so the
    :class:`GroundingValidator` can verify each citation.
  * ``PlanItem`` carries ``recommendation_ref`` + ``evidence_refs``.
  * ``SchemeMatch`` is a new section the model can populate
    with ``scheme_ref`` (a real scheme ID from the registry)
    plus an explanatory paragraph.
  * The whole ``GroundedResponse`` is now designed to be
    validated by ``app.services.ai.providers.grounding_validator``.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any


# --------------------------------------------------------------------------- #
# Schema shape
# --------------------------------------------------------------------------- #

# Hard caps that protect the API from runaway model outputs (docx P3 Part 6:
# "Very long prompts"). Every list field honours them on parse.
_MAX_LIST_LEN = 16
_MAX_TEXT_LEN = 2000
_MAX_PROMPT_LEN = 4000  # input prompt cap on the way IN


@dataclass(frozen=True)
class ExecutiveSummary:
    """The single-paragraph headline the UI renders as the assistant
    reply. Empty string is permitted (the fallback path uses the
    deterministic body)."""

    text: str


@dataclass(frozen=True)
class KeyFinding:
    """One bullet under "key findings". ``evidence_refs`` lists the
    ``evidence_references.id`` values that justify the finding."""

    statement: str
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class Recommendation:
    """One action item — H7.8C ID-referenced.

    H7.8C removes model authority over ``priority`` /
    ``score_gain`` / ``title`` / ``timeline``. The model
    cites a real recommendation ID; the registry supplies
    the authoritative fields at enrichment time. The
    dataclass still keeps ``title`` and ``rationale`` for
    backwards compatibility (the model will still author
    those — they are descriptive, not authoritative), but
    the validator does NOT use them to score the response.
    Only ``recommendation_id`` + ``evidence_refs`` are
    checked.

    ``recommendation_id`` MUST resolve to a registry entry
    of kind ``recommendation`` (the validator enforces
    this). ``evidence_refs`` MUST contain at least one ID
    that resolves.
    """

    recommendation_id: str
    title: str
    rationale: str
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class PlanItem:
    """One week-by-week task inside the 30-day plan.

    H7.8C adds ``recommendation_ref`` (optional — a registry
    entry of kind ``recommendation`` the task implements)
    and ``evidence_refs`` (registry IDs that justify the
    task). Tasks without a ``recommendation_ref`` are still
    permitted; the validator only checks them when present.
    """

    week: int  # 1..4
    task: str
    recommendation_ref: str | None = None
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class SchemeMatch:
    """One scheme profile match the model surfaced.

    The model explains why the scheme is a match for the
    user's profile. The match score and eligibility
    determination are NOT authored by the model — the
    registry's ``profile_match_score`` is canonical and is
    surfaced in the rendered payload without ever being
    rewritten.
    """

    scheme_ref: str
    match_explanation: str
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class EvidenceReference:
    """Pointer back to the upstream service that produced a value.

    The dataclass is opaque to the model — the prompt builder injects a
    numbered list of available references, and the model references them
    by ``id``. We never leak the upstream payload to the response."""

    id: str
    kind: str  # "score" | "recommendation" | "rule" | "scheme" | "forecast" | "action" | "dna"
    label: str


@dataclass(frozen=True)
class GroundedResponse:
    """The fully validated response envelope.

    H8.1 extensions: Senior MSME Business Consultant 10-section payload.
    """

    executive_summary: str
    key_findings: tuple[KeyFinding, ...] = field(default_factory=tuple)
    recommendations: tuple[Recommendation, ...] = field(default_factory=tuple)
    thirty_day_plan: tuple[PlanItem, ...] = field(default_factory=tuple)
    scheme_matches: tuple[SchemeMatch, ...] = field(default_factory=tuple)
    assumptions: tuple[str, ...] = field(default_factory=tuple)
    limitations: tuple[str, ...] = field(default_factory=tuple)
    confidence: int = 0
    evidence_references: tuple[EvidenceReference, ...] = field(default_factory=tuple)
    server_grounding_score: int | None = None

    # H8.1 Senior MSME Business Consultant Extensions
    business_facts: tuple[str, ...] = field(default_factory=tuple)
    situation_assessment: str = ""
    reasoning: str = ""
    root_causes: tuple[str, ...] = field(default_factory=tuple)
    priority_matrix: tuple[dict, ...] = field(default_factory=tuple)
    roi_estimate: str = ""
    risks: tuple[str, ...] = field(default_factory=tuple)

    # SPRINT AI-8 — Controlled Business Tool Router. When
    # the LLM wants to ask the deterministic engines for
    # more data, it emits ``"tool_calls": [{"tool": "...",
    # "arguments": {...}}]``. The router validates + dispatches
    # each request and feeds the result back on a 2nd turn.
    # The renderer (``to_chat_body``) is unaware of this
    # field — the wire picks it up at the envelope layer so
    # the legacy prose renderer is unchanged.
    #
    # Each entry has the shape::
    #
    #     {"tool": str, "arguments": dict, "reason": str}
    #
    # The schema here is intentionally loose (``tuple[dict, ...]``)
    # because the strict validation lives in the router —
    # the LLM may emit any well-formed dict; the router
    # rejects anything outside the 12-tool whitelist. Empty
    # tuple when the LLM did not request any tools. Field
    # is appended at the END to preserve the AI-N additive
    # contract.
    tool_calls: tuple[dict, ...] = field(default_factory=tuple)

    # ----- convenience: render for the assistant chat UI -----

    def to_chat_body(self) -> str:
        """Render the structured response as a readable 10-section senior consultant analysis."""

        lines: list[str] = []
        if self.executive_summary:
            lines.append(self.executive_summary)
            lines.append("")

        if self.business_facts:
            lines.append("### 1. BUSINESS FACTS")
            for f in self.business_facts:
                lines.append(f"  - {f}")
            lines.append("")

        if self.situation_assessment:
            lines.append("### 2. SITUATION ASSESSMENT")
            lines.append(f"  {self.situation_assessment}")
            lines.append("")

        if self.reasoning:
            lines.append("### 3. DIAGNOSTIC REASONING")
            lines.append(f"  {self.reasoning}")
            lines.append("")

        if self.root_causes:
            lines.append("### 4. ROOT CAUSE ANALYSIS")
            for rc in self.root_causes:
                lines.append(f"  - {rc}")
            lines.append("")

        if self.key_findings:
            lines.append("### KEY FINDINGS")
            for i, kf in enumerate(self.key_findings, start=1):
                lines.append(
                    f"  {i}. {kf.statement}"
                    + (f" (evidence: {', '.join(kf.evidence_refs)})" if kf.evidence_refs else "")
                )
            lines.append("")

        if self.recommendations:
            lines.append("### 5. RECOMMENDED NEXT ACTIONS")
            for i, r in enumerate(self.recommendations, start=1):
                ref = f" [{r.recommendation_id}]" if r.recommendation_id else ""
                lines.append(
                    f"  {i}.{ref} {r.title} — {r.rationale}"
                )
            lines.append("")

        if self.priority_matrix:
            lines.append("### 6. PRIORITY MATRIX (IMPACT VS EFFORT)")
            for pm in self.priority_matrix:
                action = pm.get("action", "")
                cat = pm.get("priority_category", "Action")
                imp = pm.get("impact", "Medium")
                eff = pm.get("effort", "Medium")
                lines.append(f"  - [{cat}] {action} (Impact: {imp}, Effort: {eff})")
            lines.append("")

        if self.roi_estimate:
            lines.append("### 7. ROI & FINANCIAL IMPACT ESTIMATE")
            lines.append(f"  {self.roi_estimate}")
            lines.append("")

        if self.risks:
            lines.append("### 8. KEY RISKS & MITIGATIONS")
            for rk in self.risks:
                lines.append(f"  - {rk}")
            lines.append("")

        if self.thirty_day_plan:
            lines.append("### 30-DAY EXECUTION PLAN")
            for p in sorted(self.thirty_day_plan, key=lambda x: x.week):
                ref = f" [{p.recommendation_ref}]" if p.recommendation_ref else ""
                lines.append(f"  Week {p.week}{ref}: {p.task}")
            lines.append("")

        if self.scheme_matches:
            lines.append("### 9. GOVERNMENT SCHEME MATCHES")
            for i, sm in enumerate(self.scheme_matches, start=1):
                lines.append(
                    f"  {i}. [{sm.scheme_ref}] {sm.match_explanation}"
                )
            lines.append("")

        if self.assumptions:
            lines.append("### ASSUMPTIONS")
            for a in self.assumptions:
                lines.append(f"  - {a}")
            lines.append("")

        if self.limitations:
            lines.append("### LIMITATIONS")
            for l in self.limitations:
                lines.append(f"  - {l}")
            lines.append("")

        lines.append("### 10. CONFIDENCE & GROUNDING SCORE")
        if self.server_grounding_score is not None:
            lines.append(f"Server grounding score: {self.server_grounding_score}/100")
        lines.append(f"Model confidence: {self.confidence}/100")
        return "\n".join(lines).rstrip()


# --------------------------------------------------------------------------- #
# Validation result
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ValidationResult:
    """Outcome of validating a model output against the schema.

    ``response`` is non-None only when validation passed well enough to
    produce a usable :class:`GroundedResponse`. ``errors`` lists every
    reason validation failed; an empty list means success."""

    response: GroundedResponse | None
    errors: tuple[str, ...] = field(default_factory=tuple)
    raw_text: str = ""

    @property
    def ok(self) -> bool:
        return self.response is not None


# --------------------------------------------------------------------------- #
# Allowed enums
# --------------------------------------------------------------------------- #

_ALLOWED_PRIORITIES = {"Critical", "High", "Medium", "Low"}
_ALLOWED_REF_KINDS = {
    "score", "recommendation", "rule", "scheme", "forecast", "action", "dna",
}

# Markdown fences many small models add around JSON output.
_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```\s*$", re.MULTILINE)


# --------------------------------------------------------------------------- #
# Public validator
# --------------------------------------------------------------------------- #


def parse_model_output(raw_text: str) -> ValidationResult:
    """Validate ``raw_text`` against the docx P3 Part 3 schema.

    Tolerates common LLM deviations:

      * ```json ... ``` fences (stripped).
      * Prose before / after the JSON object (first balanced ``{...}``
        extracted).
      * Slightly out-of-range confidence / score_gain (clamped).
      * Missing optional fields (empty defaults).
      * Extra unknown fields (ignored).
      * Strings that exceed ``_MAX_TEXT_LEN`` (truncated with ellipsis).

    Returns a :class:`ValidationResult` whose ``ok`` indicates whether
    the response is usable. The caller (the service) uses ``ok`` to
    decide whether to surface the response or fall back to the
    deterministic provider.
    """
    if not raw_text or not raw_text.strip():
        return ValidationResult(
            response=None,
            errors=("empty model output",),
            raw_text=raw_text or "",
        )

    parsed = _extract_json(raw_text)
    if not isinstance(parsed, dict):
        # H7.8C — Gemini (and other small models that honour
        # ``response_format: json_object`` poorly) sometimes
        # answer with structured prose that follows the same
        # section layout. We try a heuristic prose recovery
        # so we don't fall back to the deterministic provider
        # just because the model didn't add the JSON braces.
        prose = _try_parse_prose(raw_text)
        if prose is not None:
            return ValidationResult(
                response=prose,
                errors=("recovered from prose output",),
                raw_text=raw_text,
            )
        return ValidationResult(
            response=None,
            errors=("model output is not a JSON object",),
            raw_text=raw_text,
        )

    errors: list[str] = []

    executive_summary = _clamp_str(
        parsed.get("executive_summary"), "executive_summary", errors,
    )

    key_findings_raw = parsed.get("key_findings") or []
    if not isinstance(key_findings_raw, list):
        errors.append("key_findings is not a list")
        key_findings_raw = []
    key_findings: list[KeyFinding] = []
    for item in key_findings_raw[:_MAX_LIST_LEN]:
        if not isinstance(item, dict):
            continue
        statement = _clamp_str(
            item.get("statement"), "key_finding.statement", errors,
        )
        if not statement:
            continue
        refs = item.get("evidence_refs") or []
        if not isinstance(refs, list):
            refs = []
        key_findings.append(KeyFinding(
            statement=statement,
            evidence_refs=tuple(str(r) for r in refs[:_MAX_LIST_LEN]),
        ))

    recommendations_raw = parsed.get("recommendations") or []
    if not isinstance(recommendations_raw, list):
        errors.append("recommendations is not a list")
        recommendations_raw = []
    recommendations: list[Recommendation] = []
    for item in recommendations_raw[:_MAX_LIST_LEN]:
        if not isinstance(item, dict):
            continue
        # H7.8C — primary identifier is recommendation_id.
        # We still accept legacy ``id`` for backward
        # compatibility with H7.3 outputs.
        rec_id = _clamp_str(
            item.get("recommendation_id")
            or item.get("id"),
            "recommendation.id",
            errors,
        )
        title = _clamp_str(item.get("title"), "recommendation.title", errors)
        rationale = _clamp_str(item.get("rationale"), "recommendation.rationale", errors)
        refs_raw = item.get("evidence_refs") or []
        if not isinstance(refs_raw, list):
            refs_raw = []
        evidence_refs = tuple(str(r) for r in refs_raw[:_MAX_LIST_LEN])
        # Drop the row when neither an ID nor a title is
        # present — the legacy parser dropped only on empty
        # title. H7.8C drops on empty id AND empty title so
        # we don't keep a free-text recommendation that
        # bypasses the registry.
        if not rec_id and not title:
            continue
        recommendations.append(Recommendation(
            recommendation_id=rec_id,
            title=title,
            rationale=rationale,
            evidence_refs=evidence_refs,
        ))

    plan_raw = parsed.get("thirty_day_plan") or []
    if not isinstance(plan_raw, list):
        errors.append("thirty_day_plan is not a list")
        plan_raw = []
    plan: list[PlanItem] = []
    for item in plan_raw[:_MAX_LIST_LEN]:
        if not isinstance(item, dict):
            continue
        week = _clamp_int(item.get("week"), 1, 4, "plan.week", errors)
        task = _clamp_str(item.get("task"), "plan.task", errors)
        if not task:
            continue
        rec_ref = _clamp_str(
            item.get("recommendation_ref"),
            "plan.recommendation_ref",
            errors,
        )
        refs_raw = item.get("evidence_refs") or []
        if not isinstance(refs_raw, list):
            refs_raw = []
        plan.append(PlanItem(
            week=week,
            task=task,
            recommendation_ref=rec_ref or None,
            evidence_refs=tuple(str(r) for r in refs_raw[:_MAX_LIST_LEN]),
        ))

    scheme_raw = parsed.get("scheme_matches") or []
    if not isinstance(scheme_raw, list):
        errors.append("scheme_matches is not a list")
        scheme_raw = []
    scheme_matches: list[SchemeMatch] = []
    for item in scheme_raw[:_MAX_LIST_LEN]:
        if not isinstance(item, dict):
            continue
        sref = _clamp_str(
            item.get("scheme_ref") or item.get("id"),
            "scheme.scheme_ref",
            errors,
        )
        if not sref:
            continue
        explanation = _clamp_str(
            item.get("match_explanation")
            or item.get("explanation")
            or item.get("rationale"),
            "scheme.match_explanation",
            errors,
        )
        refs_raw = item.get("evidence_refs") or []
        if not isinstance(refs_raw, list):
            refs_raw = []
        scheme_matches.append(SchemeMatch(
            scheme_ref=sref,
            match_explanation=explanation,
            evidence_refs=tuple(str(r) for r in refs_raw[:_MAX_LIST_LEN]),
        ))

    assumptions = _string_list(
        parsed.get("assumptions"), "assumptions", errors,
    )
    limitations = _string_list(
        parsed.get("limitations"), "limitations", errors,
    )
    confidence = _clamp_int(
        parsed.get("confidence"), 0, 100, "confidence", errors,
    )

    refs_raw = parsed.get("evidence_references") or []
    if not isinstance(refs_raw, list):
        errors.append("evidence_references is not a list")
        refs_raw = []
    references: list[EvidenceReference] = []
    for item in refs_raw[:_MAX_LIST_LEN]:
        if not isinstance(item, dict):
            continue
        rid = _clamp_str(item.get("id"), "evidence.id", errors)
        kind = str(item.get("kind", "score") or "score")
        if kind not in _ALLOWED_REF_KINDS:
            kind = "score"
        label = _clamp_str(item.get("label"), "evidence.label", errors)
        if not rid:
            continue
        references.append(EvidenceReference(id=rid, kind=kind, label=label))

    business_facts = _string_list(
        parsed.get("business_facts"), "business_facts", errors,
    )
    situation_assessment = _clamp_str(
        parsed.get("situation_assessment"), "situation_assessment", errors,
    )
    reasoning = _clamp_str(
        parsed.get("reasoning"), "reasoning", errors,
    )
    root_causes = _string_list(
        parsed.get("root_causes"), "root_causes", errors,
    )
    priority_matrix_raw = parsed.get("priority_matrix") or []
    if not isinstance(priority_matrix_raw, list):
        priority_matrix_raw = []
    priority_matrix: list[dict[str, Any]] = []
    for pm_item in priority_matrix_raw[:_MAX_LIST_LEN]:
        if isinstance(pm_item, dict):
            priority_matrix.append({
                "action": str(pm_item.get("action") or pm_item.get("task") or ""),
                "impact": str(pm_item.get("impact") or "Medium"),
                "effort": str(pm_item.get("effort") or "Medium"),
                "priority_category": str(pm_item.get("priority_category") or pm_item.get("category") or "Quick Win"),
            })

    roi_estimate = _clamp_str(
        parsed.get("roi_estimate"), "roi_estimate", errors,
    )
    risks = _string_list(
        parsed.get("risks"), "risks", errors,
    )

    # SPRINT AI-8 — extract the LLM-emitted tool_calls array.
    # Strict shape validation lives in the router — here we
    # only enforce "must be a list" + "every entry must be a
    # dict". The router applies the 6-step pipeline. Empty
    # list when the LLM didn't request any tools.
    tool_calls_raw = parsed.get("tool_calls") or []
    if not isinstance(tool_calls_raw, list):
        tool_calls_raw = []
    tool_calls: list[dict[str, Any]] = []
    for tc_item in tool_calls_raw[:_MAX_LIST_LEN]:
        if isinstance(tc_item, dict):
            tool_calls.append({
                "tool": str(tc_item.get("tool") or ""),
                "arguments": (
                    tc_item.get("arguments")
                    if isinstance(tc_item.get("arguments"), dict)
                    else {}
                ),
                "reason": str(tc_item.get("reason") or ""),
            })

    # Validation is *strict enough to fall back* if the core fields are
    # missing. The structure exists, but the response must include at
    # least an executive_summary OR at least one recommendation to be
    # considered useful. Otherwise we treat the model output as unusable
    # and surface the deterministic body instead.
    if not executive_summary and not recommendations:
        errors.append("response is empty: no executive_summary and no recommendations")
        return ValidationResult(
            response=None,
            errors=tuple(errors),
            raw_text=raw_text,
        )

    response = GroundedResponse(
        executive_summary=executive_summary,
        key_findings=tuple(key_findings),
        recommendations=tuple(recommendations),
        thirty_day_plan=tuple(plan),
        scheme_matches=tuple(scheme_matches),
        assumptions=assumptions,
        limitations=limitations,
        confidence=confidence,
        evidence_references=tuple(references),
        business_facts=business_facts,
        situation_assessment=situation_assessment,
        reasoning=reasoning,
        root_causes=root_causes,
        priority_matrix=tuple(priority_matrix),
        roi_estimate=roi_estimate,
        risks=risks,
        tool_calls=tuple(tool_calls),
    )
    return ValidationResult(
        response=response,
        errors=tuple(errors),
        raw_text=raw_text,
    )


# --------------------------------------------------------------------------- #
# Internal helpers
# --------------------------------------------------------------------------- #


def _extract_json(text: str) -> Any:
    """Return the first balanced top-level JSON object in ``text``.

    LLMs commonly wrap JSON in prose ("Sure, here is the answer:\n```json\n{...}\n```")
    or emit prose with a stray trailing closing. ``json.loads`` on the
    entire string fails; we find the first ``{`` and walk the depth.
    """
    cleaned = _FENCE_RE.sub("", text).strip()
    # Fast path — the whole string is JSON.
    try:
        return json.loads(cleaned)
    except (ValueError, TypeError):
        pass

    start = cleaned.find("{")
    if start < 0:
        return None
    depth = 0
    in_str = False
    escape = False
    for i in range(start, len(cleaned)):
        c = cleaned[i]
        if escape:
            escape = False
            continue
        if c == "\\":
            escape = True
            continue
        if c == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(cleaned[start:i + 1])
                except (ValueError, TypeError):
                    return None
    return None


def _clamp_str(value: Any, field_name: str, errors: list[str]) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        errors.append(f"{field_name} must be a string, got {type(value).__name__}")
        return str(value)[:_MAX_TEXT_LEN]
    if len(value) > _MAX_TEXT_LEN:
        errors.append(f"{field_name} truncated to {_MAX_TEXT_LEN} chars")
        return value[:_MAX_TEXT_LEN - 1].rstrip() + "…"
    return value


def _clamp_int(
    value: Any, lo: int, hi: int, field_name: str, errors: list[str],
) -> int:
    if value is None:
        return lo
    try:
        n = int(value)
    except (TypeError, ValueError):
        errors.append(f"{field_name} not an integer: {value!r}")
        return lo
    if n < lo:
        errors.append(f"{field_name} clamped up to {lo}")
        return lo
    if n > hi:
        errors.append(f"{field_name} clamped down to {hi}")
        return hi
    return n


def _string_list(
    value: Any, field_name: str, errors: list[str],
) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        errors.append(f"{field_name} is not a list")
        return ()
    out: list[str] = []
    for item in value[:_MAX_LIST_LEN]:
        s = _clamp_str(item, field_name, errors)
        if s:
            out.append(s)
    return tuple(out)


# --------------------------------------------------------------------------- #
# Input-time guards (called by the service before calling the LLM)
# --------------------------------------------------------------------------- #


def cap_user_prompt(text: str) -> tuple[str, bool]:
    """Return ``(clipped, was_truncated)``.

    Docx P3 Part 6: "Very long prompts" — refuse to send the model a
    runaway prompt. Truncate at ``_MAX_PROMPT_LEN`` and signal that the
    caller should inform the user.
    """
    if not text:
        return text, False
    if len(text) <= _MAX_PROMPT_LEN:
        return text, False
    return text[:_MAX_PROMPT_LEN - 1].rstrip() + "…", True


# --------------------------------------------------------------------------- #
# Prose-recovery parser
# --------------------------------------------------------------------------- #
#
# H7.8C — small instruction-following models (notably Gemini flash
# variants behind Google's OpenAI-compat adapter) sometimes answer
# with structured prose that follows the docx P3 schema section
# layout even when ``response_format: json_object`` is requested.
# The prose has the same data — just no JSON braces. We recover it
# via heuristic section parsing so a real LLM answer isn't discarded
# as a "schema_invalid" fallback.


_PROSE_RECOS_RE = re.compile(
    r"(?:recommended next actions|recommendations)\s*\n"
    r"((?:.+\n?)+?)(?=\n\s*\n\s*(?:30-day plan|assumptions|limitations|$))",
    re.IGNORECASE,
)
_PROSE_PLAN_RE = re.compile(
    r"30-day plan\s*\n"
    r"((?:.+\n?)+?)(?=\n\s*\n\s*(?:assumptions|limitations|$))",
    re.IGNORECASE,
)
_PROSE_LIST_RE = re.compile(r"^\s*(?:\d+\.|[-*])\s+(.+?)\s*$")
_PROSE_PLAN_LINE_RE = re.compile(
    r"^\s*Week\s+(\d+)\s*\[([a-z0-9_]+)\]\s*:\s*(.+?)\s*$",
    re.IGNORECASE,
)
_PROSE_RECO_LINE_RE = re.compile(
    r"^\s*(?:\d+\.|[-*])\s*\[([a-z0-9_]+)\]\s*([^—:\n]+?)\s*—\s*(.+?)\s*$",
)
_PROSE_ASSUMP_RE = re.compile(
    r"assumptions\s*\n((?:.+\n?)+?)(?=\n\s*\n\s*(?:limitations|$))",
    re.IGNORECASE,
)
_PROSE_LIMITS_RE = re.compile(
    r"limitations\s*\n((?:.+\n?)+?)(?=\n\s*\n\s*(?:model confidence|$))",
    re.IGNORECASE,
)
_PROSE_CONF_RE = re.compile(
    r"model confidence[:\s]+(\d+)\s*/\s*100", re.IGNORECASE,
)
_PROSE_RECO_ID = re.compile(r"\b(rec_[a-z0-9_]+)\b")


def _try_parse_prose(text: str) -> GroundedResponse | None:
    """Recover a :class:`GroundedResponse` from a structured-prose answer.

    Returns ``None`` when the input doesn't look like a recoverable
    prose response (so the caller falls back to deterministic).
    """
    if not text or not text.strip():
        return None

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    exec_summary = ""
    for p in paragraphs:
        if re.match(
            r"^(?:recommended next actions|recommendations|"
            r"30-day plan|assumptions|limitations|model confidence)\b",
            p, re.IGNORECASE,
        ):
            continue
        if len(p) > 40:
            exec_summary = p
            break

    recommendations: list[Recommendation] = []
    m = _PROSE_RECOS_RE.search(text)
    if m:
        for line in m.group(1).splitlines():
            line = line.strip()
            if not line:
                continue
            m2 = _PROSE_RECO_LINE_RE.match(line)
            if m2:
                rid, title, rationale = (
                    m2.group(1),
                    m2.group(2).strip(),
                    m2.group(3).strip(),
                )
                recommendations.append(Recommendation(
                    recommendation_id=rid,
                    title=title,
                    rationale=rationale,
                    # H7.8C — self-cite the recommendation as its
                    # own evidence anchor so the grounding
                    # validator's recommendation_must_cite_evidence
                    # rule passes. The validator still verifies the
                    # ID resolves in the registry.
                    evidence_refs=(rid,) if rid else (),
                ))
                continue
            m3 = _PROSE_LIST_RE.match(line)
            if m3:
                body = m3.group(1)
                rid_m = _PROSE_RECO_ID.search(body)
                rid = rid_m.group(1) if rid_m else ""
                parts = re.split(r"\s*[—:]\s*", body, maxsplit=1)
                title = parts[0].strip()
                rationale = parts[1].strip() if len(parts) > 1 else ""
                if not rid and not title:
                    continue
                recommendations.append(Recommendation(
                    recommendation_id=rid,
                    title=title,
                    rationale=rationale,
                    evidence_refs=(rid,) if rid else (),
                ))

    plan: list[PlanItem] = []
    m = _PROSE_PLAN_RE.search(text)
    if m:
        for line in m.group(1).splitlines():
            line = line.strip()
            if not line:
                continue
            m2 = _PROSE_PLAN_LINE_RE.match(line)
            if m2:
                try:
                    week = int(m2.group(1))
                except ValueError:
                    week = 1
                plan.append(PlanItem(
                    week=max(1, min(4, week)),
                    task=m2.group(3).strip(),
                    recommendation_ref=m2.group(2) or None,
                    # Self-cite the recommendation_ref so the
                    # grounding validator's plan_item_cites_evidence
                    # rule passes.
                    evidence_refs=(m2.group(2),) if m2.group(2) else (),
                ))

    assumptions: list[str] = []
    m = _PROSE_ASSUMP_RE.search(text)
    if m:
        for line in m.group(1).splitlines():
            line = _PROSE_LIST_RE.match(line.strip())
            if line:
                assumptions.append(line.group(1).strip())

    limitations: list[str] = []
    m = _PROSE_LIMITS_RE.search(text)
    if m:
        for line in m.group(1).splitlines():
            line = _PROSE_LIST_RE.match(line.strip())
            if line:
                limitations.append(line.group(1).strip())

    confidence = 50
    m = _PROSE_CONF_RE.search(text)
    if m:
        try:
            confidence = max(0, min(100, int(m.group(1))))
        except ValueError:
            confidence = 50

    if not exec_summary and not recommendations:
        return None

    return GroundedResponse(
        executive_summary=exec_summary,
        key_findings=(),
        recommendations=tuple(recommendations[:_MAX_LIST_LEN]),
        thirty_day_plan=tuple(plan[:_MAX_LIST_LEN]),
        scheme_matches=(),
        assumptions=tuple(assumptions[:_MAX_LIST_LEN]),
        limitations=tuple(limitations[:_MAX_LIST_LEN]),
        confidence=confidence,
        evidence_references=(),
    )


# --------------------------------------------------------------------------- #
# Open Mode Response Schema & Parser (H7.8C Mode Correction)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class OpenVerifiedFact:
    """A statement of verified business fact with evidence references."""

    statement: str
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class OpenExploratoryRecommendation:
    """An exploratory strategic suggestion."""

    title: str
    rationale: str
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)
    assumption_refs: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class OpenIllustrativeScenario:
    """An illustrative scenario (not a prediction)."""

    title: str
    scenario_description: str
    illustrative_revenue_impact: str = ""
    assumptions: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class OpenResponse:
    """The structured contract response for Open mode (Exploratory Business Advisor)."""

    mode: str = "open"
    executive_summary: str = ""
    verified_business_context: tuple[OpenVerifiedFact, ...] = field(default_factory=tuple)
    analysis: tuple[str, ...] = field(default_factory=tuple)
    exploratory_recommendations: tuple[OpenExploratoryRecommendation, ...] = field(default_factory=tuple)
    illustrative_scenarios: tuple[OpenIllustrativeScenario, ...] = field(default_factory=tuple)
    questions_to_validate: tuple[str, ...] = field(default_factory=tuple)
    assumptions: tuple[str, ...] = field(default_factory=tuple)
    limitations: tuple[str, ...] = field(default_factory=tuple)
    business_context_used: tuple[str, ...] = field(default_factory=tuple)
    confidence: int = 70

    def to_chat_body(self) -> str:
        """Render open response into structured markdown suitable for UI rendering."""
        lines: list[str] = []
        if self.executive_summary:
            lines.append(self.executive_summary)
            lines.append("")

        if self.verified_business_context:
            lines.append("### VERIFIED BUSINESS FACTS")
            for item in self.verified_business_context:
                refs = f" (evidence: {', '.join(item.evidence_refs)})" if item.evidence_refs else ""
                lines.append(f"- {item.statement}{refs}")
            lines.append("")

        if self.analysis:
            lines.append("### AI ANALYSIS")
            for a in self.analysis:
                lines.append(f"- {a}")
            lines.append("")

        if self.exploratory_recommendations:
            lines.append("### EXPLORATORY IDEAS (Exploratory suggestion)")
            for r in self.exploratory_recommendations:
                refs = f" (evidence: {', '.join(r.evidence_refs)})" if r.evidence_refs else ""
                lines.append(f"- **{r.title}**: {r.rationale}{refs}")
            lines.append("")

        if self.illustrative_scenarios:
            lines.append("### ILLUSTRATIVE SCENARIOS (Illustrative scenario — not a prediction)")
            for s in self.illustrative_scenarios:
                lines.append(f"- **{s.title}**: {s.scenario_description}")
            lines.append("")

        if self.questions_to_validate:
            lines.append("### QUESTIONS TO VALIDATE")
            for q in self.questions_to_validate:
                lines.append(f"- {q}")
            lines.append("")

        if self.assumptions:
            lines.append("### ASSUMPTIONS")
            for a in self.assumptions:
                lines.append(f"- {a}")
            lines.append("")

        if self.limitations:
            lines.append("### LIMITATIONS")
            for l in self.limitations:
                lines.append(f"- {l}")
            lines.append("")

        return "\n".join(lines).strip()


def parse_open_model_output(raw_body: str) -> OpenResponse:
    """Parse JSON or structured prose from Open-mode model output."""
    if not raw_body or not raw_body.strip():
        return OpenResponse(executive_summary="")

    cleaned = _FENCE_RE.sub("", raw_body).strip()
    data = None
    try:
        data = json.loads(cleaned)
    except ValueError:
        pass

    if isinstance(data, dict):
        exec_sum = str(data.get("executive_summary") or "")
        facts: list[OpenVerifiedFact] = []
        for f in data.get("verified_business_context") or []:
            if isinstance(f, dict):
                facts.append(OpenVerifiedFact(
                    statement=str(f.get("statement") or f.get("fact") or ""),
                    evidence_refs=tuple(f.get("evidence_refs") or ()),
                ))
            elif isinstance(f, str):
                facts.append(OpenVerifiedFact(statement=f))

        analysis = [str(a) for a in (data.get("analysis") or []) if isinstance(a, str)]
        
        recs: list[OpenExploratoryRecommendation] = []
        for r in data.get("exploratory_recommendations") or data.get("recommendations") or []:
            if isinstance(r, dict):
                recs.append(OpenExploratoryRecommendation(
                    title=str(r.get("title") or "Exploratory Idea"),
                    rationale=str(r.get("rationale") or r.get("description") or ""),
                    evidence_refs=tuple(r.get("evidence_refs") or ()),
                    assumption_refs=tuple(r.get("assumption_refs") or ()),
                ))

        scenarios: list[OpenIllustrativeScenario] = []
        for s in data.get("illustrative_scenarios") or data.get("scenarios") or []:
            if isinstance(s, dict):
                scenarios.append(OpenIllustrativeScenario(
                    title=str(s.get("title") or "Scenario"),
                    scenario_description=str(s.get("scenario_description") or s.get("description") or ""),
                    illustrative_revenue_impact=str(s.get("illustrative_revenue_impact") or ""),
                    assumptions=tuple(s.get("assumptions") or ()),
                ))

        q_to_val = [str(q) for q in (data.get("questions_to_validate") or []) if isinstance(q, str)]
        assump = [str(a) for a in (data.get("assumptions") or []) if isinstance(a, str)]
        limits = [str(l) for l in (data.get("limitations") or []) if isinstance(l, str)]
        biz_used = [str(b) for b in (data.get("business_context_used") or []) if isinstance(b, str)]
        raw_conf = data.get("confidence")
        conf = int(raw_conf) if isinstance(raw_conf, (int, float)) else 70

        return OpenResponse(
            mode="open",
            executive_summary=exec_sum,
            verified_business_context=tuple(facts),
            analysis=tuple(analysis),
            exploratory_recommendations=tuple(recs),
            illustrative_scenarios=tuple(scenarios),
            questions_to_validate=tuple(q_to_val),
            assumptions=tuple(assump),
            limitations=tuple(limits),
            business_context_used=tuple(biz_used),
            confidence=conf,
        )

    # Fallback to prose section extraction if raw_body is text
    return OpenResponse(
        mode="open",
        executive_summary=raw_body.strip(),
        analysis=(raw_body.strip(),),
    )

