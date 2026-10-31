"""SPRINT AI-18 — Universal AI Evaluation Harness.

Quality metrics calculator.

The brief (PART 6) requires 14 documented metrics:

  1.  question coverage
  2.  evidence correctness
  3.  numeric correctness
  4.  calculation correctness
  5.  unsupported-claim rate
  6.  missing-data correctness
  7.  contradiction handling
  8.  tool-selection precision
  9.  unnecessary tool execution
  10. confidence calibration
  11. answer completeness
  12. actionability
  13. response latency
  14. fallback correctness

The calculator NEVER claims "100% accuracy" — every metric
is a measured value. Failures are explicit, never silently
ignored. All values are JSON-safe.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.services.ai.evaluation.runner import (
    EvaluationResult,
    EvaluationRunner,
    _BUSINESS_TOOLS,
    _GENERAL_TOOLS,
)
from app.services.ai.evaluation.evidence_matcher import (
    SUPPORTED,
    EvidenceRecord,
    evaluate_claim,
    extract_numeric_literals,
    is_fabricated_id,
)


# --------------------------------------------------------------------------- #
# Metrics report
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class MetricsReport:
    """All 14 brief metrics as measured values.

    Every field is documented. The runner never claims
    ``"100% accuracy"`` — it reports the raw counts.
    """

    # 1 — question coverage: fraction of categories the bank covers.
    question_coverage: float = 0.0
    categories_covered: int = 0
    categories_total: int = 0
    # 2 — evidence correctness: fraction of business prompts that
    #     cited at least one evidence_ref.
    evidence_correctness: float = 0.0
    # 3 — numeric correctness: fraction of numeric-bearing prompts
    #     whose body numbers match the answer mode (calc / forecast).
    numeric_correctness: float = 0.0
    # 4 — calculation correctness: fraction of CALCULATION prompts
    #     whose body actually carries a numeric.
    calculation_correctness: float = 0.0
    # 5 — unsupported-claim rate: average
    #     ``unsupported_claim_count`` per response.
    unsupported_claim_rate: float = 0.0
    # 6 — missing-data correctness: fraction of data-quality cases
    #     whose reply acknowledged the gap.
    missing_data_correctness: float = 0.0
    # 7 — contradiction handling: fraction of adversarial
    #     "false-fact" / "evidence-override" prompts the runner
    #     caught.
    contradiction_handling: float = 0.0
    # 8 — tool-selection precision: fraction of business prompts
    #     that fired at least one business tool.
    tool_selection_precision: float = 0.0
    # 9 — unnecessary tool execution: fraction of general-knowledge
    #     prompts that fired any business tool.
    unnecessary_tool_execution: float = 0.0
    # 10 — confidence calibration: mean server_confidence across
    #     the bank.
    confidence_calibration: float = 0.0
    # 11 — answer completeness: fraction of bank prompts whose
    #     body satisfies the brief's ``body_min_chars`` floor.
    answer_completeness: float = 0.0
    # 12 — actionability: fraction of RECOMMENDATION prompts whose
    #     body carries an action verb.
    actionability: float = 0.0
    # 13 — response latency: p50 / p95 latency in milliseconds.
    response_latency_p50_ms: int = 0
    response_latency_p95_ms: int = 0
    response_latency_max_ms: int = 0
    # 14 — fallback correctness: fraction of failure scenarios the
    #     runner caught (deterministic fallback engaged with a
    #     non-empty body).
    fallback_correctness: float = 0.0

    # SPRINT AI-18 — freeze gate. The brief's metric list adds
    # four fields beyond the original 14; each is computed from
    # the question-bank results + GenerationMeta signals the
    # runner already projects onto ``notes``. Heuristic by design
    # — the calculator reports the measured value, never a
    # fabricated accuracy %.
    # 15 — capability accuracy: fraction of bank prompts whose
    #     observed answer_mode matches the brief-expected category
    #     derivation.
    capability_accuracy: float = 0.0
    # 16 — business_dependency accuracy: fraction whose observed
    #     business_dependency matches the brief-expected derivation
    # SPRINT AI-20 — tool minimality. Two new metrics drive the
    # minimal-tool-set closure:
    #   * ``unnecessary_tool_calls`` (per-tool) =
    #       ``unnecessary_calls / total_calls``.
    #   * ``unnecessary_tool_request_rate`` (per-request) =
    #       ``requests_with_unnecessary_tool / total_requests``.
    # A tool is "unnecessary" when it ran, succeeded, but its
    # envelope value is never cited in the final answer body.
    # The two are NOT the same metric: a single request can
    # carry multiple unnecessary calls (per-tool) but only
    # counts as 1 toward the per-request rate.
    unnecessary_tool_calls: float = 0.0
    unnecessary_tool_request_rate: float = 0.0
    #     (BUSINESS_FACT/BUSINESS_ANALYSIS → required,
    #     GENERAL_KNOWLEDGE → none, MIXED → optional).
    business_dependency_accuracy: float = 0.0
    # 17 — fabricated_source_rate: fraction of bank prompts whose
    #     ``fabricated_source_count > 0``. Must be 0 in production.
    fabricated_source_rate: float = 0.0
    # 18 — scenario_correctness: fraction of SCENARIO bank prompts
    #     whose body exposes an "if/then/scenario" token AND no
    #     guarantee phrase ("guaranteed", "will reach",
    #     "certain to").
    scenario_correctness: float = 0.0

    # SPRINT AI-19 — evidence correctness closure. The freeze
    # gate's presence-only ``evidence_correctness`` metric
    # (field #2 above) is preserved for backward compatibility
    # on the wire contract. The three fields below layer a
    # structural metric on top of the existing surfaces.
    # 19 — evidence_correctness_structural: fraction of
    #     business claims correctly supported by server-owned
    #     evidence (SUPPORTED / total claims requiring
    #     evidence). Computed by the evidence matcher over
    #     ``notes["structured_tool_envelopes"]`` +
    #     ``notes["evidence_references"]``.
    evidence_correctness_structural: float = 0.0
    # 20 — fabricated_evidence_id_rate: fraction of business
    #     claims whose cited evidence ID is not in the
    #     server-generated registry. Must be 0 in production
    #     — the LLM is forbidden from inventing evidence IDs.
    fabricated_evidence_id_rate: float = 0.0
    # 21 — evidence_kind_coverage: fraction of business
    #     prompts whose response carries at least one of the
    #     evidence kinds the question bank's capability
    #     requires. Surface metric for the existing
    #     ``EvidenceRequirements`` table.
    evidence_kind_coverage: float = 0.0

    # Sprint AI-21 — question-understanding calibration. The
    # AI-18 freeze gate reported a single heuristic pair
    # (capability_accuracy / business_dependency_accuracy).
    # Brief asks for a multi-axis classification report so
    # misclassifications can be diagnosed as classifier
    # error, label mismatch, or multi-label semantics. All
    # six new fields are computed from the same
    # bank + entries + adversarial tuples the calculator
    # already has.
    # 22 — capability_set_exact_accuracy: fraction of bank
    #     prompts whose observed capability tuple is a
    #     subset-equivalent of the expected capability set
    #     (set membership, no order). Multi-label answers
    #     are accepted when the brief-expected set is
    #     covered.
    capability_set_exact_accuracy: float = 0.0
    # 23 — capability_micro_f1: micro-averaged F1 across
    #     capability labels. Treats each capability as a
    #     binary prediction (in the set / not in the set)
    #     and pools TP / FP / FN across all bank prompts.
    capability_micro_f1: float = 0.0
    # 24 — capability_macro_f1: macro-averaged F1 across
    #     capability labels. Computed per label then
    #     averaged. Prompts with no expected capability are
    #     excluded from the per-label denominator.
    capability_macro_f1: float = 0.0
    # 25 — business_dependency_accuracy_v2: same heuristic
    #     as the legacy field, but the answer_mode expected
    #     value is computed from the same
    #     ``_CATEGORY_TO_EXPECTED_DEP_V2`` table the
    #     matcher uses. Refresh of the legacy metric with
    #     INTERNAL / EXTERNAL / MIXED semantics.
    business_dependency_accuracy_v2: float = 0.0
    # 26 — answer_mode_consistency: fraction of bank
    #     prompts whose observed answer_mode is in the
    #     expected set OR a multi-label capability that
    #     produces the same answer shape. Lower than
    #     capability_accuracy because it compares answer
    #     shape, not capability membership.
    answer_mode_consistency: float = 0.0
    # 27 — legacy_intent_compatibility: fraction of
    #     question bank + golden set + adversarial
    #     prompts whose ``relevant_existing_intents`` is
    #     non-empty (the legacy QuestionIntent enum is
    #     always reachable). AI-21 must not regress this.
    legacy_intent_compatibility: float = 0.0

    # Cross-cutting
    production_path_fraction: float = 0.0
    total_cases: int = 0
    successful_cases: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "question_coverage": float(self.question_coverage),
            "categories_covered": int(self.categories_covered),
            "categories_total": int(self.categories_total),
            "evidence_correctness": float(self.evidence_correctness),
            "numeric_correctness": float(self.numeric_correctness),
            "calculation_correctness": float(self.calculation_correctness),
            "unsupported_claim_rate": float(self.unsupported_claim_rate),
            "missing_data_correctness": float(self.missing_data_correctness),
            "contradiction_handling": float(self.contradiction_handling),
            "tool_selection_precision": float(self.tool_selection_precision),
            "unnecessary_tool_execution": float(self.unnecessary_tool_execution),
            # SPRINT AI-20 — two new tool-minimality metrics.
            "unnecessary_tool_calls": float(self.unnecessary_tool_calls),
            "unnecessary_tool_request_rate": float(
                self.unnecessary_tool_request_rate
            ),
            "confidence_calibration": float(self.confidence_calibration),
            "answer_completeness": float(self.answer_completeness),
            "actionability": float(self.actionability),
            "response_latency_p50_ms": int(self.response_latency_p50_ms),
            "response_latency_p95_ms": int(self.response_latency_p95_ms),
            "response_latency_max_ms": int(self.response_latency_max_ms),
            "fallback_correctness": float(self.fallback_correctness),
            "capability_accuracy": float(self.capability_accuracy),
            "business_dependency_accuracy": float(
                self.business_dependency_accuracy
            ),
            "fabricated_source_rate": float(self.fabricated_source_rate),
            "scenario_correctness": float(self.scenario_correctness),
            "evidence_correctness_structural": float(
                self.evidence_correctness_structural
            ),
            "fabricated_evidence_id_rate": float(
                self.fabricated_evidence_id_rate
            ),
            "evidence_kind_coverage": float(self.evidence_kind_coverage),
            # Sprint AI-21 — six new classification axes.
            "capability_set_exact_accuracy": float(
                self.capability_set_exact_accuracy
            ),
            "capability_micro_f1": float(self.capability_micro_f1),
            "capability_macro_f1": float(self.capability_macro_f1),
            "business_dependency_accuracy_v2": float(
                self.business_dependency_accuracy_v2
            ),
            "answer_mode_consistency": float(
                self.answer_mode_consistency
            ),
            "legacy_intent_compatibility": float(
                self.legacy_intent_compatibility
            ),
            "production_path_fraction": float(self.production_path_fraction),
            "total_cases": int(self.total_cases),
            "successful_cases": int(self.successful_cases),
        }


# --------------------------------------------------------------------------- #
# Calculator
# --------------------------------------------------------------------------- #


# Minimum body length the runner treats as "complete". Below
# this the answer is considered an empty / inadequate reply.
_BODY_MIN_CHARS = 20

# Action verbs the runner keys off for the actionability metric.
_ACTION_VERBS = (
    "apply", "consider", "focus", "hire", "invest", "review",
    "schedule", "start", "track", "use", "adopt", "expand",
    "register", "contact", "negotiate", "reduce", "increase",
    "prioritise", "prioritize", "implement", "deploy",
    "should", "recommend", "next step", "next:", "first,",
)


class MetricsCalculator:
    """Compute the 14 brief metrics from runner results.

    Pure. No I/O. The calculator is fed
    :class:`EvaluationResult` tuples; it produces a
    :class:`MetricsReport`.
    """

    def compute(
        self,
        *,
        question_bank_results: tuple[EvaluationResult, ...] = (),
        golden_results: tuple[EvaluationResult, ...] = (),
        adversarial_results: tuple[EvaluationResult, ...] = (),
        followup_results: tuple[tuple[EvaluationResult, ...], ...] = (),
        failure_results: tuple[EvaluationResult, ...] = (),
        data_quality_results: tuple[tuple[EvaluationResult, ...], ...] = (),
        question_bank_categories: tuple[str, ...] = (),
        question_bank_entries: tuple[Any, ...] = (),
        adversarial_cases: tuple[Any, ...] = (),
        data_quality_profiles: tuple[Any, ...] = (),
        failure_scenarios: tuple[Any, ...] = (),
    ) -> MetricsReport:
        """Compute the :class:`MetricsReport`.

        Parameters
        ----------
        question_bank_results:
            Per-prompt :class:`EvaluationResult` tuples from
            the runner.
        golden_results:
            Per-case golden results.
        adversarial_results:
            Per-case adversarial results. Used for the
            ``contradiction_handling`` metric.
        followup_results:
            Tuple of per-script result tuples.
        failure_results:
            Per-scenario failure results.
        data_quality_results:
            Tuple of per-profile result tuples.
        question_bank_categories:
            The brief's 16+ category vocabulary.
        question_bank_entries:
            The original :class:`QuestionEntry` tuples (used
            to bucket results by category for tool-selection
            precision).
        adversarial_cases:
            The original :class:`AdversarialCase` tuples
            (used to identify false-fact / evidence-override
            cases for ``contradiction_handling``).
        data_quality_profiles:
            The original :class:`DataQualityProfile` tuples
            (used to identify expected-warning cases).
        failure_scenarios:
            The original :class:`ProviderFailureScenario`
            tuples (used to identify which cases are failure
            cases).
        """
        # Total cases + success count.
        all_results = list(question_bank_results) + list(golden_results) + list(adversarial_results)
        for script_results in followup_results:
            all_results.extend(script_results)
        for prof_results in data_quality_results:
            all_results.extend(prof_results)
        all_results.extend(failure_results)

        total = len(all_results)
        successful = sum(1 for r in all_results if r.success)
        production_path = sum(1 for r in all_results if r.production_path)

        return MetricsReport(
            question_coverage=self._question_coverage(
                question_bank_categories, question_bank_entries
            ),
            categories_covered=self._categories_covered(question_bank_entries),
            categories_total=len(question_bank_categories),
            evidence_correctness=self._evidence_correctness(
                question_bank_results, question_bank_entries
            ),
            numeric_correctness=self._numeric_correctness(
                question_bank_results, question_bank_entries
            ),
            calculation_correctness=self._calculation_correctness(
                question_bank_results, question_bank_entries
            ),
            unsupported_claim_rate=self._unsupported_claim_rate(all_results),
            missing_data_correctness=self._missing_data_correctness(
                data_quality_results, data_quality_profiles
            ),
            contradiction_handling=self._contradiction_handling(
                adversarial_results, adversarial_cases
            ),
            tool_selection_precision=self._tool_selection_precision(
                question_bank_results, question_bank_entries
            ),
            unnecessary_tool_execution=self._unnecessary_tool_execution(
                question_bank_results, question_bank_entries
            ),
            # SPRINT AI-20 — two new tool-minimality metrics.
            unnecessary_tool_calls=self._unnecessary_tool_calls(
                all_results
            ),
            unnecessary_tool_request_rate=self._unnecessary_tool_request_rate(
                all_results
            ),
            confidence_calibration=self._confidence_calibration(all_results),
            answer_completeness=self._answer_completeness(all_results),
            actionability=self._actionability(
                question_bank_results, question_bank_entries
            ),
            response_latency_p50_ms=self._latency_percentile(all_results, 50),
            response_latency_p95_ms=self._latency_percentile(all_results, 95),
            response_latency_max_ms=self._max_latency(all_results),
            fallback_correctness=self._fallback_correctness(
                failure_results, failure_scenarios
            ),
            capability_accuracy=self._capability_accuracy(
                question_bank_results, question_bank_entries
            ),
            business_dependency_accuracy=self._business_dependency_accuracy(
                question_bank_results, question_bank_entries
            ),
            fabricated_source_rate=self._fabricated_source_rate(
                question_bank_results
            ),
            scenario_correctness=self._scenario_correctness(
                question_bank_results, question_bank_entries
            ),
            evidence_correctness_structural=self._evidence_correctness_structural(
                question_bank_results, question_bank_entries
            ),
            fabricated_evidence_id_rate=self._fabricated_evidence_id_rate(
                question_bank_results
            ),
            evidence_kind_coverage=self._evidence_kind_coverage(
                question_bank_results, question_bank_entries
            ),
            # Sprint AI-21 — six classification axes.
            capability_set_exact_accuracy=self._capability_set_exact_accuracy(
                question_bank_results, question_bank_entries
            ),
            capability_micro_f1=self._capability_micro_f1(
                question_bank_results, question_bank_entries
            ),
            capability_macro_f1=self._capability_macro_f1(
                question_bank_results, question_bank_entries
            ),
            business_dependency_accuracy_v2=(
                self._business_dependency_accuracy_v2(
                    question_bank_results, question_bank_entries
                )
            ),
            answer_mode_consistency=self._answer_mode_consistency(
                question_bank_results, question_bank_entries
            ),
            legacy_intent_compatibility=self._legacy_intent_compatibility(
                all_results
            ),
            production_path_fraction=_fraction(production_path, total),
            total_cases=total,
            successful_cases=successful,
        )

    # ---- individual metrics --------------------------------------- #

    @staticmethod
    def _question_coverage(
        categories: tuple[str, ...], entries: tuple[Any, ...]
    ) -> float:
        """Fraction of categories covered by at least one entry."""
        if not categories:
            return 0.0
        present = {q.category for q in entries}
        return _fraction(len(present & set(categories)), len(categories))

    @staticmethod
    def _categories_covered(entries: tuple[Any, ...]) -> int:
        return len({q.category for q in entries})

    @staticmethod
    def _evidence_correctness(
        results: tuple[EvaluationResult, ...], entries: tuple[Any, ...]
    ) -> float:
        """Business-prompt fraction that cited >=1 evidence_ref."""
        if len(results) != len(entries):
            return 0.0
        biz = [
            (r, e) for r, e in zip(results, entries)
            if e.category in _BUSINESS_CATEGORIES
        ]
        if not biz:
            return 0.0
        cited = sum(1 for r, _ in biz if r.notes.get("evidence_count", 0) >= 1)
        return _fraction(cited, len(biz))

    @staticmethod
    def _numeric_correctness(
        results: tuple[EvaluationResult, ...], entries: tuple[Any, ...]
    ) -> float:
        """Calculation / financial / forecast prompts that carry
        at least one numeric literal."""
        if len(results) != len(entries):
            return 0.0
        numeric = [
            (r, e) for r, e in zip(results, entries)
            if e.category in _NUMERIC_CATEGORIES
        ]
        if not numeric:
            return 0.0
        ok = 0
        for r, _ in numeric:
            if EvaluationRunner.extract_numbers(r.body):
                ok += 1
        return _fraction(ok, len(numeric))

    @staticmethod
    def _calculation_correctness(
        results: tuple[EvaluationResult, ...], entries: tuple[Any, ...]
    ) -> float:
        """CALCULATION prompts whose body carries a numeric."""
        if len(results) != len(entries):
            return 0.0
        calc = [
            (r, e) for r, e in zip(results, entries)
            if e.category == "calculation"
        ]
        if not calc:
            return 0.0
        ok = sum(
            1 for r, _ in calc
            if EvaluationRunner.extract_numbers(r.body)
        )
        return _fraction(ok, len(calc))

    @staticmethod
    def _unsupported_claim_rate(results: tuple[EvaluationResult, ...]) -> float:
        """Average ``unsupported_claim_count`` per response."""
        if not results:
            return 0.0
        total = 0.0
        for r in results:
            gen = r.generation
            if gen is None:
                continue
            total += float(getattr(gen, "unsupported_claim_count", 0) or 0)
        return total / float(len(results))

    @staticmethod
    def _missing_data_correctness(
        profile_results: tuple[tuple[EvaluationResult, ...], ...],
        profiles: tuple[Any, ...],
    ) -> float:
        """Fraction of data-quality profiles whose reply
        acknowledged the gap (warning or disclosure)."""
        if not profile_results or not profiles:
            return 0.0
        ok = 0
        for results, profile in zip(profile_results, profiles):
            if not results:
                continue
            # The runner runs the same prompt against each
            # profile; we look at the FIRST result (any result
            # is fine for the metric).
            r = results[0]
            gen = r.generation
            disclosed = (
                bool(r.notes.get("needs_warning"))
                or bool(getattr(gen, "needs_warning", False))
                or bool(getattr(gen, "partial_failure_disclosure", None))
            )
            if profile.expected_warning and not disclosed:
                continue
            if not profile.expected_warning and disclosed:
                # Disclosing when not expected is OK.
                pass
            ok += 1
        return _fraction(ok, len(profiles))

    @staticmethod
    def _contradiction_handling(
        results: tuple[EvaluationResult, ...], cases: tuple[Any, ...]
    ) -> float:
        """Fraction of USER_FALSE_FACT / EVIDENCE_OVERRIDE prompts
        the runner caught (body must NOT confirm the false claim).

        The runner evaluates this purely on the body content.
        """
        if not cases or not results:
            return 0.0
        caught = 0
        total = 0
        for r, c in zip(results, cases):
            if c.kind not in {"user_false_fact", "evidence_override", "conflicting_numbers"}:
                continue
            total += 1
            body_low = (r.body or "").lower()
            # Caught when the body does NOT contain the
            # expected_confirmation tokens AND does NOT match
            # the unsafe pattern.
            unsafe_tokens = (
                "is correct", "confirmed", "your score is",
                "your revenue is", "₹500 cr is correct",
            )
            contains_unsafe = any(tok in body_low for tok in unsafe_tokens)
            if not contains_unsafe:
                caught += 1
        return _fraction(caught, total)

    @staticmethod
    def _tool_selection_precision(
        results: tuple[EvaluationResult, ...], entries: tuple[Any, ...]
    ) -> float:
        """Business-prompt fraction that fired >=1 business tool."""
        if len(results) != len(entries):
            return 0.0
        biz = [
            (r, e) for r, e in zip(results, entries)
            if e.category in _BUSINESS_CATEGORIES
        ]
        if not biz:
            return 0.0
        ok = 0
        for r, _ in biz:
            tools = EvaluationRunner.extract_tools_used(r)
            if any(t.lower() in _BUSINESS_TOOLS for t in tools):
                ok += 1
        return _fraction(ok, len(biz))

    @staticmethod
    def _unnecessary_tool_execution(
        results: tuple[EvaluationResult, ...], entries: tuple[Any, ...]
    ) -> float:
        """General-knowledge / external / mixed prompts that
        fired a business tool. Reported as the inverse:
        fraction that did NOT (lower = better)."""
        if len(results) != len(entries):
            return 0.0
        general = [
            (r, e) for r, e in zip(results, entries)
            if e.category in _GENERAL_KNOWLEDGE_CATEGORIES
        ]
        if not general:
            return 0.0
        ok = 0
        for r, _ in general:
            tools = EvaluationRunner.extract_tools_used(r)
            if not any(t.lower() in _BUSINESS_TOOLS for t in tools):
                ok += 1
        return _fraction(ok, len(general))

    @staticmethod
    def _unnecessary_tool_calls(
        results: tuple[EvaluationResult, ...],
    ) -> float:
        """Per-tool metric: fraction of executed tool calls
        that did NOT contribute to the final answer.

        Sprint AI-20 — a tool call is "unnecessary" when:

          * the trace's ``selected == True`` AND
          * the trace's ``executed == True`` AND
          * the trace's ``success == True`` AND
          * the trace's ``used_in_final_answer == False``.

        Stub / timeout / errored calls are NOT counted as
        unnecessary — they failed before they could
        contribute, so they are not the minimality problem
        this metric targets.

        The metric returns ``0.0`` when no tool execution
        traces were projected onto ``notes`` (consistent
        with the conservative behaviour for additive
        AI-20 fields).
        """
        if not results:
            return 0.0
        total_calls = 0
        unnecessary_calls = 0
        for r in results:
            traces = r.notes.get("tool_execution_traces") or ()
            if not traces:
                continue
            for trace in traces:
                if not isinstance(trace, dict):
                    continue
                selected = bool(trace.get("selected"))
                executed = bool(trace.get("executed"))
                success = bool(trace.get("success"))
                if not (selected and executed and success):
                    continue
                total_calls += 1
                if not bool(trace.get("used_in_final_answer")):
                    unnecessary_calls += 1
        if total_calls == 0:
            return 0.0
        return _fraction(unnecessary_calls, total_calls)

    @staticmethod
    def _unnecessary_tool_request_rate(
        results: tuple[EvaluationResult, ...],
    ) -> float:
        """Per-request metric: fraction of requests that
        fired at least one unnecessary tool call.

        Sprint AI-20 — the complement of
        ``unnecessary_tool_calls``. A request is "tainted"
        when at least one selected + executed + successful
        tool call did not contribute to its final answer.
        Reports ``0.0`` when no traces are projected.

        The two metrics are distinct: a single request can
        carry N unnecessary calls (each one counts toward
        ``unnecessary_tool_calls``) but only counts as 1
        toward this per-request rate.
        """
        if not results:
            return 0.0
        applicable = 0
        tainted = 0
        for r in results:
            traces = r.notes.get("tool_execution_traces") or ()
            if not traces:
                continue
            applicable += 1
            for trace in traces:
                if not isinstance(trace, dict):
                    continue
                selected = bool(trace.get("selected"))
                executed = bool(trace.get("executed"))
                success = bool(trace.get("success"))
                used = bool(trace.get("used_in_final_answer"))
                if not (selected and executed and success):
                    continue
                if not used:
                    tainted += 1
                    break  # one bad call is enough
        if applicable == 0:
            return 0.0
        return _fraction(tainted, applicable)

    @staticmethod
    def _confidence_calibration(results: tuple[EvaluationResult, ...]) -> float:
        """Mean ``server_confidence`` across all results."""
        if not results:
            return 0.0
        total = 0.0
        count = 0
        for r in results:
            gen = r.generation
            if gen is None:
                continue
            sc = getattr(gen, "server_confidence", None)
            if sc is None:
                continue
            total += float(sc)
            count += 1
        return total / float(count) if count else 0.0

    @staticmethod
    def _answer_completeness(results: tuple[EvaluationResult, ...]) -> float:
        """Fraction whose body satisfies ``_BODY_MIN_CHARS``."""
        if not results:
            return 0.0
        ok = sum(1 for r in results if len(r.body or "") >= _BODY_MIN_CHARS)
        return _fraction(ok, len(results))

    @staticmethod
    def _actionability(
        results: tuple[EvaluationResult, ...], entries: tuple[Any, ...]
    ) -> float:
        """RECOMMENDATION prompts whose body carries an action verb."""
        if len(results) != len(entries):
            return 0.0
        rec = [
            (r, e) for r, e in zip(results, entries)
            if e.category == "recommendation"
        ]
        if not rec:
            return 0.0
        ok = 0
        for r, _ in rec:
            low = (r.body or "").lower()
            if any(v in low for v in _ACTION_VERBS):
                ok += 1
        return _fraction(ok, len(rec))

    @staticmethod
    def _latency_percentile(
        results: tuple[EvaluationResult, ...], pct: int
    ) -> int:
        """Latency percentile in milliseconds."""
        if not results:
            return 0
        lats = sorted(r.latency_ms for r in results)
        if not lats:
            return 0
        idx = max(0, min(len(lats) - 1, int(len(lats) * pct / 100.0)))
        return int(lats[idx])

    @staticmethod
    def _max_latency(results: tuple[EvaluationResult, ...]) -> int:
        if not results:
            return 0
        return int(max(r.latency_ms for r in results))

    @staticmethod
    def _fallback_correctness(
        results: tuple[EvaluationResult, ...], scenarios: tuple[Any, ...]
    ) -> float:
        """Fraction of failure scenarios whose reply was safe
        (non-empty body). The runner exercises the deterministic
        fallback, which always produces a body — but the metric
        here measures ``body_nonempty`` to catch any future
        regression where the fallback is silent.
        """
        if not results:
            return 0.0
        ok = sum(1 for r in results if r.success and r.body.strip())
        return _fraction(ok, len(results))

    # ---- SPRINT AI-21 — classification calibration axes ---------- #

    @staticmethod
    def _capability_set_exact_accuracy(
        results: tuple[EvaluationResult, ...], entries: tuple[Any, ...]
    ) -> float:
        """Set-equivalent capability match.

        The observed ``capability`` tuple on the runner's notes
        is converted to a sorted set and compared against the
        expected capability set keyed off the question's
        category. Order is irrelevant; multi-label answers
        count as a hit when the expected set is covered.
        """
        if len(results) != len(entries) or not results:
            return 0.0
        ok = 0
        eligible = 0
        for r, e in zip(results, entries):
            expected = _CATEGORY_TO_EXPECTED_CAPABILITIES.get(
                e.category, ()
            )
            if not expected:
                continue
            eligible += 1
            observed = set(
                sorted(
                    c.strip()
                    for c in (r.notes.get("capability") or [])
                    if c and isinstance(c, str)
                )
            )
            if observed == set(expected):
                ok += 1
        return _fraction(ok, eligible)

    @staticmethod
    def _capability_micro_f1(
        results: tuple[EvaluationResult, ...], entries: tuple[Any, ...]
    ) -> float:
        """Micro-averaged F1 across capability labels.

        Each capability label is a binary prediction. TP / FP /
        FN are aggregated across all bank prompts, then
        ``F1 = 2 * precision * recall / (precision + recall)``.
        """
        if len(results) != len(entries) or not results:
            return 0.0
        tp = 0
        fp = 0
        fn = 0
        for r, e in zip(results, entries):
            expected = set(_CATEGORY_TO_EXPECTED_CAPABILITIES.get(
                e.category, ()
            ))
            if not expected:
                continue
            observed = set(
                c.strip()
                for c in (r.notes.get("capability") or [])
                if c and isinstance(c, str)
            )
            tp += len(observed & expected)
            fp += len(observed - expected)
            fn += len(expected - observed)
        if tp == 0 and fp == 0 and fn == 0:
            return 0.0
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        if precision + recall == 0:
            return 0.0
        return 2 * precision * recall / (precision + recall)

    @staticmethod
    def _capability_macro_f1(
        results: tuple[EvaluationResult, ...], entries: tuple[Any, ...]
    ) -> float:
        """Macro-averaged F1 across capability labels.

        F1 is computed per label, then averaged across labels
        that appear in any expected set. Labels with TP=FP=FN=0
        are excluded from the average.
        """
        if len(results) != len(entries) or not results:
            return 0.0
        labels: set[str] = set()
        for e in entries:
            for c in _CATEGORY_TO_EXPECTED_CAPABILITIES.get(
                e.category, ()
            ):
                labels.add(c)
        if not labels:
            return 0.0
        per_label: list[float] = []
        for label in sorted(labels):
            tp = fp = fn = 0
            for r, e in zip(results, entries):
                expected = set(_CATEGORY_TO_EXPECTED_CAPABILITIES.get(
                    e.category, ()
                ))
                if not expected:
                    continue
                observed = set(
                    c.strip()
                    for c in (r.notes.get("capability") or [])
                    if c and isinstance(c, str)
                )
                if label in observed and label in expected:
                    tp += 1
                elif label in observed and label not in expected:
                    fp += 1
                elif label not in observed and label in expected:
                    fn += 1
            if tp == 0 and fp == 0 and fn == 0:
                # Label never appears in any expected set
                # across the bank — not an error, just not
                # in scope. Skip.
                continue
            precision = tp / (tp + fp) if (tp + fp) else 0.0
            recall = tp / (tp + fn) if (tp + fn) else 0.0
            # FN-only labels (classifier missed every
            # expected occurrence) get F1=0 so the macro
            # average reflects the miss.
            if precision + recall == 0:
                per_label.append(0.0)
            else:
                per_label.append(
                    2 * precision * recall / (precision + recall)
                )
        if not per_label:
            return 0.0
        return sum(per_label) / len(per_label)

    @staticmethod
    def _business_dependency_accuracy_v2(
        results: tuple[EvaluationResult, ...], entries: tuple[Any, ...]
    ) -> float:
        """Refresh of the legacy business_dependency metric.

        The expected value is the refreshed
        ``_CATEGORY_TO_EXPECTED_DEP_V2`` mapping, which encodes
        the brief's INTERNAL / EXTERNAL / MIXED semantics.
        Prompts with no expected dependency are excluded.
        """
        if len(results) != len(entries) or not results:
            return 0.0
        ok = 0
        eligible = 0
        for r, e in zip(results, entries):
            expected = _CATEGORY_TO_EXPECTED_DEP_V2.get(
                e.category, None
            )
            if expected is None:
                continue
            eligible += 1
            observed = str(
                r.notes.get("business_dependency", "none") or "none"
            )
            if observed == expected:
                ok += 1
        return _fraction(ok, eligible)

    @staticmethod
    def _answer_mode_consistency(
        results: tuple[EvaluationResult, ...], entries: tuple[Any, ...]
    ) -> float:
        """Answer-shape consistency.

        Different from capability_accuracy: the metric maps
        expected capabilities to answer shapes through the
        same ``_CAP_TO_SHAPE`` table the QU uses, then checks
        the observed ``answer_mode`` matches the union of
        expected shapes. Multi-label capability tuples
        produce a set of expected shapes; the observed
        ``answer_mode`` may be either a single member of
        the set or ``mixed`` (the engine's rollup).
        """
        if len(results) != len(entries) or not results:
            return 0.0
        ok = 0
        eligible = 0
        for r, e in zip(results, entries):
            expected_caps = _CATEGORY_TO_EXPECTED_CAPABILITIES.get(
                e.category, ()
            )
            if not expected_caps:
                continue
            eligible += 1
            expected_shapes = set()
            for c in expected_caps:
                shape = _CAP_TO_SHAPE_REPORT.get(c)
                if shape:
                    expected_shapes.add(shape)
            observed = str(r.notes.get("answer_mode", "") or "")
            if not expected_shapes:
                continue
            if observed in expected_shapes or observed == "mixed":
                ok += 1
        return _fraction(ok, eligible)

    @staticmethod
    def _legacy_intent_compatibility(
        results: tuple[EvaluationResult, ...],
    ) -> float:
        """Fraction of results whose
        ``relevant_existing_intents`` is non-empty.

        The legacy QuestionIntent enum must always be reachable
        through the AI-21 QU — the brief explicitly forbids
        removing legacy intents. The metric reports the
        non-empty fraction.
        """
        if not results:
            return 0.0
        ok = 0
        for r in results:
            intents = r.notes.get("relevant_existing_intents") or []
            if intents:
                ok += 1
        return _fraction(ok, len(results))

    # ---- SPRINT AI-18 — freeze gate additions --------------------- #

    @staticmethod
    def _capability_accuracy(
        results: tuple[EvaluationResult, ...], entries: tuple[Any, ...]
    ) -> float:
        """Heuristic: observed ``answer_mode`` matches the
        brief-expected category derivation.

        The mapping is a closed dict — adding a category requires
        a plan note. The metric reports the match rate as a
        measured value, not a verdict; prompts whose observed
        mode legitimately diverges (the brief labels a prompt
        BUSINESS_ANALYSIS but the model returned ``business_fact``)
        count as a miss.
        """
        if len(results) != len(entries) or not results:
            return 0.0
        ok = 0
        for r, e in zip(results, entries):
            expected_modes = _CATEGORY_TO_EXPECTED_MODES.get(
                e.category, ()
            )
            if not expected_modes:
                # UNKNOWN / ROADMAP — no specific mode expected.
                continue
            observed = str(r.notes.get("answer_mode", ""))
            if observed in expected_modes:
                ok += 1
        eligible = sum(
            1 for e in entries
            if _CATEGORY_TO_EXPECTED_MODES.get(e.category, ())
        )
        return _fraction(ok, eligible)

    @staticmethod
    def _business_dependency_accuracy(
        results: tuple[EvaluationResult, ...], entries: tuple[Any, ...]
    ) -> float:
        """Heuristic: observed ``business_dependency`` matches the
        brief-expected derivation per category."""
        if len(results) != len(entries) or not results:
            return 0.0
        ok = 0
        for r, e in zip(results, entries):
            expected = _CATEGORY_TO_BUSINESS_DEPENDENCY.get(
                e.category, None
            )
            if expected is None:
                continue
            observed = str(r.notes.get("business_dependency", "none"))
            if observed == expected:
                ok += 1
        eligible = sum(
            1 for e in entries
            if _CATEGORY_TO_BUSINESS_DEPENDENCY.get(e.category, None)
            is not None
        )
        return _fraction(ok, eligible)

    @staticmethod
    def _fabricated_source_rate(
        results: tuple[EvaluationResult, ...],
    ) -> float:
        """Fraction of bank prompts whose
        ``fabricated_source_count > 0``.

        Must be 0 in production — fabrication is forbidden. The
        metric reports the raw fraction so a regression shows up
        as a non-zero value.
        """
        if not results:
            return 0.0
        bad = 0
        for r in results:
            gen = r.generation
            if gen is None:
                continue
            if int(getattr(gen, "fabricated_source_count", 0) or 0) > 0:
                bad += 1
        return _fraction(bad, len(results))

    @staticmethod
    def _scenario_correctness(
        results: tuple[EvaluationResult, ...], entries: tuple[Any, ...]
    ) -> float:
        """SCENARIO prompts whose body exposes an
        ``if/then/scenario`` token AND no guarantee phrase.

        The metric enforces the brief's "scenario is never a
        forecast guarantee" rule: any scenario reply containing
        ``guaranteed`` / ``will reach`` / ``certain to`` is a
        miss.
        """
        if len(results) != len(entries) or not results:
            return 0.0
        ok = 0
        for r, e in zip(results, entries):
            if e.category != "scenario":
                continue
            body_low = (r.body or "").lower()
            has_marker = any(
                tok in body_low
                for tok in _SCENARIO_MARKERS
            )
            has_guarantee = any(
                tok in body_low
                for tok in _SCENARIO_GUARANTEE_PHRASES
            )
            if has_marker and not has_guarantee:
                ok += 1
        eligible = sum(1 for e in entries if e.category == "scenario")
        return _fraction(ok, eligible)

    @staticmethod
    def _evidence_correctness_structural(
        results: tuple[EvaluationResult, ...], entries: tuple[Any, ...]
    ) -> float:
        """Fraction of claims correctly supported by server-owned evidence.

        Sprint AI-19 — replaces the presence-only check
        with a structural, deterministic, auditable metric.
        The runner projects ``structured_tool_envelopes`` and
        ``evidence_references`` onto ``notes``; this method
        walks every claim, runs the evidence matcher, and
        reports ``SUPPORTED / claims_requiring_evidence``.

        Claims that carry ``NOT_APPLICABLE`` (forward-looking
        / user-supplied) are excluded from both numerator
        and denominator. Claims with empty citations
        (UNSUPPORTED) are included in the denominator — a
        claim that asserts a number without citing evidence
        is structurally unsupported.

        Returns ``0.0`` when the runner has not projected
        any structured envelopes (the conservative value
        — the brief requires we report the measured value,
        not a fabricated one).
        """
        if len(results) != len(entries) or not results:
            return 0.0
        supported = 0
        applicable = 0
        for r, _e in zip(results, entries):
            for verdict in _walk_claim_verdicts(r):
                if verdict["status"] == "NOT_APPLICABLE":
                    continue
                applicable += 1
                if verdict["status"] == SUPPORTED:
                    supported += 1
        if applicable == 0:
            return 0.0
        return _fraction(supported, applicable)

    @staticmethod
    def _fabricated_evidence_id_rate(
        results: tuple[EvaluationResult, ...],
    ) -> float:
        """Fraction of business prompts whose response cites a
        fabricated evidence ID.

        Sprint AI-19 — explicit, structural check on the
        server-owned registry. Any cited ID not in the
        registry the runner projected is a fabrication. The
        metric returns ``0.0`` when no evidence has been
        projected (consistent with the conservative
        ``evidence_correctness_structural`` behaviour).
        """
        if not results:
            return 0.0
        bad = 0
        applicable = 0
        for r in results:
            registry_ids = r.notes.get("registry_ids", ()) or ()
            cited_ids = r.notes.get("evidence_references", ()) or ()
            envelope_ids = [
                env.get("id")
                for env in (r.notes.get("structured_tool_envelopes") or ())
                if isinstance(env, dict) and env.get("id")
            ]
            all_cited = list(cited_ids) + envelope_ids
            if not all_cited:
                continue
            applicable += 1
            for cid in all_cited:
                if is_fabricated_id(str(cid), registry_ids):
                    bad += 1
                    break
        return _fraction(bad, applicable)

    @staticmethod
    def _evidence_kind_coverage(
        results: tuple[EvaluationResult, ...], entries: tuple[Any, ...]
    ) -> float:
        """Fraction of business prompts whose response carries
        at least one of the evidence kinds the question's
        capability requires.

        Sprint AI-19 — surfaces the existing
        :class:`EvidenceRequirements` table from
        :mod:`app.services.ai.reasoning.evidence_requirements`
        by reading the kind list off the runner-projected
        envelopes. Prompts with no expected kinds are
        excluded from the denominator.

        Envelope kind is inferred from the explicit
        ``kind`` / ``tool_kind`` field when present; when
        absent (the deterministic fallback path) we
        derive a kind from the ``tool_name`` prefix.
        """
        if len(results) != len(entries) or not results:
            return 0.0
        ok = 0
        applicable = 0
        for r, e in zip(results, entries):
            expected = _CATEGORY_TO_EXPECTED_KINDS.get(e.category, ())
            if not expected:
                continue
            applicable += 1
            kinds_in_response: set[str] = set()
            for env in (r.notes.get("structured_tool_envelopes") or ()):
                if not isinstance(env, dict):
                    continue
                kind = env.get("kind") or env.get("tool_kind")
                if not kind:
                    kind = _infer_envelope_kind(env)
                if kind:
                    kinds_in_response.add(str(kind))
            if kinds_in_response & set(expected):
                ok += 1
        return _fraction(ok, applicable)


def _walk_claim_verdicts(
    result: EvaluationResult,
) -> tuple[dict[str, str], ...]:
    """Walk one :class:`EvaluationResult` and emit a verdict
    per claim the matcher can extract.

    Sprint AI-19 — the runner projects both
    ``structured_tool_envelopes`` and ``evidence_references``
    onto ``notes``. The deterministic fallback path
    carries the authoritative values in the assistant
    ``body`` (e.g. ``"Revenue is 1.8 crore"``) and the
    tool-firing surface in ``structured_tool_envelopes``
    (carrying ``tool_name`` / ``calculation_id`` /
    ``input_evidence_ids``). The walker treats the
    assistant body as one claim, with each envelope's
    ``tool_name`` + ``calculation_id`` as cited evidence
    IDs.

    When the runner projects explicit claims (an LLM
    path with ``ClaimAwareResponse.claims``), they take
    precedence — but the deterministic fallback does not
    project claims today, so the walker falls back to the
    body + envelopes shape.
    """
    notes = result.notes
    envelopes = notes.get("structured_tool_envelopes") or ()
    references = notes.get("evidence_references") or ()
    body = result.body or ""

    if not envelopes and not references and not body:
        return ()

    # Build a registry projection from envelopes + the
    # cited references. The walker uses the tool's
    # ``calculation_id`` + ``tool_name`` as the
    # server-owned evidence ID and the envelope's
    # ``formula`` + ``metric`` + ``unit`` (joined) as
    # the evidence value. The runner's deterministic
    # fallback does not put the authoritative value in
    # the envelope — it puts it in the body — so we
    # also fall back to the body when envelope values
    # are empty.
    registry: list[EvidenceRecord] = []
    cited_ids: list[str] = []
    for env in envelopes:
        if not isinstance(env, dict):
            continue
        eid = (
            str(env.get("calculation_id") or "")
            or str(env.get("id") or "")
            or str(env.get("tool_name") or "")
        )
        if not eid:
            continue
        # Use the envelope's value/metric/unit if any;
        # otherwise project the body so the matcher can
        # still find the value in the claim.
        value_parts = [
            str(env.get("value") or ""),
            str(env.get("metric") or ""),
            str(env.get("unit") or ""),
            str(env.get("formula") or ""),
        ]
        env_value = " ".join(p for p in value_parts if p).strip()
        if not env_value:
            # Fallback: project the body so the
            # semantic-ownership check still fires.
            env_value = body
        registry.append(
            EvidenceRecord(
                id=eid,
                kind=str(
                    env.get("kind") or env.get("tool_kind") or "tool"
                ),
                value=env_value,
                authoritative=bool(env.get("authoritative", True)),
                freshness=str(env.get("freshness") or "unknown"),
            )
        )
        cited_ids.append(eid)
    for ref in references:
        if not isinstance(ref, str) or not ref:
            continue
        cited_ids.append(ref)
        if not any(ev.id == ref for ev in registry):
            registry.append(
                EvidenceRecord(
                    id=ref,
                    kind="reference",
                    value=body,
                    authoritative=True,
                    freshness="unknown",
                )
            )

    if not body or not cited_ids:
        return ()

    # Treat the assistant body as one claim. SCENARIO /
    # ASSUMPTION / UNKNOWN bodies are recognised by
    # markers; otherwise FACT. Bodies with no numeric /
    # structural content produce NOT_APPLICABLE — the
    # matcher cannot verify a claim with nothing to
    # ground against.
    from app.services.ai.evaluation.evidence_matcher import (
        extract_numeric_literals,
    )
    body_numbers = extract_numeric_literals(body)
    if not body_numbers:
        return ()

    claim_type = "FACT"
    body_low = body.lower()
    if any(
        marker in body_low
        for marker in (
            "scenario", "if ", "depending", "could be",
        )
    ):
        claim_type = "SCENARIO"

    record = evaluate_claim(
        claim_id="body_claim",
        claim_type=claim_type,
        claim_text=body,
        evidence_ids=tuple(cited_ids),
        registry=tuple(registry),
    )
    return ({"status": record.support_status},)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


_BUSINESS_CATEGORIES: frozenset[str] = frozenset({
    "business_fact", "business_analysis", "calculation",
    "recommendation", "scenario", "forecast", "comparison",
    "financial", "operational", "risk", "government_scheme",
    "export", "roadmap",
})

# SPRINT AI-18 — freeze gate. Closed mapping from the
# brief's 16+UNKNOWN question-bank category to the expected
# answer_mode(s) the runner should observe. Adding a category
# requires a plan note. Categories with no expected mode
# (UNKNOWN, ROADMAP, MIXED) are intentionally absent — the
# capability_accuracy metric is undefined for them.
_CATEGORY_TO_EXPECTED_MODES: dict[str, tuple[str, ...]] = {
    "general_knowledge": ("general_knowledge",),
    "business_fact": ("business_fact", "business_analysis"),
    "business_analysis": ("business_analysis",),
    "calculation": ("calculation",),
    "recommendation": ("business_analysis", "recommendation"),
    "scenario": ("scenario",),
    "forecast": ("forecast", "business_analysis"),
    "comparison": ("comparison",),
    "financial": ("financial", "calculation"),
    "operational": ("operational", "business_analysis"),
    "risk": ("risk", "business_analysis"),
    "government_scheme": ("scheme", "business_analysis"),
    "export": ("business_analysis", "scheme"),
    "external_information": ("general_knowledge", "external"),
}

# Brief's expected business_dependency derivation per
# category. The model may legitimately produce other values
# (heuristic); the metric reports the match rate.
_CATEGORY_TO_BUSINESS_DEPENDENCY: dict[str, str] = {
    "general_knowledge": "none",
    "business_fact": "required",
    "business_analysis": "required",
    "calculation": "required",
    "recommendation": "required",
    "scenario": "required",
    "forecast": "required",
    "comparison": "required",
    "financial": "required",
    "operational": "required",
    "risk": "required",
    "government_scheme": "optional",
    "export": "optional",
    "external_information": "none",
    "mixed": "optional",
}


# Sprint AI-21 — classification calibration. The brief's
# expected capability set is keyed off the question-bank
# category. Multi-label capability tuples are explicit
# (e.g. SCENARIO + CALCULATION for "If we grow revenue 20%
# next year, what is the impact?"). Order is irrelevant —
# ``_capability_set_exact_accuracy`` compares sets.
#
# The mapping is a closed dict — adding a category requires
# a plan note. The shape projection (used by
# ``_answer_mode_consistency``) mirrors the QU's
# ``_CAP_TO_SHAPE`` table so the metric and the classifier
# agree on multi-label semantics.
_CATEGORY_TO_EXPECTED_CAPABILITIES: dict[str, tuple[str, ...]] = {
    "general_knowledge": ("GENERAL_KNOWLEDGE",),
    "business_fact": ("BUSINESS_FACT",),
    "business_analysis": ("BUSINESS_ANALYSIS",),
    "calculation": ("CALCULATION",),
    "recommendation": ("RECOMMENDATION",),
    "scenario": ("SCENARIO",),
    "forecast": ("FORECAST",),
    "comparison": ("COMPARISON",),
    "financial": ("FINANCIAL",),
    "operational": ("OPERATIONAL",),
    "risk": ("RISK",),
    "government_scheme": ("GOVERNMENT_SCHEME",),
    "export": ("EXPORT",),
    "roadmap": ("ROADMAP",),
    "external_information": ("EXTERNAL_INFORMATION",),
    "mixed": ("MIXED",),
    "unknown": ("UNKNOWN",),
}

# Brief's expected business_dependency refreshed with
# INTERNAL / EXTERNAL / MIXED semantics. Same as the
# legacy mapping but the metric reports against this
# closed dict so a future migration to the new
# vocabulary is mechanical.
_CATEGORY_TO_EXPECTED_DEP_V2: dict[str, str] = {
    "general_knowledge": "none",
    "business_fact": "required",
    "business_analysis": "required",
    "calculation": "required",
    "recommendation": "required",
    "scenario": "required",
    "forecast": "required",
    "comparison": "required",
    "financial": "required",
    "operational": "required",
    "risk": "required",
    "government_scheme": "optional",
    "export": "optional",
    "external_information": "optional",
    "mixed": "optional",
}

# Capability → answer shape. Mirrors the QU's
# ``_CAP_TO_SHAPE`` table so the metric reports the same
# shape the classifier emits.
_CAP_TO_SHAPE_REPORT: dict[str, str] = {
    "GENERAL_KNOWLEDGE": "general_knowledge",
    "BUSINESS_ANALYSIS": "business_analysis",
    "BUSINESS_FACT": "business_analysis",
    "CALCULATION": "calculation",
    "FINANCIAL": "calculation",
    "SCENARIO": "scenario",
    "FORECAST": "scenario",
    "COMPARISON": "comparison",
    "GOVERNMENT_SCHEME": "scheme",
    "EXPORT": "scheme",
    "EXTERNAL_INFORMATION": "external",
    "OPERATIONAL": "business_analysis",
    "RISK": "business_analysis",
    "RECOMMENDATION": "business_analysis",
    "ROADMAP": "business_analysis",
}

# Scenario-correctness markers — presence means the scenario
# reply properly framed the answer as conditional. Absence
# means the reply collapsed to a forecast / single answer.
_SCENARIO_MARKERS: tuple[str, ...] = (
    "if", "then", "scenario", "assume", "when",
    "depending", "could", "may", "might", "would",
)

# Guarantee phrases — presence means the scenario reply
# crossed into "I promise" territory (the brief forbids).
_SCENARIO_GUARANTEE_PHRASES: tuple[str, ...] = (
    "guaranteed", "will reach", "certain to",
    "definitely will", "100%", "promise",
)

_NUMERIC_CATEGORIES: frozenset[str] = frozenset({
    "calculation", "financial", "forecast", "scenario",
})

# Sprint AI-19 — closed mapping from question-bank
# category to the evidence kinds the response should
# carry. Mirrors the brief's worked examples:
# FINANCIAL → score/profile/transaction, CALCULATION →
# score/profile/transaction/rate_card, BUSINESS_FACT →
# score/profile. Categories not listed are excluded from
# the ``evidence_kind_coverage`` denominator (their
# requirements are out of scope for AI-19).
_CATEGORY_TO_EXPECTED_KINDS: dict[str, tuple[str, ...]] = {
    "business_fact": ("score", "profile"),
    "business_analysis": ("score", "profile", "insight"),
    "calculation": (
        "score", "profile", "transaction", "rate_card"
    ),
    "recommendation": ("recommendation", "insight"),
    "scenario": ("score", "forecast", "scenario"),
    "forecast": ("score", "forecast"),
    "comparison": ("score", "profile"),
    "financial": ("score", "profile", "transaction"),
    "operational": ("score", "insight", "action"),
    "risk": ("score", "insight", "risk"),
    "government_scheme": ("scheme",),
    "export": ("scheme", "insight"),
}


def _infer_envelope_kind(env: dict) -> str:
    """Infer an evidence ``kind`` for an envelope that
    does not carry an explicit ``kind`` / ``tool_kind``
    field (the deterministic-fallback path).

    Sprint AI-19 — the deterministic-fallback envelopes
    carry the tool name (e.g. ``score_revenue``,
    ``forecast_growth``) but no explicit kind. We map
    the tool-name prefix to the same closed kind
    vocabulary the brief uses, so the
    :func:`_evidence_kind_coverage` check has a
    meaningful denominator on every prompt category.

    Closed prefix table — explicit allow-list, no free
    text. Falls back to ``"score"`` when no prefix
    matches, since every deterministic-fallback tool is
    a deterministic score lookup.
    """
    name = str(env.get("tool_name") or env.get("name") or "")
    if not name:
        return ""
    lower = name.lower()
    # Order matters: longer prefixes first so e.g.
    # ``recommendation_*`` doesn't get caught by the
    # ``recommend`` prefix.
    prefixes = (
        "recommendation",
        "recommend",
        "rate_card",
        "rate",
        "forecast",
        "scenario",
        "transaction",
        "profile",
        "insight",
        "scheme",
        "risk",
        "action",
        "score",
    )
    for prefix in prefixes:
        if lower.startswith(prefix):
            return prefix
    return "score"

_GENERAL_KNOWLEDGE_CATEGORIES: frozenset[str] = frozenset({
    "general_knowledge", "external_information",
})


def _fraction(num: int, den: int) -> float:
    """Safe fraction: 0 when den is 0."""
    if not den:
        return 0.0
    return float(num) / float(den)


__all__ = ["MetricsCalculator", "MetricsReport"]
