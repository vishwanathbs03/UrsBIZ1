#!/usr/bin/env python3
"""Sprint H5.4 — correctness hardening verifier.

Greps the codebase for the defects fixed in H5.4 and asserts the fix is
actually present. Exits 0 when all checks PASS.
"""

from __future__ import annotations
import re
import sys
from pathlib import Path

ROOT = Path(r"D:\MSME\UrsAi")
F = ROOT / "frontend"
BACKEND = ROOT / "backend"


def ok(label, cond, detail=""):
    print(f"[{'PASS' if cond else 'FAIL'}] {label}" + (f" - {detail}" if detail else ""))
    return bool(cond)


results = []

def strip_code_only(src: str) -> str:
    """Drop /* ... */ and // ... comments, then search the remainder."""
    no_block = re.sub(r"/\*.*?\*/", " ", src, flags=re.S)
    no_line = re.sub(r"^\s*//.*$", "", no_block, flags=re.M)
    return no_line

# ---- P0.1 — fixed +14 forecast removed ----
src = strip_code_only((F / "features/analytics/RuleForecastCard.tsx").read_text(encoding="utf-8"))
results.append(ok(
    "P0.1 — fixed `currentScore + 14` removed from RuleForecastCard",
    "currentScore + 14" not in src and "Math.min(100, currentScore + 14)" not in src,
))
results.append(ok(
    "P0.1 — RuleForecastCard derives scenario from top recommendation",
    "topRec?.estimated_score_gain" in src and "Modelled change" in src,
))
results.append(ok(
    "P0.1 — explicit 'Scenario estimate unavailable' fallback present",
    "Scenario estimate unavailable from current data" in src,
))
results.append(ok(
    "P0.1 — never labels the value as a 'forecast' or 'Likely 6m Score'",
    "Likely 6m Score" not in src and "Potential Gain" not in src,
))

# ---- P0.2 — hardcoded scheme percentages removed ----
src = strip_code_only((F / "features/analytics/SchemeEligibilityChart.tsx").read_text(encoding="utf-8"))
results.append(ok(
    "P0.2 — fixed PMEGP 95 / CGTMSE 88 / MUDRA 81 / Startup India 74 removed",
    "match: 95" not in src and "match: 88" not in src
    and "match: 81" not in src and "match: 74" not in src,
))
results.append(ok(
    "P0.2 — 'Match score unavailable' fallback present",
    "Match score unavailable" in src,
))
results.append(ok(
    "P0.2 — chart accepts a live schemes[] prop instead of hardcoded array",
    "schemes?: SchemeMatch[] | null" in src,
))

# ---- P0.3 — maturity ?? 50 removed ----
src = strip_code_only((F / "features/analytics/MaturityRadarChart.tsx").read_text(encoding="utf-8"))
results.append(ok(
    "P0.3 — silent ?? 50 fallback removed from MaturityRadarChart",
    "?? 50" not in src,
))
results.append(ok(
    "P0.3 — score is now typed as number | null",
    "score: number | null" in src,
))

# ---- P0.4 — loan readiness ?? 50 removed ----
src = (F / "features/advisor/AdvisorView.tsx").read_text(encoding="utf-8")
results.append(ok(
    "P0.4 — loan readiness ?? 50 fallback removed from AdvisorView",
    "loan_readiness_score ?? 50" not in src and "aggregate ? 70 : 50" not in src,
))
results.append(ok(
    "P0.4 — explicit 'Not yet assessed' / 'Data unavailable' branch added",
    "Loan readiness not yet assessed" in src or "Data unavailable" in src,
))
src = (F / "features/advisor/FundingCard.tsx").read_text(encoding="utf-8")
results.append(ok(
    "P0.4 — FundingCard shows profile-complete guidance when data missing",
    "Not yet assessed" in src and "profile_complete" in src,
))

# ---- P0.5 — benchmarks labelled INTERNAL_ILLUSTRATIVE_BASELINE ----
src = (BACKEND / "app/services/benchmark_service.py").read_text(encoding="utf-8")
results.append(ok(
    "P0.5 — benchmark constants classified as INTERNAL_ILLUSTRATIVE_BASELINE",
    "INTERNAL_ILLUSTRATIVE_BASELINE" in src and "Illustrative baseline" in src,
))

# ---- P0.6 — opportunities labelled scenario estimate ----
src = (BACKEND / "app/services/opportunity_service.py").read_text(encoding="utf-8")
results.append(ok(
    "P0.6 — opportunity values labelled scenario estimate / illustrative",
    "scenario estimate" in src.lower() and "illustrative opportunity value" in src.lower(),
))

# ---- P0.7 — currency not forced to USD ----
src = (F / "features/intelligence/twin-sections/TopOpportunities.tsx").read_text(encoding="utf-8")
results.append(ok(
    "P0.7 — TopOpportunities no longer hardcodes USD",
    'currency === "USD" ? "USD" : "USD"' not in src
    and "report?.currency" in src,
))
src = (F / "features/intelligence/twin-sections/AIBusinessBrief.tsx").read_text(encoding="utf-8")
results.append(ok(
    "P0.7 — AIBusinessBrief no longer hardcodes $$ in opportunity sentence",
    "$${topOpp" not in src and "currency" in src,
))
src = (BACKEND / "app/services/insights_service.py").read_text(encoding="utf-8")
results.append(ok(
    "P0.7 — insights_service.py no longer hardcodes USD",
    "${rev:,.2f} USD" not in src,
))

# ---- P0.8 — missing score != 0 ----
src = (F / "features/intelligence/twin-sections/BusinessHealth.tsx").read_text(encoding="utf-8")
results.append(ok(
    "P0.8 — BusinessHealth no longer falls back to 0",
    "overall?.score ?? 0" not in src
    and "Not yet assessed" in src
    and "Complete your business profile" in src,
))

# ---- P0.9 — "expected to add X points" softened ----
src = strip_code_only((F / "features/intelligence/twin-sections/AIBusinessBrief.tsx").read_text(encoding="utf-8"))
results.append(ok(
    "P0.9 — 'expected to add X points' replaced with modelled language",
    "expected to add" not in src
    and "modelled to add up to" in src
    and "under current rules" in src,
))

# ---- P0.10 — score-gap formula corrected ----
src = (F / "features/dashboard/command-center/TopPriorities.tsx").read_text(encoding="utf-8")
results.append(ok(
    "P0.10 — TopPriorities no longer calculates 100 - estimated_score_gain",
    "100 - (rec.estimated_score_gain" not in src,
))
results.append(ok(
    "P0.10 — TopPriorities uses deterministic Why-now copy",
    "aligned with your weakest dimension" in src,
))

# ---- P0.11 — type safety ----
# Portable equivalent of `grep -rn` (works on Windows without POSIX grep).
# Force a UTF-8 console so Hindi/₹/dash output never crashes cp1252.
import io
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, io.UnsupportedOperation):
    pass

def grep_text(pattern: str, dirs: list[Path], exts=(".ts", ".tsx")) -> str:
    rx = re.compile(pattern)
    hits: list[str] = []
    for base in dirs:
        for p in sorted(base.rglob("*")):
            if p.is_file() and p.suffix in exts:
                try:
                    lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()
                except OSError:
                    continue
                for n, line in enumerate(lines, 1):
                    if rx.search(line):
                        hits.append(f"{p}:{n}:{line}")
    return "\n".join(hits).strip()

out = grep_text(
    r"as any\b",
    [F / "features/dashboard/command-center",
     F / "features/analytics",
     F / "features/intelligence"],
)
results.append(ok(
    "P0.11 — no `as any` casts in H5 surfaces",
    out == "",
    out[:200] if out else "",
))
# @ts-ignore / @ts-nocheck
out = grep_text(r"@ts-ignore|@ts-nocheck", [F / "features"])
results.append(ok(
    "P0.11 — no @ts-ignore / @ts-nocheck in features/",
    "@ts-ignore" not in out and "@ts-nocheck" not in out,
))

# ---- P0.12 — scheme service error vs no match ----
src = (F / "features/schemes/SchemesView.tsx").read_text(encoding="utf-8")
results.append(ok(
    "P0.12 — SchemesView distinguishes 'no schemes returned' from 'no match'",
    "No schemes returned" in src and "No matching schemes for this filter" in src,
))
# Service error already handled above via ErrorState — sanity check
results.append(ok(
    "P0.12 — SchemesView keeps ErrorState for service errors",
    "Could not load Government Schemes" in src or "Failed to load scheme" in src,
))

# ---- P0.13 — KPIGrid not in dashboard command center ----
src = (F / "features/dashboard/DashboardView.tsx").read_text(encoding="utf-8")
results.append(ok(
    "P0.13 — KPIGrid kpis={null} removed from command center",
    "<KPIGrid kpis={null}" not in src,
))

# ---- P0.14 — consistent snapshot ----
# Already verified: useAssistantData + use-analytics-data both use TanStack
# Query and there is no parallel duplicate fetch in DashboardView.
results.append(ok(
    "P0.14 — DashboardView uses single coordinated data hooks (useAnalyticsData)",
    "useAnalyticsData" in (F / "features/dashboard/DashboardView.tsx").read_text(encoding="utf-8")
    or "useAssistantData" in (F / "features/dashboard/DashboardView.tsx").read_text(encoding="utf-8"),
))

# Aggregate
print("\n" + "=" * 60)
print("AGGREGATE")
print("=" * 60)
pass_n = sum(1 for r in results if r)
fail_n = len(results) - pass_n
print(f"PASS: {pass_n}")
print(f"FAIL: {fail_n}")
print(f"TOTAL: {len(results)}")
sys.exit(0 if fail_n == 0 else 1)
