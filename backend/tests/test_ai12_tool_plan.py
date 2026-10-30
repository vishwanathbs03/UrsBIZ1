"""Tests for SPRINT AI-12 — ToolPlan dataclass.

Frozen dataclass: ``required / optional / parallelizable /
sequential / rationale``. The tests focus on the round-trip
behaviour (legacy tuple compat) and the wire ``to_dict()``
shape. Six tests covering the 6 most common capability
splits.
"""
from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from app.services.ai.reasoning.tool_plan import ToolPlan, tool_plan_empty
from app.services.ai.reasoning.tool_selector import ToolCall


class TestToolPlan:

    def _call(self, name: str) -> ToolCall:
        return ToolCall(
            service_name=name,
            inputs={"owner_id": 1},
            expected_output_shape="x",
        )

    def test_empty_helper(self) -> None:
        plan = tool_plan_empty("nothing to run")
        assert plan.required == ()
        assert plan.optional == ()
        assert plan.parallelizable == ()
        assert plan.sequential == ()
        assert plan.rationale == "nothing to run"

    def test_all_tools_legacy_drop_in(self) -> None:
        """``plan.required + plan.optional`` matches the legacy tuple."""
        req = (self._call("health_score"),)
        opt = (self._call("recommendation"),)
        plan = ToolPlan(required=req, optional=opt)
        assert plan.all_tools() == req + opt

    def test_constructor_is_frozen(self) -> None:
        plan = ToolPlan(required=(self._call("a"),))
        with pytest.raises(FrozenInstanceError):
            plan.rationale = "x"  # type: ignore[misc]

    def test_to_dict_carries_all_fields(self) -> None:
        req = (self._call("health_score"),)
        plan = ToolPlan(required=req, rationale="test")
        d = plan.to_dict()
        assert d["required"][0]["service_name"] == "health_score"
        assert d["optional"] == []
        assert d["parallelizable"] == []
        assert d["sequential"] == []
        assert d["rationale"] == "test"

    def test_parallelizable_subset(self) -> None:
        a = self._call("a")
        b = self._call("b")
        c = self._call("c")
        plan = ToolPlan(
            required=(a, b, c),
            parallelizable=(a, b),
            sequential=(c,),
            rationale="c must run after a+b",
        )
        parallel_names = tuple(c.service_name for c in plan.parallelizable)
        assert set(parallel_names) == {"a", "b"}
        assert plan.sequential == (c,)

    def test_rationale_default_string(self) -> None:
        plan = ToolPlan()
        assert plan.rationale == ""
