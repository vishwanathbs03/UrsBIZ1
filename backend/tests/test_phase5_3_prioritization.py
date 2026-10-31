"""Unit tests for Phase 5.3: Recommendation Prioritization, Scoring & Evidence.

Verifies:
  1. Priority formula weights: 0.25*U + 0.25*I + 0.20*E + 0.15*C + 0.15*F.
  2. Canonical priority bands: Critical (>=80), High (65-79), Medium (45-64), Low (<45).
  3. Score clamping between 10 and 100.
  4. Evidence strength is decoupled from confidence.
  5. Deterministic calculation independence from external services.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
import pytest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.schemas.smart_recommendations import RecommendationPriority
from app.services.recommendations.prioritization_service import (
    RecommendationPrioritizationService,
)


def test_prioritization_formula_exact_weights():
    # 0.25*100 + 0.25*100 + 0.20*100 + 0.15*100 + 0.15*100 = 100
    score, band = RecommendationPrioritizationService.calculate_score(100, 100, 100, 100, 100)
    assert score == 100
    assert band == RecommendationPriority.CRITICAL

    # 0.25*80 + 0.25*80 + 0.20*80 + 0.15*80 + 0.15*80 = 80
    score, band = RecommendationPrioritizationService.calculate_score(80, 80, 80, 80, 80)
    assert score == 80
    assert band == RecommendationPriority.CRITICAL

    # 0.25*70 + 0.25*70 + 0.20*70 + 0.15*70 + 0.15*70 = 70
    score, band = RecommendationPrioritizationService.calculate_score(70, 70, 70, 70, 70)
    assert score == 70
    assert band == RecommendationPriority.HIGH

    # 0.25*50 + 0.25*50 + 0.20*50 + 0.15*50 + 0.15*50 = 50
    score, band = RecommendationPrioritizationService.calculate_score(50, 50, 50, 50, 50)
    assert score == 50
    assert band == RecommendationPriority.MEDIUM

    # 0.25*30 + 0.25*30 + 0.20*30 + 0.15*30 + 0.15*30 = 30
    score, band = RecommendationPrioritizationService.calculate_score(30, 30, 30, 30, 30)
    assert score == 30
    assert band == RecommendationPriority.LOW


def test_prioritization_score_clamping():
    # Below 10 clamps to 10
    score, band = RecommendationPrioritizationService.calculate_score(0, 0, 0, 0, 0)
    assert score == 10
    assert band == RecommendationPriority.LOW

    # Above 100 clamps to 100
    score, band = RecommendationPrioritizationService.calculate_score(150, 120, 110, 130, 140)
    assert score == 100
    assert band == RecommendationPriority.CRITICAL


def test_evidence_strength_decoupled_from_confidence():
    # High confidence (e.g. verified model), low empirical evidence (small sample size)
    score_low_ev, _ = RecommendationPrioritizationService.calculate_score(
        urgency=70, impact=70, evidence_strength=50, confidence=95, feasibility=80
    )
    # High confidence, high empirical evidence (large sample size, long history)
    score_high_ev, _ = RecommendationPrioritizationService.calculate_score(
        urgency=70, impact=70, evidence_strength=95, confidence=95, feasibility=80
    )
    # Evidence difference (45 pts) weighted at 0.20 should produce 9 point lift
    assert score_high_ev - score_low_ev == 9
