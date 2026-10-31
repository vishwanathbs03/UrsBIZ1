"""ToolPlan — SPRINT AI-12 Universal Reasoning Layer.

A ``ToolPlan`` is the structured plan emitted by
``ToolSelector.select(...)``. It splits the flat tuple of
``ToolCall``s the AI-1 → AI-11 selector produced into four
splits:

  * ``required`` — must run for the prompt to be answerable.
  * ``optional`` — improve the answer but the question stands without them.
  * ``parallelizable`` — can be dispatched concurrently (no
    mutual dependencies).
  * ``sequential`` — must run after the parallel batch
    completes (e.g. ``predictive_sprint14`` after
    ``finance`` has stamped its assumption baseline).

The dataclass is frozen; every call site that today holds a
``tuple[ToolCall, ...]`` can be migrated by reading
``plan.required + plan.optional`` with no behavioural change
when the consumer ignores the new split.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - import-time only
    from app.services.ai.reasoning.tool_selector import ToolCall


@dataclass(frozen=True)
class ToolPlan:
    """Structured tool-selection plan emitted by ``ToolSelector``.

    Attributes
    ----------
    required:
        Tools that MUST run for the prompt to be answerable
        (e.g. ``finance`` for an explicit ROI prompt;
        ``schemes_sprint16`` for a government-scheme prompt).
    optional:
        Tools that IMPROVE the answer but the question can
        still be answered without them (e.g. ``benchmark``
        after ``recommendation``).
    parallelizable:
        Subset of ``required`` that have no mutual
        dependencies; the dispatcher runs these in one
        parallel batch.
    sequential:
        Subset of ``required`` that must run after the
        parallel batch completes (depends on the parallel
        batch's output, e.g. scenario simulators that read
        the finance baseline).
    rationale:
        Human-readable explanation of why each tool made the
        cut. Surfaces in the audit trail only — never the
        response body.
    """

    required: tuple["ToolCall", ...] = ()
    optional: tuple["ToolCall", ...] = ()
    parallelizable: tuple["ToolCall", ...] = ()
    sequential: tuple["ToolCall", ...] = ()
    rationale: str = ""

    def all_tools(self) -> tuple["ToolCall", ...]:
        """Return ``required + optional`` for the legacy code path.

        Drop-in replacement for the AI-1 → AI-11 flat tuple.
        """
        return self.required + self.optional

    def to_dict(self) -> dict:
        """JSON-serialisable view for ``GenerationMeta`` stamping."""
        return {
            "required": [
                {
                    "service_name": c.service_name,
                    "inputs": c.inputs,
                    "expected_output_shape": c.expected_output_shape,
                }
                for c in self.required
            ],
            "optional": [
                {
                    "service_name": c.service_name,
                    "inputs": c.inputs,
                    "expected_output_shape": c.expected_output_shape,
                }
                for c in self.optional
            ],
            "parallelizable": [
                c.service_name for c in self.parallelizable
            ],
            "sequential": [c.service_name for c in self.sequential],
            "rationale": self.rationale,
        }


def tool_plan_empty(rationale: str = "") -> ToolPlan:
    """Return an empty ``ToolPlan`` with the given rationale.

    Helper so call sites that want a default plan (e.g. when
    ``understand_question`` reports ``required_tools=()``) do
    not have to spell out every field.
    """
    return ToolPlan(rationale=rationale)
