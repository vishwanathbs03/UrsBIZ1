#!/usr/bin/env python3
"""Sprint H5.7 — Public Git History Closure verifier.

Confirms:
  Part 1 — current remote / branch / HEAD documented.
  Part 2 — exact commit SHAs where H5.5-flagged history artifacts live.
  Part 4 — current tree is clean (no tracked .db, cookies, env,
    bundle, frontend/c, frontend/tmp; secret_scan passes).
  Part 6 — all current regression verifiers + npm gates pass.

The verifier does NOT rewrite history. It produces a structured
report so the user can decide on filter-repo vs orphan-branch.
"""

from __future__ import annotations
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(r"D:\MSME\UrsAi")
FRONTEND = ROOT / "frontend"


def ok(label, cond, detail=""):
    print(f"[{'PASS' if cond else 'FAIL'}] {label}" + (f" - {detail}" if detail else ""))
    return bool(cond)


def shell(cmd, cwd=None, timeout=60):
    return subprocess.run(
        cmd, cwd=cwd or str(ROOT), capture_output=True, text=True, timeout=timeout
    )


results = []

# --- Part 1 — submission repo identity ---
res = shell(["git", "remote", "-v"])
origin_url = next(
    (line.split()[1] for line in res.stdout.splitlines()
     if line.startswith("origin") and "(push)" in line),
    "<unknown>",
)
results.append(ok(
    "Part 1 — submission remote is github.com/vishwanathbs03/UrsAi-2.git",
    "UrsAi-2" in origin_url,
    origin_url,
))

res = shell(["git", "branch", "--show-current"])
# H5.7 §5 Path A recommends `release/hackathon-clean` as the
# canonical submission branch; accept it as the source of truth.
branch = res.stdout.strip()
results.append(ok(
    "Part 1 — current branch is the canonical submission branch",
    branch in {"main", "release/hackathon-clean"},
    branch,
))

res = shell(["git", "rev-parse", "HEAD"])
head = res.stdout.strip()
results.append(ok("Part 1 — HEAD captured", bool(head), head[:12]))

res = shell(["git", "rev-parse", "origin/main"])
origin_main = res.stdout.strip()
# Note: we do NOT assert HEAD equals origin's main SHA in this verifier.
# explicitly says the existing remote may carry history that needs
# scrubbing; the user is expected to push a clean branch. We only
# assert that origin/main is parseable and document its current SHA.
results.append(ok(
    "Part 1 — origin/main captured (HEAD may differ; see H5.7 §5)",
    bool(origin_main),
    f"origin/main={origin_main[:12]} HEAD={head[:12]}",
))

# --- Part 2 — historical artifact audit ---
# .db / sqlite — use --diff-filter=A --name-status so each commit shows
# as a block starting with `A\t<path>` lines after the commit line.
res = shell(["git", "log", "--all", "--pretty=format:COMMIT %H %s", "--name-status", "--",
             "*.db", "*.sqlite", "*.sqlite3"])
db_commits = []
current_sha = None
for line in res.stdout.splitlines():
    if line.startswith("COMMIT "):
        current_sha = line.split()[1]
    elif line.startswith("A\t") and current_sha:
        db_commits.append((current_sha, line.split("\t", 1)[1]))
results.append(ok(
    "Part 2 — historical commit containing .db / sqlite flagged",
    any("9a6f8ac" in sha for sha, _ in db_commits),
    f"db commits={[(c[0][:8], p) for c, p in db_commits]}",
))

# frontend/c/ + frontend/tmp/ in history
res = shell(["git", "log", "--all", "--pretty=format:%H", "--diff-filter=A", "--name-only", "--",
             "frontend/c/Users/Win/", "frontend/tmp/"])
history_leak_commits = []
for line in res.stdout.splitlines():
    if len(line) == 40 and all(c in "0123456789abcdef" for c in line):
        history_leak_commits.append(line)
results.append(ok(
    "Part 2 — historical commit containing frontend/c/ + frontend/tmp/ flagged",
    any(s.startswith("71361d0") for s in history_leak_commits),
    f"leak commits={[s[:8] for s in history_leak_commits]}",
))

# cookies.txt, .env, .bundle.js in history
res = shell(["git", "log", "--all", "--pretty=format:%H %s", "--diff-filter=A", "--name-only", "--",
             "cookies.txt", "*.env", "*.bundle.js"])
other_history = res.stdout.strip()
results.append(ok(
    "Part 2 — no cookies.txt / .env / .bundle.js in history",
    not other_history,
    other_history[:200] if other_history else "clean",
))

# --- Part 4 — current tree clean ---
res = shell(["git", "ls-files"])
tracked = res.stdout.splitlines()
tracked_db = [p for p in tracked if p.endswith((".db", ".sqlite", ".sqlite3"))]
tracked_cookies = [p for p in tracked if p.endswith("cookies.txt")]
tracked_env = [p for p in tracked if p.endswith(".env")]
tracked_bundle = [p for p in tracked if p.endswith(".bundle.js")]
tracked_leaks = [p for p in tracked if p.startswith(("frontend/c/", "frontend/tmp/"))]
results.append(ok("Part 4 — no .db / .sqlite tracked at HEAD", not tracked_db))
results.append(ok("Part 4 — no cookies.txt tracked at HEAD", not tracked_cookies))
results.append(ok("Part 4 — no .env tracked at HEAD", not tracked_env))
results.append(ok("Part 4 — no *.bundle.js tracked at HEAD", not tracked_bundle))
results.append(ok("Part 4 — no frontend/c/ + frontend/tmp/ tracked at HEAD", not tracked_leaks))

# secret_scan
res = shell(["python", str(ROOT / "scripts/verification/secret_scan.py")])
results.append(ok(
    "Part 4 — secret_scan.py reports no JWT/AWS/PEM/API-key hits",
    "No JWT/AWS/PEM/password/API-key hits" in res.stdout and res.returncode == 0,
))

# --- Part 6 — regression matrix ---
for script, label, expected_pass in [
    ("scripts/verify_sprint_h5_2.py", "H5.2 verifier", "PASS: 140"),
    ("scripts/verification/verify_assistant_default_consultant.py", "H5.3 verifier", "PASS: 21"),
    ("scripts/verification/verify_h5_4_correctness.py", "H5.4 verifier", "PASS: 27"),
    ("scripts/verification/verify_h5_6_deployment.py", "H5.6 verifier", "PASS: 24"),
]:
    res = shell(["python", str(ROOT / script)], timeout=180)
    pass_line = next((l for l in res.stdout.splitlines() if l.startswith("PASS:")), "")
    fail_line = next((l for l in res.stdout.splitlines() if l.startswith("FAIL:")), "")
    results.append(ok(
        f"{label} still passes",
        expected_pass in pass_line and "FAIL: 0" in fail_line and res.returncode == 0,
        f"{pass_line} / {fail_line}",
    ))

# npm gates
env = dict(os.environ); env["NODE_OPTIONS"] = "--max-old-space-size=8192"
for script in ("type-check", "lint"):
    res = subprocess.run(
        ["npm.cmd", "run", script],
        cwd=str(FRONTEND), capture_output=True, text=True, timeout=180, env=env,
    )
    results.append(ok(f"npm run {script}", res.returncode == 0, f"exit={res.returncode}"))

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
