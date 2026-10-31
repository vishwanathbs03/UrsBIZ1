# Archive — Stale Submission Materials

This folder holds submission artifacts that **must not** appear in any
root-level submission path. The docx Master Operating Rules forbid the
following phrases in root-level files:

- "25+ schemes"
- "vector RAG" / "Hybrid RAG"
- "zero hallucination guarantee"
- "5,000+ RPS"
- "sub-50ms"
- "Redis"
- "AES-256"
- "100% test pass rate"
- "localhost" in any production-facing reference

## `UrsAi_Project_Structure_Details_End_to_End.pdf`

Quarantined on 2026-08-05 during H7.8A. Stale branding
("UrsAi (Atlas AI)", repo name `vishwanathbs03/UrsAii` — neither of
which matches the current canonical UrsBiz repository at
`vishwanathbs03/UrsAi-2`). No forbidden-phrase violations, but the
naming and the brand reference are misleading. The truthful
architecture narrative lives in:

- `docs/architecture-hackathon.svg`
- `docs/SYSTEM_ARCHITECTURE.md`
- `docs/ARCHITECTURE.md`

## `UrsBiz_AKKA_Hack4Good_2026.pptx`

The original pitch deck. **Quarantined on 2026-08-05 during the
H7.8A submission truth-repair pass** because it contained every
forbidden phrase above and a `localhost:3001` demo link.

## Replacement

Use the truthful, browser-native deck at:

- `frontend/public/pitch-deck.html`

It has been rewritten in H7.7 and again in H7.8A. No forbidden
phrases, no localhost links, every claim traceable to code or tests.

For the architecture overview, see:

- `docs/architecture-hackathon.svg`

For the full audit history, see:

- `H7_7_CLAIMS_AND_DOCUMENTATION_REPORT.md`
- `H7_8A_SUBMISSION_TRUTH_REPAIR_REPORT.md`
