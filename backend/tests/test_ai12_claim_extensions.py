"""Tests for SPRINT AI-12 — Claim dataclass extensions.

Three additive fields: ``calculation_ids``, ``source_authority``,
``status``. The tests assert:

  * default construction still works (legacy callers),
  * ``to_dict()`` carries the three new fields,
  * the dataclass stays ``frozen=True``.
"""
from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from app.services.ai.providers.claim_schema import Claim


class TestClaimExtensions:

    def test_default_construction_is_safe(self) -> None:
        """Legacy 5-arg construction must keep working."""
        c = Claim(text="x", claim_type="FACT")
        assert c.calculation_ids == ()
        assert c.source_authority == 0.0
        assert c.status == "active"

    def test_new_fields_default_safe(self) -> None:
        c = Claim(text="x", claim_type="FACT")
        assert c.calculation_ids == ()
        assert c.source_authority == 0.0
        assert c.status == "active"

    def test_full_construction(self) -> None:
        c = Claim(
            text="Revenue is ₹1.5 Cr",
            claim_type="CALCULATION",
            calculation_ids=("calc_growth_42",),
            source_authority=0.95,
            status="active",
        )
        assert c.calculation_ids == ("calc_growth_42",)
        assert c.source_authority == 0.95
        assert c.status == "active"

    def test_frozen_contract_preserved(self) -> None:
        c = Claim(text="x", claim_type="FACT")
        with pytest.raises(FrozenInstanceError):
            c.status = "superseded"  # type: ignore[misc]

    def test_to_dict_carries_three_new_fields(self) -> None:
        from app.services.ai.providers.claim_schema import ClaimAwareResponse
        car = ClaimAwareResponse(
            claims=(Claim(
                text="x",
                claim_type="CALCULATION",
                calculation_ids=("c1",),
                source_authority=0.9,
                status="active",
            ),),
        )
        d = car.to_dict()
        claim_d = d["claims"][0]
        assert claim_d["calculation_ids"] == ["c1"]
        assert claim_d["source_authority"] == 0.9
        assert claim_d["status"] == "active"
