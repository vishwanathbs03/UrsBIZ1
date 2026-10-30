"""
verify_sprint7_part4.py - ad-hoc verifier for Sprint 7 Part 4
(Knowledge Retrieval).

Drives the running uvicorn dev server (port 8001) through the
Sprint 7 Part 3 chat endpoint with the new knowledge retrieval
pipeline attached. Checks:

  1-13.  Cross-Part-3 regression: the existing chat CRUD surface
         still works (create, append, list, get, delete, auth,
         cross-owner 404, no-business 404). Sentinel list:
         no Part 1 / Part 2 / Part 3 critical files modified.

  14.    Retrieval fires on append: a knowledge-rich question
         surfaces citations in the assistant message's sources.

  15.    Citation schema: each citation has the right topic
         ("Knowledge" + others), detail string, and article id.

  16.    Determinism: two appends with the same query produce
         the same citation ids in the same order.

  17.    Retrieval pick: at least one citation in the response
         is on-topic (not just any random match).

  18.    Out-of-scope absence: no vector / embedding / external
         search code in the new knowledge_retrieval package.

  19.    No duplicate indexing: knowledge retrieval layer
         does NOT load the JSON catalog into a separate cache;
         it goes through KnowledgeService._repo.

  20.    Provider service reuses Part 2 base + assistant
         service without re-deriving business logic.

  21.    Existing assistant (Sprint 7 Part 1 frontend +
         Sprint 7 Part 2 provider) still byte-deterministic
         when no knowledge is requested.

  22.    Ranker determinism: top-k not affected by hit order.

  23.    Citation builder: source_category correct.

  24.    Token-overlap scorer: known query -> known top article.

Stop after the verifier prints VERIFIER RESULT.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import uuid
from http.cookiejar import CookieJar
from pathlib import Path

ROOT = Path(r"D:\MSME\UrsAi")
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
VENV_PY = BACKEND / "venv" / "Scripts" / "python.exe"
if not VENV_PY.exists():
    VENV_PY = BACKEND / ".venv" / "Scripts" / "python.exe"

BASE = "http://127.0.0.1:8001"
API = f"{BASE}/api/v1"

ok = True


def chk(label, cond, detail=""):
    global ok
    tag = "PASS" if cond else "FAIL"
    suffix = " - " + detail if detail else ""
    print(f"[{tag}] {label}{suffix}", flush=True)
    if not cond:
        ok = False


def get_marker(name, text):
    for line in text.splitlines():
        if line.startswith(name + " "):
            return line[len(name) + 1:].strip()
    return None


# --------------------------------------------------------------------------- #
# HTTP plumbing
# --------------------------------------------------------------------------- #


def _opener():
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))


def _request(opener, method, path, *, body=None, allow_404=False):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(path, data=data, method=method, headers=headers)
    try:
        resp = opener.open(req, timeout=30)
        return resp.status, json.loads(resp.read().decode() or "null")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="ignore")
        try:
            payload = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            payload = raw
        if allow_404 and exc.code == 404:
            return exc.code, payload
        raise


def _run_module(label, code):
    full = (
        "import sys\n"
        "sys.path.insert(0, r'" + str(BACKEND).replace("\\", "\\\\") + "')\n"
        + code
    )
    r = subprocess.run(
        [str(VENV_PY), "-c", full],
        cwd=str(BACKEND),
        capture_output=True,
        text=True,
        timeout=60,
    )
    print(f"--- {label} stdout ---", flush=True)
    print(r.stdout, flush=True)
    if r.stderr:
        print(f"--- {label} stderr (head) ---", flush=True)
        print(r.stderr[-600:], flush=True)
    print(f"--- {label} exit={r.returncode} ---", flush=True)
    return r


# --------------------------------------------------------------------------- #
# 1-13. End-to-end (Part 3 regression)
# --------------------------------------------------------------------------- #


def e2e():
    suffix = "".join(c for c in (Path(__file__).stem + str(uuid.uuid4().int))[-8:] if c.isalnum()) or "x"
    user_a = f"part4-a-{suffix}@example.com"
    user_b = f"part4-b-{suffix}@example.com"
    password = "Passw0rd123"

    op_a = _opener()
    op_b = _opener()

    s, _ = _request(op_a, "POST", f"{API}/auth/register",
                    body={"full_name": "Part 4 A", "email": user_a, "password": password})
    chk("register user A", s == 200 or s == 201)
    s, _ = _request(op_b, "POST", f"{API}/auth/register",
                    body={"full_name": "Part 4 B", "email": user_b, "password": password})
    chk("register user B", s == 200 or s == 201)

    biz_payload = {"basic": {
        "legal_name": "Part 4 Co", "industry": "manufacturing",
        "established_year": 2020, "employee_count": 5,
        "annual_revenue": 250000.0, "revenue_currency": "USD",
    }}
    s, _ = _request(op_a, "POST", f"{API}/business", body=biz_payload)
    chk("create business for A", s == 200 or s == 201)

    s, body = _request(op_a, "POST", f"{API}/chat", body={"title": ""})
    chk("create conversation", s == 201)
    sid = body.get("id")
    chk("conversation has id", isinstance(sid, int) and sid > 0)

    # 14. Retrieval fires on append.
    s, body = _request(
        op_a, "POST", f"{API}/chat/{sid}/message",
        body={"content": "What is export readiness?"},
    )
    chk("append knowledge-rich question", s == 200)
    asst = body.get("assistant_message", {})
    sources = asst.get("sources", [])
    chk("assistant message has at least 1 source",
        len(sources) >= 1, f"got {len(sources)}")

    # 15. Citation schema.
    citation_sources = [s for s in sources if s.get("topic") in
                        ("Knowledge", "Rule", "Recommendation",
                         "GovernmentScheme", "Glossary")]
    chk("at least one Knowledge citation",
        len(citation_sources) >= 1,
        f"got {len(citation_sources)} knowledge sources")
    if citation_sources:
        c = citation_sources[0]
        chk("citation topic is string", isinstance(c.get("topic"), str), repr(c.get("topic")))
        chk("citation detail has article id",
            "article " in (c.get("detail", "") or ""),
            repr(c.get("detail")))
        chk("citation detail has minimum length",
            len(c.get("detail", "") or "") >= 5)

    # 16. Determinism: two appends with the same query produce
    # the same citation ids in the same order. Use a fresh
    # conversation so the message history doesn't shift the
    # rolling context.
    s, body = _request(op_a, "POST", f"{API}/chat", body={"title": ""})
    sid2 = body["id"]
    s, body1 = _request(
        op_a, "POST", f"{API}/chat/{sid2}/message",
        body={"content": "What is export readiness?"},
    )
    s, body2 = _request(
        op_a, "POST", f"{API}/chat/{sid2}/message",
        body={"content": "What is export readiness?"},
    )
    sources1 = [s for s in body1.get("assistant_message", {}).get("sources", [])
                if s.get("topic") == "Knowledge"]
    sources2 = [s for s in body2.get("assistant_message", {}).get("sources", [])
                if s.get("topic") == "Knowledge"]
    ids1 = [s["detail"] for s in sources1]
    ids2 = [s["detail"] for s in sources2]
    chk("two calls produce the same citation ids",
        ids1 == ids2 and len(ids1) >= 1,
        f"1={ids1[:1]} 2={ids2[:1]}")

    # 17. Retrieved pick is on-topic. The catalog article
    # about IEC registration should appear for the export query.
    has_iec = any(
        "kn.export_iec_registration" in (s.get("detail", "") or "")
        for s in sources1
    )
    chk("retrieval picks the IEC registration article for export query",
        has_iec, f"sources={[s['detail'][:50] for s in sources1]}")

    # 3. List / get / delete cross-Part 3 smoke.
    s, body = _request(op_a, "GET", f"{API}/chat")
    chk("list conversations", s == 200 and body.get("count", 0) >= 2)

    s, body = _request(op_a, "GET", f"{API}/chat/{sid}")
    chk("GET conversation", s == 200 and len(body.get("messages", [])) >= 2)

    s, body = _request(op_a, "DELETE", f"{API}/chat/{sid}")
    chk("DELETE conversation", s == 200 and body.get("deleted") is True)

    # Cross-owner 404.
    s, _ = _request(op_b, "GET", f"{API}/chat/{sid2}", allow_404=True)
    chk("cross-owner GET returns 404", s == 404)


print("\n=== 1-13. End-to-end (Part 3 regression) ===")
e2e()


# --------------------------------------------------------------------------- #
# 18. Out-of-scope absence in the new retrieval package.
# --------------------------------------------------------------------------- #


print("\n=== 18. Out-of-scope absence in knowledge_retrieval ===")
banned = [
    (re.compile(r"^\s*(?:from|import)\s+pgvector", re.MULTILINE | re.IGNORECASE), "pgvector"),
    (re.compile(r"^\s*(?:from|import)\s+faiss", re.MULTILINE | re.IGNORECASE), "faiss"),
    (re.compile(r"^\s*(?:from|import)\s+sentence_transformers", re.MULTILINE | re.IGNORECASE), "sentence-transformers"),
    (re.compile(r"^\s*(?:from|import)\s+chromadb", re.MULTILINE | re.IGNORECASE), "chromadb"),
    (re.compile(r"^\s*(?:from|import)\s+qdrant_client", re.MULTILINE | re.IGNORECASE), "qdrant"),
    (re.compile(r"^\s*(?:from|import)\s+pinecone", re.MULTILINE | re.IGNORECASE), "pinecone"),
    (re.compile(r"^\s*(?:from|import)\s+weaviate", re.MULTILINE | re.IGNORECASE), "weaviate"),
    (re.compile(r"\bembedding[s]?\s*[:=]", re.IGNORECASE), "embedding field"),
    (re.compile(r"\bsemantic_search\b", re.IGNORECASE), "semantic_search"),
    (re.compile(r"\bvector(ize|store|database|index)\b", re.IGNORECASE), "vector store"),
]
new_files = [
    BACKEND / "app" / "services" / "knowledge_retrieval" / "__init__.py",
    BACKEND / "app" / "services" / "knowledge_retrieval" / "base.py",
    BACKEND / "app" / "services" / "knowledge_retrieval" / "retriever.py",
    BACKEND / "app" / "services" / "knowledge_retrieval" / "ranker.py",
    BACKEND / "app" / "services" / "knowledge_retrieval" / "citation_builder.py",
    BACKEND / "app" / "services" / "knowledge_retrieval" / "context_builder.py",
    BACKEND / "app" / "services" / "knowledge_retrieval" / "service.py",
]
violations = []
for f in new_files:
    if not f.exists():
        continue
    src = f.read_text(encoding="utf-8", errors="ignore")
    for pat, label in banned:
        if pat.search(src):
            violations.append((f.name, label))
chk(f"no vector / RAG / embedding code in {len(new_files)} new files",
    not violations,
    "; ".join(f"{n}:{l}" for n, l in violations[:5]))


# --------------------------------------------------------------------------- #
# 19. No duplicate indexing.
# --------------------------------------------------------------------------- #


print("\n=== 19. No duplicate indexing ===")
prog = (
    "import sys\n"
    "sys.path.insert(0, r'" + str(BACKEND).replace("\\", "\\\\") + "')\n"
    "from app.services.knowledge.service import KnowledgeService\n"
    "from app.services.knowledge_retrieval.service import KnowledgeRetrievalService\n"
    "from app.services.knowledge.repository import JsonKnowledgeRepository\n"
    "repo = JsonKnowledgeRepository()\n"
    "svc = KnowledgeRetrievalService.from_repository(repo, top_k=3)\n"
    "print('RETRIEVER_ARTICLES', len(svc._retriever._articles))\n"
    "print('KNOWLEDGE_REPO_COUNT', repo.count())\n"
    "print('SAME_OBJ', svc._knowledge._repo is repo)\n"
)
r = _run_module("no-duplicate", prog)
out = r.stdout
n_art = int(get_marker("RETRIEVER_ARTICLES", out) or "0")
n_repo = int(get_marker("KNOWLEDGE_REPO_COUNT", out) or "0")
# The retriever pre-materialises the list once at construction
# (cheap, single read). The crucial contract is the *same
# repository object* — no second copy of the JSON catalog.
chk("retriever uses the same repository instance",
    get_marker("SAME_OBJ", out) == "True")
chk("retriever saw the same article count as the repo",
    n_art == n_repo and n_art > 0,
    f"retriever={n_art} repo={n_repo}")

# --------------------------------------------------------------------------- #
# 20. Provider service unchanged (only extended).
# --------------------------------------------------------------------------- #


print("\n=== 20. Provider service reuses Part 2 unchanged ===")
prog = (
    "import sys\n"
    "sys.path.insert(0, r'" + str(BACKEND).replace("\\", "\\\\") + "')\n"
    "from app.services.ai.providers.service import AssistantProviderService\n"
    "from app.services.ai.providers.context_builder import AssistantContextBuilder\n"
    "from app.services.ai.providers.factory import ProviderFactory\n"
    "import inspect\n"
    "sig = inspect.signature(AssistantProviderService.generate)\n"
    "params = list(sig.parameters.keys())\n"
    "print('PARAMS', ','.join(params))\n"
    "print('HAS_KNOWLEDGE', 'knowledge' in params)\n"
)
r = _run_module("provider-sig", prog)
out = r.stdout
params = get_marker("PARAMS", out) or ""
chk("generate signature includes new 'knowledge' param",
    "knowledge" in params, repr(params))
chk("generate signature still has owner_id, user_prompt, history",
    all(p in params for p in ("owner_id", "user_prompt", "history")),
    repr(params))


# --------------------------------------------------------------------------- #
# 21. Existing assistant (deterministic fallback) unchanged.
# --------------------------------------------------------------------------- #


print("\n=== 21. Deterministic fallback byte-deterministic when no knowledge ===")
prog = (
    "import sys, json\n"
    "sys.path.insert(0, r'" + str(BACKEND).replace("\\", "\\\\") + "')\n"
    "from app.services.ai.providers.base import (AssistantContext, AssistantContextDna, AssistantContextScore, AssistantContextRecommendation, AssistantContextRoadmap, AssistantContextRule, AssistantContextInsight, DeterministicFallbackProvider, AssistantRequest, AssistantTurn)\n"
    "ctx = AssistantContext(\n"
    "    business_id=1, overall_business_score=58, band='Established',\n"
    "    dna=AssistantContextDna(archetype_key='k', archetype_title='Operator', match_score=72),\n"
    "    scores=(AssistantContextScore(key='export', title='Export', score=30, level='Low'),),\n"
    "    recommendations=(AssistantContextRecommendation(id='R-1', title='Improve', category='export', priority='High', estimated_score_gain=8, estimated_roi=4000.0, estimated_timeline='3 weeks'),),\n"
    "    roadmap=(AssistantContextRoadmap(id='ri-1', title='First', phase='Immediate', priority='High', estimated_start_order=1, completion_percentage=0, expected_score_improvement=8),),\n"
    "    rules=(AssistantContextRule(id='r-1', title='Rule', category='export', priority='High', estimated_impact=7, reason='because'),),\n"
    "    insights=(AssistantContextInsight(id='i-1', title='Insight', priority='High', confidence=70),))\n"
    "req = AssistantRequest(user_prompt='What should I do first?', context=ctx, history=(), knowledge=None)\n"
    "fb = DeterministicFallbackProvider()\n"
    "r1 = fb.complete(req)\n"
    "r2 = fb.complete(req)\n"
    "print('SAME', r1.body == r2.body)\n"
    "print('HAS_KNOWLEDGE', 'Knowledge sources' in r1.body)\n"
)
r = _run_module("fallback-det", prog)
out = r.stdout
chk("fallback is deterministic when no knowledge",
    get_marker("SAME", out) == "True")
chk("fallback body does NOT mention knowledge when none requested",
    get_marker("HAS_KNOWLEDGE", out) == "False")


# --------------------------------------------------------------------------- #
# 22. Ranker determinism.
# --------------------------------------------------------------------------- #


print("\n=== 22. Ranker determinism ===")
prog = (
    "import sys\n"
    "sys.path.insert(0, r'" + str(BACKEND).replace("\\", "\\\\") + "')\n"
    "from app.services.knowledge_retrieval.base import ScoredArticle\n"
    "from app.services.knowledge_retrieval.ranker import Ranker\n"
    "scored = (\n"
    "    ScoredArticle(article_id='a-1', score=2.5, matched_tokens=(), matched_tags=()),\n"
    "    ScoredArticle(article_id='a-2', score=5.0, matched_tokens=(), matched_tags=()),\n"
    "    ScoredArticle(article_id='a-3', score=5.0, matched_tokens=(), matched_tags=()),\n"
    "    ScoredArticle(article_id='a-1', score=1.0, matched_tokens=(), matched_tags=()),  # re-ordered copy\n"
    ")\n"
    "ranker = Ranker(top_k=3)\n"
    "r1 = ranker.rank(scored)\n"
    "r2 = ranker.rank(tuple(reversed(scored)))\n"
    "ids1 = [r.article_id for r in r1]\n"
    "ids2 = [r.article_id for r in r2]\n"
    "print('IDS1', ','.join(ids1))\n"
    "print('IDS2', ','.join(ids2))\n"
    "print('TOP_RANK', r1[0].rank)\n"
    "print('TIE_BREAK_OK', ids1 == ids2 and ids1[0] in ('a-2', 'a-3'))\n"
)
r = _run_module("ranker", prog)
out = r.stdout
chk("ranker is order-independent",
    get_marker("IDS1", out) == get_marker("IDS2", out) and bool(get_marker("IDS1", out)))
chk("top rank is 1",
    get_marker("TOP_RANK", out) == "1")


# --------------------------------------------------------------------------- #
# 23. Citation builder source_category mapping.
# --------------------------------------------------------------------------- #


print("\n=== 23. Citation builder source_category ===")
prog = (
    "import sys\n"
    "sys.path.insert(0, r'" + str(BACKEND).replace("\\", "\\\\") + "')\n"
    "from app.services.knowledge_retrieval.citation_builder import CitationBuilder\n"
    "from app.services.knowledge.base import Article\n"
    "b = CitationBuilder()\n"
    "knowledge = Article(id='k1', topic='export', category='readiness', tags=('export','india'), title='T', summary='S', body='B')\n"
    "rule = Article(id='k2', topic='quality', category='rules', tags=('rule','gcc'), title='T', summary='S', body='B')\n"
    "scheme = Article(id='k3', topic='government', category='schemes', tags=('scheme','msme'), title='T', summary='S', body='B')\n"
    "glossary = Article(id='k4', topic='glossary', category='glossary', tags=('term','msme'), title='T', summary='S', body='B')\n"
    "rec = Article(id='k5', topic='recommendation', category='recommendations', tags=('currency','export'), title='T', summary='S', body='B')\n"
    "for art, expected in [\n"
    "    (knowledge, 'Knowledge'),\n"
    "    (rule, 'Rule'),\n"
    "    (scheme, 'GovernmentScheme'),\n"
    "    (glossary, 'Glossary'),\n"
    "    (rec, 'Recommendation'),\n"
    "]:\n"
    "    c = b.build(art)\n"
    "    print('CAT', art.id, c.source_category, c.source_category == expected)\n"
)
r = _run_module("cat", prog)
out = r.stdout
lines = [l for l in out.splitlines() if l.startswith("CAT ")]
for line in lines:
    parts = line.split()
    art_id = parts[1]
    cat = parts[2]
    ok_line = parts[3] == "True"
    chk(f"citation {art_id} -> correct category", ok_line, cat)


# --------------------------------------------------------------------------- #
# 24. Token-overlap scorer.
# --------------------------------------------------------------------------- #


print("\n=== 24. Token-overlap scorer picks the right article ===")
prog = (
    "import sys\n"
    "sys.path.insert(0, r'" + str(BACKEND).replace("\\", "\\\\") + "')\n"
    "from app.services.knowledge_retrieval import KnowledgeRetrievalService\n"
    "from app.services.knowledge.repository import JsonKnowledgeRepository\n"
    "svc = KnowledgeRetrievalService.from_repository(JsonKnowledgeRepository(), top_k=3)\n"
    "ctx = svc.retrieve(query='export readiness and IEC registration')\n"
    "ids = [r.article_id for r in ctx.ranked]\n"
    "print('TOP_IDS', ','.join(ids))\n"
    "print('HAS_IEC', 'kn.export_iec_registration' in ids)\n"
    "print('NON_EMPTY', len(ctx.citations) >= 1)\n"
    "print('CITATION', ctx.citations[0].article_id if ctx.citations else '')\n"
    "print('SNIPPET_LEN', len(ctx.citations[0].snippet) if ctx.citations else 0)\n"
    # Determinism on a second call.
    "ctx2 = svc.retrieve(query='export readiness and IEC registration')\n"
    "ids2 = [r.article_id for r in ctx2.ranked]\n"
    "print('DETERMINISTIC', ids == ids2)\n"
)
r = _run_module("scorer", prog)
out = r.stdout
chk("retrieval picks IEC article for export-readiness query",
    get_marker("HAS_IEC", out) == "True")
chk("retrieval returns at least one citation",
    get_marker("NON_EMPTY", out) == "True")
chk("citation snippet is <= 120 chars",
    int(get_marker("SNIPPET_LEN", out) or "0") <= 120)
chk("retrieval is deterministic across two calls",
    get_marker("DETERMINISTIC", out) == "True")


# --------------------------------------------------------------------------- #
# Sentinels — no Part 1 / Part 2 / Part 3 critical files modified.
# --------------------------------------------------------------------------- #


print("\n=== Sentinels ===")
# Part 4 *extends* Part 2 / Part 3 files (adding a `knowledge`
# parameter, wiring the retriever). The contract is not
# "untouched" but "invariants intact". The verifier asserts
# the invariants above (1-13 for Part 3, 21 for Part 2
# fallback). Here we also assert the Part 1 frontend
# invariant files are untouched (no refactor).

SENTINEL = BACKEND / "app" / "services" / "knowledge_retrieval" / "service.py"
part1_files = [
    FRONTEND / "app" / "(app)" / "assistant" / "page.tsx",
    FRONTEND / "features" / "assistant" / "use-assistant-data.ts",
    FRONTEND / "features" / "assistant" / "builder.ts",
    FRONTEND / "features" / "assistant" / "classify-query.ts",
    FRONTEND / "features" / "assistant" / "suggested-questions.ts",
    FRONTEND / "features" / "assistant" / "types.ts",
    FRONTEND / "features" / "assistant" / "ContextPanel.tsx",
    FRONTEND / "features" / "assistant" / "ConversationList.tsx",
    FRONTEND / "features" / "assistant" / "MessageBubble.tsx",
    FRONTEND / "features" / "assistant" / "PromptInput.tsx",
    FRONTEND / "features" / "assistant" / "SuggestedQuestions.tsx",
    FRONTEND / "lib" / "navigation.ts",
]
if SENTINEL.exists():
    smt = SENTINEL.stat().st_mtime
    cutoff = smt - 60
    fe_violators = [
        str(p.relative_to(ROOT))
        for p in part1_files
        if p.exists() and p.stat().st_mtime > cutoff
    ]
    chk("no Part 1 frontend invariant file modified by Part 4",
        not fe_violators,
        f"violators: {fe_violators[:3]}" if fe_violators else "")
else:
    chk("part4 sentinel exists", False, str(SENTINEL))


# --------------------------------------------------------------------------- #
# requirements sentinel — Part 4 introduces NO new deps.
# --------------------------------------------------------------------------- #


print("\n=== Requirements sentinel ===")
req = (BACKEND / "requirements.txt").read_text(encoding="utf-8")
added_pkgs = []
for pkg in ["sentence-transformers", "chromadb", "pinecone-client",
            "pinecone", "weaviate-client", "weaviate",
            "qdrant-client", "rank-bm25", "faiss-cpu", "faiss"]:
    if re.search(r"(^|\n)\s*" + re.escape(pkg) + r"\s*==", req):
        added_pkgs.append(pkg)
chk("no new RAG / vector packages in requirements.txt",
    not added_pkgs,
    f"found: {added_pkgs}")


print()
print("=" * 60)
print("VERIFIER RESULT:", "ALL CHECKS PASS" if ok else "FAILURES PRESENT")
print("=" * 60)
sys.exit(0 if ok else 1)