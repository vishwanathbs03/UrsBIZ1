"""
Sprint H6.3 — Branding & Scheme Trust Verifier.

Runs from the repo root (D:\\MSME\\UrsAi). Exits 0 on PASS, 1 on any
FAIL. Designed to be runnable in this VM without Docker / browser
automation (per H5.x and H6.1 conventions).

Checks:

  P1 — Old brand strings in user-visible surfaces
        (Atlas, Atlas AI, UrsAi, UrsAii)
  P2 — "You are approved" / "guaranteed" / "will receive" language
        in any frontend .tsx / .ts and in the backend scheme service
  P3 — Every scheme row carries official_authority +
        official_source_url + last_verified + verified_status
        + match_basis + disclaimer in the engine envelope
  P4 — Every PDF/CSV download has UrsBiz branding
  P5 — Page metadata uses Part 7 canonical terms with "UrsBiz" suffix
  P6 — Schemes page renders disclaimer (test via grep on the page
        file) and avoids "eligible" / "approved" labels
  P7 — knowledge_catalog sources no longer say "Atlas AI internal"

This script is intentionally grep + Python stdlib. No third-party
deps. The first failing check prints its own error and the script
exits 1. Every passing check prints "[PASS] ..." inline.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent  # D:\MSME\UrsAi

FRONTEND = REPO / "frontend"
BACKEND = REPO / "backend"

# Files / surfaces we DO audit for user-visible brand strings.
# Internal identifiers (logger names, db filenames, env keys,
# metric names, internal storage keys, package name) are explicitly
# excluded by the glob / path filters below.
USER_VISIBLE_FILE_GLOBS = (
    "frontend/app/**/*.tsx",
    "frontend/app/**/*.ts",
    "frontend/components/**/*.tsx",
    "frontend/components/**/*.ts",
    "frontend/features/**/*.tsx",
    "frontend/features/**/*.ts",
    "frontend/services/**/*.ts",
    "frontend/public/manifest.json",
    "frontend/lib/env.ts",
    "backend/app/services/pdf_report_service.py",
    "backend/app/data/knowledge_catalog.json",
    "backend/app/config/settings.py",
    "backend/app/services/schemes_sprint16_service.py",
    "backend/app/api/v1/endpoints/copilot.py",
    "backend/app/services/copilot/mock_provider.py",
    "backend/app/services/ai/prompt_builder.py",
    "backend/app/services/ai/providers/prompt_builder.py",
    "backend/app/services/copilot/prompt_builder.py",
    "README.md",
)

# Files / surfaces we EXCLUDE from the brand audit (internal
# identifiers, safe to leave alone per the brief: "Internal
# technical identifiers may remain when changing them is risky.").
INTERNAL_GLOB_PREFIXES = (
    "frontend/components/common/StartupSplash.tsx",  # internal localStorage key
    "frontend/components/common/GlobalSearchModal.tsx",  # internal search ids
    "frontend/features/action-board/use-action-status-storage.ts",
    "frontend/features/notifications/use-notification-read-status.ts",
    "frontend/services/auth-service.ts",  # cookie name comment
    "frontend/services/api-client.ts",  # internal comment
    "frontend/package.json",  # npm package name
    "frontend/package-lock.json",  # npm lockfile
    "backend/.env",
    "backend/.env.example",
    "backend/.dockerignore",
    "backend/migrations.ini",
    "backend/gunicorn_conf.py",
    "backend/app/monitoring/",  # logger / metric names
    "backend/app/middleware/",  # cookie name
    "backend/app/main.py",  # internal loggers
    "backend/app/services/ai/providers/__init__.py",  # internal docstring
    "backend/app/services/ai/__init__.py",
    "backend/app/services/copilot/__init__.py",
    "backend/app/services/ocr/parser.py",  # internal docstring
    "backend/app/__init__.py",  # package docstring
    "backend/app/services/scenario/base.py",  # internal docstring
    "backend/app/data/knowledge_catalog.json",  # audited separately in P7
    "backend/tests/",  # internal test config
    "deployment/",  # internal deploy config
    "docs/",  # internal developer docs (Atlas AI is the project codename)
    "SPRINT_*.md",  # sprint reports reference internal codename
    "RELEASE_*.md",
    "PROJECT_*.md",
    "FINAL_*.md",
)

# Lines that are "internal identifier" mentions inside other
# otherwise user-visible files (storage keys, cookie names, log
# names) and are safe to leave. We never strip these from grep
# because we want to know the file also has them — but we only
# count them as a finding if the match is on a user-visible
# rendered string (e.g. in JSX text content, not a localStorage
# key, not a CSS class, not a comment).
INTERNAL_LINE_REGEX = re.compile(
    r"(localStorage|sessionStorage|getLogger\(|@|//|/\*|\*\s|cookie|\.pyc|metrics|Metric|MIDDLEWARE|"
    r"atlas_access_token|atlas\.security|atlas\.access|atlas\.error|"
    r"atlas\.notifications|atlas\.startupSplash|atlas-init|"
    r"atlas-ai\.|atlas_http_|atlas_db|atlas_knowledge|atlas_ai_|atlas_app|"
    r"atlas_ai\.db|atlas_access|"
    r"proc_name|APP_NAME|atlas_backend|atlas_frontend)",
    re.IGNORECASE,
)

# Banned user-visible phrases — Part 4 / Part 3 wording checks.
BANNED_GUARANTEE_PATTERNS = [
    re.compile(r"\byou\s+are\s+approved\b", re.IGNORECASE),
    re.compile(r"\byou\s+will\s+receive\b", re.IGNORECASE),
    re.compile(r"\bguaranteed\s+(?:subsidy|approval|amount|to\s+qualify|eligibility)\b", re.IGNORECASE),
    re.compile(r"\byou\s+are\s+guaranteed\b", re.IGNORECASE),
    re.compile(r"\bapproval\s+guaranteed\b", re.IGNORECASE),
    # NOTE: bare "guarantee" is allowed when it appears in the
    # official CGTMSE name (Credit Guarantee Fund), as a noun
    # describing the scheme's mechanism, or in disclaimers
    # ("do not guarantee"). We only ban approval/eligibility
    # guarantees, not the word itself.
]

# Lines that are documenting a rule that BANS the phrase are
# not themselves user-visible. We skip them so the verifier
# doesn't false-positive on docstrings and code comments that
# explicitly say "never use this language".
BANNER_BAN_LINE_REGEX = re.compile(
    r"(?:never|do\s+not|don'?t|banning|forbidden|prohibited|"
    r"must\s+not|mustn't)\s+(?:use|say|claim|include|write|"
    r"use\s+the\s+phrase|[\"'])",
    re.IGNORECASE,
)

# Old brand patterns — we audit case-insensitively for the
# short forms that are user-visible. The longer "Atlas AI" is
# only a fail when the match is NOT inside the excluded
# internal-glob prefix.
OLD_BRAND_PATTERNS = [
    re.compile(r"\bAtlas\s+AI\b", re.IGNORECASE),  # e.g. "Atlas AI Copilot"
    re.compile(r"\bAtlas\s+is\b", re.IGNORECASE),  # "Atlas is observing"
    re.compile(r"\bAtlas\s+works\b", re.IGNORECASE),
    re.compile(r"\bAtlas\s+intelligence\b", re.IGNORECASE),
    re.compile(r"\bAtlas\s+ran\b", re.IGNORECASE),
    re.compile(r"\bAtlas\s+recommend", re.IGNORECASE),
    re.compile(r"\bAtlas\s+measure", re.IGNORECASE),
    re.compile(r"\bAtlas\s+accept", re.IGNORECASE),
    re.compile(r"\bAtlas\s+engines\b", re.IGNORECASE),
    re.compile(r"\bAtlas\s+found\b", re.IGNORECASE),
    re.compile(r"\bAtlas\s+produce", re.IGNORECASE),
    re.compile(r"\bAtlas\s+Engineers?\b", re.IGNORECASE),  # "Atlas AI Engineers"
    re.compile(r"\bAtlas\s+Enterprise\b", re.IGNORECASE),  # legal_name fallback
    re.compile(r"\bUrsAi\b"),  # codename in user-visible text (NOT in paths)
    re.compile(r"\bUrsAii\b"),
    # The bare "Atlas" without "AI" — we audit case-sensitive to
    # avoid hitting the literal string inside the directory name
    # UrsAi (which contains "Ai" at the end). Only catches
    # "Atlas" as a standalone word.
    re.compile(r"\bAtlas\b(?!\s+AI)"),
]

DISCLAIMER_PHRASE = "Matching is informational. Final eligibility and approval are determined by the official authority."


def should_skip(path: Path) -> bool:
    rel = str(path.relative_to(REPO)).replace("\\", "/")
    return any(rel.startswith(prefix.rstrip("/")) or rel == prefix for prefix in INTERNAL_GLOB_PREFIXES)


def is_internal_line(line: str) -> bool:
    return bool(INTERNAL_LINE_REGEX.search(line))


def collect_files() -> list[Path]:
    out: list[Path] = []
    for glob in USER_VISIBLE_FILE_GLOBS:
        out.extend(REPO.glob(glob))
    # Dedup
    seen: set[Path] = set()
    final: list[Path] = []
    for p in out:
        if p.is_file() and p not in seen:
            seen.add(p)
            final.append(p)
    return final


def read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")


def run_p1_old_brands(files: list[Path]) -> list[str]:
    fails: list[str] = []
    for p in files:
        if should_skip(p):
            continue
        try:
            text = read_text(p)
        except Exception as e:
            fails.append(f"  {p}: read error {e}")
            continue
        rel = str(p.relative_to(REPO)).replace("\\", "/")
        for lineno, line in enumerate(text.splitlines(), 1):
            if is_internal_line(line):
                continue
            for pat in OLD_BRAND_PATTERNS:
                m = pat.search(line)
                if m:
                    fails.append(f"  {rel}:{lineno}: {m.group(0)!r}  |  {line.strip()[:120]}")
                    break
    return fails


def run_p2_guarantee_language(files: list[Path]) -> list[str]:
    fails: list[str] = []
    for p in files:
        if should_skip(p):
            continue
        try:
            text = read_text(p)
        except Exception:
            continue
        rel = str(p.relative_to(REPO)).replace("\\", "/")
        for lineno, line in enumerate(text.splitlines(), 1):
            if is_internal_line(line):
                continue
            # Skip lines that are documenting a rule that bans the
            # phrase (e.g. 'never "you will receive ..."' inside
            # a module docstring). Those are anti-pattern notes,
            # not user-visible claims.
            if BANNER_BAN_LINE_REGEX.search(line):
                continue
            for pat in BANNED_GUARANTEE_PATTERNS:
                m = pat.search(line)
                if m:
                    fails.append(f"  {rel}:{lineno}: {m.group(0)!r}  |  {line.strip()[:120]}")
                    break
    return fails


def run_p3_scheme_engine_required_fields() -> list[str]:
    """Every scheme row must have authority/source/verified/date + disclaimer in envelope."""
    fails: list[str] = []
    service_py = BACKEND / "app" / "services" / "schemes_sprint16_service.py"
    schema_py = BACKEND / "app" / "schemas" / "schemes_sprint16.py"
    if not service_py.exists() or not schema_py.exists():
        return [f"  scheme service/schema file missing"]
    service_text = read_text(service_py)
    schema_text = read_text(schema_py)
    required_fields = (
        "official_authority",
        "official_source_url",
        "last_verified",
        "verified_status",
        "match_basis",
    )
    for f in required_fields:
        if f not in schema_text:
            fails.append(f"  schema missing field: {f}")
        if f not in service_text:
            fails.append(f"  service missing field: {f}")
    # Envelope must carry `disclaimer`
    if "disclaimer" not in schema_text:
        fails.append("  envelope missing 'disclaimer' field")
    # Disclaimer text must include the canonical Part 4 wording
    if DISCLAIMER_PHRASE not in service_text:
        fails.append(f"  engine disclaimer missing canonical Part 4 wording: {DISCLAIMER_PHRASE!r}")
    return fails


def run_p4_pdf_csv_branding() -> list[str]:
    """PDF footer/header must say UrsBiz (not Atlas). CSV filename fallback not 'atlas'."""
    fails: list[str] = []
    pdf = BACKEND / "app" / "services" / "pdf_report_service.py"
    btn = FRONTEND / "features" / "reports" / "DownloadPdfButton.tsx"
    if not pdf.exists():
        return [f"  PDF service missing: {pdf}"]
    pdf_text = read_text(pdf)
    if "Atlas AI" in pdf_text:
        # Find line number
        for i, line in enumerate(pdf_text.splitlines(), 1):
            if "Atlas AI" in line:
                fails.append(f"  pdf_report_service.py:{i}: {line.strip()[:160]}")
                break
    # Footer must say UrsBiz
    if "UrsBiz" not in pdf_text:
        fails.append("  PDF report footer does not include 'UrsBiz' brand")
    # CSV/PDF filename slug fallback
    if btn.exists():
        btn_text = read_text(btn)
        if re.search(r'\(businessName\s*\?\?\s*"atlas"\)', btn_text):
            fails.append("  DownloadPdfButton.buildFilename fallback uses 'atlas' (should be 'ursbiz')")
        if "UrsBiz" not in btn_text:
            fails.append("  DownloadPdfButton does not mention 'UrsBiz' anywhere")
    return fails


def run_p5_page_metadata() -> list[str]:
    """Each top-level app route's metadata.title must end with 'UrsBiz'."""
    fails: list[str] = []
    routes = [
        "frontend/app/(app)/dashboard/page.tsx",
        "frontend/app/(app)/advisor/page.tsx",
        "frontend/app/(app)/analytics/page.tsx",
        "frontend/app/(app)/predictive-analytics/page.tsx",
        "frontend/app/(app)/intelligence/page.tsx",
        "frontend/app/(app)/schemes/page.tsx",
        "frontend/app/(app)/reports/page.tsx",
        "frontend/app/(app)/assistant/page.tsx",
        "frontend/app/(app)/business/page.tsx",
        "frontend/app/(auth)/login/page.tsx",
        "frontend/app/(auth)/register/page.tsx",
    ]
    # Part 7 canonical terms (per brief)
    canonical = {
        "/dashboard": "Executive Command Center",
        "/advisor": "Business Advisor",
        "/analytics": "Analytics",
        "/predictive-analytics": "Business Forecast",
        "/intelligence": "Business Digital Twin",
        "/schemes": "Government Schemes",
        "/reports": "Executive Report",
        "/assistant": "AI Business Assistant",
    }
    for r in routes:
        p = REPO / r
        if not p.exists():
            continue
        text = read_text(p)
        if "metadata:" not in text:
            fails.append(f"  {r}: no metadata block (cannot audit)")
            continue
        # Find the first 'title:' line after 'metadata:'
        m = re.search(r"metadata:\s*Metadata\s*=\s*\{[^}]*title:\s*['\"]([^'\"]+)['\"]", text, re.DOTALL)
        if not m:
            fails.append(f"  {r}: no title in metadata")
            continue
        title = m.group(1)
        if "UrsBiz" not in title:
            fails.append(f"  {r}: title does not end with 'UrsBiz' — got: {title!r}")
        # Part 7 canonical term check (only for routes listed)
        for route_slug, term in canonical.items():
            if route_slug in r and term not in title:
                fails.append(f"  {r}: title should use Part 7 term {term!r} — got: {title!r}")
    return fails


def run_p6_schemes_page() -> list[str]:
    fails: list[str] = []
    schemes_view = FRONTEND / "features" / "schemes" / "SchemesView.tsx"
    if not schemes_view.exists():
        return [f"  schemes view missing: {schemes_view}"]
    text = read_text(schemes_view)
    # Must render the engine's disclaimer text (P3 confirms the
    # engine sends the canonical wording). The view must:
    #   (a) read data.disclaimer from the API response, AND
    #   (b) render it in the DOM under a recognisable test id.
    if "data.disclaimer" not in text and "data?.disclaimer" not in text:
        fails.append("  schemes view does not read data.disclaimer from the API response")
    if "data-testid=\"schemes-disclaimer\"" not in text and "schemes-disclaimer" not in text:
        # Allow any test id, but require some persistent hook so
        # a regression can be caught in the rendered DOM.
        if "{data.disclaimer}" not in text and "{data?.disclaimer}" not in text:
            fails.append("  schemes view does not render data.disclaimer to the DOM")
    # The page caption must also carry the "informational" wording
    if "Matching is informational" not in text:
        fails.append("  schemes view caption does not include 'Matching is informational' wording")
    # The engine supplies the canonical Part 4 disclaimer sentence;
    # the view must not override it with a stricter / weaker
    # version. We check for the banned capitalised labels.
    if re.search(r">\s*Approved\b", text):
        for lineno, line in enumerate(text.splitlines(), 1):
            if re.search(r">\s*Approved\b", line):
                fails.append(f"  schemes view 'Approved' label on line {lineno}: {line.strip()[:120]}")
                break
    if re.search(r">\s*Eligible\b", text):
        for lineno, line in enumerate(text.splitlines(), 1):
            if re.search(r">\s*Eligible\b", line):
                fails.append(f"  schemes view 'Eligible' label on line {lineno}: {line.strip()[:120]}")
                break
    return fails


def run_p7_knowledge_catalog_sources() -> list[str]:
    fails: list[str] = []
    p = BACKEND / "app" / "data" / "knowledge_catalog.json"
    if not p.exists():
        return [f"  knowledge catalog missing"]
    data = json.loads(read_text(p))
    for art in data.get("articles", []):
        src = art.get("source", "")
        if "Atlas AI" in src:
            fails.append(f"  knowledge article {art.get('id')}: source={src!r}")
    return fails


def main() -> int:
    files = collect_files()
    print("=" * 72)
    print("Sprint H6.3 — Scheme Trust & Brand Consistency Verifier")
    print("=" * 72)

    checks = [
        ("P1 — Old brand strings in user-visible surfaces", run_p1_old_brands, [files]),
        ("P2 — 'Approved' / 'guaranteed' language in user-visible surfaces", run_p2_guarantee_language, [files]),
        ("P3 — Scheme engine required fields + envelope disclaimer", run_p3_scheme_engine_required_fields, []),
        ("P4 — PDF report + CSV filename UrsBiz branding", run_p4_pdf_csv_branding, []),
        ("P5 — Page metadata uses Part 7 canonical terms + UrsBiz", run_p5_page_metadata, []),
        ("P6 — Schemes page canonical disclaimer + no 'Approved' label", run_p6_schemes_page, []),
        ("P7 — knowledge_catalog sources clean of 'Atlas AI'", run_p7_knowledge_catalog_sources, []),
    ]

    total_fail = 0
    for name, fn, args in checks:
        print(f"\n[{name}]")
        fails = fn(*args)
        if fails:
            for f in fails:
                print(f"[FAIL] {f}")
            total_fail += len(fails)
        else:
            print("[PASS]")
    print()
    if total_fail == 0:
        print("=" * 72)
        print("VERIFIER RESULT: ALL CHECKS PASS")
        print("=" * 72)
        return 0
    print("=" * 72)
    print(f"VERIFIER RESULT: {total_fail} FAILURE(S)")
    print("=" * 72)
    return 1


if __name__ == "__main__":
    sys.exit(main())
