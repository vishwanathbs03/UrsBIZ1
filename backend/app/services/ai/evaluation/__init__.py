"""SPRINT AI-18 — Universal AI Evaluation Harness.

Public surface.
"""
from app.services.ai.evaluation.adversarial_fixtures import (
    AdversarialAssertion,
    AdversarialCase,
    AdversarialKind,
    adversarial_by_kind,
    adversarial_kinds,
    all_adversarial_cases,
)
from app.services.ai.evaluation.evidence_matcher import (
    CONTRADICTED,
    ClaimRecord,
    EvidenceAuditEvent,
    EvidenceRecord,
    NOT_APPLICABLE,
    PARTIALLY_SUPPORTED,
    SUPPORTED,
    SUPPORT_STATUSES,
    UNSUPPORTED,
    classify_support_status,
    contains_semantic_value,
    evaluate_claim,
    extract_numeric_literals,
    is_fabricated_id,
    to_audit_event,
)
from app.services.ai.evaluation.data_quality_profiles import (
    DataQualityProfile,
    all_profiles,
    get_profile,
)
from app.services.ai.evaluation.followup_scripts import (
    FollowUpScript,
    ScriptTurn,
    TurnAssertion,
    all_scripts,
    get_script,
)
from app.services.ai.evaluation.golden_set import (
    GOLDEN_CASES,
    GoldenCase,
    GoldenTool,
    all_golden_cases,
    get_case,
)
from app.services.ai.evaluation.metrics_calculator import (
    MetricsCalculator,
    MetricsReport,
)
from app.services.ai.evaluation.provider_failure_scenarios import (
    FailureKind,
    FailureOutcome,
    ProviderFailureScenario,
    all_failure_scenarios,
    failure_kinds,
)
from app.services.ai.evaluation.question_bank import (
    QuestionCategory,
    QuestionEntry,
    all_questions,
    category_coverage,
    category_vocabulary,
    questions_by_category,
)
from app.services.ai.evaluation.runner import (
    EvaluationResult,
    EvaluationRunner,
)


__all__ = [
    # question bank
    "QuestionCategory",
    "QuestionEntry",
    "all_questions",
    "category_coverage",
    "category_vocabulary",
    "questions_by_category",
    # golden set
    "GoldenCase",
    "GoldenTool",
    "GOLDEN_CASES",
    "all_golden_cases",
    "get_case",
    # follow-up scripts
    "FollowUpScript",
    "ScriptTurn",
    "TurnAssertion",
    "all_scripts",
    "get_script",
    # adversarial
    "AdversarialAssertion",
    "AdversarialCase",
    "AdversarialKind",
    "all_adversarial_cases",
    "adversarial_by_kind",
    "adversarial_kinds",
    # provider failures
    "FailureKind",
    "FailureOutcome",
    "ProviderFailureScenario",
    "all_failure_scenarios",
    "failure_kinds",
    # data quality profiles
    "DataQualityProfile",
    "all_profiles",
    "get_profile",
    # runner
    "EvaluationResult",
    "EvaluationRunner",
    # metrics
    "MetricsCalculator",
    "MetricsReport",
    # Sprint AI-20 — tool-minimality metrics.
    # ``MetricsReport.unnecessary_tool_calls`` and
    # ``MetricsReport.unnecessary_tool_request_rate``
    # are read directly off the report object's
    # attribute, so no public symbol is added here.
    # evidence matcher (Sprint AI-19)
    "ClaimRecord",
    "EvidenceRecord",
    "EvidenceAuditEvent",
    "SUPPORTED",
    "PARTIALLY_SUPPORTED",
    "UNSUPPORTED",
    "CONTRADICTED",
    "NOT_APPLICABLE",
    "SUPPORT_STATUSES",
    "extract_numeric_literals",
    "contains_semantic_value",
    "is_fabricated_id",
    "classify_support_status",
    "evaluate_claim",
    "to_audit_event",
]
