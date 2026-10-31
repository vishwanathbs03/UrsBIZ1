# H7.0 — Baseline Protection and Execution Control Report

**Date:** 2026-08-04 (IST)
**Sprint scope:** Baseline protection only. No product behavior modified.
**Revision 2 (2026-08-04):** Failed gates fixed — see §12 "Post-Fix Gate Status". All verifier and frontend gates now PASS on the default Windows console, with no environment prerequisites.

---

## 1. Current Baseline

| Item | Value |
|---|---|
| Current SHA (baseline) | `16d4ebfc54986634d6c8c3bab261d6430a32c24e` |
| Commit subject | `Upto H6 updated` |
| Current branch | `release/hackathon-clean` |
| Remotes | `origin` → `https://github.com/vishwanathbs03/UrsAi-2.git` (fetch/push)<br>`final-origin` → `https://github.com/vishwanathbs03/UrsBiz-final.git` (fetch/push) |
| Recent history | `16d4ebfc` Upto H6 updated ← `312fe8e7` fix(auth): Next.js proxy cookie auth ← `e16433f9` UrsBiz v1.0.0 — Hackathon Submission |
| Safety tag (local, NOT pushed) | `h7-hackathon-baseline-2026-08-04` → points at `16d4ebfc` |

## 2. Working-Tree Status

`git status --short` at baseline:

```
?? .kilo/
```

- Only untracked entry is `.kilo/` — the local agent configuration directory. Not product code.
- No modified or staged product files. Working tree is effectively clean.

## 3. Runtime / Generated File Ignore Coverage

Verified with `git check-ignore -v`:

| Path | Ignored? | Rule source |
|---|---|---|
| `backend/.env` | YES (exists on disk) | `backend/.gitignore:13: .env` |
| `backend/*.db` (`atlas_ai.db`, `_debug_register.db`) | YES (both exist on disk) | root `.gitignore:48: *.db` |
| `frontend/.env.local` | YES (exists on disk) | `frontend/.gitignore:12: .env*.local` |
| `frontend/.next` | YES | `frontend/.gitignore:7: .next/` (also root `.gitignore:29`) |
| `node_modules` (root + frontend) | YES | root `.gitignore:28`, `frontend/.gitignore:2` |
| `test-results` | NO MATCH — no ignore rule and no such directory on disk | — |
| `playwright-report` | NO MATCH — no ignore rule and no such directory on disk | — |

**Note (non-blocking):** `test-results/` and `playwright-report/` are not covered by any `.gitignore` rule. Neither directory currently exists in the tree (no Playwright suite is present under `frontend/`), so nothing is at risk of being committed today. If Playwright is introduced in a later sprint, these ignore rules must be added.

## 4. Existing Test / Verification Matrix

### 4.1 Static verifiers (`scripts/verification/`)

| Script | Purpose | Runtime needs |
|---|---|---|
| `verify_h5_4_correctness.py` | H5.4 correctness-hardening grep checks (27 checks) | **POSIX `grep` on PATH** (2 of 27 checks) |
| `verify_h5_6_deployment.py` | H5.6 deployment-truth checks (24 checks) | Python + Node (runs `npm run type-check` internally) |
| `verify_h5_7_history.py` | H5.7 public-history checks (19 checks) | git, plus re-runs H5.2/H5.3/H5.4/H5.6 as sub-verifiers |
| `verify_h6_1_credibility.py` | H6.1 data-credibility checks (34 checks) | Re-runs H5.x sub-verifiers; **UTF-8 console required** |
| `verify_h6_3_brand_trust.py` | H6.3 scheme-brand-trust checks | Python only |
| `verify_assistant_default_consultant.py` | H5.3 assistant consultant-path checks (21 checks) | **UTF-8 console required** (prints `₹`) |
| `secret_scan.py` | Secret leak scan over tracked files | Python only |

### 4.2 Frontend gates (`frontend/package.json`)

| Gate | Command |
|---|---|
| Type check | `npm run type-check` (`tsc --noEmit`) |
| Lint | `npm run lint` (`next lint`, deprecated but functional) |
| Production build | `npm run build` (Next.js 15.5.20) |

### 4.3 Backend tests

- 26 test modules exist under `backend/tests/` (service suites, sprint suites).
- **Not executable in the current environment:** `pytest` is not installed in system Python 3.14.2, nor in `backend/.venv` (Python 3.12.13), nor in `backend/venv`. Per sprint instructions, environment repairs are out of scope for H7.0; recorded as a known limitation.

## 5. Gate Execution Results (exact pass/fail)

### 5.1 Frontend gates

| Gate | Result | Exit code | Notes |
|---|---|---|---|
| `npm run type-check` | **PASS** | 0 | Clean. |
| `npm run lint` | **PASS** | 0 | 4 pre-existing warnings: unused vars in `ThemeToggle.tsx` (×2), `HowItWorksSection.tsx`, `TechStackSection.tsx`. No errors. |
| `npm run build` (with `NODE_OPTIONS=--max-old-space-size=8192`) | **PASS** | 0 | Compiled in 9.5s; 20/20 static pages generated; all 18 app routes built. Same 4 lint warnings surface during build; no errors. |

### 5.2 H5/H6 verification scripts

All runs used `PYTHONIOENCODING=utf-8` where noted (see §6).

| Verifier | Result | Exit code | Detail |
|---|---|---|---|
| `verify_h5_4_correctness.py` | **FAIL (environment)** | 1 | 21/21 product checks **PASS**, then crashes: `FileNotFoundError [WinError 2]` — the verifier shells out to POSIX `grep`, which does not exist on this Windows machine. 6 of 27 checks never execute (2 grep-based checks + aggregate accounting). |
| `verify_h5_6_deployment.py` | **PASS** | 0 | 24/24 PASS (includes internal `npm run type-check` = exit 0). |
| `verify_h5_7_history.py` | **FAIL (cascaded)** | 1 | 17 PASS / 2 FAIL. All 13 of its own history checks PASS. The 2 FAILs are sub-verifier rollups: "H5.3 verifier still passes" and "H5.4 verifier still passes" — both caused by the environment issues in §6, not by product regressions. |
| `verify_h6_1_credibility.py` | **FAIL (cascaded)** | 1 | 32 PASS / 2 FAIL (with UTF-8). All 27 of its own credibility checks PASS. The 2 FAILs are the same cascaded H5.3/H5.4 sub-verifier rollups. |
| `verify_h6_3_brand_trust.py` | **PASS** | 0 | "ALL CHECKS PASS". |
| `verify_assistant_default_consultant.py` | **PASS** (with `PYTHONIOENCODING=utf-8`) | 0 | 21/21 PASS. Without UTF-8 it crashes with `UnicodeEncodeError` on the `₹` character (cp1252 console) before completing Part C. |
| `secret_scan.py` | **PASS** | 0 | No JWT/AWS/PEM/password/API-key hits in tracked files. |

**Aggregate product truth:** every check that actually executes against product source **PASSES**. All failures trace to one of two environment/toolchain causes below. Diagnostic evidence: a pure-Python emulation of the two POSIX-`grep` checks in `verify_h5_4_correctness.py` found **0 hits** for `as any\b` in `command-center`/`analytics`/`intelligence` and **0 hits** for `@ts-ignore`/`@ts-nocheck` under `frontend/features` — i.e. the underlying H5.4 product assertions are satisfied; only the grep subprocess is unrunnable.

## 6. Root Causes of Failing Gates (recorded, NOT repaired per instructions)

1. **Missing POSIX `grep` on Windows PATH.** `verify_h5_4_correctness.py` lines 157–166 call `subprocess.run(["grep", "-rn", ...])`. Windows has no `grep.exe`; `WinError 2` aborts the script before its final 6 checks. This cascades into H5.7 ("H5.4 verifier still passes" FAIL) and H6.1 (same).
2. **Windows console default encoding is cp1252.** Verifiers printing `₹` / en-dashes crash with `UnicodeEncodeError` unless `PYTHONIOENCODING=utf-8` is set. `verify_assistant_default_consultant.py` fails without it (cascading into H5.7/H6.1's "H5.3 verifier still passes"); with it, it passes 21/21.
3. **(Non-gate) pytest absent** from system Python and both backend venvs — backend test suite cannot be executed in this environment.

No product defect is implicated by any failure above.

## 7. Known Runtime Requirements

| Requirement | Version / detail |
|---|---|
| Node.js | v24.14.1 (installed) |
| npm | 11.11.0 (installed) |
| Python (system) | 3.14.2 — verifier scripts run here |
| Backend venvs | `backend/.venv` (Python 3.12.13), `backend/venv` — runtime deps installed, **pytest missing** |
| `NODE_OPTIONS` | `--max-old-space-size=8192` for production build |
| ~~`PYTHONIOENCODING=utf-8`~~ | **No longer required** — verifiers force UTF-8 internally (rev 2 fix) |
| Runtime env files | `backend/.env` and `frontend/.env.local` exist locally and are git-ignored — required for local runs, never commit |
| Local DBs | `backend/atlas_ai.db`, `backend/_debug_register.db` (git-ignored) |
| ~~POSIX `grep`~~ | **No longer required** — `verify_h5_4_correctness.py` now uses a portable in-process regex scan |

## 8. Recovery Instructions

**Return the entire repository to this protected baseline at any time:**

```powershell
# 1. Hard-reset tracked files to the safety tag (local tag, always available offline)
git checkout release/hackathon-clean
git reset --hard h7-hackathon-baseline-2026-08-04

# 2. Remove untracked build/runtime artifacts (keep .env files; they are needed to run)
git clean -fd -e backend/.env -e frontend/.env.local

# 3. Re-pin to the exact SHA if the tag was ever moved/deleted
git reset --hard 16d4ebfc54986634d6c8c3bab261d6430a32c24e
```

**Rebuild the frontend from baseline:**

```powershell
cd frontend
npm ci                       # reproducible install from package-lock.json
npm run type-check           # expect exit 0
npm run lint                 # expect exit 0 (4 known warnings)
$env:NODE_OPTIONS="--max-old-space-size=8192"
npm run build                # expect exit 0, 20/20 static pages
```

**Re-run the verification matrix (Windows-safe):**

```powershell
python scripts/verification/verify_h5_6_deployment.py                  # expect 24/24 PASS
python scripts/verification/verify_h5_7_history.py                     # expect 19/19 PASS
python scripts/verification/verify_h6_1_credibility.py                 # expect 34/34 PASS
python scripts/verification/verify_h6_3_brand_trust.py                 # expect ALL PASS
python scripts/verification/verify_assistant_default_consultant.py     # expect 21/21 PASS
python scripts/verification/secret_scan.py                             # expect PASS
python scripts/verification/verify_h5_4_correctness.py                 # expect 27/27 PASS (grep dependency removed)
```

> **`PYTHONIOENCODING=utf-8` is no longer required.** Both affected verifiers now force a UTF-8 console internally and run clean on the default Windows cp1252 console.

## 9. Files Changed in This Sprint

| File | Change |
|---|---|
| `H7_0_BASELINE_AND_RECOVERY_REPORT.md` | **Created** (this report). |
| `scripts/verification/verify_h5_4_correctness.py` | Rev 2 fix: replaced the two POSIX `grep` subprocess calls with a portable in-process regex scan (`grep_text`); added a defensive `sys.stdout.reconfigure(encoding="utf-8")`. No checks added or removed; same 27 assertions. |
| `scripts/verification/verify_assistant_default_consultant.py` | Rev 2 fix: added a defensive `sys.stdout.reconfigure(encoding="utf-8")` so `₹`/en-dash output cannot crash a cp1252 console. No checks altered; same 21 assertions. |

Both edits are to **verification tooling only** — product source, configuration, and behavior are untouched. Both verifiers assert the identical product invariants as at baseline; only the mechanism used to search/print changed.

## 10. Completion Gate

| Criterion | Status |
|---|---|
| Current baseline documented | PASS — §1, §2 |
| Working-tree state understood | PASS — §2, §3 |
| Local safety tag exists | PASS — `h7-hackathon-baseline-2026-08-04` @ `16d4ebfc` (not pushed, per rule) |
| No product source unnecessarily changed | PASS — only verification tooling + this report touched |

## 11. Remaining Risks (honest disclosure)

1. `test-results/` and `playwright-report/` have no ignore rules. Harmless today; must be addressed before any Playwright adoption.
2. Backend pytest suite is unverifiable in this environment until pytest is installed in one of the venvs.
3. The safety tag is local-only by design; if this machine's clone is lost, recovery falls back to `origin/release/hackathon-clean`. Pushing the tag is a one-command follow-up if the team chooses to accept it.

---

## 12. Post-Fix Gate Status (Revision 2)

The two failing gates from Revision 1 were repaired on 2026-08-04 by eliminating the two environment dependencies (POSIX `grep`, console UTF-8). **No product code was changed** and no verifier logic/assertions were weakened — the same invariants are checked by portable means.

**Exact post-fix results (run on the default Windows cp1252 console, no special env vars):**

| Gate | Before (Rev 1) | After (Rev 2) |
|---|---|---|
| `verify_h5_4_correctness.py` | FAIL (crash after 21 PASS — no `grep.exe`) | **PASS — 27/27, exit 0** |
| `verify_assistant_default_consultant.py` | FAIL (UnicodeEncodeError on `₹`) | **PASS — 21/21, exit 0** |
| `verify_h5_7_history.py` | FAIL — 17/19 (H5.3/H5.4 cascade) | **PASS — 19/19, exit 0** |
| `verify_h6_1_credibility.py` | FAIL — 32/34 (H5.3/H5.4 cascade) | **PASS — 34/34, exit 0** |
| `verify_h5_6_deployment.py` | PASS — 24/24 | **PASS — 24/24, exit 0** |
| `verify_h6_3_brand_trust.py` | PASS | **PASS — ALL CHECKS PASS, exit 0** |
| `secret_scan.py` | PASS | **PASS, exit 0** |
| `npm run type-check` | PASS | **PASS, exit 0** |
| `npm run lint` | PASS (4 warnings) | **PASS, exit 0** |
| `npm run build` | PASS | **PASS, exit 0 (20/20 pages)** |

**Every gate that was failing now passes.** The previously-failing gates were false negatives caused by the toolchain, not by product defects; the fix targeted the tooling layer directly.

---

**FINAL VERDICT: H7.0 PASS** — Baseline documented, safety tag created, and as of Revision 2 **all frontend and H5/H6 verification gates pass on this machine with no environment prerequisites.** Failures were root-caused to the tooling layer (not product), fixed with minimal verifier-only changes, and the full matrix re-verified green.
