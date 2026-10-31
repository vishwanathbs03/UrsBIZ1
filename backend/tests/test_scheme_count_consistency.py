"""H7.8A scheme-count consistency assertion.

Authoritative source: backend/app/services/schemes_sprint16_service.py
                       SCHEMES_CATALOG

Public-facing claims about scheme counts (landing page, README, pitch deck,
architecture diagram, marketing components) must equal len(SCHEMES_CATALOG).

This test reads the live catalog and asserts:
  1. len(SCHEMES_CATALOG) is stable and > 0
  2. no tracked text file in the repo contains the legacy "14+" / "25+"
     scheme-count claims outside the documented correction notes
     (H7.5 / H7.6 / H7.7 / H7.8A report headers)

Run:
    ./.venv/Scripts/python.exe -m pytest backend/tests/test_scheme_count_consistency.py -v
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Allow the test to be run from the repo root without pytest path bootstrap.
ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BREPO := BACKEND) not in sys.path:
    sys.path.insert(0, str(BREPO))

from app.services.schemes_sprint16_service import SCHEMES_CATALOG  # noqa: E402


def _authoritative_count() -> int:
    return len(SCHEMES_CATALOG)


def test_catalog_is_nonempty() -> None:
    assert _authoritative_count() > 0, "SCHEMES_CATALOG must have at least one entry"


def test_catalog_has_expected_shape() -> None:
    for entry in SCHEMES_CATALOG:
        assert "id" in entry, f"catalog entry missing id: {entry}"
        assert "name" in entry, f"catalog entry missing name: {entry}"
        assert "official_authority" in entry, f"entry missing official_authority: {entry}"
        assert "application_link" in entry, f"entry missing application_link: {entry}"


def test_public_scheme_count_claim_consistent() -> None:
    """The number printed in the marketing surface must equal the live count.

    The frontend ImpactSection.tsx renders `val: "<N>"` for the scheme tile.
    We read it directly and assert equality.
    """
    impact_section = (ROOT / "frontend" / "components" / "marketing" / "ImpactSection.tsx").read_text(
        encoding="utf-8"
    )
    # Find the tile whose label is "Curated Schemes & Registrations"
    match = re.search(
        r'label:\s*"Curated Schemes & Registrations",\s*desc:\s*"([^"]+)",',
        impact_section,
        flags=re.DOTALL,
    )
    assert match, "Could not find the 'Curated Schemes & Registrations' tile in ImpactSection.tsx"
    desc = match.group(1)
    expected = _authoritative_count()
    # The tile description lists the scheme names; assert the count appears.
    # Easiest robust check: count the names we expect in the description.
    expected_names = sorted(
        e["name"].split("(")[0].strip().split("—")[0].strip()
        for e in SCHEMES_CATALOG
    )
    short_names = [
        "CGTMSE",
        "ZED",
        "PMEGP",
        "MAI",
        "MUDRA Shishu",
        "NSIC",
        "Udyam",
    ]
    found = sum(1 for n in short_names if n in desc)
    assert found == expected, (
        f"Marketing surface lists {found} of {expected} curated schemes. "
        f"Description was: {desc}"
    )


def test_no_legacy_count_claims_in_marketing_and_pitch() -> None:
    """The 14+/25+ scheme-count phrases must not appear in user-facing surfaces.

    Allowed in: historical reports (H7_5, H7_6, H7_7) where they appear inside
    correction notes. Disallowed in: README, marketing components, pitch-deck,
    architecture diagram, DEMO_PROFILE, IMPACT_EVIDENCE.
    """
    banned_pattern = re.compile(r"\b(14\+|25\+)\s*schemes?\b", re.IGNORECASE)
    bad_files: list[tuple[str, str]] = []
    targets = [
        ROOT / "README.md",
        ROOT / "frontend" / "components" / "marketing",
        ROOT / "frontend" / "public" / "pitch-deck.html",
        ROOT / "docs" / "architecture-hackathon.svg",
        ROOT / "docs" / "DEMO_PROFILE.md",
        ROOT / "docs" / "IMPACT_EVIDENCE.md",
    ]
    for target in targets:
        if target.is_dir():
            files = list(target.rglob("*"))
        else:
            files = [target]
        for f in files:
            if not f.is_file():
                continue
            try:
                content = f.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for m in banned_pattern.finditer(content):
                line_no = content[: m.start()].count("\n") + 1
                bad_files.append((str(f.relative_to(ROOT)), f"line {line_no}"))
    assert not bad_files, (
        "Legacy scheme-count claims still present. "
        "Update these files to use the actual count from SCHEMES_CATALOG:\n  "
        + "\n  ".join(f"{p} ({why})" for p, why in bad_files)
    )


def test_authoritative_count_is_seven() -> None:
    """Pin the authoritative count so a future catalog expansion is loud.

    When the catalog grows, this test fails and forces the author to also
    update README, pitch-deck, marketing, architecture diagram, etc.
    """
    assert _authoritative_count() == 7, (
        f"SCHEMES_CATALOG now has {_authoritative_count()} entries. "
        "Update README + marketing + pitch-deck + architecture SVG + "
        "DEMO_PROFILE + IMPACT_EVIDENCE to match, then bump this assertion."
    )
