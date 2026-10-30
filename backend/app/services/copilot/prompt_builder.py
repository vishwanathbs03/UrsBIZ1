"""CopilotPromptBuilder — turn a
:class:`CopilotContext` into a
:class:`CopilotPrompt` ready for any provider.

The builder is a pure function. It does not call
any LLM. The output is shaped exactly like a
real-provider call (system message + user
message + structured context), so a future
OpenAI / Claude / Gemini / Ollama provider can
swap in without changing the prompt format.

Design choice
-------------

The spec says:

  "design the prompt builder exactly as if OpenAI
   / Claude / Gemini will be plugged in later."

A real provider receives ``prompt.system`` and
``prompt.user`` as the model call's messages
plus ``prompt.context`` for structured grounding.
The mock provider ignores them and produces a
deterministic answer. Either way, the prompt
format is the contract — the future real
provider swap is a one-line change in
:class:`CopilotService`.

Determinism
-----------

The user message is rendered in a stable, sorted
order: intents in declared order, scores in
``(key,)`` order, rules by ``(-impact, id)``,
recommendations by ``id``, knowledge by ``id``.
The mock provider does not depend on the
prompt, so the determinism contract is owned by
the intent detector + the provider template
+ the citation builder.
"""

from __future__ import annotations

from app.services.copilot.base import CopilotContext, CopilotPrompt


# System message — every provider call uses
# the same one. A real provider may tune the
# tone / length / persona, but the *contract*
# (return a JSON-shaped object that fits the
# envelope) is fixed.
_SYSTEM = (
    "You are UrsBiz Copilot, a business "
    "consultant for an Indian SMB. You receive a "
    "structured snapshot of the user's business "
    "and the detected intent of their question. "
    "Your job is to answer the question in plain "
    "language, grounded ONLY in the snapshot — "
    "never invent a rule id, recommendation id, "
    "knowledge article id, score key, or roadmap "
    "id. When the snapshot is thin (e.g. an empty "
    "business profile, no recommendations), say so "
    "honestly. Return a JSON object with the "
    "shape: {response: str, highlights: list[str]}. "
    "The response is a 2-4 sentence consultant's "
    "answer; the highlights are inline tags the "
    "caller can use to find supporting sources."
)


class CopilotPromptBuilder:
    """Build a :class:`CopilotPrompt` from a
    :class:`CopilotContext`.

    The builder is stateless. The same context
    produces the same prompt; the same prompt
    + the same provider produce the same
    response.
    """

    def build(self, context: CopilotContext) -> CopilotPrompt:
        return CopilotPrompt(
            system=_SYSTEM,
            user=_render_user(context),
            context=context,
        )


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #


def _render_user(ctx: CopilotContext) -> str:
    """Render the user message — pure string
    assembly.

    The shape is stable so a real provider
    parses the same input the mock does. The
    sections appear in the same order every
    call: identity, intent, scores, rules,
    recommendations, roadmap, dna, knowledge,
    business.
    """
    lines: list[str] = []
    lines.append("BUSINESS CONTEXT")
    lines.append(f"business_id: {ctx.business_id}")
    lines.append(f"intent: {ctx.intent}")
    lines.append(f"intent_confidence: {ctx.intent_confidence}")
    lines.append(
        f"services_used: {', '.join(ctx.services_used) or '(none)'}"
    )
    lines.append("")

    if ctx.scores is not None:
        lines.append("SCORES")
        for s in sorted(
            (ctx.scores.get("scores") or []),
            key=lambda s: str((s or {}).get("key", "")),
        ):
            if not isinstance(s, dict):
                continue
            lines.append(
                f"- {s.get('key', '?')}: {s.get('score', '?')} "
                f"({s.get('level', '?')}) — {s.get('title', '')}"
            )
        summary = ctx.scores.get("summary") or {}
        if summary:
            lines.append(
                f"summary: score={summary.get('score')} "
                f"level={summary.get('level')}"
            )
        lines.append("")

    if ctx.rules is not None:
        lines.append("RULES (top by impact)")
        flat = _flatten_rules(ctx.rules)
        for r in flat[:12]:
            lines.append(
                f"- {r['id']} [{r['priority']} imp={r['estimated_impact']}] "
                f"({r['category']}) {r['title']} :: {r['reason']}"
            )
        if not flat:
            lines.append("- (none)")
        lines.append("")

    if ctx.recommendations is not None:
        lines.append("RECOMMENDATIONS (top by impact)")
        for r in sorted(
            (ctx.recommendations.get("recommendations") or []),
            key=lambda r: (
                -int((r or {}).get("business_impact", 0) or 0),
                str((r or {}).get("id", "")),
            ),
        )[:12]:
            if not isinstance(r, dict):
                continue
            lines.append(
                f"- {r.get('id', '?')} "
                f"[{r.get('priority', '?')} impact={r.get('business_impact', 0)}] "
                f"({r.get('category', '?')}) {r.get('title', '')}"
            )
        if not ctx.recommendations.get("recommendations"):
            lines.append("- (none)")
        lines.append("")

    if ctx.roadmap is not None:
        lines.append("ROADMAP (top items)")
        for it in sorted(
            (ctx.roadmap.get("items") or []),
            key=lambda it: int((it or {}).get("estimated_start_order", 0) or 0),
        )[:12]:
            if not isinstance(it, dict):
                continue
            lines.append(
                f"- {it.get('recommendation_id', '?')} "
                f"[{it.get('phase', '?')}/{it.get('priority', '?')}] "
                f"{it.get('title', '')}"
            )
        if not ctx.roadmap.get("items"):
            lines.append("- (none)")
        lines.append("")

    if ctx.dna is not None:
        dna_inner = ctx.dna.get("dna") or {}
        archetype = dna_inner.get("archetype") or {}
        lines.append("DNA")
        lines.append(
            f"- archetype: {archetype.get('key', '?')} "
            f"({archetype.get('title', '?')}, "
            f"match={archetype.get('match_score', 0)})"
        )
        for tr in (dna_inner.get("secondary_traits") or [])[:5]:
            if not isinstance(tr, dict):
                continue
            lines.append(
                f"- trait: {tr.get('key', '?')} "
                f"present={tr.get('present', False)} "
                f"strength={tr.get('strength', 0)}"
            )
        lines.append("")

    if ctx.knowledge is not None:
        lines.append("KNOWLEDGE (top articles)")
        for a in sorted(
            (ctx.knowledge.get("articles") or []),
            key=lambda a: str((a or {}).get("id", "")),
        )[:8]:
            if not isinstance(a, dict):
                continue
            lines.append(
                f"- {a.get('id', '?')} "
                f"[{a.get('topic', '?')}/{a.get('category', '?')}] "
                f"{a.get('title', '')}"
            )
        if not ctx.knowledge.get("articles"):
            lines.append("- (none)")
        lines.append("")

    if ctx.business is not None:
        lines.append("BUSINESS (summary)")
        meta = (ctx.business or {}).get("meta") or {}
        lines.append(
            f"- profile_completion: {meta.get('profile_completion', '?')}"
        )
        lines.append(
            f"- completeness_level: {meta.get('completeness_level', '?')}"
        )
        lines.append("")

    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _flatten_rules(rules_payload: dict) -> list[dict]:
    """Flatten the rules payload's
    ``categories`` map into a single list of
    firings, sorted by ``(-impact, id)``.
    """
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
