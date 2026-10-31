"""MockCopilotProvider — deterministic, template-based
Copilot provider.

The spec says:

  * "Implement deterministic provider."
  * "No network. No API keys. No LLM."
  * "Generate responses from templates."
  * "Response quality should depend on context."

The mock is the only provider shipped in Sprint
6 — Part 1. It is honest about being a mock:
``self.name`` is ``"mock-copilot-1"`` and the
response sidecar carries the same name.

The mock is a pure function of the
:class:`CopilotContext` — no time, no random,
no I/O. Two calls with the same context
produce byte-identical output.

The mock also produces a ``highlights`` tuple
of inline tags the :class:`CitationBuilder`
uses to find supporting sources. The tags are
deterministic and shaped so a real provider can
emit the same vocabulary (``"score:export"``,
``"rule:rule.export.no_iec"``,
``"recommendation:R-123"``,
``"article:KB-001"``, ``"roadmap:R-123"``,
``"dna:archetype.foundation_builder"``).

When a real provider lands in a future
milestone, the swap is
``CopilotService(provider=MockCopilotProvider())``
-> ``CopilotService(provider=OpenAIProvider(...))``.
Nothing else changes.
"""

from __future__ import annotations

from app.services.copilot.base import (
    CopilotContext,
    CopilotPrompt,
    CopilotProvider,
    CopilotProviderOutput,
)


class MockCopilotProvider(CopilotProvider):
    """Deterministic, template-based provider.

    The provider does NOT call an LLM. It walks
    the context, picks the most decision-worthy
    signals, and stitches a 2-4 sentence
    consultant's answer out of template
    fragments. The output is shaped exactly like
    a future real-provider response.
    """

    name = "mock-copilot-1"

    def complete(self, prompt: CopilotPrompt) -> CopilotProviderOutput:
        ctx = prompt.context
        text, highlights = _render(ctx)
        return CopilotProviderOutput(
            text=text,
            highlights=tuple(highlights),
        )


# --------------------------------------------------------------------------- #
# Templates
# --------------------------------------------------------------------------- #


_INTENT_OPENERS: dict[str, str] = {
    "GENERAL_BUSINESS": (
        "Looking at your business overall, here is what the "
        "UrsBiz engines are showing right now."
    ),
    "BUSINESS_SCORE": (
        "Your business score reflects the state of the five "
        "readiness lenses UrsBiz measures."
    ),
    "EXPORT": (
        "Export readiness is a function of certifications, "
        "online presence, and an active international sales "
        "channel."
    ),
    "DIGITAL": (
        "Digital readiness is a function of online presence, "
        "automation, and tooling."
    ),
    "COMPLIANCE": (
        "Compliance readiness is a function of registrations, "
        "active certifications, and recurring renewals."
    ),
    "DNA": (
        "Your Business DNA captures the dominant archetype, "
        "secondary traits, strengths, and risk areas."
    ),
    "ROADMAP": (
        "The execution roadmap sequences your top "
        "recommendations into a single, dependency-respecting "
        "plan."
    ),
    "RECOMMENDATIONS": (
        "UrsBiz produces a ranked list of recommendations, "
        "each tied to a specific rule firing and knowledge "
        "article."
    ),
    "RULES": (
        "The Rule Engine surfaces the gaps UrsBiz found in "
        "your business profile."
    ),
    "SCENARIO": (
        "The Scenario Simulator lets you preview the impact of "
        "an action before you commit to it."
    ),
    "OCR": (
        "Document ingestion is handled by the OCR engine. "
        "UrsBiz accepts a single file upload and returns a "
        "review payload."
    ),
    "FINANCE": (
        "Financial projections blend your current score with the "
        "ROI of your top recommendations."
    ),
    "GREETING": (
        "Hello. I am the UrsBiz Copilot. Ask me about your "
        "business score, recommendations, roadmap, DNA, or any "
        "of the other engines."
    ),
    "UNKNOWN": (
        "I can answer questions about your business score, "
        "recommendations, roadmap, DNA, rules, finance, exports, "
        "digital, compliance, and OCR document uploads."
    ),
}


# --------------------------------------------------------------------------- #
# Composition
# --------------------------------------------------------------------------- #


def _render(ctx: CopilotContext) -> tuple[str, list[str]]:
    intent = ctx.intent
    highlights: list[str] = []
    opener = _INTENT_OPENERS.get(
        intent, _INTENT_OPENERS["UNKNOWN"]
    )
    parts: list[str] = [opener]

    # The body depends on which services the
    # context builder pulled. Each section is
    # optional so a thin context (e.g. an empty
    # business profile) still produces a
    # well-formed response.
    if ctx.scores is not None:
        s, h = _render_scores(ctx)
        parts.append(s)
        highlights.extend(h)

    if ctx.dna is not None:
        s, h = _render_dna(ctx)
        parts.append(s)
        highlights.extend(h)

    if ctx.rules is not None and intent in (
        "RULES", "EXPORT", "DIGITAL", "COMPLIANCE",
        "RECOMMENDATIONS", "GENERAL_BUSINESS",
    ):
        s, h = _render_rules(ctx)
        parts.append(s)
        highlights.extend(h)

    if ctx.recommendations is not None and intent in (
        "RECOMMENDATIONS", "ROADMAP", "EXPORT",
        "DIGITAL", "COMPLIANCE", "DNA", "SCENARIO",
        "FINANCE", "GENERAL_BUSINESS",
    ):
        s, h = _render_recommendations(ctx)
        parts.append(s)
        highlights.extend(h)

    if ctx.roadmap is not None and intent in (
        "ROADMAP", "EXPORT", "DIGITAL", "SCENARIO",
    ):
        s, h = _render_roadmap(ctx)
        parts.append(s)
        highlights.extend(h)

    if ctx.knowledge is not None and intent in (
        "EXPORT", "COMPLIANCE", "OCR",
    ):
        s, h = _render_knowledge(ctx)
        parts.append(s)
        highlights.extend(h)

    if ctx.business is not None and intent == "OCR":
        s, h = _render_business(ctx)
        parts.append(s)
        highlights.extend(h)

    # Closing line: deterministic, intent-
    # specific, always present so the response
    # never ends on a half-sentence.
    closer = _render_closer(ctx)
    if closer:
        parts.append(closer)

    return _join(parts), highlights


# --------------------------------------------------------------------------- #
# Section renderers
# --------------------------------------------------------------------------- #


def _render_scores(ctx: CopilotContext) -> tuple[str, list[str]]:
    highlights: list[str] = []
    summary = (ctx.scores or {}).get("summary") or {}
    overall = summary.get("score")
    level = summary.get("level", "Low")
    if overall is None:
        return "", highlights
    highlights.append("score:overall")
    lines: list[str] = []
    lines.append(
        f"Your overall score is {overall} ({level}), "
        f"a weighted average of {summary.get('weighted_inputs', '?')} "
        f"lens scores."
    )
    for s in sorted(
        (ctx.scores.get("scores") or []),
        key=lambda s: -int((s or {}).get("score", 0) or 0),
    )[:3]:
        if not isinstance(s, dict):
            continue
        key = s.get("key", "?")
        highlights.append(f"score:{key}")
        lines.append(
            f" {key} is {s.get('score', '?')} ({s.get('level', '?')})."
        )
    return _join(lines), highlights


def _render_dna(ctx: CopilotContext) -> tuple[str, list[str]]:
    highlights: list[str] = []
    dna_inner = (ctx.dna or {}).get("dna") or {}
    archetype = dna_inner.get("archetype") or {}
    key = str(archetype.get("key", ""))
    title = str(archetype.get("title", "your archetype"))
    match = int(archetype.get("match_score", 0) or 0)
    if key:
        highlights.append(f"dna:archetype.{key}")
    traits = [
        t for t in (dna_inner.get("secondary_traits") or [])
        if isinstance(t, dict) and t.get("present")
    ]
    if not archetype:
        return "", highlights
    lines = [
        f"Your dominant archetype is {title} (match {match})."
    ]
    if traits:
        for tr in traits[:2]:
            highlights.append(
                f"dna:trait.{tr.get('key', '?')}"
            )
            lines.append(
                f" A secondary trait ({tr.get('key', '?')}) "
                f"is also present at strength {tr.get('strength', 0)}."
            )
    return _join(lines), highlights


def _render_rules(ctx: CopilotContext) -> tuple[str, list[str]]:
    highlights: list[str] = []
    flat = _flatten_rules(ctx.rules)
    if not flat:
        return "", highlights
    lines: list[str] = []
    lines.append(
        f"The Rule Engine found {len(flat)} active firings."
    )
    for f in flat[:3]:
        rid = f.get("id", "?")
        highlights.append(f"rule:{rid}")
        lines.append(
            f" {f.get('priority', '?')} priority: {f.get('title', '')} "
            f"(impact {f.get('estimated_impact', 0)})."
        )
    return _join(lines), highlights


def _render_recommendations(ctx: CopilotContext) -> tuple[str, list[str]]:
    highlights: list[str] = []
    recs = sorted(
        (ctx.recommendations.get("recommendations") or []),
        key=lambda r: -int((r or {}).get("business_impact", 0) or 0),
    )
    if not recs:
        return "", highlights
    lines = [
        f"There are {len(recs)} ranked recommendations; "
        f"the top three are:"
    ]
    for r in recs[:3]:
        if not isinstance(r, dict):
            continue
        rid = r.get("id", "?")
        highlights.append(f"recommendation:{rid}")
        lines.append(
            f" {r.get('priority', '?')} priority — "
            f"{r.get('title', '')} (impact "
            f"{r.get('business_impact', 0)})."
        )
    return _join(lines), highlights


def _render_roadmap(ctx: CopilotContext) -> tuple[str, list[str]]:
    highlights: list[str] = []
    items = sorted(
        (ctx.roadmap.get("items") or []),
        key=lambda it: int((it or {}).get("estimated_start_order", 0) or 0),
    )
    if not items:
        return "", highlights
    lines = [
        f"The execution plan has {len(items)} items."
    ]
    for it in items[:3]:
        if not isinstance(it, dict):
            continue
        rid = it.get("recommendation_id", "?")
        highlights.append(f"roadmap:{rid}")
        lines.append(
            f" Start: {it.get('title', '')} "
            f"({it.get('phase', '?')}, "
            f"impact {it.get('expected_business_impact', 0)})."
        )
    return _join(lines), highlights


def _render_knowledge(ctx: CopilotContext) -> tuple[str, list[str]]:
    highlights: list[str] = []
    arts = sorted(
        (ctx.knowledge.get("articles") or []),
        key=lambda a: str((a or {}).get("id", "")),
    )
    if not arts:
        return "", highlights
    lines = [f"{len(arts)} knowledge articles are available."]
    for a in arts[:3]:
        if not isinstance(a, dict):
            continue
        aid = a.get("id", "?")
        highlights.append(f"article:{aid}")
        lines.append(
            f" {aid} — {a.get('title', '')} "
            f"({a.get('topic', '?')})."
        )
    return _join(lines), highlights


def _render_business(ctx: CopilotContext) -> tuple[str, list[str]]:
    highlights: list[str] = ["score:business_profile"]
    meta = (ctx.business or {}).get("meta") or {}
    pc = meta.get("profile_completion")
    cl = meta.get("completeness_level", "?")
    if pc is None:
        return "", highlights
    return (
        f"Your business profile is {pc}% complete "
        f"({cl}).",
        highlights,
    )


def _render_closer(ctx: CopilotContext) -> str:
    intent = ctx.intent
    if intent == "GREETING":
        return (
            "Try one of: 'How can I improve my export readiness?', "
            "'What is my business DNA?', or 'Show me my top "
            "recommendations'."
        )
    if intent == "UNKNOWN":
        return (
            "Rephrase with a specific area — export, digital, "
            "compliance, finance, DNA, roadmap, or recommendations "
            "— and I can give you a more targeted answer."
        )
    return ""


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _flatten_rules(rules_payload: dict | None) -> list[dict]:
    out: list[dict] = []
    cats = (rules_payload or {}).get("categories") or {}
    if not isinstance(cats, dict):
        return out
    for cat, block in cats.items():
        if not isinstance(block, dict):
            continue
        for f in block.get("firings") or []:
            if isinstance(f, dict):
                f2 = dict(f)
                f2.setdefault("category", cat)
                out.append(f2)
    out.sort(
        key=lambda f: (
            -int(f.get("estimated_impact", 0) or 0),
            str(f.get("id", "")),
        )
    )
    return out


def _join(parts: list[str]) -> str:
    """Join fragments into a single response.

    The joiner is a single space because each
    fragment already ends in a period, so
    two newlines would produce an empty
    blank line in the rendered response. The
    result is a clean 2-4 sentence consultant's
    answer.
    """
    cleaned: list[str] = []
    for p in parts:
        if not p:
            continue
        s = p.strip()
        if not s:
            continue
        if not s.endswith((".", "?", "!")):
            s = s + "."
        cleaned.append(s)
    return " ".join(cleaned)
