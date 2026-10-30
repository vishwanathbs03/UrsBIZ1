"""AssistantContextBuilder — Sprint 7 Part 2.

Pure projection from the five upstream service payloads (Twin,
Recommendations, Roadmap, Rules, Insights) into the narrow
:class:`AssistantContext` dataclass the provider is allowed to
see.

The builder is a **delegator**, not a re-deriver. It reads the
upstream payloads' *output shapes* once and projects the fields
the prompt actually needs. It never:

  * re-computes a business score
  * re-derives a recommendation priority
  * re-sorts roadmap items by estimated_start_order
  * re-classifies a rule firing's priority

The Sprint 7 Part 1 frontend builder in
``frontend/features/assistant/builder.ts`` is the source of
truth for the deterministic path. This builder exists because
the backend layer needs to feed a real LLM the same shape
locally when one is configured (Ollama). When no real LLM is
configured, the deterministic fallback in ``base.py`` produces
a similar body from the same context.

The builder is stateless. Two calls with the same
``owner_id`` and same database state produce identical
:class:`AssistantContext` instances (sans the response envelope's
``generated_at``).
"""
from dataclasses import replace
from typing import Any

from app.services.ai.providers.base import (
    AnalyticsMetric,
    AssistantContext,
    AssistantContextActionItem,
    AssistantContextDna,
    AssistantContextForecast,
    AssistantContextInsight,
    AssistantContextRecommendation,
    AssistantContextRoadmap,
    AssistantContextRule,
    AssistantContextScheme,
    AssistantContextScore,
    BusinessContextManifest,
    ReportSummary,
)
from app.services.ai.providers.intent_router import QuestionIntent, classify_intent


# Cap on how many records the LLM sees per source. Long
# contexts degrade response quality and burn tokens. The
# numbers are conservative; a future RAG layer can tune
# them.
_MAX_SCORES = 11
_MAX_RECOMMENDATIONS = 12
_MAX_ROADMAP = 12
_MAX_RULES = 12
_MAX_INSIGHTS = 8
# H7.3 — docx P3 Part 2 evidence-bundle extension caps.
_MAX_SCHEMES = 8
_MAX_FORECASTS = 4
_MAX_ACTION_ITEMS = 6
_MAX_ANALYTICS = 10
_MAX_REPORTS = 5

# AI-1 — context-priority mapping: which categories each
# flagship intent boosts. The first element wins ties. The
# context builder uses this to order the prompt's category
# sections, ensuring the most pertinent slice is surfaced first.
_INTENT_CATEGORY_PRIORITY: dict[QuestionIntent, tuple[str, ...]] = {
    QuestionIntent.REACH_REVENUE_TARGET: (
        "business_profile", "recommendations", "roadmap",
        "forecasts", "rules", "readiness_scores",
    ),
    QuestionIntent.BIGGEST_WEAKNESS: (
        "rules", "insights", "readiness_scores",
        "recommendations", "business_profile",
    ),
    QuestionIntent.GOVERNMENT_SCHEMES: (
        "scheme_matches", "business_profile",
    ),
    QuestionIntent.TWELVE_MONTH_ROADMAP: (
        "roadmap", "recommendations", "analytics",
    ),
    QuestionIntent.EXPORT_EXPANSION: (
        "business_profile", "export_history", "certifications",
        "recommendations", "rules",
    ),
    QuestionIntent.GENERAL: (
        "business_profile", "recommendations",
        "readiness_scores", "rules",
    ),
}


class AssistantContextBuilder:
    """Build an :class:`AssistantContext` from the upstream payloads."""

    def __init__(
        self,
        *,
        twin_provider,
        recommendations_provider,
        roadmap_provider,
        rules_provider,
        insights_provider,
        schemes_provider=None,
        forecast_provider=None,
        action_board_provider=None,
        profile_provider=None,
        analytics_provider=None,
        reports_provider=None,
    ) -> None:
        self._twin = twin_provider
        self._recs = recommendations_provider
        self._roadmap = roadmap_provider
        self._rules = rules_provider
        self._insights = insights_provider
        self._schemes = schemes_provider or (lambda _owner: {})
        self._forecast = forecast_provider or (lambda _owner: {})
        self._action_board = action_board_provider or (lambda _owner: {})
        self._profile = profile_provider or (lambda _owner: {})
        self._analytics = analytics_provider or (lambda _owner: {})
        self._reports = reports_provider or (lambda _owner: {})

    def build(self, *, owner_id: int, user_prompt: str = "") -> AssistantContext:
        twin = self._twin(owner_id)
        recs = self._recs(owner_id)
        roadmap = self._roadmap(owner_id)
        rules = self._rules(owner_id)
        decision = self._insights(owner_id)
        schemes = self._schemes(owner_id)
        forecast = self._forecast(owner_id)
        action_board = self._action_board(owner_id)
        profile = self._profile(owner_id)
        analytics = self._analytics(owner_id)
        reports = self._reports(owner_id)

        p_details = _project_profile_details(profile, twin)
        analytics_metrics = _project_analytics(analytics)
        report_summaries = _project_reports(reports)

        ctx = AssistantContext(
            business_id=int(owner_id),
            overall_business_score=_overall_score(twin),
            band=_band(_overall_score(twin)),
            dna=_project_dna(twin),
            scores=_project_scores(twin),
            recommendations=_project_recommendations(recs),
            roadmap=_project_roadmap(roadmap),
            rules=_project_rules(rules),
            insights=_project_insights(decision),
            schemes=_project_schemes(schemes),
            forecasts=_project_forecasts(forecast),
            action_items=_project_action_items(action_board),
            annual_revenue_inr=_annual_revenue_inr(profile),
            legal_name=p_details.get("legal_name", "unknown"),
            trade_name=p_details.get("trade_name", "unknown"),
            industry=p_details.get("industry", "unknown"),
            sub_industry=p_details.get("sub_industry", "unknown"),
            business_type=p_details.get("business_type", "unknown"),
            location=p_details.get("location", "unknown"),
            employee_count=p_details.get("employee_count", "unknown"),
            target_revenue_inr=p_details.get("target_revenue_inr", 0),
            products=tuple(p_details.get("products", [])),
            services=tuple(p_details.get("services", [])),
            certifications=tuple(p_details.get("certifications", [])),
            digital_presence=tuple(p_details.get("digital_presence", [])),
            export_history=tuple(p_details.get("export_history", [])),
            goals=tuple(p_details.get("goals", [])),
            challenges=tuple(p_details.get("challenges", [])),
            supplier_dependencies=tuple(p_details.get("supplier_dependencies", [])),
            customer_dependencies=tuple(p_details.get("customer_dependencies", [])),
            analytics_metrics=analytics_metrics,
            report_summaries=report_summaries,
            twin_generated_at=twin.get("generated_at") if isinstance(twin, dict) else None,
            recommendations_generated_at=recs.get("generated_at") if isinstance(recs, dict) else None,
            roadmap_generated_at=roadmap.get("generated_at") if isinstance(roadmap, dict) else None,
            rules_generated_at=rules.get("generated_at") if isinstance(rules, dict) else None,
            insights_generated_at=(decision.get("generated_at")
                                   if isinstance(decision, dict) else None),
            schemes_generated_at=schemes.get("generated_at") if isinstance(schemes, dict) else None,
            forecasts_generated_at=forecast.get("generated_at") if isinstance(forecast, dict) else None,
            action_items_generated_at=(action_board.get("generated_at")
                                       if isinstance(action_board, dict) else None),
        )

        return select_relevant_context(ctx, user_prompt)


# --------------------------------------------------------------------------- #
# Field projectors — defensive against upstream shape drift
# --------------------------------------------------------------------------- #


def _overall_score(twin: Any) -> int:
    if not isinstance(twin, dict):
        return 0
    ch = twin.get("current_health") or {}
    if isinstance(ch, dict) and "overall_business_score" in ch:
        try:
            return max(0, min(100, int(ch.get("overall_business_score") or 0)))
        except (TypeError, ValueError):
            pass
    # Twin also exposes an overall_twin_health (0..100) and
    # health_summary.overall_health.score. Try them in order.
    overall_health = twin.get("overall_twin_health")
    if isinstance(overall_health, (int, float)):
        return max(0, min(100, int(overall_health)))
    health = twin.get("health_summary") or {}
    if isinstance(health, dict):
        ov = health.get("overall_health")
        if isinstance(ov, dict) and "score" in ov:
            try:
                return max(0, min(100, int(ov.get("score") or 0)))
            except (TypeError, ValueError):
                return 0
    return 0


def _band(score: int) -> str:
    if score >= 75:
        return "Leading"
    if score >= 50:
        return "Established"
    if score >= 25:
        return "Developing"
    return "Foundation"


def _project_dna(twin: Any) -> AssistantContextDna:
    if not isinstance(twin, dict):
        return AssistantContextDna(
            archetype_key="foundation_builder",
            archetype_title="Foundation Builder",
            match_score=0,
        )
    dna_block = twin.get("dna") or {}
    inner = dna_block.get("dna") if isinstance(dna_block, dict) else None
    if not isinstance(inner, dict):
        inner = dna_block if isinstance(dna_block, dict) else {}
    archetype = inner.get("archetype") or {}
    if not isinstance(archetype, dict):
        archetype = {}
    key = str(archetype.get("key", "foundation_builder") or "foundation_builder")
    title = str(
        archetype.get("title")
        or inner.get("archetype_title")
        or "Foundation Builder"
    )
    match_score = _safe_int(
        archetype.get("match_score"),
        inner.get("archetype_match_score"),
    )
    return AssistantContextDna(
        archetype_key=key,
        archetype_title=title,
        match_score=match_score,
    )


def _project_scores(twin: Any) -> tuple[AssistantContextScore, ...]:
    if not isinstance(twin, dict):
        return ()
    health = twin.get("health_summary") or {}
    items = health.get("scores") if isinstance(health, dict) else None
    if not isinstance(items, list):
        # Twin exposes readiness scores under several keys —
        # try the most common one. We never re-derive scores.
        items = twin.get("readiness_scores") or twin.get("scores_block", {}).get("scores") or []
    if not isinstance(items, list):
        return ()
    out: list[AssistantContextScore] = []
    for s in items[:_MAX_SCORES]:
        if not isinstance(s, dict):
            continue
        out.append(AssistantContextScore(
            key=str(s.get("key", "") or ""),
            title=str(s.get("title", s.get("key", "")) or ""),
            score=_safe_int(s.get("score")),
            level=str(s.get("level", "Low") or "Low"),
        ))
    return tuple(out)


def _project_recommendations(recs: Any) -> tuple[AssistantContextRecommendation, ...]:
    if isinstance(recs, list):
        items = recs
    elif isinstance(recs, dict):
        items = recs.get("recommendations") or []
    else:
        return ()
    if not isinstance(items, list):
        return ()
    out: list[AssistantContextRecommendation] = []
    for r in items[:_MAX_RECOMMENDATIONS]:
        if not isinstance(r, dict):
            continue
        out.append(AssistantContextRecommendation(
            id=str(r.get("id", "") or ""),
            title=str(r.get("title", "") or ""),
            category=str(r.get("category", "") or ""),
            priority=str(r.get("priority", "Medium") or "Medium"),
            estimated_score_gain=_safe_int(r.get("estimated_score_gain")),
            estimated_roi=_safe_float(r.get("estimated_roi")),
            estimated_timeline=str(r.get("estimated_timeline", "") or ""),
        ))
    return tuple(out)


def _project_roadmap(roadmap: Any) -> tuple[AssistantContextRoadmap, ...]:
    if isinstance(roadmap, list):
        items = roadmap
    elif isinstance(roadmap, dict):
        items = roadmap.get("items") or []
    else:
        return ()
    if not isinstance(items, list):
        return ()
    out: list[AssistantContextRoadmap] = []
    for it in items[:_MAX_ROADMAP]:
        if not isinstance(it, dict):
            continue
        out.append(AssistantContextRoadmap(
            id=str(it.get("id", "") or ""),
            title=str(it.get("title", "") or ""),
            phase=str(it.get("phase", "Short-Term") or "Short-Term"),
            priority=str(it.get("priority", "Medium") or "Medium"),
            estimated_start_order=_safe_int(it.get("estimated_start_order")),
            completion_percentage=_safe_int(it.get("completion_percentage")),
            expected_score_improvement=_safe_int(it.get("expected_score_improvement")),
        ))
    return tuple(out)


def _project_rules(rules: Any) -> tuple[AssistantContextRule, ...]:
    if not isinstance(rules, dict):
        return ()
    categories = rules.get("categories") or {}
    if not isinstance(categories, dict):
        return ()
    out: list[AssistantContextRule] = []
    # Iterate categories in the dict's insertion order — the
    # Rules engine emits them in spec order, which is the
    # order the brief expects.
    for cat, block in categories.items():
        if not isinstance(block, dict):
            continue
        firings = block.get("firings") or []
        if not isinstance(firings, list):
            continue
        for f in firings:
            if not isinstance(f, dict):
                continue
            out.append(AssistantContextRule(
                id=str(f.get("id", "") or ""),
                title=str(f.get("title", "") or ""),
                category=str(cat or ""),
                priority=str(f.get("priority", "Low") or "Low"),
                estimated_impact=_safe_int(f.get("estimated_impact")),
                reason=str(f.get("reason", "") or ""),
            ))
            if len(out) >= _MAX_RULES:
                return tuple(out)
    return tuple(out)


def _project_insights(decision: Any) -> tuple[AssistantContextInsight, ...]:
    if not isinstance(decision, dict):
        return ()
    dec = decision.get("decision") or {}
    if not isinstance(dec, dict):
        return ()
    items = dec.get("insights") or []
    if not isinstance(items, list):
        return ()
    out: list[AssistantContextInsight] = []
    for ins in items[:_MAX_INSIGHTS]:
        if not isinstance(ins, dict):
            continue
        out.append(AssistantContextInsight(
            id=str(ins.get("id", "") or ""),
            title=str(ins.get("title", "") or ""),
            priority=str(ins.get("priority", "Medium") or "Medium"),
            confidence=_safe_int(ins.get("confidence")),
        ))
    return tuple(out)


# --------------------------------------------------------------------------- #
# H7.3 — evidence-bundle extension projectors (schemes, forecast, action_board)
# --------------------------------------------------------------------------- #
#
# These follow the existing pattern: defensive projection against
# upstream shape drift, no re-derivation. Each upstream service may
# surface its data under several keys; we try the most likely ones.


def _project_schemes(payload: Any) -> tuple[AssistantContextScheme, ...]:
    """Project the scheme catalog payload into LLM-visible records.

    Accepts payloads shaped like the BusinessSchemesResponse from
    ``SchemeRecommendationEngine.compute`` (a dict with a
    ``schemes`` list). Tolerates alternative keys like
    ``recommended`` / ``catalog``. Always returns the trust
    fields the model needs to cite a scheme; never the
    eligibility verdict.
    """
    if not isinstance(payload, dict):
        return ()
    items = (
        payload.get("schemes")
        or payload.get("recommended")
        or payload.get("catalog")
        or []
    )
    if not isinstance(items, list):
        return ()
    out: list[AssistantContextScheme] = []
    for raw in items[:_MAX_SCHEMES]:
        if not isinstance(raw, dict):
            continue
        scheme_id = str(raw.get("scheme_id") or raw.get("id") or "").strip()
        if not scheme_id:
            continue
        out.append(AssistantContextScheme(
            scheme_id=scheme_id,
            title=str(raw.get("title") or raw.get("scheme_name") or scheme_id),
            authority=str(raw.get("authority") or raw.get("ministry") or ""),
            application_url=str(raw.get("application_url") or raw.get("official_link") or ""),
            profile_match_score=_safe_int(raw.get("profile_match_score") or raw.get("match_score")),
            last_verified_date=str(
                raw.get("last_verified_date")
                or raw.get("last_verified")
                or raw.get("verified_at")
                or ""
            ),
        ))
    return tuple(out)


def _project_forecasts(payload: Any) -> tuple[AssistantContextForecast, ...]:
    """Project the scenario / forecast payload into LLM-visible records.

    Accepts payloads shaped like ``ScenarioService.simulate`` (a dict
    with a ``scenarios`` list) or ``RevenuePredictionResponse`` (a
    dict with a ``forecast`` block). Always surfaces the data as a
    *scenario estimate* — never as a prediction.
    """
    if not isinstance(payload, dict):
        return ()
    items = (
        payload.get("scenarios")
        or payload.get("forecast")
        or payload.get("projections")
        or []
    )
    if not isinstance(items, list):
        # Some payloads wrap a single object in 'forecast' or 'primary'.
        single = payload.get("forecast") or payload.get("primary")
        if isinstance(single, dict):
            items = [single]
        else:
            return ()
    out: list[AssistantContextForecast] = []
    for raw in items[:_MAX_FORECASTS]:
        if not isinstance(raw, dict):
            continue
        sid = str(raw.get("scenario_id") or raw.get("id") or "primary").strip()
        out.append(AssistantContextForecast(
            scenario_id=sid,
            horizon_label=str(raw.get("horizon_label") or raw.get("horizon") or "scenario"),
            revenue_delta=_safe_float(raw.get("revenue_delta") or raw.get("revenue_change")),
            score_delta=_safe_int(raw.get("score_delta") or raw.get("score_change")),
            assumption_summary=str(raw.get("assumption_summary") or raw.get("assumptions") or ""),
            confidence=_safe_int(raw.get("confidence")),
        ))
    return tuple(out)


def _project_action_items(payload: Any) -> tuple[AssistantContextActionItem, ...]:
    """Project the action-board payload into LLM-visible records."""
    if not isinstance(payload, dict):
        return ()
    items = (
        payload.get("items")
        or payload.get("action_items")
        or payload.get("actions")
        or []
    )
    if not isinstance(items, list):
        return ()
    out: list[AssistantContextActionItem] = []
    for raw in items[:_MAX_ACTION_ITEMS]:
        if not isinstance(raw, dict):
            continue
        aid = str(raw.get("id") or raw.get("action_id") or "").strip()
        if not aid:
            continue
        out.append(AssistantContextActionItem(
            action_id=aid,
            title=str(raw.get("title") or ""),
            status=str(raw.get("status") or "open"),
            priority=str(raw.get("priority") or "Medium"),
            due_in_days=_safe_int(raw.get("due_in_days")),
        ))
    return tuple(out)


def _safe_int(*candidates: Any) -> int:
    for v in candidates:
        if v is None:
            continue
        try:
            return int(v)
        except (TypeError, ValueError):
            continue
    return 0


def _safe_float(*candidates: Any) -> float:
    for v in candidates:
        if v is None:
            continue
        try:
            return float(v)
        except (TypeError, ValueError):
            continue
    return 0.0


# Approximate USD→INR rate. The exact rate is irrelevant
# for the grounding registry — we only need to anchor the
# magnitude. Using a stable constant keeps the registry
# deterministic across requests.
_USD_TO_INR = 83.0


def _annual_revenue_inr(profile: Any) -> int:
    """Convert the ``profile_provider`` payload to INR int.

    Accepts dicts with ``annual_revenue`` (float) and an
    optional ``revenue_currency`` (str, ISO 4217). USD
    figures are converted at ``_USD_TO_INR``; other
    currencies pass through unchanged (the registry value
    is shown verbatim). Returns 0 when the payload is
    empty / missing — the registry then skips the entry
    and the ``no_invented_numbers`` rule will flag
    user-prompted revenue figures. Tests should pass a
    non-empty profile payload to exercise the path.
    """
    if not isinstance(profile, dict):
        return 0
    raw = profile.get("annual_revenue")
    if raw is None:
        return 0
    try:
        amount = float(raw)
    except (TypeError, ValueError):
        return 0
    if amount <= 0:
        return 0
    currency = str(profile.get("revenue_currency", "USD") or "USD").upper()
    if currency == "USD":
        return int(round(amount * _USD_TO_INR))
    if currency == "INR":
        return int(round(amount))
    # Unrecognised currency — assume already in INR; this is
    # the conservative default that keeps the registry value
    # close to the user's stated figure.
    return int(round(amount))


def _project_profile_details(profile: Any, twin: Any) -> dict[str, Any]:
    out: dict[str, Any] = {
        "legal_name": "unknown",
        "trade_name": "unknown",
        "industry": "unknown",
        "sub_industry": "unknown",
        "business_type": "unknown",
        "location": "unknown",
        "employee_count": "unknown",
        "target_revenue_inr": 0,
        "products": [],
        "services": [],
        "certifications": [],
        "digital_presence": [],
        "export_history": [],
        "goals": [],
        "challenges": [],
        "supplier_dependencies": [],
        "customer_dependencies": [],
    }
    if isinstance(twin, dict):
        identity = twin.get("identity") or {}
        if isinstance(identity, dict):
            if identity.get("legal_name"):
                out["legal_name"] = str(identity["legal_name"])
            if identity.get("trade_name"):
                out["trade_name"] = str(identity["trade_name"])
            if identity.get("industry"):
                out["industry"] = str(identity["industry"])
            if identity.get("sub_industry"):
                out["sub_industry"] = str(identity["sub_industry"])

    if not isinstance(profile, dict):
        return out

    if profile.get("legal_name"):
        out["legal_name"] = str(profile["legal_name"])
    if profile.get("trade_name"):
        out["trade_name"] = str(profile["trade_name"])
    if profile.get("industry"):
        out["industry"] = str(profile["industry"])
    if profile.get("sub_industry"):
        out["sub_industry"] = str(profile["sub_industry"])
    if profile.get("business_type"):
        out["business_type"] = str(profile["business_type"])

    city = profile.get("city") or ""
    state = profile.get("state_region") or ""
    country = profile.get("country") or ""
    loc_parts = [p for p in [city, state, country] if p]
    if loc_parts:
        out["location"] = ", ".join(loc_parts)

    emp = profile.get("employee_count")
    if emp is not None:
        out["employee_count"] = str(emp)

    tr = profile.get("target_revenue")
    if tr is not None:
        out["target_revenue_inr"] = _safe_int(tr)

    for key in [
        "products",
        "services",
        "certifications",
        "digital_presence",
        "export_history",
        "goals",
        "challenges",
        "supplier_dependencies",
        "customer_dependencies",
    ]:
        raw_items = profile.get(key)
        if isinstance(raw_items, list):
            item_strings = []
            for item in raw_items:
                if isinstance(item, str):
                    item_strings.append(item)
                elif isinstance(item, dict):
                    name = item.get("name") or item.get("title") or item.get("description") or str(item)
                    item_strings.append(name)
            out[key] = item_strings

    return out


def _project_analytics(analytics: Any) -> tuple[AnalyticsMetric, ...]:
    if not isinstance(analytics, dict):
        return ()
    items = analytics.get("metrics") or analytics.get("kpis") or analytics.get("items") or []
    if not isinstance(items, list):
        if isinstance(analytics, dict) and "growth_score" in analytics:
            items = [
                {"id": "growth_score", "name": "Growth Score", "value": analytics.get("growth_score")},
                {"id": "digital_readiness", "name": "Digital Readiness", "value": analytics.get("digital_readiness")},
                {"id": "operational_maturity", "name": "Operational Maturity", "value": analytics.get("operational_maturity")},
                {"id": "market_presence", "name": "Market Presence", "value": analytics.get("market_presence")},
                {"id": "customer_reach", "name": "Customer Reach", "value": analytics.get("customer_reach")},
            ]
        else:
            return ()
    out: list[AnalyticsMetric] = []
    for raw in items[:_MAX_ANALYTICS]:
        if not isinstance(raw, dict):
            continue
        mid = str(raw.get("id") or raw.get("metric_id") or raw.get("name") or "")
        if not mid:
            continue
        out.append(AnalyticsMetric(
            metric_id=mid,
            metric_name=str(raw.get("name") or raw.get("title") or mid),
            current_value=raw.get("value") or raw.get("current_value") or 0,
            unit=str(raw.get("unit") or ""),
            time_period=str(raw.get("time_period") or raw.get("period") or "current"),
            trend=str(raw.get("trend") or "stable"),
            baseline=str(raw.get("baseline") or ""),
            method=str(raw.get("method") or "calculated"),
            updated_at=str(raw.get("updated_at") or ""),
        ))
    return tuple(out)


def _project_reports(reports: Any) -> tuple[ReportSummary, ...]:
    if not isinstance(reports, dict):
        return ()
    items = reports.get("reports") or reports.get("summaries") or []
    if not isinstance(items, list):
        rep = reports.get("report")
        if isinstance(rep, dict):
            items = [rep]
        else:
            return ()
    out: list[ReportSummary] = []
    for raw in items[:_MAX_REPORTS]:
        if not isinstance(raw, dict):
            continue
        exec_sum = ""
        if isinstance(raw.get("executive_summary"), dict):
            exec_sum = str(raw["executive_summary"].get("summary_text") or raw["executive_summary"].get("headline") or "")
        elif isinstance(raw.get("executive_summary"), str):
            exec_sum = raw["executive_summary"]

        rid = str(raw.get("report_id") or raw.get("id") or "report_1")
        out.append(ReportSummary(
            report_id=rid,
            report_type=str(raw.get("report_type") or raw.get("type") or "unified_business_report"),
            generated_at=str(raw.get("generated_at") or ""),
            executive_summary=exec_sum,
            key_metrics=tuple(raw.get("key_metrics") or ()),
            risks=tuple(raw.get("risks") or ()),
            recommendations=tuple(raw.get("recommendations") or ()),
            assumptions=tuple(raw.get("assumptions") or ()),
        ))
    return tuple(out)


def select_relevant_context(
    context: AssistantContext,
    user_prompt: str = "",
) -> AssistantContext:
    """Build a relevant, bounded context bundle and attach BusinessContextManifest."""
    categories: list[str] = []
    records = 0

    if context.legal_name != "unknown" or context.annual_revenue_inr > 0 or context.industry != "unknown":
        categories.append("business_profile")
        records += 1

    if context.products:
        categories.append("products")
        records += len(context.products)

    if context.services:
        categories.append("services")
        records += len(context.services)

    if context.certifications:
        categories.append("certifications")
        records += len(context.certifications)

    if context.export_history:
        categories.append("export_history")
        records += len(context.export_history)

    if context.scores:
        categories.append("readiness_scores")
        records += len(context.scores)

    if context.recommendations:
        categories.append("recommendations")
        records += len(context.recommendations)

    if context.roadmap:
        categories.append("roadmap")
        records += len(context.roadmap)

    if context.rules:
        categories.append("rules")
        records += len(context.rules)

    if context.insights:
        categories.append("insights")
        records += len(context.insights)

    if context.schemes:
        categories.append("scheme_matches")
        records += len(context.schemes)

    if context.forecasts:
        categories.append("forecasts")
        records += len(context.forecasts)

    if context.action_items:
        categories.append("action_board")
        records += len(context.action_items)

    if context.analytics_metrics:
        categories.append("analytics")
        records += len(context.analytics_metrics)

    if context.report_summaries:
        categories.append("report_summary")
        records += len(context.report_summaries)

    from app.services.ai.knowledge.knowledge_graph import BusinessKnowledgeGraph
    from app.services.ai.knowledge.relationship_engine import RelationshipEngine
    from app.services.ai.knowledge.priority_engine import PriorityEngine

    kg = BusinessKnowledgeGraph.from_context(context)
    rel_engine = RelationshipEngine()
    rel_engine.infer_and_link_relationships(kg)
    p_engine = PriorityEngine()
    p_engine.score_nodes(kg)

    manifest = BusinessContextManifest(
        business_context_used=tuple(categories),
        records_used=records,
        prompt_truncated=False,
        # AI-1 — audit trail for context selection. The
        # pre-truncation snapshot is the same as the post-
        # truncation snapshot today (no truncation in the
        # builder) but the fields exist for future RAG
        # tuning and for the explainability dashboard.
        categories_available=tuple(categories),
        categories_used=tuple(categories),
        records_available=records,
        evidence_ids_used=tuple(_collect_kg_evidence_ids(kg)),
        context_priority=_compute_context_priority(tuple(categories), user_prompt),
        context_selection_reason=_compute_selection_reason(
            tuple(categories), user_prompt
        ),
    )

    return replace(context, context_manifest=manifest, knowledge_graph=kg)


def _collect_kg_evidence_ids(kg: Any) -> tuple[str, ...]:
    """Return the deduplicated set of ``evidence_id``s from the knowledge graph.

    Falls back gracefully when the KG is malformed — never
    raises.
    """
    if kg is None:
        return ()
    nodes = getattr(kg, "nodes", None) or []
    seen: set[str] = set()
    out: list[str] = []
    for node in nodes:
        eid = getattr(node, "evidence_id", None) if not isinstance(node, dict) else node.get("evidence_id")
        if not eid:
            continue
        if eid in seen:
            continue
        seen.add(eid)
        out.append(eid)
    return tuple(out)


def _compute_context_priority(
    categories: tuple[str, ...], user_prompt: str
) -> tuple[str, ...]:
    """Order categories by relevance to the user prompt.

    The intent classifier picks a priority template; the
    builder then orders the available categories accordingly.
    Categories not present in the template are appended at
    the end in their original order, so the result is always
    a permutation of the input.
    """
    if not categories:
        return ()
    intent = classify_intent(user_prompt or "")
    template = _INTENT_CATEGORY_PRIORITY.get(
        intent, _INTENT_CATEGORY_PRIORITY[QuestionIntent.GENERAL]
    )
    available_set = set(categories)
    ordered: list[str] = []
    seen: set[str] = set()
    for cat in template:
        if cat in available_set and cat not in seen:
            ordered.append(cat)
            seen.add(cat)
    for cat in categories:
        if cat not in seen:
            ordered.append(cat)
            seen.add(cat)
    return tuple(ordered)


def _compute_selection_reason(
    categories: tuple[str, ...], user_prompt: str
) -> str:
    """One-line explanation of why these categories were selected.

    The reason is informational — surfaced on the audit trail
    so reviewers can answer "why was this slice included /
    excluded?". The format is stable so it can be matched in
    tests:

      * "intent=<intent>; categories=<n>"
    """
    intent = classify_intent(user_prompt or "")
    return (
        f"intent={intent.value}; categories={len(categories)}"
    )