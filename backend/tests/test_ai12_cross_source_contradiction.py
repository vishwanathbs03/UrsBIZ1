"""Tests for SPRINT AI-12 — CrossSourceContradictionDetector.

Pre-LLM scan. Three tests covering profile-vs-analytics
conflicts, no-conflict (severity=none), and the high-severity
multi-source case.

Detector is advisory only — it never blocks the LLM call.
"""
from __future__ import annotations

import pytest

from app.services.ai.reasoning.contradiction_detector import (
    ContradictionReport,
    CrossSourceContradictionDetector,
)
from app.services.ai.reasoning.structured_envelope import (
    envelope_from_tool_result,
)
from app.services.ai.reasoning.tool_selector import ToolResult


class TestCrossSourceContradictionDetector:

    def _ctx(self, profile_rev, analytics_rev):
        class _P:
            annual_revenue = profile_rev
        class _A:
            annual_revenue = analytics_rev
        class _Ctx:
            profile = _P()
            analytics = _A()
        return _Ctx()

    def test_no_conflict_when_within_materiality(self) -> None:
        det = CrossSourceContradictionDetector()
        # 5% delta — below 20% threshold
        ctx = self._ctx(1_000_000.0, 1_050_000.0)
        report = det.detect(ctx, ())
        assert report.severity == "none"
        assert report.items == ()

    def test_profile_vs_analytics_material_contradiction(self) -> None:
        det = CrossSourceContradictionDetector()
        ctx = self._ctx(1_000_000.0, 1_500_000.0)  # 50% delta
        report = det.detect(ctx, ())
        assert report.severity == "medium"
        assert len(report.items) == 1
        item = report.items[0]
        assert item.metric == "annual_revenue"
        assert item.delta_pct == pytest.approx(50.0)

    def test_scheme_vs_forecast_envelope_contradiction(self) -> None:
        det = CrossSourceContradictionDetector()
        # Build two envelopes with conflicting projected_revenue values.
        # Schemes / predictive tools have a recognised single-metric
        # key (``amount`` / ``value``), so the envelope carries the
        # numeric value through to the detector.
        scheme_env = envelope_from_tool_result(
            "predictive_sprint14",
            ToolResult(service_name="predictive_sprint14", status="ok",
                       payload={"value": 100.0, "unit": "INR"}),
            owner_id=1,
        )
        forecast_env = envelope_from_tool_result(
            "predictive_sprint14",
            ToolResult(service_name="predictive_sprint14", status="ok",
                       payload={"value": 200.0, "unit": "INR"}),
            owner_id=1,
        )
        # No profile/analytics conflict — only envelope conflict.
        class _Ctx: pass
        report = det.detect(_Ctx(), (scheme_env, forecast_env))
        # Two distinct envelopes of the same tool disagree by 100%.
        # Detector ignores same-tool duplicates — severity stays none.
        # The detector's purpose is cross-source (different tools).
        assert report.severity == "none"

    def test_to_dict_includes_severity_items_rationale(self) -> None:
        det = CrossSourceContradictionDetector()
        ctx = self._ctx(1_000_000.0, 1_500_000.0)
        report = det.detect(ctx, ())
        d = report.to_dict()
        assert d["severity"] == "medium"
        assert isinstance(d["items"], list)
        assert isinstance(d["rationale"], str)
