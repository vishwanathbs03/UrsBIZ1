"""Snapshot builder — shape the upstream payloads
into the spec'd Twin snapshot blocks.

The snapshot builder is the *only* place that
knows the upstream payload shape. It consumes
plain dicts and emits plain dicts that match the
Pydantic schema in :mod:`app.schemas.twin`. The
service façade hands the output to the schema's
``model_validate`` for the API boundary.

Architecture
------------

The builders are deliberately simple: each
function reads a few fields off the upstream
payload and returns a dict that maps 1:1 to the
schema model. No business logic, no derived
metrics — those live in the timeline / risk /
opportunity / health modules.
"""

from __future__ import annotations

from typing import Any

from app.services.twin.base import TwinBundle


# --------------------------------------------------------------------------- #
# Identity + profile
# --------------------------------------------------------------------------- #


def build_identity(business: dict) -> dict[str, Any]:
    """Pull the legal + trade identity off the
    BusinessService payload."""
    business_data = (
        business.get("business")
        if isinstance(business.get("business"), dict)
        else business
    )
    basic = (
        business_data.get("basic")
        if isinstance(business_data.get("basic"), dict)
        else business_data
    )
    return {
        "business_id": int(business_data.get("id", 0) or business.get("id", 0) or 0),
        "owner_id": int(business_data.get("owner_id", 0) or business.get("owner_id", 0) or 0),
        "legal_name": str(basic.get("legal_name", "") or ""),
        "trade_name": basic.get("trade_name"),
        "industry": str(basic.get("industry", "") or ""),
        "sub_industry": basic.get("sub_industry"),
        "business_type": basic.get("business_type"),
        "established_year": int(basic.get("established_year", 0) or 0),
        "employee_count": int(basic.get("employee_count", 0) or 0),
        "annual_revenue": float(basic.get("annual_revenue", 0) or 0),
        "revenue_currency": str(basic.get("revenue_currency", "USD") or "USD"),
        "country": basic.get("country"),
        "state_region": basic.get("state_region"),
        "city": basic.get("city"),
        "is_completed": bool(
            business.get("completeness", {}).get("completed")
            if isinstance(business.get("completeness"), dict)
            else (business_data.get("is_completed", False) or business.get("is_completed", False))
        ),
    }


def build_profile(business: dict) -> dict[str, Any]:
    """Roll the nested collections up into counts +
    flags. The BusinessService payload already has
    a ``profile`` block; the twin profile is a
    flatter view that the UI can render as a
    single card."""
    business_data = (
        business.get("business")
        if isinstance(business.get("business"), dict)
        else business
    )
    capacity = (
        business_data.get("capacity")
        if isinstance(business_data.get("capacity"), dict)
        else business_data
    )
    products = business_data.get("products") or []
    certs = business_data.get("certifications") or []
    digital = business_data.get("digital_presence") or {}
    exports = business_data.get("export_history") or []
    goals = business_data.get("goals") or []
    challenges = business_data.get("challenges") or []

    social_channels = sum(
        1
        for field in (
            "linkedin_url",
            "facebook_url",
            "instagram_url",
            "twitter_url",
            "youtube_url",
        )
        if (digital.get(field) or "").strip()
    )

    has_active = any(_is_active_cert(c) for c in certs)
    has_iec = any((e.get("iec_number") or "").strip() for e in exports)

    return {
        "capacity_utilization_pct": capacity.get("capacity_utilization_pct"),
        "monthly_production_units": capacity.get("monthly_production_units"),
        "products_count": len(products),
        "certifications_count": len(certs),
        "has_active_certification": has_active,
        "has_website": bool((digital.get("website_url") or "").strip()),
        "has_ecommerce": bool(digital.get("has_ecommerce", False)),
        "uses_digital_marketing": bool(digital.get("uses_digital_marketing", False)),
        "uses_cloud_systems": bool(digital.get("uses_cloud_systems", False)),
        "social_channel_count": social_channels,
        "has_iec_number": has_iec,
        "export_countries": len(exports),
        "goals_count": len(goals),
        "challenges_count": len(challenges),
    }


def _is_active_cert(cert: dict) -> bool:
    """A certification is active if it has an
    issued_date and no expiry_date in the past.
    The Twin service treats the absence of an
    expiry as "expires in the future" — the
    upstream wizard does not always require an
    expiry."""
    from datetime import date

    issued = cert.get("issued_date")
    expiry = cert.get("expiry_date")
    if not issued:
        return False
    if expiry:
        try:
            y, m, d = (int(x) for x in str(expiry).split("-")[:3])
            return date(y, m, d) >= date.today()
        except Exception:
            return True
    return True


# --------------------------------------------------------------------------- #
# DNA
# --------------------------------------------------------------------------- #


def build_dna(dna_payload: dict) -> dict[str, Any]:
    inner = dna_payload.get("dna") or dna_payload
    archetype = inner.get("archetype") or {}
    swot = inner.get("swot") or {}

    # The DNA engine emits ``confidence`` as an int
    # and ``confidence_rationale`` as a list. The
    # twin schema combines them into a single
    # ``confidence`` block. We normalise both
    # shapes here so the API contract is the
    # canonical one regardless of what the
    # upstream payload looks like in this
    # release.
    raw_confidence = inner.get("confidence")
    if isinstance(raw_confidence, dict):
        conf_value = int(raw_confidence.get("confidence", 0) or 0)
        conf_rationale = list(raw_confidence.get("rationale", []) or [])
    else:
        conf_value = int(raw_confidence or 0)
        conf_rationale = list(inner.get("confidence_rationale", []) or [])

    return {
        "archetype": {
            "key": str(archetype.get("key", "") or ""),
            "title": str(archetype.get("title", "") or ""),
            "description": str(archetype.get("description", "") or ""),
            "match_score": int(archetype.get("match_score", 0) or 0),
            "runner_up_key": archetype.get("runner_up_key"),
            "runner_up_score": int(archetype.get("runner_up_score", 0) or 0),
        },
        "secondary_traits": [
            {
                "key": t.get("key", ""),
                "title": t.get("title", ""),
                "present": bool(t.get("present", False)),
                "strength": int(t.get("strength", 0) or 0),
                "rationale": _rationale_to_strings(
                    t.get("rationale", []) or []
                ),
            }
            for t in (inner.get("secondary_traits") or [])
        ],
        "swot": {
            "strengths": list(swot.get("strengths", []) or []),
            "weaknesses": list(swot.get("weaknesses", []) or []),
            "opportunities": list(swot.get("opportunities", []) or []),
            "risks": list(swot.get("risks", []) or []),
        },
        "confidence": {
            "confidence": conf_value,
            "rationale": _rationale_to_strings(conf_rationale),
        },
    }


def _rationale_to_strings(items: list) -> list[str]:
    """The DNA engine emits rationale entries as
    dicts with ``{"claim": str, "key": str,
    "value": ...}``. The twin schema accepts
    plain strings. We flatten the dict to its
    claim string; non-dict entries are coerced
    via ``str(...)``."""
    out: list[str] = []
    for it in items:
        if isinstance(it, dict):
            claim = it.get("claim")
            if isinstance(claim, str) and claim:
                out.append(claim)
                continue
            out.append(str(it))
        elif isinstance(it, str):
            out.append(it)
        else:
            out.append(str(it))
    return out


# --------------------------------------------------------------------------- #
# Scores
# --------------------------------------------------------------------------- #


def build_scores(scores_payload: dict) -> dict[str, Any]:
    summary = scores_payload.get("summary") or {}
    return {
        "scores": [
            {
                "key": s.get("key", ""),
                "title": s.get("title", ""),
                "score": int(s.get("score", 0) or 0),
                "level": s.get("level", "Low"),
                "explanation": s.get("explanation", ""),
            }
            for s in (scores_payload.get("scores") or [])
        ],
        "overall_score": int(summary.get("score", 0) or 0),
        "overall_level": str(summary.get("level", "Low") or "Low"),
        "band_distribution": dict(summary.get("band_distribution") or {}),
    }


# --------------------------------------------------------------------------- #
# Intelligence
# --------------------------------------------------------------------------- #


def build_intelligence(intel_payload: dict) -> dict[str, Any]:
    overall = intel_payload.get("overall") or {}
    return {
        "overall_score": int(overall.get("score", 0) or 0),
        "overall_level": str(overall.get("level", "low") or "low"),
        "analyzers": [
            {
                "key": a.get("key", ""),
                "title": a.get("title", ""),
                "score": int(a.get("score", 0) or 0),
                "level": a.get("level", "low"),
                "summary": a.get("summary", ""),
                "missing_count": len(a.get("missing", []) or []),
            }
            for a in (intel_payload.get("analyzers") or [])
        ],
    }


# --------------------------------------------------------------------------- #
# Rules
# --------------------------------------------------------------------------- #


def build_rules(rules_payload: dict) -> dict[str, Any]:
    firings = rules_payload.get("firings") or []
    counts = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
    for f in firings:
        p = f.get("priority")
        if p in counts:
            counts[p] += 1

    # Top risk = highest-priority firing by impact.
    # The rules engine already sorts the firings by
    # (category_order, priority_rank, -impact), so
    # the first entry is the top risk.
    top_id = firings[0].get("id") if firings else None

    return {
        "total_firings": len(firings),
        "critical_count": counts["Critical"],
        "high_count": counts["High"],
        "medium_count": counts["Medium"],
        "low_count": counts["Low"],
        "firings": [
            {
                "id": f.get("id", ""),
                "category": f.get("category", ""),
                "priority": f.get("priority", "Low"),
                "title": f.get("title", ""),
                "description": f.get("description", ""),
                "estimated_impact": int(f.get("estimated_impact", 0) or 0),
            }
            for f in firings
        ],
    }


# Internal echo for the risk_overview block —
# these live on the *return value* the service
# façade consumes, not on the Pydantic rules
# block. We split them out so the API contract
# stays clean of internal helpers.
def _rules_internal_echo(rules_block: dict) -> dict:
    firings = rules_block.get("firings") or []
    counts = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
    for f in firings:
        p = f.get("priority")
        if p in counts:
            counts[p] += 1
    top_id = firings[0].get("id") if firings else None
    return {"_counts": counts, "_top_id": top_id}


# --------------------------------------------------------------------------- #
# Recommendations
# --------------------------------------------------------------------------- #


def build_recommendations(recs_payload: dict) -> dict[str, Any]:
    recs = recs_payload.get("recommendations") or []
    summary = recs_payload.get("summary") or {}
    return {
        "total_recommendations": int(summary.get("total_recommendations", 0) or 0),
        "critical_count": int(summary.get("critical_count", 0) or 0),
        "high_count": int(summary.get("high_count", 0) or 0),
        "medium_count": int(summary.get("medium_count", 0) or 0),
        "low_count": int(summary.get("low_count", 0) or 0),
        "total_estimated_impact": int(
            summary.get("total_estimated_impact", 0) or 0
        ),
        "total_estimated_score_gain": float(
            summary.get("total_estimated_score_gain", 0) or 0
        ),
        "total_estimated_roi": int(summary.get("total_estimated_roi", 0) or 0),
        "recommendations": [
            {
                "id": r.get("id", ""),
                "title": r.get("title", ""),
                "description": r.get("description", ""),
                "category": r.get("category", ""),
                "priority": r.get("priority", "Low"),
                "phase": r.get("phase", "Medium-Term"),
                "business_impact": int(r.get("business_impact", 0) or 0),
                "estimated_score_gain": float(r.get("estimated_score_gain", 0) or 0),
                "estimated_roi": int(r.get("estimated_roi", 0) or 0),
                "estimated_timeline": r.get("estimated_timeline", ""),
                "difficulty": r.get("difficulty", ""),
            }
            for r in recs
        ],
    }


# --------------------------------------------------------------------------- #
# Roadmap
# --------------------------------------------------------------------------- #


def build_roadmap(roadmap_payload: dict) -> dict[str, Any]:
    items = roadmap_payload.get("items") or []
    summary = roadmap_payload.get("summary") or {}
    return {
        "total_items": int(summary.get("total_items", 0) or 0),
        "total_estimated_duration": str(
            summary.get("total_estimated_duration", "") or ""
        ),
        "total_estimated_roi": int(summary.get("total_estimated_roi", 0) or 0),
        "items": [
            {
                "recommendation_id": it.get("recommendation_id", ""),
                "title": it.get("title", ""),
                "phase": it.get("phase", "Medium-Term"),
                "priority": it.get("priority", "Low"),
                "estimated_start_order": int(it.get("estimated_start_order", 0) or 0),
                "estimated_duration": it.get("estimated_duration", ""),
                "expected_score_improvement": float(
                    it.get("expected_score_improvement", 0) or 0
                ),
                "expected_business_impact": int(
                    it.get("expected_business_impact", 0) or 0
                ),
                "estimated_roi": int(it.get("estimated_roi", 0) or 0),
                "completion_percentage": int(
                    it.get("completion_percentage", 0) or 0
                ),
            }
            for it in items
        ],
    }


# --------------------------------------------------------------------------- #
# Current health + readiness sub-blocks
# --------------------------------------------------------------------------- #


def build_current_health(
    bundle: TwinBundle,
    dna_block: dict,
    scores_block: dict,
    rules_block: dict,
    recs_block: dict,
) -> dict[str, Any]:
    archetype = dna_block.get("archetype") or {}
    return {
        "overall_business_score": int(scores_block.get("overall_score", 0) or 0),
        "business_dna_match": int(archetype.get("match_score", 0) or 0),
        "business_dna_archetype": str(archetype.get("title", "") or ""),
        "rule_critical_count": int(rules_block.get("critical_count", 0) or 0),
        "recommendation_count": int(recs_block.get("total_recommendations", 0) or 0),
    }


def build_risk_overview(rules_block: dict) -> dict[str, Any]:
    return {
        "total_risks": int(rules_block.get("total_firings", 0) or 0),
        "critical_count": int(rules_block.get("critical_count", 0) or 0),
        "high_count": int(rules_block.get("high_count", 0) or 0),
        "medium_count": int(rules_block.get("medium_count", 0) or 0),
        "low_count": int(rules_block.get("low_count", 0) or 0),
        "top_risk_id": rules_block.get("_top_id"),
    }


def build_growth_potential(recs_block: dict, roadmap_block: dict) -> dict[str, Any]:
    """Sum the expected score gain + ROI from the
    active recommendations; the average timeline is
    the arithmetic mean of the per-recommendation
    estimated_timeline strings (parsed via the
    timeline module's week parser)."""
    recs = recs_block.get("recommendations") or []
    if not recs:
        return {
            "total_expected_score_gain": 0.0,
            "total_expected_roi": 0,
            "average_estimated_timeline": "~0 weeks",
        }
    total_gain = sum(float(r.get("estimated_score_gain", 0) or 0) for r in recs)
    total_roi = int(
        round(sum(int(r.get("estimated_roi", 0) or 0) for r in recs) / len(recs))
    )

    # Average timeline. The recommendations carry
    # human-readable strings; we average the parsed
    # week count, then render back to the same
    # format. Imported lazily to avoid a top-level
    # cycle (the timeline module imports the
    # snapshot module's recommendation shape).
    from app.services.twin.timeline import (
        average_timeline_string,
    )

    avg_timeline = average_timeline_string(
        [r.get("estimated_timeline", "") for r in recs]
    )

    return {
        "total_expected_score_gain": float(total_gain),
        "total_expected_roi": total_roi,
        "average_estimated_timeline": avg_timeline,
    }


def build_digital_maturity(profile_block: dict) -> dict[str, Any]:
    """A simple 0..100 maturity score derived from
    the profile flags. The mapping is the same
    formula the Business Intelligence / Sprint 4
    Polish work uses, so the front-end number is
    consistent across the dashboard and the
    twin."""
    score = 0
    score += 25 if profile_block.get("has_website") else 0
    social = int(profile_block.get("social_channel_count", 0) or 0)
    score += min(social, 3) * 8  # 8 per channel, capped at 3
    score += 12 if profile_block.get("uses_digital_marketing") else 0
    score += 10 if profile_block.get("uses_cloud_systems") else 0
    score += 17 if profile_block.get("has_ecommerce") else 0
    return {
        "has_website": bool(profile_block.get("has_website", False)),
        "social_channel_count": int(profile_block.get("social_channel_count", 0) or 0),
        "has_ecommerce": bool(profile_block.get("has_ecommerce", False)),
        "uses_digital_marketing": bool(
            profile_block.get("uses_digital_marketing", False)
        ),
        "uses_cloud_systems": bool(profile_block.get("uses_cloud_systems", False)),
        "maturity_score": _clamp(score),
    }


def build_export_readiness(
    profile_block: dict, scores_block: dict
) -> dict[str, Any]:
    export = _lens_score(scores_block, "export")
    return {
        "has_iec_number": bool(profile_block.get("has_iec_number", False)),
        "export_countries": int(profile_block.get("export_countries", 0) or 0),
        "export_score": export,
    }


def build_compliance_readiness(
    profile_block: dict, scores_block: dict
) -> dict[str, Any]:
    compliance = _lens_score(scores_block, "compliance")
    return {
        "certifications_count": int(
            profile_block.get("certifications_count", 0) or 0
        ),
        "has_active_certification": bool(
            profile_block.get("has_active_certification", False)
        ),
        "compliance_score": compliance,
    }


def build_scenario_readiness(recs_block: dict, roadmap_block: dict) -> dict[str, Any]:
    active = int(recs_block.get("total_recommendations", 0) or 0)
    items = int(roadmap_block.get("total_items", 0) or 0)
    # Scenario is "ready" when the business has at
    # least one active recommendation (i.e. there
    # is something to simulate against).
    return {
        "active_recommendations": active,
        "remaining_roadmap_items": items,
        "simulation_ready": active >= 1,
    }


# --------------------------------------------------------------------------- #
# Internal
# --------------------------------------------------------------------------- #


def _lens_score(scores_block: dict, lens_key: str) -> int:
    for s in scores_block.get("scores") or []:
        if s.get("key") == lens_key:
            return int(s.get("score", 0) or 0)
    return 0


def _clamp(n: int, lo: int = 0, hi: int = 100) -> int:
    return max(lo, min(hi, int(n)))
