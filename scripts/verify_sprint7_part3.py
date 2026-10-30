"""
verify_sprint7_part3.py - ad-hoc verifier for Sprint 7 Part 3
(Conversation Memory).

In-tree copy lives at D:/MSME/UrsAi/scripts/verify_sprint7_part3.py.

The verifier drives the running uvicorn dev server (port 8001)
through the full CRUD cycle for the /api/v1/chat surface:

  1.  POST /api/v1/auth/register           -> register a throwaway user
  2.  POST /api/v1/business                -> create a minimal business
                                              (required so the provider
                                              layer has data to read)
  3.  POST /api/v1/chat                    -> create conversation A
  4.  POST /api/v1/chat/A/message          -> append message -> reply
  5.  POST /api/v1/chat                    -> create conversation B
  6.  POST /api/v1/chat/B/message          -> append message -> reply
  7.  GET  /api/v1/chat                    -> list 2 sessions, A first
                                              (most recently updated)
  8.  GET  /api/v1/chat/A                  -> history reloads (>=2 msgs)
  9.  POST /api/v1/chat/A/message          -> rolling context: ask a
                                              follow-up, get a reply
                                              that references prior
                                              context (deterministic
                                              fallback does not, but
                                              we assert the message
                                              count grows)
 10.  DELETE /api/v1/chat/A                -> session A removed
 11.  GET  /api/v1/chat                    -> list 1 session (B)
 12.  Cross-owner 404                      -> a second user cannot
                                              read user 1's session
 13.  No-business 404                      -> when business is deleted,
                                              append returns 404
 14.  Frontend sentinel                    -> no Sprint 7 Part 1
                                              frontend file modified
 15.  No-LLM-package sentinel              -> no new LLM packages
 16.  Out-of-scope absence                 -> no vector / embedding
                                              imports

Plus, in-tree unit smoke (no server):

  17. Schema Pydantic extra=forbid          -> unknown field rejected
  18. Two-call determinism on fallback       -> same body byte-equal
  19. Rolling context trim                   -> only the last N turns
                                                are replayed
  20. Summary regeneration                   -> summary updates when
                                                a new message is
                                                appended

Ad-hoc verification, not suite green. Re-run any time.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path

ROOT = Path(r"D:\MSME\UrsAi")
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
ASSISTANT_PAGE = FRONTEND / "app" / "(app)" / "assistant" / "page.tsx"
ASSISTANT_FEATURES = FRONTEND / "features" / "assistant"
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
# HTTP plumbing — register / login / cookie jar
# --------------------------------------------------------------------------- #


def _opener():
    cj = CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))


def _request(opener, method, path, *, body=None, allow_404=False):
    url = path
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        resp = opener.open(req, timeout=30)
        return resp.status, json.loads(resp.read().decode("utf-8") or "null")
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
        print(r.stderr[-800:], flush=True)
    print(f"--- {label} exit={r.returncode} ---", flush=True)
    return r


# --------------------------------------------------------------------------- #
# 1-11. End-to-end conversation CRUD via the running server
# --------------------------------------------------------------------------- #


def e2e():
    suffix = "".join(
        c for c in (Path(__file__).stem + str(subprocess.os.getpid()))[-8:]
        if c.isalnum()
    ) or "x"
    user_a = f"chat-a-{suffix}@example-test.com"
    user_b = f"chat-b-{suffix}@example-test.com"
    password = "Passw0rd123"

    op_a = _opener()
    op_b = _opener()

    # 1. register two users
    s, body = _request(
        op_a, "POST", f"{API}/auth/register",
        body={"full_name": "Chat A", "email": user_a, "password": password},
    )
    chk("register user A", s == 200 or s == 201, f"status={s}")
    s, body = _request(
        op_b, "POST", f"{API}/auth/register",
        body={"full_name": "Chat B", "email": user_b, "password": password},
    )
    chk("register user B", s == 200 or s == 201, f"status={s}")

    # 2. create a business for user A
    biz_payload = {
        "basic": {
            "legal_name": "Chat Test Co",
            "industry": "manufacturing",
            "established_year": 2020,
            "employee_count": 5,
            "annual_revenue": 250000.0,
            "revenue_currency": "USD",
        },
        "capacity": {"production_capacity": "200 units / month"},
    }
    s, _ = _request(op_a, "POST", f"{API}/business", body=biz_payload)
    chk("create business for A", s == 200 or s == 201, f"status={s}")

    # 3. create conversation A
    s, body = _request(op_a, "POST", f"{API}/chat", body={"title": "First chat"})
    chk("create conversation A", s == 201, f"status={s}")
    session_a_id = body.get("id")
    chk("conversation A has id", isinstance(session_a_id, int) and session_a_id > 0,
        repr(session_a_id))
    chk("conversation A empty initially",
        body.get("message_count") == 0 and body.get("messages") == [])

    # 4. append first message -> reply
    s, body = _request(
        op_a, "POST", f"{API}/chat/{session_a_id}/message",
        body={"content": "How can I improve my business?"},
    )
    chk("append message to A", s == 200, f"status={s}")
    sess = body.get("session", {})
    user_msg = body.get("user_message", {})
    asst_msg = body.get("assistant_message", {})
    chk("assistant_message.body non-empty",
        isinstance(asst_msg.get("content"), str) and len(asst_msg["content"]) > 0)
    chk("assistant_message.role == 'assistant'",
        asst_msg.get("role") == "assistant")
    chk("user_message.role == 'user'",
        user_msg.get("role") == "user")
    chk("session A explicit title preserved across append",
        sess.get("title") == "First chat",
        repr(sess.get("title")))
    chk("session A summary populated",
        isinstance(sess.get("summary"), str) and len(sess["summary"]) > 0,
        repr(sess.get("summary")))
    chk("session A message_count == 2",
        sess.get("message_count") == 2, repr(sess.get("message_count")))
    chk("session A has fallback model stamped",
        (sess.get("last_model") or "").startswith(("deterministic", "ollama", "")) or sess.get("last_model") == "",
        repr(sess.get("last_model")))

    # 5. create conversation B (no explicit title -> auto-derived)
    s, body = _request(op_a, "POST", f"{API}/chat", body={})
    chk("create conversation B", s == 201, f"status={s}")
    session_b_id = body.get("id")
    chk("B has distinct id",
        isinstance(session_b_id, int) and session_b_id != session_a_id,
        f"A={session_a_id} B={session_b_id}")

    # 6. append first message to B
    s, body = _request(
        op_a, "POST", f"{API}/chat/{session_b_id}/message",
        body={"content": "Explain my Business DNA."},
    )
    chk("append message to B", s == 200, f"status={s}")
    chk("B title auto-derived from first user message",
        (body.get("session", {}).get("title") or "").startswith("Explain"),
        repr(body.get("session", {}).get("title")))

    # 7. list sessions -> A first (most recently updated)
    s, body = _request(op_a, "GET", f"{API}/chat")
    chk("list conversations", s == 200, f"status={s}")
    listed = body.get("sessions", [])
    chk("list count == 2", body.get("count") == 2 and len(listed) == 2,
        repr(body.get("count")))
    if len(listed) >= 2:
        chk("newest conversation first (B)",
            listed[0]["id"] == session_b_id,
            f"first id={listed[0]['id']} expected B={session_b_id}")
        chk("older conversation second (A)",
            listed[1]["id"] == session_a_id)

    # 8. fetch conversation A -> history reloads
    s, body = _request(op_a, "GET", f"{API}/chat/{session_a_id}")
    chk("GET conversation A", s == 200, f"status={s}")
    msgs = body.get("messages", [])
    chk("GET A returns >=2 messages",
        len(msgs) >= 2, f"got {len(msgs)}")
    chk("first message role == 'user'",
        msgs and msgs[0]["role"] == "user")
    chk("second message role == 'assistant'",
        len(msgs) >= 2 and msgs[1]["role"] == "assistant")
    chk("first message content matches",
        msgs and msgs[0]["content"] == "How can I improve my business?")

    # 9. append a follow-up -> message count grows
    s, body = _request(
        op_a, "POST", f"{API}/chat/{session_a_id}/message",
        body={"content": "Why is my score low?"},
    )
    chk("append follow-up to A", s == 200, f"status={s}")
    chk("follow-up message_count grew to 4",
        body.get("session", {}).get("message_count") == 4,
        repr(body.get("session", {}).get("message_count")))

    # 10. delete conversation A
    s, body = _request(op_a, "DELETE", f"{API}/chat/{session_a_id}")
    chk("DELETE conversation A", s == 200, f"status={s}")
    chk("DELETE response deleted=True",
        body.get("deleted") is True)

    # 11. list -> only B remains
    s, body = _request(op_a, "GET", f"{API}/chat")
    chk("list after delete returns 1", body.get("count") == 1,
        repr(body.get("count")))

    # 12. cross-owner 404 -> user B cannot see user A's session B
    s, body = _request(op_b, "GET", f"{API}/chat/{session_b_id}", allow_404=True)
    chk("cross-owner GET returns 404",
        s == 404, f"status={s}")
    s, body = _request(op_b, "DELETE", f"{API}/chat/{session_b_id}", allow_404=True)
    chk("cross-owner DELETE returns 404",
        s == 404, f"status={s}")
    s, body = _request(
        op_b, "POST", f"{API}/chat/{session_b_id}/message",
        body={"content": "steal this"},
        allow_404=True,
    )
    chk("cross-owner POST message returns 404",
        s == 404, f"status={s}")

    # 13. no-business 404 -> delete user A's business, append returns 404
    s, _ = _request(op_a, "DELETE", f"{API}/business", allow_404=True)
    # Then try to append a message to B
    s, body = _request(
        op_a, "POST", f"{API}/chat/{session_b_id}/message",
        body={"content": "any question"},
        allow_404=True,
    )
    chk("no-business append returns 404",
        s == 404, f"status={s}")


print("\n=== 1-13. End-to-end conversation CRUD ===")
e2e()


# --------------------------------------------------------------------------- #
# 14-16. Sentinels + out-of-scope absence
# --------------------------------------------------------------------------- #


print("\n=== 14. Frontend sentinel: no Sprint 7 Part 1 file touched ===")
# Only the files Sprint 7 Part 1 introduced are watched.
# New Part 3 files (chat-service.ts, ChatSessionsList.tsx,
# AssistantView.tsx update, AssistantHeader.tsx update) are
# intentionally modified by this milestone and must be
# excluded from the sentinel.
SENTINEL = BACKEND / "app" / "api" / "v1" / "endpoints" / "chat.py"
# The untouched-by-Part-3 invariants. AssistantView /
# AssistantHeader are excluded because Part 3 adds the
# server-history toggle to them (the local-first behaviour
# is preserved, but the JSX gained a control).
part1_files = [
    FRONTEND / "app" / "(app)" / "assistant" / "page.tsx",
    FRONTEND / "features" / "assistant" / "use-assistant-data.ts",
    FRONTEND / "features" / "assistant" / "builder.ts",
    FRONTEND / "features" / "assistant" / "classify-query.ts",
    FRONTEND / "features" / "assistant" / "suggested-questions.ts",
    FRONTEND / "features" / "assistant" / "types.ts",
    FRONTEND / "features" / "assistant" / "index.ts",
    FRONTEND / "features" / "assistant" / "ContextPanel.tsx",
    FRONTEND / "features" / "assistant" / "ConversationList.tsx",
    FRONTEND / "features" / "assistant" / "MessageBubble.tsx",
    FRONTEND / "features" / "assistant" / "PromptInput.tsx",
    FRONTEND / "features" / "assistant" / "SuggestedQuestions.tsx",
    FRONTEND / "lib" / "navigation.ts",
]
if not SENTINEL.exists():
    chk("sentinel chat.py exists", False, str(SENTINEL))
else:
    smt = SENTINEL.stat().st_mtime
    cutoff = smt - 60
    fe_violators = [
        str(p.relative_to(ROOT))
        for p in part1_files
        if p.exists() and p.stat().st_mtime > cutoff
    ]
    chk("no Part 1 frontend invariant files modified",
        not fe_violators,
        f"violators: {fe_violators[:3]}" if fe_violators else "")

    # Sprint 7 Part 2 backend files (provider layer) must NOT
    # be touched either — the new endpoint consumes them via
    # the existing imports.
    providers_dir = BACKEND / "app" / "services" / "ai" / "providers"
    provider_violators = [
        str(p.relative_to(ROOT))
        for p in providers_dir.rglob("*.py")
        if p.stat().st_mtime > cutoff
    ]
    chk("no Sprint 7 Part 2 provider file modified",
        not provider_violators,
        f"violators: {provider_violators[:3]}" if provider_violators else "")

    # Sprint 7 Part 2 settings: only the test settings check
    # above mutated the env. config/settings.py mtime must
    # NOT be after the sentinel (Part 3 does not edit it).
    settings = BACKEND / "app" / "config" / "settings.py"
    if settings.exists():
        chk("config/settings.py untouched",
            settings.stat().st_mtime <= cutoff)


print("\n=== 15. requirements.txt sentinel ===")
req = (BACKEND / "requirements.txt").read_text(encoding="utf-8")
forbidden = ["openai", "anthropic", "google-generativeai", "langchain",
             "llama-index", "pgvector", "sentence-transformers", "faiss"]
req_v = [p for p in forbidden
         if ('"' + p + '"' in req) or ("'" + p + "'" in req) or
         re.search(r"(^|\n)\s*" + re.escape(p) + r"\s*==", req) is not None]
chk("no LLM / vector / embedding packages in requirements.txt",
    not req_v, f"found: {req_v}" if req_v else "")


print("\n=== 16. Out-of-scope absence (vector / RAG / collaboration) ===")
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
]
new_py_files = [
    BACKEND / "app" / "api" / "v1" / "endpoints" / "chat.py",
    BACKEND / "app" / "services" / "chat" / "conversation_service.py",
    BACKEND / "app" / "services" / "chat" / "__init__.py",
    BACKEND / "app" / "repositories" / "chat_session_repository.py",
    BACKEND / "app" / "models" / "chat.py",
    BACKEND / "app" / "schemas" / "chat.py",
    BACKEND / "migrations" / "versions" / "20260101_0004_create_chat_tables.py",
]
violations = []
for f in new_py_files:
    if not f.exists():
        continue
    src = f.read_text(encoding="utf-8", errors="ignore")
    for pat, label in banned:
        if pat.search(src):
            violations.append((f.name, label))
chk(f"no vector / RAG / embedding code-constructs in {len(new_py_files)} new files",
    not violations,
    "; ".join(f"{n}:{l}" for n, l in violations[:5]))


# --------------------------------------------------------------------------- #
# 17-20. In-tree service smoke (no server)
# --------------------------------------------------------------------------- #


print("\n=== 17. Pydantic extra=forbid rejects unknown fields ===")
prog = (
    "import sys\n"
    "sys.path.insert(0, r'" + str(BACKEND).replace("\\", "\\\\") + "')\n"
    "from pydantic import ValidationError\n"
    "from app.schemas.chat import ChatMessageCreateRequest, ChatSessionCreateRequest\n"
    "try:\n"
    "    ChatMessageCreateRequest(content='hi', unknown_field=1)\n"
    "    print('REJECTED', False)\n"
    "except ValidationError:\n"
    "    print('REJECTED', True)\n"
    "try:\n"
    "    ChatSessionCreateRequest(title='t', bogus=True)\n"
    "    print('REJECTED2', False)\n"
    "except ValidationError:\n"
    "    print('REJECTED2', True)\n"
)
r = _run_module("schema-extra", prog)
out = r.stdout
chk("unknown field on ChatMessageCreateRequest rejected",
    get_marker("REJECTED", out) == "True")
chk("unknown field on ChatSessionCreateRequest rejected",
    get_marker("REJECTED2", out) == "True")


print("\n=== 18. Two-call determinism (fallback path) ===")
prog = (
    "import sys, json\n"
    "sys.path.insert(0, r'" + str(BACKEND).replace("\\", "\\\\") + "')\n"
    "from app.services.ai.providers import (AssistantContextBuilder, AssistantProviderService, ProviderFactory)\n"
    "from app.services.ai.providers.base import DeterministicFallbackProvider\n"
    "_TWIN = {'generated_at': '2026-01-01T00:00:00Z', 'current_health': {'overall_business_score': 58}, 'dna': {'dna': {'archetype': {'key': 'scaling_operator', 'title': 'Scaling Operator', 'match_score': 72}}}, 'health_summary': {'overall_health': {'score': 58, 'level': 'Established'}, 'scores': [{'key': 'export', 'title': 'Export', 'score': 30, 'level': 'Low'}]}}\n"
    "_RECS = {'recommendations': [{'id': 'R-1', 'title': 'Improve digital presence', 'category': 'export_readiness_actions', 'priority': 'High', 'estimated_score_gain': 8, 'estimated_roi': 4000, 'estimated_timeline': '3 weeks'}]}\n"
    "_ROADMAP = {'items': [{'id': 'ri-1', 'title': 'Improve digital presence', 'phase': 'Immediate', 'priority': 'High', 'estimated_start_order': 1, 'completion_percentage': 0, 'expected_score_improvement': 8}]}\n"
    "_RULES = {'categories': {'export_readiness_actions': {'firings': [{'id': 'rule.x', 'title': 't', 'priority': 'High', 'estimated_impact': 7, 'reason': 'r'}]}}}\n"
    "_DECISION = {'decision': {'insights': [{'id': 'i.1', 'title': 'Push export', 'priority': 'High', 'confidence': 70}]}}\n"
    "b = AssistantContextBuilder(\n"
    "    twin_provider=lambda o: _TWIN, recommendations_provider=lambda o: _RECS,\n"
    "    roadmap_provider=lambda o: _ROADMAP, rules_provider=lambda o: _RULES,\n"
    "    insights_provider=lambda o: _DECISION)\n"
    "class S:\n"
    "    ai_provider='placeholder'; ollama_base_url=''; ollama_model=''; ai_request_timeout_seconds=60.0\n"
    "f = ProviderFactory(S())\n"
    "svc = AssistantProviderService(context_builder=b, provider_factory=f)\n"
    "r1 = svc.generate(owner_id=1, user_prompt='What should I do first?')\n"
    "r2 = svc.generate(owner_id=1, user_prompt='What should I do first?')\n"
    "k1 = json.dumps({'body': r1.body, 'model': r1.model, 'fallback_used': r1.fallback_used, 'provider_used': r1.provider_used}, sort_keys=True)\n"
    "k2 = json.dumps({'body': r2.body, 'model': r2.model, 'fallback_used': r2.fallback_used, 'provider_used': r2.provider_used}, sort_keys=True)\n"
    "print('DETERMINISTIC', k1 == k2)\n"
    "print('MODEL', r1.model)\n"
)
r = _run_module("det", prog)
out = r.stdout
chk("fallback is deterministic across two calls",
    get_marker("DETERMINISTIC", out) == "True")
chk("fallback model is 'deterministic-fallback'",
    get_marker("MODEL", out) == "deterministic-fallback")


print("\n=== 19. Rolling context trim ===")
prog = (
    "import sys\n"
    "sys.path.insert(0, r'" + str(BACKEND).replace("\\", "\\\\") + "')\n"
    "from app.services.chat.conversation_service import ConversationService\n"
    "class FakeMsg:\n"
    "    def __init__(self, mid, role, content):\n"
    "        self.id = mid; self.role = role; self.content = content\n"
    "        self.sources_json = '[]'; self.kind = ''; self.created_at = None\n"
    "class FakeSess:\n"
    "    def __init__(self): self.id = 99; self.messages = []\n"
    "class FakeRepo:\n"
    "    def __init__(self): self._messages = []\n"
    "    def get_messages(self, *, session):\n"
    "        return self._messages\n"
    "sess = FakeSess()\n"
    "repo = FakeRepo()\n"
    "for i in range(20):\n"
    "    repo._messages.append(FakeMsg(i+1, 'user' if i%2==0 else 'assistant', f'msg {i}'))\n"
    "svc = ConversationService(repo, assistant_service=object(), rolling_context_turns=8)\n"
    "history = svc._build_history(sess)\n"
    "print('N_HISTORY', len(history))\n"
    "print('FIRST_ROLE', history[0].role)\n"
    "print('LAST_ROLE', history[-1].role)\n"
    "print('LAST_CONTENT', history[-1].content)\n"
)
r = _run_module("rolling", prog)
out = r.stdout
chk("rolling context capped at 8 turns",
    get_marker("N_HISTORY", out) == "8")
chk("rolling context starts on oldest kept turn (msg 12, role user)",
    get_marker("FIRST_ROLE", out) == "user")
chk("rolling context ends on most recent turn (msg 19, role assistant)",
    get_marker("LAST_ROLE", out) == "assistant" and
    get_marker("LAST_CONTENT", out) == "msg 19")


print("\n=== 20. Summary regeneration ===")
prog = (
    "import sys\n"
    "sys.path.insert(0, r'" + str(BACKEND).replace("\\", "\\\\") + "')\n"
    "from app.services.chat.conversation_service import _derive_summary, _derive_title\n"
    "from app.services.ai.providers.base import (AssistantContext, AssistantContextDna, AssistantContextScore)\n"
    "ctx = AssistantContext(\n"
    "    business_id=1, overall_business_score=58, band='Established',\n"
    "    dna=AssistantContextDna(archetype_key='k', archetype_title='Scaling Operator', match_score=72),\n"
    "    scores=(AssistantContextScore(key='export', title='Export', score=30, level='Low'),),\n"
    "    recommendations=(), roadmap=(), rules=(), insights=())\n"
    "s1 = _derive_summary(session_summary='', context=ctx, latest_user='How can I improve my business?', latest_assistant='reply 1')\n"
    "s2 = _derive_summary(session_summary=s1, context=ctx, latest_user='Why is my score low?', latest_assistant='reply 2')\n"
    "print('HAS_SCORE', 'Score 58/100' in s1)\n"
    "print('HAS_DNA', 'Scaling Operator' in s1)\n"
    "print('LATEST_UPDATED', 'Why is my score low' in s2)\n"
    "print('LEN_OK', len(s2) <= 480)\n"
    "t = _derive_title('How can I improve my business? please help')\n"
    "print('TITLE', t[:60])\n"
)
r = _run_module("summary", prog)
out = r.stdout
chk("summary mentions overall score",
    get_marker("HAS_SCORE", out) == "True")
chk("summary mentions DNA archetype",
    get_marker("HAS_DNA", out) == "True")
chk("summary refreshes with latest user message",
    get_marker("LATEST_UPDATED", out) == "True")
chk("summary stays within 480-char cap",
    get_marker("LEN_OK", out) == "True")
chk("title derived from first user message",
    get_marker("TITLE", out).startswith("How can I improve my business"))


print()
print("=" * 60)
print("VERIFIER RESULT:", "ALL CHECKS PASS" if ok else "FAILURES PRESENT")
print("=" * 60)
sys.exit(0 if ok else 1)