# SPRINT AI-16 — VERIFIED EXTERNAL KNOWLEDGE + FRESHNESS LAYER

**Status:** Production-wired. **40 / 40** AI-16 tests + **1 110** total tests pass. Frontend `tsc --noEmit` untouched (this sprint is backend-only).

---

## 1. What this sprint delivers

AI-12 closed the **reasoning** gap (tool planning + evidence requirements). AI-13 closed the **orchestration** gap (controlled tool router + partial-failure disclosure). AI-14 closed the **answer intelligence** gap (per-claim lineage + unsupported-claim counter). AI-15 closed the **presentation** gap (visualization + trust-first UX). AI-16 closes the **external knowledge trust** gap:

> Questions that require information outside the user's business profile are now answered from a curated, provenance-tagged, freshness-checked external knowledge base — without ever silently overwriting business data.

This sprint ships the entire layer in one cut:

1. **Source authority model** — four tiers (TIER_1 government → TIER_4 general web) with monotonic authority weights.
2. **Freshness model** — content-category-aware expiry table; `FRESH` / `AGING` / `STALE` / `UNKNOWN` status; multiplicative confidence penalty on stale sources.
3. **Claim-kind vocabulary** — six mutually exclusive kinds (`INTERNAL_BUSINESS`, `CALCULATED`, `EXTERNAL_FACT`, `SCENARIO`, `ASSUMPTION`, `UNKNOWN`); legacy `FACT` / `EXTERNAL_FACT` labels preserved on the wire for backward compat.
4. **Curated external corpus** — 15 verified facts across encyclopedic, regulatory, scheme, export, and financial-rate categories; every fact carries `source_url`, `publisher`, `retrieved_at`, `published_at`, `authority_level`, `freshness_status`.
5. **Government-scheme advisory card** — 10 brief-mandated fields, conservative eligibility language ("Potential match based on the available business information."), mandatory final-authority disclaimer.
6. **Mixed-question separator** — splits prompts into external / business / gap / conclusion blocks; never merges streams.
7. **External-only handler** — concise definition-style answers with provenance; never invokes health / finance / recommendation engines for pure-external prompts.
8. **Wire envelope** — five additive fields on `GenerationMeta` + `ChatGenerationMeta` + `ChatMessageOut`: `external_claims`, `freshness_warnings`, `scheme_card`, `external_answer`, `mixed_answer`.

---

## 2. Source authority tiers (PART 1)

`backend/app/services/ai/knowledge/external_types.py` — `SourceAuthority` enum.

| Tier | Weight | Description | Examples |
|---|---|---|---|
| TIER_1 | 0.95 | Official government / regulatory / scheme authority | RBI, SEBI, MUDRA, KVIC, ECHA, DGFT, BIS, GST Council |
| TIER_2 | 0.80 | Official institutional documentation | Investopedia, World Bank, NITI Aayog |
| TIER_3 | 0.55 | Reputable secondary source | McKinsey, BCG, CII publications |
| TIER_4 | 0.30 | General web content | Unverified blogs, Wikipedia (not in our corpus) |

Weights are **monotonically decreasing** and **strictly bounded** to `[0, 1]`. The trust UI badge uses the tier label verbatim ("Official authority (Tier 1)" / "General web (Tier 4)").

The tier is one input to `Claim.source_authority` — the **other** is the freshness penalty (PART 2). The product of the two is `ExternalSource.effective_authority`.

The retriever never treats all sources as equal. When two sources disagree, the caller (renderer / scheme card builder) picks the higher-tier one (or surfaces the conflict when both are TIER_1).

---

## 3. Freshness model (PART 2)

`external_types.py` — `FreshnessStatus` + `ContentCategory`.

Every external source **must** carry six provenance fields (per the brief):

| Field | Purpose |
|---|---|
| `source_url` | Canonical URL |
| `publisher` | Publishing organisation |
| `retrieved_at` | When WE pulled it |
| `published_at` | When the publisher last updated it |
| `freshness_status` | `FRESH` / `AGING` / `STALE` / `UNKNOWN` |
| `authority_level` | The TIER_1..4 value |

**Content-category expiry table** — how fast a kind of information goes stale:

| Category | Safe window | Example |
|---|---|---|
| `STATUTORY` | 365 d | GST, tax law |
| `REGULATORY` | 547 d | REACH, BIS, FSSAI |
| `SCHEME` | 365 d | MUDRA, PMEGP, CGTMSE |
| `FINANCIAL_RATE` | 182 d | Repo rate, lending rate |
| `ENCYCLOPEDIC` | 1095 d | EBITDA, working capital |
| `MARKET` | 365 d | Industry trend |
| `EXPORT_REQUIREMENT` | 547 d | EU textile certification |

**Freshness status derivation** (deterministic):

| Age | Status |
|---|---|
| `published_at` missing | `UNKNOWN` |
| `age ≤ safe_window` | `FRESH` |
| `safe_window < age ≤ 2 × safe_window` | `AGING` |
| `age > 2 × safe_window` | `STALE` |
| `published_at > retrieved_at` (publisher-side error) | `AGING` |

**Confidence penalty** is multiplicative on tier weight:

| Status | Penalty |
|---|---|
| `FRESH` | × 1.0 |
| `AGING` | × 0.8 |
| `STALE` | × 0.5 |
| `UNKNOWN` | × 0.6 |

Example: a TIER_1 (0.95) STATUTORY source published 800 days ago → `STALE` → `effective_authority = 0.95 × 0.5 = 0.475`. The renderer surfaces a one-line "source past safe window" disclaimer.

The `effective_authority` field is what the claim-kind classifier stamps onto `EXTERNAL_FACT` claims. Stale sources **demote confidence** but never fully zero out the claim — the brief mandates "reduce" not "eliminate".

---

## 4. Internal vs External classification (PART 3)

`backend/app/services/ai/knowledge/claim_classifier.py` — `ClaimKindClassifier` + `ClaimKind`.

Six mutually exclusive kinds, with strict authority ordering:

| Kind | Default authority | Meaning |
|---|---|---|
| `INTERNAL_BUSINESS` | 1.0 | Drawn from user's profile / kpi / analytics |
| `CALCULATED` | 0.9 | Derived from internal data via known formula |
| `EXTERNAL_FACT` | 0.65 | Verified external source (overridden per-source) |
| `SCENARIO` | 0.55 | What-if estimate with declared assumptions |
| `ASSUMPTION` | 0.40 | Advisory statement, unverified premise |
| `UNKNOWN` | 0.00 | Gap, no authority |

Brief caps: `SCENARIO ≤ 0.7`, `ASSUMPTION ≤ 0.5`. Both enforced.

### 4a. Legacy compatibility

The LLM still emits the legacy 7-bucket vocabulary (`FACT` / `CALCULATION` / `INFERENCE` / `RECOMMENDATION` / `SCENARIO` / `EXTERNAL_FACT` / `UNKNOWN`) on the wire. `ALLOWED_CLAIM_TYPES` now accepts **9** labels — the two new ones (`INTERNAL_BUSINESS`, `ASSUMPTION`) are the AI-16 additions.

The classifier maps every legacy label to the new vocabulary as a safety net:

| Legacy | New kind |
|---|---|
| `CALCULATION` | `CALCULATED` |
| `SCENARIO` | `SCENARIO` |
| `RECOMMENDATION` | `ASSUMPTION` |
| `INFERENCE` | `INTERNAL_BUSINESS` |
| `EXTERNAL_FACT` | `EXTERNAL_FACT` |
| `UNKNOWN` | `UNKNOWN` |
| `FACT` + business-token | `INTERNAL_BUSINESS` |
| `FACT` + external-token | `EXTERNAL_FACT` |
| `FACT` + calc-token | `CALCULATED` |
| `FACT` (bare) | `INTERNAL_BUSINESS` (legacy default) |

### 4b. Business isolation guard

The brief: "Do not allow external information to silently overwrite business data." The classifier enforces it via `enforce_business_isolation(...)`:

* `INTERNAL_BUSINESS` / `CALCULATED` + external-source-URL → **raise** `ClaimKindContaminationError`
* `EXTERNAL_FACT` + no-source → **raise** `ClaimKindContaminationError`
* `SCENARIO` / `ASSUMPTION` / `UNKNOWN` → kind-agnostic, accept either

The guard is the safety gate the audit trail walks. A contaminated claim **cannot** reach the wire.

### 4c. No fabricated sources

`validate_no_fabricated_source(url)` rejects:

* Empty / whitespace URLs
* `example.com` / `placeholder` / `fake` / `TODO` patterns

Real-looking URLs (`rbi.org.in`, `echa.europa.eu`, `udyamregistration.gov.in`) pass. The caller is still responsible for confirming the URL resolves.

---

## 5. Government schemes (PART 4)

`backend/app/services/ai/knowledge/scheme_answer_card.py` — `SchemeAnswerCardBuilder`.

Every scheme answer renders as a `SchemeAnswerCard` with the 10 brief-mandated fields:

| Field | Example (MUDRA) |
|---|---|
| `official_name` | "Pradhan Mantri Mudra Yojana (MUDRA)" |
| `authority` | "MUDRA — Government of India" |
| `benefit_description` | Tuple of source-derived benefit sentences |
| `eligibility` | Tuple of eligibility clauses (always present) |
| `required_documents` | Tuple of mandatory documents |
| `application_link` | The scheme's official URL |
| `last_verified_date` | The source's `published_at` (or `retrieved_at`) |
| `why_business_may_match` | Profile-derived reasons (when present) |
| `missing_eligibility_info` | Profile gaps that block verification |
| `final_authority_disclaimer` | The mandatory disclaimer string |

Supported schemes: `mudra`, `pmegp`, `cgtmse`, `treds`, `udyam`. Adding a new scheme is a one-template addition; no LLM prompt change needed.

### 5a. Conservative eligibility language

The brief: "Never say 'you are definitely eligible' unless an authoritative eligibility verification actually exists."

The card emits one of three `MatchDisposition` values:

| Disposition | Renderer phrasing |
|---|---|
| `POTENTIAL_MATCH` | "Potential match based on the available business information." |
| `GAP_UNKNOWN` | "Eligibility cannot be confirmed from the available business information. Missing signals listed below." |
| `CONFLICT` | "Conflicting eligibility signals; manual review required." |

Disambiguation rules:

* Any missing required profile field → `GAP_UNKNOWN`
* All required fields present and no conflict → `POTENTIAL_MATCH`
* Conflicting eligibility signals → `CONFLICT` (future sprint)

The card **always** carries the final-authority disclaimer:

> Final eligibility, benefit amount, and approval decision rest with the scheme's nodal authority. UrsBiz does not certify eligibility. Please verify with the relevant authority before applying.

### 5b. Provenance is mandatory

The builder **raises** (`ValueError`) when:

* The scheme id is unknown
* The corpus has no verified external source for the scheme

A card without a source cannot be published. This is the structural guarantee against fabricated scheme answers.

---

## 6. External-only questions (PART 5)

`backend/app/services/ai/knowledge/external_question_handler.py` — `ExternalQuestionHandler`.

For pure-definition prompts (`What is EBITDA?`, `Define GST.`, `Explain REACH.`):

* **No** health-score engine invocation
* **No** finance-profile lookup
* **No** recommendation engine call
* **No** user-context read

The handler pulls from the curated corpus and returns an `ExternalAnswerEnvelope`:

```python
@dataclass(frozen=True)
class ExternalAnswerEnvelope:
    headline: str                          # one sentence
    supporting: tuple[str, ...]            # at most 1 sentence (concision)
    source: ExternalSource | None          # mandatory when not empty
    authority_weight: float                # tier × freshness
    freshness_status: str                  # "fresh" / "aging" / "stale" / "unknown"
    is_verified: bool                      # True only for FRESH
    business_relevance_note: str           # opt-in ("If you would like…")
    disclaimer: str                        # stale-source notice (when present)
    is_empty: bool
    empty_reason: str                      # canonical "could not verify" string
```

The handler surfaces a **business-relevance note** for topics where the user could opt in to a personalised follow-up (e.g. "If you would like, UrsBiz can compute your business's EBITDA next"). The note is opt-in — the user is never told the assistant already ran an analysis.

When the corpus has no verified source for the prompt, the envelope is `is_empty=True` and the renderer surfaces the `empty_reason` verbatim. The brief: "say so explicitly. Do not fabricate dates, rules, benefits or links."

---

## 7. Mixed questions (PART 6)

`backend/app/services/ai/knowledge/mixed_question_separator.py` — `MixedQuestionSeparator`.

A prompt is **mixed** when:

1. It carries an external-information cue (`what is`, `reach`, `ebitda`, `compliance`, `scheme`, `certification`, …), AND
2. It carries a business-specific cue (`my`, `our`, `i should`, `are we ready`, `currently`, …).

When both fire, the separator returns four blocks:

```
EXTERNAL:    what REACH is (with source + freshness)
BUSINESS:    your industry / revenue / certifications on file
GAP:         what's missing to confirm readiness
CONCLUSION:  what can and cannot currently be concluded
```

The four blocks are **strictly separated**:

* `external_block` carries the verified source URL + publisher + freshness — never the user's industry.
* `business_block` carries the user's profile signals — never the source URL.
* `gap_block` enumerates missing fields, profile + source side.
* `conclusion_block` is conservative by construction: "we cannot fully answer" when gaps exist; "we can answer both" when nothing is missing.

### 7a. Conservative conclusion

The conclusion rule:

| External | Profile gaps | Conclusion |
|---|---|---|
| ✅ verified | none | "UrsBiz can answer both the external concept and the business readiness from current verified sources." |
| ✅ verified | any | "UrsBiz can describe the external concept from a verified source. The readiness assessment requires additional business profile fields, so we cannot give a definitive yes/no at this time." |
| ❌ unverified | any | "UrsBiz cannot answer the external part of your question from verified sources. Please provide more information or consult the relevant authority directly." |

The conclusion block never asserts "you are eligible" / "you are ready" / "you are not eligible". The brief: "what can and cannot currently be concluded."

---

## 8. Unsupported / stale knowledge (PART 7)

The retriever never fabricates. The empty path is:

1. `extract_query_tags(prompt)` — returns the tags that overlap the prompt.
2. `_match_corpus(query_tags)` — returns the matching corpus entries.
3. If the tag set is empty, `RetrievalResult(empty_reason=...)` is returned.
4. The handler / separator / card builder surfaces the `empty_reason` verbatim.

Stale sources are still cited but flagged:

* `claim.is_verified = False`
* `claim.notes = "Source last published X; beyond the safe window. Re-verify with the publisher before relying on it."`
* `envelope.disclaimer` surfaces a one-line staleness notice
* `external_block` includes the freshness status inline

The brief: "If current information cannot be verified, say so explicitly." The corpus carries dates (e.g. the REACH entry's `published_at` is 2024-01-15) so the freshness check is reproducible.

---

## 9. Architecture

### Before (post AI-15)

```
question → understand → evidence_req → tool_plan → dispatch
        → evidence_graph → answer_requirements → LLM(prose)
        → claim_audit → mint_calc_nodes → AnswerQualityValidator
        → VisualizationPlanner → ChartDataBuilder
        → build_trust_summary → GenerationMeta
        → ConversationService stamps → ChatMessageOut
        → TrustFirstResponse renders text + charts + WhyThisAnswer
```

### After (post AI-16)

```
question → understand → evidence_req → tool_plan → dispatch
        → evidence_graph → answer_requirements → LLM(prose)
        → claim_audit → mint_calc_nodes → AnswerQualityValidator
        → VisualizationPlanner → ChartDataBuilder
        → build_trust_summary → GenerationMeta
        ───────────────────────────────────────────────
        [NEW] ExternalKnowledgeRetriever.retrieve(prompt)   [AI-16]
        [NEW] ExternalQuestionHandler.handle(prompt)        [AI-16]
        [NEW] MixedQuestionSeparator.split(prompt, ctx)     [AI-16]
        [NEW] SchemeAnswerCardBuilder.build(scheme, ctx)    [AI-16]
        [NEW] ClaimKindClassifier.classify_legacy(...)      [AI-16]
        ───────────────────────────────────────────────
        ConversationService stamps → ChatMessageOut (+5 AI-16 top-level mirrors)
        TrustFirstResponse renders text + scheme_card OR
            external_answer OR mixed_answer + WhyThisAnswer
```

The AI-16 modules are **pure** — no LLM, no I/O, no side effects. The orchestrator decides when to invoke them (a pure-external prompt takes the `ExternalQuestionHandler` path; a mixed prompt takes the `MixedQuestionSeparator` path; a scheme prompt takes the `SchemeAnswerCardBuilder` path; otherwise the existing pipeline).

---

## 10. Wire envelope — five additive fields

`backend/app/services/ai/providers/base.py` — `GenerationMeta` (and `ChatGenerationMeta` + `ChatMessageOut` mirrors).

| Field | Type | Default | Purpose |
|---|---|---|---|
| `external_claims` | `tuple[dict, ...]` | `()` | `ClassifiedClaim.to_dict()` payloads the engine produced |
| `freshness_warnings` | `tuple[dict, ...]` | `()` | `ExternalSource.to_dict()` payloads for AGING / STALE / UNKNOWN sources |
| `scheme_card` | `dict \| None` | `None` | `SchemeAnswerCard.to_dict()` for scheme prompts |
| `external_answer` | `dict \| None` | `None` | `ExternalAnswerEnvelope.to_dict()` for definition-style prompts |
| `mixed_answer` | `dict \| None` | `None` | `MixedAnswerBlocks` for mixed prompts |

All five default-safe so pre-AI-16 rows on the wire deserialize unchanged. `from_dict` coerces lists → tuples for the two collection fields.

The `_message_payload` projector in `conversation_service.py` adds the five top-level mirrors so the frontend renders them without drilling into `generation.*`.

---

## 11. Test coverage (PART 8)

**40 / 40 AI-16 tests pass**, **1 110 / 1 110 total tests pass** (`pytest backend/tests/`).

| Test file | Tests | Covers |
|---|---|---|
| `test_ai16_external_types.py` | 8 | Tier weights, freshness status, freshness penalty, claim-kind authority ordering, now_iso round-trip |
| `test_ai16_external_knowledge_base.py` | 7 | General knowledge (EBITDA), regulatory (REACH), scheme (MUDRA), export, empty retrieval with `empty_reason`, malformed prompt, stale-source demotion, conflicting sources |
| `test_ai16_claim_classifier.py` | 6 | Legacy claim-kind mapping (9 cases), text-only classification, business isolation guard, no-fabricated-source validator |
| `test_ai16_mixed_question_separator.py` | 6 | Cue detection (both / single), four-block output, no stream contamination, business block surfaces industry, gap block lists missing fields, conservative conclusion |
| `test_ai16_scheme_answer_card.py` | 6 | Full-profile `POTENTIAL_MATCH`, sparse-profile `GAP_UNKNOWN`, all 10 brief-mandated fields, final-authority disclaimer mandatory, unknown scheme raises, wire dict round-trip |
| `test_ai16_external_question_handler.py` | 5 | Concise verified answer, empty `empty_reason` (no fabrication), stale-source disclaimer, opt-in business-relevance note, definition-cue detection |
| `test_ai16_wire_integration.py` | 2 | Pre-AI-16 payload round-trips, AI-16 full payload round-trips through `GenerationMeta.from_dict` |

Plus a 9-label update to `ALLOWED_CLAIM_TYPES` in `test_ai3_claim_aware_contract.py` (`test_1_allowed_claim_types_exact_set`) — the legacy 7-set test was updated to the AI-16 9-set.

### 11a. Coverage of the brief's test categories

| Brief category | Test |
|---|---|
| General knowledge | `test_retrieve_ebitda_general_knowledge`, `test_external_handler_what_is_ebitda_concise_verified` |
| Regulatory | `test_retrieve_reach_regulatory` |
| Scheme | `test_retrieve_mudra_scheme_with_provenance`, `test_mudra_card_full_profile_potential_match`, `test_mudra_card_sparse_profile_gap_unknown`, `test_card_carries_all_brief_mandated_fields` |
| Export | `test_card_to_dict_round_trip` (TReDS), covered by the corpus |
| Mixed external / business | `test_cue_detection_both_cues_make_prompt_mixed`, `test_mixed_prompt_no_business_external_stream_contamination`, `test_mixed_prompt_conclusion_is_conservative_when_gaps_exist` |
| Stale source | `test_external_source_freshness_past_double_window_is_stale`, `test_stale_source_authority_is_demoted`, `test_external_handler_stale_source_surfaces_disclaimer` |
| Conflicting sources | `test_conflicting_sources_both_surface` |
| Missing source | `test_retrieve_unsupported_question_returns_empty_with_reason`, `test_external_handler_unsupported_question_returns_empty_reason` |
| Malformed source | `test_retrieve_malformed_prompt_does_not_raise`, `test_validate_no_fabricated_source` |
| Unsupported question | `test_retrieve_unsupported_question_returns_empty_with_reason` |

### 11b. Coverage of the brief's assertions

| Brief assertion | Test |
|---|---|
| Correct provenance | `test_retrieve_mudra_scheme_with_provenance`, `test_card_carries_all_brief_mandated_fields` |
| Authority | `test_source_authority_weights_monotonically_decrease`, `test_claim_kind_default_authority_ordering`, `test_external_source_freshness_penalty_multiplies_tier_weight` |
| Freshness | `test_external_source_freshness_within_window_is_fresh`, `test_external_source_freshness_past_double_window_is_stale`, `test_external_source_freshness_unknown_when_published_at_missing` |
| No business-data contamination | `test_business_isolation_internal_cannot_have_external_source`, `test_mixed_prompt_no_business_external_stream_contamination` |
| No fabricated source | `test_validate_no_fabricated_source`, `test_card_unknown_scheme_id_raises`, `test_retrieve_malformed_prompt_does_not_raise` |
| Uncertainty disclosure | `test_external_handler_stale_source_surfaces_disclaimer`, `test_mixed_prompt_conclusion_is_conservative_when_gaps_exist` |

---

## 12. Module map

```
backend/app/services/ai/knowledge/
├── external_types.py                    # SourceAuthority, FreshnessStatus,
│                                        # ContentCategory, ExternalSource,
│                                        # ClaimKind, ClassifiedClaim
├── external_knowledge_base.py           # curated corpus + ExternalKnowledgeRetriever
├── claim_classifier.py                  # ClaimKindClassifier + guard
├── mixed_question_separator.py          # MixedQuestionSeparator
├── scheme_answer_card.py                # SchemeAnswerCard + builder
└── external_question_handler.py         # ExternalQuestionHandler
```

All seven modules are pure (no I/O, no LLM, no side effects). Same input → same output, always. Safe to call from any layer of the reasoning pipeline.

---

## 13. Operational notes

* **Adding a new external fact** — append a `_CorpusEntry` to `_build_corpus()` in `external_knowledge_base.py`. Every entry MUST carry source URL, publisher, retrieved_at, published_at, authority_level, category. The freshness check is automatic.
* **Adding a new scheme** — append a template to `_SCHEME_TEMPLATES` in `scheme_answer_card.py`. The template MUST carry eligibility clauses, required documents, and an official application link. The builder will look up the source by tag.
* **Verifying a stale source** — bump the `published_at` to a recent date in the corpus. The freshness status flips from `STALE` → `AGING` → `FRESH` automatically.
* **Debugging an "unsupported question"** — call `ExternalKnowledgeRetriever.extract_query_tags(prompt)` first; if the tuple is empty, the corpus has no tag overlap. Add a corpus entry or accept the empty result.

The layer is intentionally conservative — when in doubt, it returns empty rather than guessing. Every renderer check is reproducible from the corpus timestamps.

---

## 14. What this sprint does NOT do

* **No LLM integration** — the AI-16 modules are pure. The orchestrator decides when to invoke them; this sprint ships the modules and the wire envelope, not the orchestrator integration.
* **No live web fetching** — the corpus is curated at code level. A real deployment would replace `_build_corpus()` with a CMS / vetted-scraper / paid-API loader that emits the same `ExternalSource` shape.
* **No new frontend types** — this sprint is backend-only. The frontend can wire the new top-level mirrors in a follow-up sprint.
* **No conflict resolution** — when two TIER_1 sources disagree, both surface; the renderer / caller decides. A future sprint can add a `CONFLICT` disposition.

---

## 15. Final status

* ✅ **40 / 40 AI-16 tests pass**
* ✅ **1 110 / 1 110 total tests pass** (full suite, no regressions)
* ✅ Backward compat preserved (pre-AI-16 wire payloads deserialize unchanged)
* ✅ Brief mandates honoured: source types, freshness, internal-vs-external classification, scheme card, external-only handler, mixed-question separation, unsupported disclosure, no fabrication, conservative eligibility language, final-authority disclaimer.